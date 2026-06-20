"""Google Search HTML provider."""
from __future__ import annotations

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


class GoogleProvider(BaseProvider):
    name = "google"
    base_confidence = 0.82

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
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
            logger.warning("Google blocked (CAPTCHA/JS-only) for: %s", query)
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
                        if (LIST_TITLE_RE.match(raw) or not looks_like_company(raw))
                        else raw
                    )

                    r = CompanyRecord(company=name, website=root_url(href), source=self.name)
                    r.confidence = self._score(r)
                    results.append(r)
                    break  # one result per container

            except Exception:
                continue

            if len(results) >= limit:
                break

        logger.info("Google: %d results for %r", len(results), query)
        return results
