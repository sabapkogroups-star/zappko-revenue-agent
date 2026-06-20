"""
Google Local Search provider (tbm=lcl).

Google's local-results page embeds structured business data including business
name, phone, and sometimes a "Visit website" link wrapped in /url?q=.
This provider extracts what it can; records without a resolvable website are
dropped so the audit pipeline always has a URL to work with.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .base import (
    BaseProvider,
    CompanyRecord,
    build_headers,
    clean_name,
    get_domain,
    is_captcha_page,
    is_valid_url,
    looks_like_company,
    root_url,
)

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\+?[\d][\d\s\-().]{6,18}[\d]")


class GoogleMapsProvider(BaseProvider):
    name = "google_maps"
    base_confidence = 0.78

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        url = (
            f"https://www.google.com/search"
            f"?q={quote_plus(query)}&tbm=lcl"
            f"&num={min(limit + 5, 20)}&hl=en&gl=us"
        )

        try:
            resp = requests.get(url, headers=build_headers(), timeout=12, allow_redirects=True)
        except Exception as exc:
            logger.warning("GoogleMaps request failed: %s", exc)
            return []

        if is_captcha_page(resp):
            logger.warning("GoogleMaps blocked for: %s", query)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[CompanyRecord] = []
        seen: set[str] = set()

        # Local business blocks live inside div.rllt__details or similar containers.
        # Try several selectors in order of reliability.
        blocks = (
            soup.select("div.rllt__details")
            or soup.select("div[data-rc_f]")
            or soup.select("div.uMdZh")
            or soup.select("div.VkpGBb")
        )

        for block in blocks:
            try:
                # Business name — first heading or .OSrXXb span
                name_el = (
                    block.find(["h3", "h4"])
                    or block.select_one(".OSrXXb")
                    or block.select_one(".BNeawe.tAd8D")
                )
                if not name_el:
                    continue
                name = clean_name(name_el.get_text(strip=True))
                if not name or not looks_like_company(name):
                    continue

                # Phone — search block text for a phone-like pattern
                block_text = block.get_text(" ", strip=True)
                phone = ""
                m = _PHONE_RE.search(block_text)
                if m:
                    candidate = m.group(0).strip()
                    digits = re.sub(r"\D", "", candidate)
                    if 7 <= len(digits) <= 15:
                        phone = candidate

                # Website — Google wraps external links as /url?q=https://...
                website = ""
                search_els = [block] + ([block.parent] if block.parent else [])
                for el in search_els:
                    for a in el.find_all("a", href=True):
                        href: str = a.get("href", "")
                        if "/url?q=" in href or href.startswith("/url?"):
                            m2 = re.search(r"[?&]q=([^&]+)", href)
                            if m2:
                                decoded = unquote(m2.group(1))
                                if decoded.startswith("http") and is_valid_url(decoded):
                                    website = root_url(decoded)
                                    break
                        elif href.startswith("http") and is_valid_url(href):
                            website = root_url(href)
                            break
                    if website:
                        break

                if not website:
                    continue  # filter: must have a resolvable website

                domain = get_domain(website)
                if domain in seen:
                    continue
                seen.add(domain)

                r = CompanyRecord(
                    company=name,
                    website=website,
                    phone=phone,
                    source=self.name,
                )
                r.confidence = self._score(r)
                results.append(r)

            except Exception:
                continue

            if len(results) >= limit:
                break

        logger.info("GoogleMaps: %d results for %r", len(results), query)
        return results
