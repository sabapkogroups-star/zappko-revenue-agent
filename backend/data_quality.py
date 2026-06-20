"""
Revenue Agent Data Quality Lock.

Normalization and validation applied to every lead before it leaves the
discovery pipeline. Never raises — returns empty string / False on bad data.

Exports:
  normalize_phone(raw)       -> str   (empty if invalid)
  is_valid_phone(raw)        -> bool
  is_valid_email(email)      -> bool  (rejects placeholders / disposable)
  deduplicate_leads(leads)   -> list[dict]
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Phone normalization & validation
# ---------------------------------------------------------------------------

_FAKE_PHONE_RES: list[re.Pattern] = [re.compile(p) for p in [
    r"^0{7,}$",           # all zeros
    r"^1{7,}$",           # all ones
    r"^(\d)\1{7,}$",      # 8+ repeated same digit
    r"^1234567",          # ascending sequence
    r"^000\d",            # starts 000x
    r"555-?0[01]\d\d",    # US TV placeholder 555-01xx
]]


def normalize_phone(raw: str) -> str:
    """
    Return a cleaned phone string, or "" if the number is invalid or fake.

    Rules:
      - Must contain 7–15 digits
      - Strips everything except digits, +, spaces, hyphens, parens, dots
      - Rejects known fake patterns (all-zeros, sequential, etc.)
    """
    if not raw:
        return ""
    cleaned = re.sub(r"[^\d+\s\-().]", "", raw.strip())
    digits = re.sub(r"\D", "", cleaned)
    if not (7 <= len(digits) <= 15):
        return ""
    for pat in _FAKE_PHONE_RES:
        if pat.search(digits):
            return ""
    return cleaned.strip()


def is_valid_phone(raw: str) -> bool:
    """True iff normalize_phone returns a non-empty string."""
    return bool(normalize_phone(raw))


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_FAKE_PREFIXES: frozenset[str] = frozenset({
    "test", "example", "sample", "demo", "fake", "noreply", "no-reply",
    "donotreply", "do-not-reply", "placeholder", "email", "user",
    "admin123", "test123", "dummy", "abc", "xyz", "foo", "bar",
    "null", "none", "na", "webmaster", "postmaster", "bounce",
})

_DISPOSABLE_DOMAINS: frozenset[str] = frozenset({
    "example.com", "example.org", "example.net",
    "test.com", "test.org", "fake.com", "dummy.com",
    "mailinator.com", "guerrillamail.com", "temp-mail.org",
    "throwaway.email", "trashmail.com", "yopmail.com",
    "10minutemail.com", "tempinbox.com", "sharklasers.com",
    "guerrillamailblock.com", "grr.la", "guerrillamail.info",
    "spam4.me", "trashmail.at", "dispostable.com", "maildrop.cc",
    "mailnull.com", "spamgourmet.com", "spamgourmet.net",
})


def is_valid_email(email: str) -> bool:
    """
    True iff the email:
      - Matches the RFC-like format regex
      - Is not a known fake/placeholder prefix
      - Is not a disposable-domain address
      - Prefix is not all-digits
    """
    if not email:
        return False
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return False
    try:
        prefix, domain = email.rsplit("@", 1)
    except ValueError:
        return False
    if prefix in _FAKE_PREFIXES:
        return False
    if domain in _DISPOSABLE_DOMAINS:
        return False
    if re.match(r"^\d+$", prefix):  # purely numeric prefix
        return False
    return True


# ---------------------------------------------------------------------------
# Generic (non-personal) email prefixes — used to skip email dedup
# ---------------------------------------------------------------------------

_GENERIC_PREFIXES: frozenset[str] = frozenset({
    "info", "hello", "contact", "support", "admin", "mail", "office",
    "team", "enquiries", "enquiry", "sales", "marketing", "pr", "media",
    "help", "general", "accounts", "reception", "enquire", "connect",
    "business", "service", "services", "hello",
})


def _is_personal_email(email: str) -> bool:
    """Return True if the email looks personal (not a role/generic address)."""
    prefix = email.split("@")[0].lower()
    return prefix not in _GENERIC_PREFIXES


# ---------------------------------------------------------------------------
# Domain extraction helper
# ---------------------------------------------------------------------------


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Cross-field lead deduplication
# ---------------------------------------------------------------------------


def deduplicate_leads(leads: list[dict]) -> list[dict]:
    """
    Remove duplicate leads from a list.

    A lead is a duplicate if ANY of these match an already-seen entry:
      - Website domain (normalized, www-stripped)
      - Personal email address (generic role emails are skipped)
      - Phone number digits (≥7 digits match)
      - LinkedIn personal profile URL

    First occurrence wins. Order is preserved.
    """
    seen_domains:   set[str] = set()
    seen_emails:    set[str] = set()
    seen_phones:    set[str] = set()
    seen_linkedins: set[str] = set()

    result: list[dict] = []

    for lead in leads:
        # --- Domain ---
        domain = _domain(lead.get("website", ""))
        if domain and domain in seen_domains:
            continue

        # --- Email (personal only) ---
        email = (lead.get("email") or "").strip().lower()
        if email and is_valid_email(email) and _is_personal_email(email):
            if email in seen_emails:
                continue

        # --- Phone ---
        phone_digits = re.sub(r"\D", "", lead.get("phone", "") or "")
        if len(phone_digits) >= 7 and phone_digits in seen_phones:
            continue

        # --- LinkedIn personal profile ---
        linkedin = (lead.get("linkedinUrl") or "").rstrip("/").lower()
        if linkedin and "linkedin.com/in/" in linkedin and linkedin in seen_linkedins:
            continue

        # Accepted — register and keep
        result.append(lead)
        if domain:
            seen_domains.add(domain)
        if email and is_valid_email(email) and _is_personal_email(email):
            seen_emails.add(email)
        if len(phone_digits) >= 7:
            seen_phones.add(phone_digits)
        if linkedin and "linkedin.com/in/" in linkedin:
            seen_linkedins.add(linkedin)

    return result
