"""
Follow-up sequence generator for Zappko Revenue Agent.

Produces 4 timed messages per lead:
  Email 1     — Day 0   initial outreach with full audit summary
  Follow-up 1 — Day 4   single-issue spotlight, conversational
  Follow-up 2 — Day 8   ROI / deal-value angle
  Final       — Day 14  permission-based close
"""
from __future__ import annotations

_DAY_OFFSETS = [0, 4, 8, 14]
_LABELS = ["Email 1", "Follow-up 1", "Follow-up 2", "Final Follow-up"]


def _first_name(decision_maker: str) -> str:
    name = (decision_maker or "").strip()
    return name.split()[0] if name else "there"


def _domain(website: str) -> str:
    return website.replace("https://", "").replace("http://", "").rstrip("/")


def _bullet_issues(issues: list[str], max_items: int = 5) -> str:
    return "\n".join(f"  • {issue}" for issue in issues[:max_items])


def _primary_issue(issues: list[str]) -> str:
    return issues[0] if issues else "website optimisation gap"


def _top_service(services: list[str]) -> str:
    return services[0] if services else "lead generation"


def _services_inline(services: list[str], max_items: int = 3) -> str:
    return ", ".join(services[:max_items]) or "website optimisation"


# ---------------------------------------------------------------------------
# Individual message builders
# ---------------------------------------------------------------------------

def _email_1(
    company: str,
    website: str,
    decision_maker: str,
    website_score: int,
    deal_value: str,
    issues: list[str],
    recommended_services: list[str],
) -> dict:
    first = _first_name(decision_maker)
    domain = _domain(website)
    n = len(issues)
    bullets = _bullet_issues(issues)
    services = _services_inline(recommended_services)

    subject = f"{company}'s website audit — {n} issue{'s' if n != 1 else ''} found"

    body = (
        f"Hi {first},\n\n"
        f"I ran a quick technical audit on {company}'s website ({domain}) and found "
        f"{n} specific {'issues' if n != 1 else 'issue'} that are likely costing you leads right now.\n\n"
        f"Your site scored {website_score}/100. Here's the summary:\n\n"
        f"{bullets}\n\n"
        f"The good news: every one of these is fixable — some in as little as 48 hours.\n\n"
        f"At Zappko we specialise in exactly this: {services}. "
        f"Not a full website rebuild — just the targeted fixes that turn your existing traffic into enquiries.\n\n"
        f"Would it make sense to get on a 15-minute call? "
        f"I can walk you through exactly what we'd do for {company}.\n\n"
        f"Best,\n"
        f"Zaid\n"
        f"Founder, Zappko | zappko.com"
    )

    return {"label": _LABELS[0], "dayOffset": _DAY_OFFSETS[0], "subject": subject, "body": body}


def _followup_1(
    company: str,
    decision_maker: str,
    issues: list[str],
) -> dict:
    first = _first_name(decision_maker)
    primary = _primary_issue(issues)

    subject = f"Re: {company} — the {primary.lower()} fix"

    body = (
        f"Hi {first},\n\n"
        f"Just following up on the audit note I sent last week.\n\n"
        f"One thing I wanted to flag specifically: {primary}.\n\n"
        f"For businesses in your space, this single gap typically reduces inbound enquiries by 30–40%. "
        f"It's the kind of thing that's invisible until it's fixed — and then the difference is immediate.\n\n"
        f"We can have this sorted for {company} in under a week.\n\n"
        f"Worth a quick reply?\n\n"
        f"Zaid\n"
        f"Zappko | zappko.com"
    )

    return {"label": _LABELS[1], "dayOffset": _DAY_OFFSETS[1], "subject": subject, "body": body}


def _followup_2(
    company: str,
    decision_maker: str,
    website_score: int,
    deal_value: str,
    recommended_services: list[str],
) -> dict:
    first = _first_name(decision_maker)
    top_svc = _top_service(recommended_services)

    subject = f"{company} — what {deal_value} looks like in 30 days"

    body = (
        f"Hi {first},\n\n"
        f"I'll keep this short.\n\n"
        f"Based on your site's audit score ({website_score}/100) and the gaps we identified, "
        f"fixing {top_svc} alone typically generates {deal_value} in additional monthly revenue "
        f"for businesses at your stage.\n\n"
        f"That's not a projection — it's what we see consistently from businesses with similar audit profiles.\n\n"
        f"I'm confident we can move the needle for {company} within 30 days. "
        f"The only question is timing.\n\n"
        f"15 minutes this week?\n\n"
        f"Zaid\n"
        f"Zappko | zappko.com"
    )

    return {"label": _LABELS[2], "dayOffset": _DAY_OFFSETS[2], "subject": subject, "body": body}


def _final_followup(
    company: str,
    decision_maker: str,
    issues: list[str],
) -> dict:
    first = _first_name(decision_maker)
    primary = _primary_issue(issues)

    subject = f"Last note — {company}"

    body = (
        f"Hi {first},\n\n"
        f"I've reached out a few times about {company}'s website — "
        f"I don't want to keep interrupting if the timing is off.\n\n"
        f"Quick question: is fixing {primary.lower()} and improving your website's lead generation "
        f"even a priority in the next 90 days?\n\n"
        f"Three options:\n"
        f"  → Reply \"yes\" and I'll send a quick 15-min calendar link.\n"
        f"  → Reply \"not now\" and I'll close your file — no hard feelings.\n"
        f"  → Reply \"later\" and I'll check back in a few months.\n\n"
        f"Either way, wishing {company} all the best.\n\n"
        f"Zaid\n"
        f"Founder, Zappko | zappko.com"
    )

    return {"label": _LABELS[3], "dayOffset": _DAY_OFFSETS[3], "subject": subject, "body": body}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_followups(
    company: str,
    website: str,
    decision_maker: str,
    website_score: int,
    deal_value: str,
    issues: list[str],
    recommended_services: list[str],
) -> list[dict]:
    """
    Generate a 4-message follow-up sequence for a lead.

    Returns:
        List of {label, dayOffset, subject, body} dicts in send order.
    """
    return [
        _email_1(company, website, decision_maker, website_score, deal_value, issues, recommended_services),
        _followup_1(company, decision_maker, issues),
        _followup_2(company, decision_maker, website_score, deal_value, recommended_services),
        _final_followup(company, decision_maker, issues),
    ]
