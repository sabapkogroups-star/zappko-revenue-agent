import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Matches phone numbers: +971 50 123 4567 / (04) 123-4567 / 10-digit runs etc.
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,15}\d)")

_CTA_WORDS = frozenset({
    "book", "get started", "contact us", "call now", "free consultation",
    "schedule", "request", "enquire", "get a quote", "buy now", "order",
    "sign up", "talk to us", "reach us", "hire us", "free estimate",
    "get in touch", "start now", "try free",
})

_SOCIAL_DOMAINS = frozenset({
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com",
})

_THIRD_PARTY_FORMS = frozenset({
    "typeform", "jotform", "calendly", "hubspot", "gravityforms",
    "wufoo", "formstack", "cognito", "paperform",
})


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _has_contact_form(soup: BeautifulSoup) -> bool:
    # Real <form> with contact-like fields
    for form in soup.find_all("form"):
        inputs = form.find_all(["input", "textarea", "select"])
        for inp in inputs:
            t = inp.get("type", "").lower()
            n = inp.get("name", "").lower()
            p = inp.get("placeholder", "").lower()
            label_text = (t + n + p)
            if any(w in label_text for w in ("email", "name", "message", "phone", "contact", "subject")):
                return True

    # Embedded third-party form (iframe or script)
    for tag in soup.find_all(["iframe", "script"]):
        src = (tag.get("src") or tag.get("data-src") or "").lower()
        if any(svc in src for svc in _THIRD_PARTY_FORMS):
            return True

    # Link to /contact page as a proxy (at least there's a contact page)
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if re.search(r"/(contact|enqui(r|ry)|get.?in.?touch|reach.?us)", href):
            return True

    return False


def _has_whatsapp(soup: BeautifulSoup, text: str) -> bool:
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "wa.me" in href or "api.whatsapp.com" in href or "whatsapp" in href:
            return True
    # Widget scripts often embed via JS class names or data attributes
    for tag in soup.find_all(True):
        cls = " ".join(tag.get("class") or []).lower()
        if "whatsapp" in cls:
            return True
    return "whatsapp" in text


def _has_email(soup: BeautifulSoup, text: str) -> bool:
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            return True
    # Email address visible in page text (not inside a script/style tag)
    for tag in ["script", "style", "noscript"]:
        for t in soup.find_all(tag):
            t.decompose()
    visible = soup.get_text(" ")
    return bool(_EMAIL_RE.search(visible))


def _has_phone(soup: BeautifulSoup, text: str) -> bool:
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("tel:"):
            return True
    # Phone number in visible text — require at least 8 contiguous digits
    m = _PHONE_RE.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        return len(digits) >= 8
    return False


def _has_cta(soup: BeautifulSoup) -> bool:
    for tag in soup.find_all(["a", "button"]):
        label = tag.get_text(strip=True).lower()
        if any(w in label for w in _CTA_WORDS):
            return True
    # Also check inputs of type submit/button
    for inp in soup.find_all("input", type=re.compile(r"^(submit|button)$", re.I)):
        val = (inp.get("value") or "").lower()
        if any(w in val for w in _CTA_WORDS):
            return True
    return False


def _has_social_links(soup: BeautifulSoup) -> bool:
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(domain in href for domain in _SOCIAL_DOMAINS):
            return True
    return False


def _has_meta_title(soup: BeautifulSoup) -> bool:
    tag = soup.find("title")
    if not tag:
        return False
    title = tag.get_text(strip=True)
    return 5 < len(title) < 120


def _has_meta_description(soup: BeautifulSoup) -> bool:
    tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if not tag:
        return False
    content = (tag.get("content") or "").strip()
    return len(content) > 10


def _has_lead_capture(soup: BeautifulSoup, text: str) -> bool:
    # Newsletter / lead-magnet form (distinct from generic contact form)
    lead_keywords = frozenset({
        "subscribe", "newsletter", "free guide", "download", "ebook",
        "join our", "get the", "free resource", "get updates", "sign up for",
    })
    if any(kw in text for kw in lead_keywords):
        return True
    for form in soup.find_all("form"):
        form_text = form.get_text(" ", strip=True).lower()
        if any(kw in form_text for kw in ("subscribe", "newsletter", "free", "download", "join")):
            return True
    return False


def _page_speed_ok(soup: BeautifulSoup) -> bool:
    images = soup.find_all("img")
    if len(images) > 8:
        lazy = sum(
            1 for img in images
            if img.get("loading") == "lazy" or img.get("data-src") or img.get("data-lazy")
        )
        if lazy == 0:
            return False  # Many images, none lazy-loaded

    head = soup.find("head")
    if head:
        blocking_scripts = [
            s for s in head.find_all("script", src=True)
            if not s.get("async") and not s.get("defer")
        ]
        if len(blocking_scripts) > 6:
            return False

    return True


# ---------------------------------------------------------------------------
# Audit orchestration
# ---------------------------------------------------------------------------

_CHECKS = [
    # (check_fn_name, issue_label, service_label, penalty)
    # check_fn is called inside _run_live_audit
]


def _run_live_audit(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    # Build plain text once (before email check removes tags)
    text = soup.get_text(" ", strip=True).lower()

    score = 100
    issues: list[str] = []
    services: list[str] = []

    def flag(failed: bool, issue: str, service: str, penalty: int) -> None:
        nonlocal score
        if failed:
            issues.append(issue)
            if service not in services:
                services.append(service)
            score -= penalty

    flag(not _has_contact_form(soup),       "No Contact Form",            "Lead Generation System",    12)
    flag(not _has_whatsapp(soup, text),     "No WhatsApp Integration",    "WhatsApp Automation",        15)
    flag(not _has_email(soup, text),        "No Email Address Visible",   "Contact Optimization",       10)
    flag(not _has_phone(soup, text),        "No Phone Number Visible",    "Contact Optimization",        8)
    flag(not _has_cta(soup),               "Weak Call-to-Action",         "Conversion Optimization",    10)
    flag(not _page_speed_ok(soup),          "Slow Page Performance",      "Website Optimization",        8)
    flag(not _has_meta_title(soup),         "Missing Meta Title",         "SEO Optimization",           10)
    flag(not _has_meta_description(soup),   "Missing Meta Description",   "SEO Optimization",            8)
    flag(not _has_social_links(soup),       "No Social Media Links",      "Social Media Integration",    7)
    flag(not _has_lead_capture(soup, text), "No Lead Capture Form",       "Lead Generation System",     12)

    return {
        "websiteScore": max(10, score),
        "issues": issues,
        "recommendedService": services,
    }


def _fallback_audit() -> dict:
    """Used when the site cannot be reached. Returns a conservative fixed result."""
    return {
        "websiteScore": 35,
        "issues": [
            "Site Unreachable or Too Slow",
            "No WhatsApp Integration",
            "No Lead Capture Form",
        ],
        "recommendedService": [
            "Website Optimization",
            "WhatsApp Automation",
            "Lead Generation System",
        ],
    }


def audit_website(url: str, seed: int = 0) -> dict:
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            },
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Live audit OK: %s (%d bytes)", url, len(resp.text))
        return _run_live_audit(resp.text)
    except Exception as exc:
        logger.info("Audit fallback for %s: %s", url, exc)
        return _fallback_audit()
