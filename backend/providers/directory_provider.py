"""
Multi-source directory provider.

Sources attempted additively (region-aware routing):
  Google Maps local  — high-quality UAE/India local results  (primary)
  Yellow Pages UAE   — yellowpages.ae scraper (UAE queries)
  Connect.ae         — connect.ae scraper (UAE queries)
  IndiaMART          — indiamart.com via DDG site: search (India queries)
  DuckDuckGo         — general HTML search (always, as backbone)

All sources fail gracefully — the provider always returns whatever it could
collect without raising exceptions.
"""
from __future__ import annotations

import logging
import re
import time
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
    is_valid_url,
    looks_like_company,
    root_url,
)

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\+?[\d][\d\s\-().]{6,18}[\d]")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(url: str, timeout: int = 14, **kwargs) -> requests.Response | None:
    """GET with full exception swallowing."""
    try:
        return requests.get(url, headers=build_headers(), timeout=timeout, allow_redirects=True, **kwargs)
    except Exception as exc:
        logger.debug("HTTP error for %s: %s", url, exc)
        return None


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        if 7 <= len(digits) <= 15:
            return m.group(0).strip()
    return ""


# ---------------------------------------------------------------------------
# 1. Yellow Pages UAE  (yellowpages.ae)
# ---------------------------------------------------------------------------


def _search_yellowpages_uae(query: str, limit: int) -> list[CompanyRecord]:
    """
    Scrape yellowpages.ae search results.
    Uses two strategies:
      a) Direct HTTP scrape of search page (works on production Linux servers)
      b) DuckDuckGo site:yellowpages.ae query + follow listing pages (fallback)
    """
    results = _yp_uae_direct(query, limit)
    if not results:
        results = _yp_uae_via_ddg(query, limit)
    logger.info("Yellow Pages UAE: %d results for %r", len(results), query)
    return results


def _yp_uae_direct(query: str, limit: int) -> list[CompanyRecord]:
    search_url = f"https://www.yellowpages.ae/search?keyword={quote_plus(query)}"
    resp = _get(search_url)
    if not resp or resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[CompanyRecord] = []
    seen: set[str] = set()

    # yellowpages.ae uses several class names depending on page version
    items = (
        soup.select("div.listing-item")
        or soup.select("li.listing-item")
        or soup.select("div.ypListing")
        or soup.select("article.b_box")
        or soup.select("div[class*='listing']")
    )

    for item in items:
        try:
            name_el = (
                item.select_one("h2.listing-name a, h3.listing-name a")
                or item.select_one(".business-name a, .company-name a")
                or item.find(["h2", "h3", "h4"])
            )
            if not name_el:
                continue
            name = clean_name(name_el.get_text(strip=True))
            if not name or not looks_like_company(name):
                continue

            # Phone
            phone_el = item.select_one(".phone, .tel, [class*='phone']")
            phone = _extract_phone(phone_el.get_text(strip=True)) if phone_el else ""

            # Website — look for links that are NOT yellowpages.ae
            website = ""
            for a in item.find_all("a", href=True):
                href = a["href"]
                if (
                    href.startswith("http")
                    and is_valid_url(href)
                    and "yellowpages" not in href
                ):
                    website = root_url(href)
                    break

            if not website:
                continue

            domain = get_domain(website)
            if domain in seen:
                continue
            seen.add(domain)

            r = CompanyRecord(company=name, website=website, phone=phone, source="google_maps")
            r.confidence = 0.76 + (0.05 if phone else 0)
            results.append(r)

        except Exception:
            continue

        if len(results) >= limit:
            break

    return results


def _yp_uae_via_ddg(query: str, limit: int) -> list[CompanyRecord]:
    """Find yellowpages.ae listing URLs via DuckDuckGo, then scrape each listing."""
    ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus('site:yellowpages.ae ' + query)}"
    resp = _get(ddg_url)
    if not resp or resp.status_code not in (200, 202):
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    yp_urls: list[str] = []

    for item in soup.select(".result"):
        a = item.select_one("a.result__a")
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"uddg=([^&]+)", href)
        url = unquote(m.group(1)) if m else href
        if "yellowpages.ae" in url and "/search/" not in url and "/companies/" in url:
            yp_urls.append(url)
        if len(yp_urls) >= limit + 3:
            break

    results: list[CompanyRecord] = []
    seen: set[str] = set()

    for yp_url in yp_urls[:limit]:
        resp2 = _get(yp_url)
        if not resp2 or resp2.status_code != 200:
            continue
        try:
            soup2 = BeautifulSoup(resp2.text, "lxml")
            name_el = soup2.select_one("h1, .company-name, .business-name")
            if not name_el:
                continue
            name = clean_name(name_el.get_text(strip=True))
            if not name or not looks_like_company(name):
                continue

            website = ""
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and is_valid_url(href) and "yellowpages" not in href:
                    website = root_url(href)
                    break

            if not website:
                continue

            domain = get_domain(website)
            if domain in seen:
                continue
            seen.add(domain)

            phone = _extract_phone(soup2.get_text(" ", strip=True))
            r = CompanyRecord(company=name, website=website, phone=phone, source="google_maps")
            r.confidence = 0.74
            results.append(r)
            time.sleep(0.4)

        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# 2. Connect.ae
# ---------------------------------------------------------------------------


def _search_connectae(query: str, limit: int) -> list[CompanyRecord]:
    """Scrape connect.ae business directory."""
    # Try direct scrape first
    url = f"https://www.connect.ae/search/?q={quote_plus(query)}"
    resp = _get(url)
    results: list[CompanyRecord] = []
    seen: set[str] = set()

    if resp and resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "lxml")
        cards = (
            soup.select(".listing-card, .business-card, article.listing")
            or soup.select("div[class*='listing'], div[class*='company']")
        )

        for card in cards:
            try:
                name_el = card.find(["h2", "h3", "h4"]) or card.select_one(".name")
                if not name_el:
                    continue
                name = clean_name(name_el.get_text(strip=True))
                if not name or not looks_like_company(name):
                    continue

                website = ""
                for a in card.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and is_valid_url(href) and "connect.ae" not in href:
                        website = root_url(href)
                        break
                if not website:
                    continue

                domain = get_domain(website)
                if domain in seen:
                    continue
                seen.add(domain)

                phone = _extract_phone(card.get_text(" ", strip=True))
                r = CompanyRecord(company=name, website=website, phone=phone, source="google_maps")
                r.confidence = 0.72 + (0.05 if phone else 0)
                results.append(r)

            except Exception:
                continue

            if len(results) >= limit:
                break

    # DDG site: fallback
    if not results:
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus('site:connect.ae ' + query)}"
        resp2 = _get(ddg_url)
        if resp2 and resp2.status_code in (200, 202):
            soup2 = BeautifulSoup(resp2.text, "lxml")
            for item in soup2.select(".result"):
                a = item.select_one("a.result__a")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r"uddg=([^&]+)", href)
                connect_url = unquote(m.group(1)) if m else href
                if "connect.ae" not in connect_url or not is_valid_url(connect_url):
                    continue
                # Follow the connect.ae listing page
                resp3 = _get(connect_url)
                if not resp3 or resp3.status_code != 200:
                    continue
                try:
                    soup3 = BeautifulSoup(resp3.text, "lxml")
                    name_el = soup3.select_one("h1, .company-name")
                    if not name_el:
                        continue
                    name = clean_name(name_el.get_text(strip=True))
                    if not name or not looks_like_company(name):
                        continue
                    website = ""
                    for at in soup3.find_all("a", href=True):
                        h = at["href"]
                        if h.startswith("http") and is_valid_url(h) and "connect.ae" not in h:
                            website = root_url(h)
                            break
                    if not website:
                        continue
                    domain = get_domain(website)
                    if domain in seen:
                        continue
                    seen.add(domain)
                    phone = _extract_phone(soup3.get_text(" ", strip=True))
                    r = CompanyRecord(company=name, website=website, phone=phone, source="directory")
                    r.confidence = 0.68
                    results.append(r)
                    time.sleep(0.4)
                except Exception:
                    continue
                if len(results) >= limit:
                    break

    logger.info("Connect.ae: %d results for %r", len(results), query)
    return results


# ---------------------------------------------------------------------------
# 3. IndiaMART
# ---------------------------------------------------------------------------


def _search_indiamart(query: str, limit: int) -> list[CompanyRecord]:
    """
    Find IndiaMART supplier pages via DuckDuckGo site: search,
    then scrape each page for company name, phone, and website.
    """
    # Use a direct IndiaMART search URL as primary
    im_url = f"https://www.indiamart.com/search.mp?ss={quote_plus(query)}&prdsrc=1"
    resp = _get(im_url, timeout=12)

    results: list[CompanyRecord] = []
    seen: set[str] = set()

    if resp and resp.status_code == 200 and "indiamart" in resp.url:
        soup = BeautifulSoup(resp.text, "lxml")
        # IndiaMART product/supplier cards
        cards = soup.select("div.b-ser-item") or soup.select("[class*='product-listing']") or soup.select("div.prd-list")
        for card in cards[:limit]:
            try:
                name_el = card.select_one("span.companyname, .seller-name, h3")
                if not name_el:
                    continue
                name = clean_name(name_el.get_text(strip=True))
                if not name or not looks_like_company(name):
                    continue

                website = ""
                for a in card.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and is_valid_url(href) and "indiamart" not in href:
                        website = root_url(href)
                        break
                if not website:
                    continue

                domain = get_domain(website)
                if domain in seen:
                    continue
                seen.add(domain)

                phone = _extract_phone(card.get_text(" ", strip=True))
                r = CompanyRecord(company=name, website=website, phone=phone, source="directory")
                r.confidence = 0.68 + (0.05 if phone else 0)
                results.append(r)

            except Exception:
                continue

    # DDG site:indiamart fallback
    if not results:
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus('site:indiamart.com ' + query + ' supplier company')}"
        resp2 = _get(ddg_url)
        if resp2 and resp2.status_code in (200, 202):
            soup2 = BeautifulSoup(resp2.text, "lxml")
            im_urls: list[str] = []
            for item in soup2.select(".result"):
                a = item.select_one("a.result__a")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r"uddg=([^&]+)", href)
                url = unquote(m.group(1)) if m else href
                if "indiamart.com" in url and "indiamart.com/search" not in url:
                    im_urls.append(url)
                if len(im_urls) >= limit + 3:
                    break

            for im_url in im_urls[:limit]:
                time.sleep(0.5)
                resp3 = _get(im_url, timeout=10)
                if not resp3 or resp3.status_code != 200:
                    continue
                try:
                    soup3 = BeautifulSoup(resp3.text, "lxml")
                    name_el = (
                        soup3.select_one("h1.lcname, h1[itemprop='name']")
                        or soup3.select_one(".company-name h1, h1")
                    )
                    if not name_el:
                        continue
                    name = clean_name(name_el.get_text(strip=True))
                    if not name or not looks_like_company(name):
                        continue

                    website = ""
                    for at in soup3.find_all("a", href=True):
                        h = at["href"]
                        if h.startswith("http") and is_valid_url(h) and "indiamart" not in h:
                            website = root_url(h)
                            break
                    if not website:
                        continue

                    domain = get_domain(website)
                    if domain in seen:
                        continue
                    seen.add(domain)

                    phone_els = soup3.select("[itemprop='telephone'], .tel, .phone")
                    phone = ""
                    for el in phone_els:
                        phone = _extract_phone(el.get_text(strip=True))
                        if phone:
                            break

                    r = CompanyRecord(company=name, website=website, phone=phone, source="directory")
                    r.confidence = 0.66
                    results.append(r)
                except Exception:
                    continue

                if len(results) >= limit:
                    break

    logger.info("IndiaMART: %d results for %r", len(results), query)
    return results


# ---------------------------------------------------------------------------
# 4. DuckDuckGo (backbone)
# ---------------------------------------------------------------------------


def _search_duckduckgo(query: str, limit: int) -> list[CompanyRecord]:
    """DuckDuckGo HTML search — robust, no CAPTCHA, no JS required."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    resp = _get(url)
    if not resp or resp.status_code not in (200, 202):
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[CompanyRecord] = []
    seen: set[str] = set()

    for item in soup.select(".result"):
        try:
            a_tag = item.select_one("a.result__a")
            if not a_tag:
                continue

            href: str = a_tag.get("href", "")
            if "duckduckgo.com/l/" in href or href.startswith("//"):
                m = re.search(r"uddg=([^&]+)", href)
                href = unquote(m.group(1)) if m else ("https:" + href if href.startswith("//") else href)

            if not href.startswith("http"):
                href = "https://" + href.lstrip("/")

            if not is_valid_url(href):
                continue

            domain = urlparse(href).netloc.lower()
            if domain in seen:
                continue
            seen.add(domain)

            raw = clean_name(a_tag.get_text(strip=True))
            name = (
                domain_to_name(root_url(href))
                if (not raw or LIST_TITLE_RE.match(raw) or not looks_like_company(raw))
                else raw
            )

            r = CompanyRecord(company=name, website=root_url(href), source="directory")
            r.confidence = 0.60 + (0.05 if r.phone else 0) + (0.05 if r.email else 0)
            results.append(r)

        except Exception:
            continue

        if len(results) >= limit:
            break

    logger.info("DuckDuckGo: %d results for %r", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Main DirectoryProvider
# ---------------------------------------------------------------------------

_UAE_KEYWORDS = frozenset({
    "uae", "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
    "fujairah", "umm al quwain", "qatar", "bahrain", "kuwait", "saudi",
    "riyadh", "jeddah", "doha",
})

_INDIA_KEYWORDS = frozenset({
    "india", "mumbai", "delhi", "new delhi", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "surat",
    "jaipur", "lucknow", "chandigarh", "noida", "gurgaon",
})


class DirectoryProvider(BaseProvider):
    """
    Multi-source directory provider.

    Routing:
      UAE queries  → YP UAE + Connect.ae + DuckDuckGo
      India queries → IndiaMART + DuckDuckGo
      Other         → DuckDuckGo
    """

    name = "directory"
    base_confidence = 0.60

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        q_lower = query.lower()
        is_uae = any(kw in q_lower for kw in _UAE_KEYWORDS)
        is_india = any(kw in q_lower for kw in _INDIA_KEYWORDS)

        all_results: list[CompanyRecord] = []
        seen_domains: set[str] = set()

        def merge(records: list[CompanyRecord]) -> None:
            for r in records:
                if not r.website:
                    continue
                d = get_domain(r.website)
                if d not in seen_domains:
                    seen_domains.add(d)
                    all_results.append(r)

        # DuckDuckGo always runs first — it's the backbone
        merge(_search_duckduckgo(query, limit))

        # UAE-specific enrichment
        if is_uae and len(all_results) < limit:
            merge(_search_yellowpages_uae(query, limit - len(all_results) + 5))

        if is_uae and len(all_results) < limit:
            merge(_search_connectae(query, limit - len(all_results) + 5))

        # India-specific enrichment
        if is_india and len(all_results) < limit:
            merge(_search_indiamart(query, limit - len(all_results) + 5))

        logger.info(
            "Directory total: %d results for %r (uae=%s, india=%s)",
            len(all_results), query, is_uae, is_india,
        )
        return all_results[:limit]
