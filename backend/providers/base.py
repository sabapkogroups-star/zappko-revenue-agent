"""
Shared data types, constants, and utilities used by all discovery providers.
"""
from __future__ import annotations

import abc
import random
import re
from dataclasses import dataclass
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Domain / URL filter
# ---------------------------------------------------------------------------

SKIP_DOMAINS: frozenset[str] = frozenset(
    {
        # Search engines
        "google.com", "google.co", "google.in", "googleapis.com", "goo.gl",
        "bing.com", "yahoo.com", "duckduckgo.com",
        # Social / video
        "youtube.com", "youtu.be", "facebook.com", "fb.com",
        "twitter.com", "x.com", "instagram.com", "linkedin.com",
        "tiktok.com", "pinterest.com", "snapchat.com",
        # Encyclopaedia
        "wikipedia.org", "wikimedia.org", "wikidata.org",
        # Review / directory / aggregator
        "yelp.com", "tripadvisor.com", "trustpilot.com",
        "justdial.com", "sulekha.com", "indiamart.com",
        "tradeindia.com", "exportersindia.com", "dir.indiamart.com",
        "yellowpages.com", "yellowpages.ae", "yellowpages.in",
        "businesslist.com", "businesslist.in",
        "mca.gov.in", "zaubacorp.com", "mapsofindia.com",
        "clutch.co", "sortlist.com", "goodfirms.co", "upcity.com",
        "designrush.com", "agencyspotter.com",
        "crunchbase.com", "pitchbook.com", "owler.com",
        "bbb.org", "angieslist.com", "houzz.com", "thumbtack.com",
        "bark.com", "checkatrade.com", "ratedpeople.com",
        "glassdoor.com", "glassdoor.co.in", "indeed.com", "naukri.com",
        "monster.com", "timesjobs.com",
        # E-commerce
        "amazon.com", "amazon.in", "amazon.ae",
        "flipkart.com", "snapdeal.com", "noon.com", "dubizzle.com",
        "alibaba.com", "aliexpress.com",
        # Q&A / forums
        "quora.com", "reddit.com", "medium.com",
        # Lead / data vendors
        "aeroleads.com", "apollo.io", "zoominfo.com", "lusha.com",
        "hunter.io", "rocketreach.com",
        # B2B tech directories
        "superbcompanies.com", "techbehemoths.com", "themanifest.com",
        "itfirms.co", "appfutura.com", "topdevelopers.co",
        "topsoftwarecompanies.co",
        # Real estate portals
        "bayut.com", "propertyfinder.ae", "99acres.com",
        "magicbricks.com", "housing.com", "makaan.com",
        "engelvoelkers.com", "kw.com", "remax.com",
        # Indian business directories
        "eximbankindia.in", "bdir.in",
        "threebestrated.in", "threebestrated.com",
        "asklaila.com", "urbanclap.com", "urban-company.com",
        # Startup / company lists
        "f6s.com", "ensun.io", "beststartup.in", "beststartup.ae",
        "startupblink.com", "top10indubai.com", "top10dubai.com",
        "top10india.com", "businessofapps.com", "topcompanieslist.com",
        "datagemba.com", "listcorp.com", "companieslist.com",
        # Yellow pages variants
        "yellowpages-uae.com", "yellowpages-india.com", "yellowpagesindia.com",
        "pagesdubai.com", "dubai-directory.com", "emiratesdirectory.com",
        "uaedirectory.com",
        # News / media
        "forbes.com", "businessinsider.com", "techcrunch.com",
        "gulf-news.com", "arabianbusiness.com", "khaleejtimes.com",
        "timesofindia.com", "economictimes.com", "livemint.com",
        "thehindu.com", "ndtv.com",
        # Dictionaries / reference / encyclopaedia
        "merriam-webster.com", "dictionary.com", "oxfordlearnersdictionaries.com",
        "cambridge.org", "britannica.com", "vocabulary.com", "thesaurus.com",
        "collinsdictionary.com", "macmillandictionary.com",
        # Tourism / travel
        "tripadvisor.in", "booking.com", "airbnb.com", "expedia.com",
        "makemytrip.com", "goibibo.com", "cleartrip.com", "yatra.com",
        "jaipurtourism.co.in", "tourism.gov", "incredibleindia.org",
        # Education / courses
        "coursera.org", "udemy.com", "edx.org", "khanacademy.org",
        "geeksforgeeks.org", "w3schools.com", "tutorialspoint.com",
        "stackoverflow.com", "github.com", "gitlab.com",
        # Government portals (not individual businesses)
        "dubai.gov.ae", "uaegov.ae", "moefc.gov.ae",
        "lawmin.gov.in", "lawcommissionofindia.nic.in", "india.gov.in",
        "mca.gov.in", "judiciary.gov.ae", "moj.gov.ae",
        # Legal databases / research portals
        "indiankanoon.org", "judis.nic.in", "legalbites.in",
        "barandbench.com", "livelaw.in", "verdictum.in",
        # Education / career portals
        "shiksha.com", "collegedunia.com", "careers360.com",
        "getmyuni.com", "studyabroad.com",
        # Restaurant / venue aggregators
        "eazydiner.com", "venuelook.com", "zomato.com", "swiggy.com",
        "opentable.com", "tableagent.com", "dineout.co.in",
        # Legal databases
        "juristopedia.com", "casemine.com", "manupatra.com",
        "legallyindia.com", "aironline.in",
        # Home decor aggregators
        "houzz.in", "homedepot.com", "ikea.com",
        # Generic business listing/review
        "wamda.com", "zawya.com", "dubaicityinfo.com",
        # Indian Yellow Pages aggregators
        "webindia123.com", "yellowpages.webindia123.com",
        "tradeindia.com", "clickindia.com", "indiabizclub.com",
        # Business data / directory aggregators
        "dnb.com", "dun-bradstreet.com",
        "companydetails.in", "listcompany.org", "onefivenine.com",
        "falconebiz.com", "tofler.in", "comparably.com",
        "roc.in", "mcaservices.gov.in",
        # Food/restaurant equipment (not restaurants)
        "sheebaequipments.com", "mayurmetalworks.in",
        "raunakkitchen.in", "kitchenequipments.in", "commercialkitchen.in",
        # Link aggregators / bio pages
        "linktr.ee", "linktree.com", "bio.link", "beacons.ai",
        # Job boards / tech company directories
        "builtin.com", "builtinsf.com", "builtinnyc.com",
        "simplyhired.com", "dice.com", "wellfound.com", "angel.co",
        # Finance / stock
        "moneycontrol.com", "investing.com", "marketwatch.com",
        # Health / medical portals
        "webmd.com", "healthline.com", "medicalnewstoday.com",
        # Generic content sites
        "wordpress.com", "blogspot.com", "wix.com", "squarespace.com",
        "housegyan.com", "architecturaldigest.in", "architecturaldigest.com",
        "designcafe.com", "livspace.com", "interiorcompany.com",
        "homedecor.com", "decorilla.com",
    }
)

LIST_PATH_RE = re.compile(
    r"/(top-?\d+|best[-_]|top[-_]|list[-_]of|directory|companies[-_]in|"
    r"ranking|compare|vs[-_]|review[-_]|blog/|article/|news/)",
    re.IGNORECASE,
)

LIST_TITLE_RE = re.compile(
    r"^(top\s*\d+|best\s*\d+|\d+\s*best|\d+\s*top|list\s+of|"
    r"\d+\s+(places|ways|tips|things|reasons|examples|ideas)|"
    r"how\s+to|what\s+is|why\s+|when\s+|where\s+|who\s+is|the\s+best\b|"
    r"#\s*\d+|no\.?\s*\d+\s+(top|best|rated)|"
    r"(best|top|leading|premier)\s+\w[\w\s]*\s+(in|of|for)\s+)",
    re.IGNORECASE,
)

TAGLINE_RE = re.compile(
    r"(your\s+space|in\s+\w+,?\s*(uae|india|dubai|mumbai|delhi|london|uk|us)|"
    r"\bwe\s+are\b|\bwe\s+offer\b|\bis\s+a\b|the\s+best\b|the\s+leading|"
    r"\boffers?\b|\bprovides?\b|\bspecialists?\b|\bexperts?\b)",
    re.IGNORECASE,
)

USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.2210.91"
    ),
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CompanyRecord:
    company: str
    website: str
    phone: str = ""
    email: str = ""
    source: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "website": self.website,
            "phone": self.phone,
            "email": self.email,
            "source": self.source,
            "confidence": self.confidence,
            "decisionMaker": "",
        }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def build_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        netloc = p.netloc.lower().lstrip("www.")
        if any(skip in netloc for skip in SKIP_DOMAINS):
            return False
        # Skip government and institutional domains (not individual businesses)
        if re.search(r"\.gov(\.|$)|\.nic\.in$|\.gov\.in$|\.gov\.ae$", netloc):
            return False
        if LIST_PATH_RE.search(p.path):
            return False
        return True
    except Exception:
        return False


def root_url(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return url


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url


def domain_to_name(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        slug = re.sub(
            r"\.(co\.(uk|in|ae|nz)|com|ae|in|uk|net|org|io|me|info|biz|gov|edu).*$",
            "",
            netloc,
        )
        parts = re.split(r"[-_]", slug)
        return " ".join(p.title() for p in parts if p)
    except Exception:
        return url


_GEO_WORDS = frozenset({
    # Geography
    "dubai", "uae", "abu dhabi", "sharjah", "india", "mumbai", "delhi",
    "bangalore", "hyderabad", "pune", "chennai", "kolkata", "london", "uk",
    # Generic nav/page labels that often appear as first segment
    "home", "homepage", "welcome", "contact", "contact us", "get in touch",
    "about", "about us", "who we are", "services", "portfolio", "gallery",
    "blog", "news", "careers", "faq", "privacy", "terms",
})


_FIRST_NOISE_RE = re.compile(
    r"\b(uae|dubai|abu\s+dhabi|sharjah|india|mumbai|delhi|bangalore|"
    r"law\s+firm|interior\s+design|marketing\s+agency|architecture\s+firm|"
    r"restaurant|it\s+company|software\s+company)\b",
    re.IGNORECASE,
)


def clean_name(raw: str) -> str:
    for sep in (" | ", " - ", " – ", " — ", " :: ", ": "):
        if sep in raw:
            parts = raw.split(sep, 1)
            first = parts[0].strip()
            second = parts[1].strip()
            # Prefer second segment when first is a bare geo/nav label,
            # very short, or is a generic descriptive phrase (contains geo/industry words)
            first_lower = first.lower()
            if (
                first_lower in _GEO_WORDS
                or (len(first) <= 5 and len(second) > len(first))
                or (_FIRST_NOISE_RE.search(first) and len(second) >= 3)
            ):
                raw = second
            else:
                raw = first
            break
    noise = re.compile(
        r"\s*(official site|home|welcome|main page|homepage)$",
        re.IGNORECASE,
    )
    return noise.sub("", raw).strip(" .,|-")


def looks_like_company(name: str) -> bool:
    if len(name.split()) > 6:
        return False
    if TAGLINE_RE.search(name):
        return False
    return True


def is_captcha_page(resp) -> bool:  # type: ignore[no-untyped-def]
    low = resp.text.lower()
    return (
        resp.status_code in (429, 503)
        or "/sorry/" in resp.url
        or "captcha" in low
        or "unusual traffic" in low
        or "our systems have detected" in low
        or (len(resp.text) < 10_000 and "enablejs" in low)
    )


# ---------------------------------------------------------------------------
# Abstract base provider
# ---------------------------------------------------------------------------


class BaseProvider(abc.ABC):
    name: str = "base"
    base_confidence: float = 0.65

    @abc.abstractmethod
    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        """Return up to `limit` CompanyRecord objects for the given query string."""
        ...

    def _score(self, record: CompanyRecord) -> float:
        s = self.base_confidence
        if record.phone:
            s += 0.05
        if record.email:
            s += 0.05
        return round(min(0.95, s), 2)
