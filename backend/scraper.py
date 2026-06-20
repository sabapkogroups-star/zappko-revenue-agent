"""
Discovery orchestrator — V2 provider architecture.

Provider failover order per query:
  1. Google Search      (base_confidence 0.82)
  2. Google Maps Local  (base_confidence 0.78)
  3. Directory/DDG      (base_confidence 0.60)

If a provider returns results for a given query, lower-priority providers are
skipped for that query (failover). Results are merged and deduplicated across
all queries; the best-confidence record wins on domain collision.

Pagination: the caller requests page N of size L; the engine fetches
N × L + 10 total results up-front so any page can be sliced without re-fetching.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from providers import DirectoryProvider, GoogleMapsProvider, GoogleSearchProvider
from providers.base import CompanyRecord, get_domain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query templates — tried in order; more specific variants first
# ---------------------------------------------------------------------------

_QUERY_TEMPLATES = [
    "{industry} company {city} {country} official website",
    "{industry} firm {city} {country}",
    "{industry} agency {city} {country}",
    "{industry} services {city} {country}",
    "{industry} {city} {country} contact",
    "{industry} {city} business website",
    "{industry} studio {city}",
]

# Provider priority:
#   1. GoogleSearchProvider (Google HTML + Bing fallback)
#   2. GoogleMapsProvider   (local results with phone numbers)
#   3. DirectoryProvider    (YP UAE / Connect.ae / IndiaMART / DuckDuckGo)
_PROVIDERS = [GoogleSearchProvider(), GoogleMapsProvider(), DirectoryProvider()]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_query(
    query: str,
    need: int,
    seen: dict[str, CompanyRecord],
) -> None:
    """
    Run ALL providers for `query` and merge results by domain.

    All providers run regardless — higher-confidence records win on domain
    collision. DirectoryProvider (DuckDuckGo) is the reliable backbone;
    Google/Maps/Bing enrich when they succeed.
    """
    for provider in _PROVIDERS:
        try:
            records = provider.search(query, need + 5)
        except Exception as exc:
            logger.warning("Provider %s raised for %r: %s", provider.name, query, exc)
            records = []

        added = 0
        for r in records:
            if not r.website:
                continue
            domain = get_domain(r.website)
            # Higher-confidence record wins on collision
            if domain not in seen or r.confidence > seen[domain].confidence:
                seen[domain] = r
                added += 1

        if added:
            logger.debug("Provider %s added %d records for %r", provider.name, added, query)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_companies(
    industry: str,
    city: str,
    country: str,
    limit: int = 20,
    page: int = 1,
) -> list[dict]:
    """
    Discover real companies matching industry + location.

    Returns a paginated list of dicts compatible with the audit pipeline:
      {company, website, phone, email, source, confidence, decisionMaker}

    Raises no exceptions — returns [] on total failure.
    """
    limit = max(1, min(limit, 50))
    page = max(1, page)

    # Over-fetch so we can paginate without re-fetching
    target = limit * page + 10

    queries = [
        t.format(industry=industry, city=city, country=country)
        for t in _QUERY_TEMPLATES
    ]

    # Seen dict: domain → best CompanyRecord found so far
    seen: dict[str, CompanyRecord] = {}

    for i, query in enumerate(queries):
        if len(seen) >= target:
            break
        if i > 0:
            time.sleep(0.6)  # Avoid DDG rate-limiting between queries
        _run_query(query, target - len(seen), seen)

    if not seen:
        logger.error(
            "No results from any provider — industry=%s city=%s country=%s",
            industry, city, country,
        )
        return []

    # Sort: confidence descending, then company name ascending (deterministic tie-break)
    all_records = sorted(
        seen.values(),
        key=lambda r: (-r.confidence, r.company.lower()),
    )

    logger.info(
        "Discovery complete: %d unique companies found (target %d, page %d of %d)",
        len(all_records), target, page, limit,
    )

    # Slice the requested page
    start = (page - 1) * limit
    page_records = all_records[start : start + limit]

    return [r.to_dict() for r in page_records]
