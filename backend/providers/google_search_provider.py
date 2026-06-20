"""
Google Search + Bing fallback provider.

Tries Google HTML first. When Google blocks (CAPTCHA / 429),
automatically falls back to Bing which is far more scraper-friendly.
"""
from __future__ import annotations

import base64
import logging
import re
from urllib.parse import quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .base import (
    BaseProvider,
    CompanyRecord,
    LIST_TITLE_RE,
    build_headers,
    clean_name,
    domain_to_name,
    get_domain,
    is_captcha_page,
    is_valid_url,
    looks_like_company,
    root_url,
)

logger = logging.getLogger(__name__)


def _decode_bing_url(href: str) -> str:
    """Decode a Bing click-tracking URL to the real destination."""
    m = re.search(r"[?&]u=a1([A-Za-z0-9+/=_-]+)", href)
    if m:
        try:
            padded = m.group(1) + "=="
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
            if decoded.startswith("http"):
                return decoded.split("&")[0]
        except Exception:
            pass
    return ""


class GoogleSearchProvider(BaseProvider):
    """Google HTML search with automatic Bing fallback."""

    name = "google"
    base_confidence = 0.82

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        results = self._search_google(query, limit)
        if results:
            return results
        logger.info("Google blocked — falling back to Bing for: %r", query)
        return self._search_bing(query, limit)

    # ------------------------------------------------------------------
    # Google HTML search
    # ------------------------------------------------------------------

    def _search_google(self, query: str, limit: int) -> list[CompanyRecord]:
        fetch_n = min(limit + 15, 40)
        url = (
            f"https://www.google.com/search"
            f"?q={quote_plus(query)}&num={fetch_n}&hl=en&gl=us&pws=0"
        )
        try:
            resp = requests.get(url, headers=build_headers(), timeout=12, allow_redirects=True)
        except Exception as exc:
            logger.warning("Google request failed: %s", exc)
            return []

        if is_captcha_page(resp):
            logger.warning("Google blocked (CAPTCHA) for: %s", query)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[CompanyRecord] = []
        seen: set[str] = set()

        containers = (
            soup.select("div.g")
            or soup.select("div[data-sokoban-container]")
            or soup.select("div[data-hveid]")
            or soup.select("div.MjjYud")
        )

        for container in containers:
            try:
                for a_tag in container.find_all("a", href=True):
                    href: str = a_tag["href"]
                    if href.startswith("/url?"):
                        m = re.search(r"[?&]q=([^&]+)", href)
                        if m:
                            href = unquote(m.group(1))
                    if not href.startswith("http") or not is_valid_url(href):
                        continue

                    domain = urlparse(href).netloc.lower()
                    if domain in seen:
                        continue
                    seen.add(domain)

                    h3 = container.find("h3")
                    raw = clean_name(h3.get_text(strip=True)) if h3 else domain
                    name = (
                        domain_to_name(root_url(href))
                        if (not raw or LIST_TITLE_RE.match(raw) or not looks_like_company(raw))
                        else raw
                    )

                    r = CompanyRecord(company=name, website=root_url(href), source=self.name)
                    r.confidence = self._score(r)
                    results.append(r)
                    break

            except Exception:
                continue

            if len(results) >= limit:
                break

        logger.info("Google: %d results for %r", len(results), query)
        return results

    # ------------------------------------------------------------------
    # Bing HTML search (fallback)
    # ------------------------------------------------------------------

    def _search_bing(self, query: str, limit: int) -> list[CompanyRecord]:
        q_lower = query.lower()
        if any(k in q_lower for k in ("uae", "dubai", "abu dhabi", "sharjah", "ajman")):
            mkt = "en-AE"
        elif any(k in q_lower for k in ("india", "mumbai", "delhi", "bangalore", "hyderabad", "pune", "chennai")):
            mkt = "en-IN"
        elif any(k in q_lower for k in ("uk", "london", "manchester", "birmingham")):
            mkt = "en-GB"
        else:
            mkt = "en-US"

        url = (
            f"https://www.bing.com/search"
            f"?q={quote_plus(query)}&count={min(limit + 10, 30)}&setlang=en&mkt={mkt}&cc={mkt[-2:]}"
        )
        try:
            resp = requests.get(url, headers=build_headers(), timeout=12, allow_redirects=True)
        except Exception as exc:
            logger.warning("Bing request failed: %s", exc)
            return []

        if resp.status_code not in (200, 203):
            logger.warning("Bing returned %s", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[CompanyRecord] = []
        seen: set[str] = set()

        for item in soup.select("li.b_algo"):
            try:
                h2 = item.find("h2")
                if not h2:
                    continue
                a = h2.find("a", href=True)
                if not a:
                    continue

                href = a["href"]
                # Bing wraps real URLs in their redirect; decode the base64 payload
                real_url = _decode_bing_url(href)
                if not real_url:
                    # Fallback: use cite element for domain
                    cite = item.find("cite")
                    if cite:
                        cite_text = cite.get_text(strip=True).split(" ›")[0]
                        real_url = (
                            cite_text if cite_text.startswith("http")
                            else "https://" + cite_text
                        )
                    else:
                        continue

                if not is_valid_url(real_url):
                    continue

                domain = urlparse(real_url).netloc.lower()
                if domain in seen:
                    continue
                seen.add(domain)

                raw = clean_name(a.get_text(strip=True))
                name = (
                    domain_to_name(root_url(real_url))
                    if (not raw or LIST_TITLE_RE.match(raw) or not looks_like_company(raw))
                    else raw
                )

                r = CompanyRecord(
                    company=name,
                    website=root_url(real_url),
                    source=self.name,
                )
                r.confidence = self._score(r) - 0.04  # Slightly lower than native Google
                results.append(r)

            except Exception:
                continue

            if len(results) >= limit:
                break

        if not results:
            logger.info("Bing fallback: 0 results for %r", query)
            return []

        # Quality gate: reject if geographic mismatch (Bing ignores mkt= often)
        q_lower = query.lower()
        if any(k in q_lower for k in ("uae", "dubai", "abu dhabi", "sharjah")):
            expected_tlds = {".ae"}
            expected_kws = {"dubai", "uae", "emirates", "abu dhabi", "sharjah"}
        elif any(k in q_lower for k in ("india", "mumbai", "delhi", "bangalore", "hyderabad", "pune", "chennai")):
            expected_tlds = {".in", ".co.in"}
            # Extract specific city to reject wrong-city Bing results
            expected_kws = {"india"}
            for city_kw in ("mumbai", "delhi", "bangalore", "hyderabad", "pune", "chennai", "kolkata"):
                if city_kw in q_lower:
                    expected_kws.add(city_kw)
        else:
            expected_tlds = set()
            expected_kws = set()

        if expected_tlds or expected_kws:
            geo_matches = sum(
                1 for r in results
                if any(r.website.lower().endswith(t) for t in expected_tlds)
                or any(kw in r.website.lower() for kw in expected_kws)
                or any(kw in r.company.lower() for kw in expected_kws)
            )
            if geo_matches == 0:
                logger.warning(
                    "Bing returned %d results but 0 matched geography for %r — discarding",
                    len(results), query,
                )
                return []

        logger.info("Bing fallback: %d results for %r", len(results), query)
        return results
