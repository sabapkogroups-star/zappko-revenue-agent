"""
Contact Intelligence Engine V2.

Given a company website, probes About / Team / Leadership / Contact pages to
find the most senior decision-maker and their contact details.

Extraction strategies (in descending quality):
  1. JSON-LD schema.org  — structured Person / Organization nodes
  2. Microformats        — h-card (p-name / p-role) and vCard (fn / title)
  3. Team card patterns  — heading + adjacent title, card containers
  4. Prose bio patterns  — "Meet [Name], [Title]" / "About [Name]" paragraphs
  5. Meta author tag     — <meta name="author"> (common on founder-run sites)

Priority order: CEO > Founder > Co-Founder > Managing Director >
                Director > Owner > President > GM > Principal > Partner

Returns:
    {
        "decisionMaker": str,   # name only
        "title":         str,   # role only
        "email":         str,
        "phone":         str,
        "linkedinUrl":   str,
    }
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

_PAGE_TIMEOUT = 7          # seconds per request
_MAX_PAGES_TO_PROBE = 4   # homepage + this many sub-pages

_PROBE_PATHS = [
    "/about", "/about-us", "/about_us", "/who-we-are",
    "/team", "/our-team", "/meet-the-team", "/the-team",
    "/leadership", "/management", "/founders", "/people", "/staff",
    "/contact", "/contact-us",
]

_PROBE_PATH_RE = re.compile(
    r"/(about|team|people|leadership|founders?|management|staff|contact|who.we.are|meet)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Title taxonomy
# ---------------------------------------------------------------------------

# Ordered from most to least senior (rank = list index)
_TITLE_TAXONOMY: list[tuple[list[str], str]] = [
    (["ceo", "chief executive officer", "chief executive"], "CEO"),
    (["founder", "co-founder", "cofounder", "founding director"], "Founder"),
    (["managing director"], "Managing Director"),
    (["director"], "Director"),
    (["owner", "proprietor"], "Owner"),
    (["president"], "President"),
    (["general manager", "gm"], "General Manager"),
    (["principal"], "Principal"),
    (["managing partner", "partner"], "Partner"),
    (["head of", "chief "], "Head"),
    (["vice president", "vp "], "VP"),
]

_ALL_TITLE_KW: frozenset[str] = frozenset(
    kw for kw_list, _ in _TITLE_TAXONOMY for kw in kw_list
)

# Words that look capitalised but are NOT person names
_NON_NAME_WORDS: frozenset[str] = frozenset({
    "about", "contact", "home", "services", "team", "the", "our", "your",
    "view", "read", "more", "next", "previous", "blog", "news", "click",
    "design", "interior", "studio", "architecture", "company", "group",
    "dubai", "uae", "india", "london", "new", "york", "abu", "dhabi",
    "get", "book", "learn", "see", "all", "please", "welcome", "page",
    "menu", "site", "meet", "join", "founded", "established", "copyright",
    "management", "leadership", "executive",
})

_GENERIC_EMAIL_PREFIXES: frozenset[str] = frozenset({
    "info", "hello", "contact", "support", "admin", "mail", "office",
    "team", "enquiries", "enquiry", "sales", "marketing", "pr", "media",
    "help", "general", "noreply", "no-reply", "donotreply", "accounts",
    "reception", "enquire", "connect",
})

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?[\d][\d\s\-().]{7,18}[\d])")

_LINKEDIN_PERSON_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?", re.IGNORECASE
)
_LINKEDIN_CO_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[A-Za-z0-9\-_%]+/?", re.IGNORECASE
)

# Prose patterns: "Meet John Smith, Founder" / "John Smith is the CEO"
_PROSE_PERSON_RE = re.compile(
    r"(?:meet|about|hi,?\s+i['']m|i['']m)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)"
    r"(?:[,\s]+(?:our\s+)?([^.]{3,60}))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------


@dataclass
class _Person:
    name: str
    title: str
    rank: int = 99
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    source_quality: int = 0  # higher = more reliable source


@dataclass
class _PageSignals:
    people: list[_Person] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)   # best first (mailto: before text)
    phones: list[str] = field(default_factory=list)   # best first (tel: before text)
    linkedins: list[str] = field(default_factory=list) # /in/ before /company/


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _title_rank(title: str) -> int:
    t = title.lower()
    for i, (kw_list, _) in enumerate(_TITLE_TAXONOMY):
        if any(kw in t for kw in kw_list):
            return i
    return 99


def _canonical_title(raw: str) -> str:
    """Clean a raw title string — strip noise, preserve known acronyms."""
    raw = raw.strip(" .,|&-–—")
    words = raw.split()
    out = []
    for w in words:
        if re.match(r"^(CEO|CFO|COO|CTO|CMO|MD|GM|VP|HR|PR|IT)$", w):
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _has_title_kw(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _ALL_TITLE_KW)


def _looks_like_name(text: str) -> bool:
    """Heuristic: is this string a plausible human name?"""
    words = text.strip().split()
    if len(words) < 2 or len(words) > 5:
        return False
    for w in words:
        if not re.match(r"^[A-Z][a-zA-Z'\-]{1,25}$", w):
            return False
    if any(w.lower() in _NON_NAME_WORDS for w in words):
        return False
    return True


def _name_matches_email(name: str, email: str) -> bool:
    parts = [p.lower() for p in name.split() if len(p) > 2]
    prefix = email.split("@")[0].lower()
    return any(p in prefix for p in parts)


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if 7 <= len(digits) <= 15:
        return raw.strip()
    return ""


# ---------------------------------------------------------------------------
# Strategy 1 — JSON-LD schema.org
# ---------------------------------------------------------------------------


def _strategy_schema(soup: BeautifulSoup) -> list[_Person]:
    people: list[_Person] = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = json.loads(script.string or "")
        except Exception:
            continue

        items = raw.get("@graph", [raw]) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

        for item in items:
            itype = item.get("@type", "")
            if isinstance(itype, list):
                itype = " ".join(itype)

            # Direct Person node
            if "Person" in itype:
                name = (item.get("name") or "").strip()
                title = (item.get("jobTitle") or item.get("title") or "").strip()
                if not name:
                    continue
                p = _Person(
                    name=name,
                    title=_canonical_title(title) if title else "",
                    rank=_title_rank(title),
                    email=(item.get("email") or "").replace("mailto:", "").strip().lower(),
                    phone=(item.get("telephone") or "").strip(),
                    source_quality=3,
                )
                same_as = item.get("sameAs", [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                for s in same_as:
                    if "linkedin.com/in/" in s:
                        p.linkedin = s.rstrip("/?")
                        break
                people.append(p)

            # Organization → embedded founder / employee
            if "Organization" in itype or "LocalBusiness" in itype:
                for role_key in ("founder", "employee", "member"):
                    person_data = item.get(role_key)
                    if not isinstance(person_data, dict):
                        continue
                    name = (person_data.get("name") or "").strip()
                    title = (person_data.get("jobTitle") or role_key.title()).strip()
                    if name:
                        people.append(
                            _Person(
                                name=name,
                                title=_canonical_title(title),
                                rank=_title_rank(title),
                                email=(person_data.get("email") or "").replace("mailto:", "").strip().lower(),
                                phone=(person_data.get("telephone") or "").strip(),
                                source_quality=3,
                            )
                        )

    return people


# ---------------------------------------------------------------------------
# Strategy 2 — Microformats (h-card / vCard)
# ---------------------------------------------------------------------------


def _strategy_microformats(soup: BeautifulSoup) -> list[_Person]:
    people: list[_Person] = []
    seen: set[str] = set()

    # h-card (microformats2)
    for card in soup.find_all(True, class_=re.compile(r"\bh-card\b")):
        name_el = card.find(class_=re.compile(r"\bp-name\b"))
        role_el = card.find(class_=re.compile(r"\bp-role\b|\bp-job-title\b"))
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        title = role_el.get_text(strip=True) if role_el else ""
        if _looks_like_name(name) and _has_title_kw(title) and name not in seen:
            seen.add(name)
            people.append(
                _Person(
                    name=name,
                    title=_canonical_title(title),
                    rank=_title_rank(title),
                    source_quality=2,
                )
            )

    # vCard (microformats1)
    for vcard in soup.find_all(True, class_=re.compile(r"\bvcard\b")):
        name_el = vcard.find(class_=re.compile(r"\bfn\b"))
        title_el = vcard.find(class_=re.compile(r"\btitle\b|\brole\b"))
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        title = title_el.get_text(strip=True) if title_el else ""
        if _looks_like_name(name) and _has_title_kw(title) and name not in seen:
            seen.add(name)
            people.append(
                _Person(
                    name=name,
                    title=_canonical_title(title),
                    rank=_title_rank(title),
                    source_quality=2,
                )
            )

    return people


# ---------------------------------------------------------------------------
# Strategy 3 — Team cards and heading-sibling patterns
# ---------------------------------------------------------------------------


def _strategy_team_cards(soup: BeautifulSoup) -> list[_Person]:
    people: list[_Person] = []
    seen: set[str] = set()

    # 3a: heading + next non-empty sibling containing title keyword
    for heading in soup.find_all(["h2", "h3", "h4"]):
        name_text = heading.get_text(strip=True)
        if not _looks_like_name(name_text) or name_text in seen:
            continue
        title_text = ""
        for sib in heading.next_siblings:
            if not isinstance(sib, Tag):
                continue
            st = sib.get_text(strip=True)
            if not st:
                continue
            if _has_title_kw(st) and len(st) < 100:
                title_text = _canonical_title(st)
            break
        if title_text:
            linkedin = ""
            parent = heading.parent
            if parent:
                for a in parent.find_all("a", href=True):
                    m = _LINKEDIN_PERSON_RE.search(a["href"])
                    if m:
                        linkedin = m.group(0).rstrip("/")
                        break
            seen.add(name_text)
            people.append(
                _Person(
                    name=name_text,
                    title=title_text,
                    rank=_title_rank(title_text),
                    linkedin=linkedin,
                    source_quality=1,
                )
            )

    # 3b: container elements with team/member/leadership class names
    card_cls = re.compile(r"team|member|staff|person|people|founder|leadership|bio|executive", re.I)
    for card in soup.find_all(True, class_=card_cls):
        card_text = card.get_text(" ", strip=True)
        if not _has_title_kw(card_text):
            continue

        for tag in card.find_all(["h2", "h3", "h4", "strong", "b"]):
            name_text = tag.get_text(strip=True)
            if not _looks_like_name(name_text) or name_text in seen:
                continue

            # Find title within the card
            title_text = ""
            for child in card.find_all(["p", "span", "div", "em", "small", "figcaption"]):
                ct = child.get_text(strip=True)
                if _has_title_kw(ct) and 2 < len(ct) < 100:
                    title_text = _canonical_title(ct)
                    break

            # Find LinkedIn within the card
            linkedin = ""
            for a in card.find_all("a", href=True):
                m = _LINKEDIN_PERSON_RE.search(a["href"])
                if m:
                    linkedin = m.group(0).rstrip("/")
                    break

            seen.add(name_text)
            people.append(
                _Person(
                    name=name_text,
                    title=title_text,
                    rank=_title_rank(title_text),
                    linkedin=linkedin,
                    source_quality=1,
                )
            )

    return people


# ---------------------------------------------------------------------------
# Strategy 4 — Prose bio patterns
# ---------------------------------------------------------------------------


def _strategy_prose(soup: BeautifulSoup) -> list[_Person]:
    """
    Match patterns like:
      "Meet Jane Smith, Founder of Acme"
      "Hi, I'm John Doe, CEO"
      "Jane Smith is the Managing Director"
    """
    people: list[_Person] = []
    seen: set[str] = set()

    # Scan paragraphs only (avoid menu noise)
    for para in soup.find_all(["p", "li", "div"], limit=200):
        text = para.get_text(" ", strip=True)
        if len(text) > 300 or not _has_title_kw(text):
            continue

        m = _PROSE_PERSON_RE.search(text)
        if not m:
            continue

        name = m.group(1).strip()
        raw_title = (m.group(2) or "").strip()

        if not _looks_like_name(name) or name in seen:
            continue
        if not _has_title_kw(raw_title) and not _has_title_kw(text):
            continue

        # If title not captured by regex, try to find nearest title keyword in text
        if not raw_title or not _has_title_kw(raw_title):
            for kw_list, canonical in _TITLE_TAXONOMY:
                if any(kw in text.lower() for kw in kw_list):
                    raw_title = canonical
                    break

        if raw_title:
            seen.add(name)
            people.append(
                _Person(
                    name=name,
                    title=_canonical_title(raw_title),
                    rank=_title_rank(raw_title),
                    source_quality=1,
                )
            )

    return people


# ---------------------------------------------------------------------------
# Strategy 5 — <meta name="author"> (founder-run sites often set this)
# ---------------------------------------------------------------------------


def _strategy_meta_author(soup: BeautifulSoup) -> list[_Person]:
    people: list[_Person] = []
    tag = soup.find("meta", attrs={"name": re.compile(r"^author$", re.I)})
    if not tag:
        return []
    content = (tag.get("content") or "").strip()
    if _looks_like_name(content):
        people.append(
            _Person(name=content, title="", rank=99, source_quality=0)
        )
    return []  # only use as corroboration, not standalone


# ---------------------------------------------------------------------------
# Contact extraction (email / phone / LinkedIn) from a page
# ---------------------------------------------------------------------------


def _extract_contact_signals(soup: BeautifulSoup, visible: str) -> tuple[list[str], list[str], list[str]]:
    """
    Returns (emails, phones, linkedin_urls) lists — best quality first.
    """
    emails: list[str] = []
    phones: list[str] = []
    linkedins: list[str] = []

    # Emails — mailto: links are highest quality
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email and _EMAIL_RE.match(email) and email not in emails:
                emails.append(email)

    # Emails — visible text (after adding mailto: ones above)
    for m in _EMAIL_RE.finditer(visible):
        e = m.group(0).lower()
        if e not in emails:
            emails.append(e)

    # Phones — tel: links first
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("tel:"):
            num = _clean_phone(href[4:])
            if num and num not in phones:
                phones.insert(0, num)

    # Phones — visible text
    for m in _PHONE_RE.finditer(visible):
        num = _clean_phone(m.group(0))
        if num and num not in phones:
            phones.append(num)

    # LinkedIn — /in/ (personal) first, then /company/
    for a in soup.find_all("a", href=True):
        href = a["href"]
        mp = _LINKEDIN_PERSON_RE.search(href)
        if mp:
            url = mp.group(0).rstrip("/")
            if url not in linkedins:
                linkedins.append(url)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        mc = _LINKEDIN_CO_RE.search(href)
        if mc:
            url = mc.group(0).rstrip("/")
            if url not in linkedins:
                linkedins.append(url)

    return emails, phones, linkedins


# ---------------------------------------------------------------------------
# Full page extraction
# ---------------------------------------------------------------------------


def _extract_page(html: str) -> _PageSignals:
    soup = BeautifulSoup(html, "lxml")

    # Strip noise tags before extracting visible text
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()
    visible = soup.get_text(" ", strip=True)

    # Run all five extraction strategies
    people: list[_Person] = (
        _strategy_schema(soup)
        + _strategy_microformats(soup)
        + _strategy_team_cards(soup)
        + _strategy_prose(soup)
        + _strategy_meta_author(soup)
    )

    emails, phones, linkedins = _extract_contact_signals(soup, visible)

    return _PageSignals(people=people, emails=emails, phones=phones, linkedins=linkedins)


# ---------------------------------------------------------------------------
# Merge signals across all probed pages
# ---------------------------------------------------------------------------


def _merge(signals: list[_PageSignals]) -> dict:
    all_people: list[_Person] = []
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_linkedins: list[str] = []

    for sig in signals:
        all_people.extend(sig.people)
        for e in sig.emails:
            if e not in all_emails:
                all_emails.append(e)
        for ph in sig.phones:
            if ph not in all_phones:
                all_phones.append(ph)
        for li in sig.linkedins:
            if li not in all_linkedins:
                all_linkedins.append(li)

    # ── Pick best person ────────────────────────────────────────────────────
    best: _Person | None = None
    if all_people:
        # Deduplicate by name — keep the highest source_quality + lowest rank
        by_name: dict[str, _Person] = {}
        for p in all_people:
            key = p.name.lower()
            if key not in by_name:
                by_name[key] = p
            else:
                existing = by_name[key]
                if p.source_quality > existing.source_quality or (
                    p.source_quality == existing.source_quality and p.rank < existing.rank
                ):
                    by_name[key] = p

        candidates = sorted(by_name.values(), key=lambda p: (p.rank, -p.source_quality))
        best = candidates[0] if candidates else None

    # ── Pick best email ────────────────────────────────────────────────────
    email = ""
    if all_emails:
        # Priority 1: email that contains the decision-maker's name parts
        if best and best.name:
            for e in all_emails:
                if _name_matches_email(best.name, e):
                    email = e
                    break
        # Priority 2: non-generic email address
        if not email:
            for e in all_emails:
                if e.split("@")[0].lower() not in _GENERIC_EMAIL_PREFIXES:
                    email = e
                    break
        # Priority 3: any email (even generic)
        if not email:
            email = all_emails[0]

    # Use decision-maker's own email if found via schema
    if best and best.email and not email:
        email = best.email

    # ── Pick best phone ────────────────────────────────────────────────────
    phone = (best.phone if best and best.phone else "") or (all_phones[0] if all_phones else "")

    # ── Pick best LinkedIn ─────────────────────────────────────────────────
    linkedin_url = (best.linkedin if best and best.linkedin else "") or (all_linkedins[0] if all_linkedins else "")

    # ── Confidence score ───────────────────────────────────────────────────
    # Reflects how much contact intelligence was actually recovered.
    confidence = 0.0
    if best:
        confidence += 0.35
        if best.source_quality >= 3:   # schema.org — most reliable
            confidence += 0.20
        elif best.source_quality >= 2:  # microformats
            confidence += 0.10
        if best.title:
            confidence += 0.05
    if email:
        if email.split("@")[0].lower() not in _GENERIC_EMAIL_PREFIXES:
            confidence += 0.20  # personal / named email
        else:
            confidence += 0.10  # generic contact@ etc.
    if phone:
        confidence += 0.15
    if linkedin_url and "linkedin.com/in/" in linkedin_url:
        confidence += 0.10
    confidence = round(min(1.0, confidence), 2)

    return {
        "decisionMaker": best.name if best else "",
        "title":         best.title if best else "",
        "email":         email,
        "phone":         phone,
        "linkedinUrl":   linkedin_url,
        "confidence":    confidence,
    }


# ---------------------------------------------------------------------------
# Internal page discovery
# ---------------------------------------------------------------------------


def _discover_probe_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    base_netloc = urlparse(base_url).netloc
    seen_paths: set[str] = set()
    candidates: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(base_url, href).split("?")[0]
        parsed = urlparse(full)
        if parsed.netloc != base_netloc:
            continue
        path = parsed.path.rstrip("/") or "/"
        if _PROBE_PATH_RE.search(path) and path not in seen_paths:
            seen_paths.add(path)
            candidates.append(full)

    # Hardcoded fallbacks for sites with hidden nav
    for path in _PROBE_PATHS:
        full = urljoin(base_url, path).split("?")[0]
        p = urlparse(full).path.rstrip("/") or "/"
        if p not in seen_paths:
            seen_paths.add(p)
            candidates.append(full)

    return candidates[:8]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_contacts(website: str) -> dict:
    """
    Probe a company website for the most senior decision-maker and their
    contact details.

    Returns:
        {
            "decisionMaker": str,   # person name only
            "title":         str,   # job title only
            "email":         str,
            "phone":         str,
            "linkedinUrl":   str,
        }
    All values default to "" if not found.
    """
    empty = {
        "decisionMaker": "",
        "title": "",
        "email": "",
        "phone": "",
        "linkedinUrl": "",
    }

    # ── Step 1: fetch homepage ──────────────────────────────────────────────
    try:
        resp = requests.get(
            website, headers=_HEADERS, timeout=_PAGE_TIMEOUT, allow_redirects=True
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.info("contact_finder: homepage unreachable %s — %s", website, exc)
        return empty

    homepage_soup = BeautifulSoup(resp.text, "lxml")
    all_signals: list[_PageSignals] = [_extract_page(resp.text)]

    # ── Step 2: probe sub-pages ─────────────────────────────────────────────
    probe_urls = _discover_probe_urls(homepage_soup, website)
    probed = 0

    for url in probe_urls:
        if probed >= _MAX_PAGES_TO_PROBE:
            break
        if url.rstrip("/") == website.rstrip("/"):
            continue
        try:
            r = requests.get(
                url, headers=_HEADERS, timeout=_PAGE_TIMEOUT, allow_redirects=True
            )
            if r.status_code == 200:
                all_signals.append(_extract_page(r.text))
                probed += 1
                logger.info("contact_finder: probed %s", url)
        except Exception:
            continue

        # Early exit once we have a named person with contact info
        interim = _merge(all_signals)
        if interim["decisionMaker"] and (interim["email"] or interim["phone"]):
            logger.info("contact_finder: complete contact found at %s", url)
            return interim

    result = _merge(all_signals)
    logger.info(
        "contact_finder: %s → name=%r title=%r email=%r phone=%r linkedin=%r",
        website,
        bool(result["decisionMaker"]),
        bool(result["title"]),
        bool(result["email"]),
        bool(result["phone"]),
        bool(result["linkedinUrl"]),
    )
    return result
