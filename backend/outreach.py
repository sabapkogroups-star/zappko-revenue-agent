def generate_outreach(company: str, audit: dict, decision_maker: str = "") -> dict:
    """
    Generate personalised email and WhatsApp outreach drafts.

    Every draft must reference:
      - The company name
      - Specific audit findings (issues list)
      - Recommended services

    When a decision-maker name is available the greeting is personalised
    to their first name. Generic outreach is not acceptable.
    """
    issues   = audit.get("issues", [])
    services = audit.get("recommendedService", [])

    issue_bullets   = "\n".join(f"• {issue}" for issue in issues)
    primary_issue   = issues[0] if issues else "website optimisation opportunities"
    primary_service = services[0] if services else "business automation"
    service_list    = ", ".join(services[:3]) if services else "automation and lead generation"

    # Personalised greeting — use first name when available
    if decision_maker:
        first_name   = decision_maker.strip().split()[0]
        email_greet  = f"Hi {first_name},"
        wa_greet     = f"Hi {first_name}! 👋"
    else:
        email_greet  = "Hi,"
        wa_greet     = "Hi! 👋"

    email = f"""{email_greet}

I was reviewing {company}'s online presence and noticed a few specific gaps that are likely costing you leads every week:

{issue_bullets}

The "{primary_issue}" alone typically means losing 30–40% of potential enquiries before they even reach you.

At Zappko, we specialise in {primary_service} for businesses like yours. We've helped similar companies increase their lead capture by 2–3× within 30 days — without rebuilding their entire website.

Would you be open to a 15-minute call this week? I'll share exactly what we'd fix for {company} and what result you can expect.

Best regards,
Zaid
Founder, Zappko
zappko.com"""

    whatsapp = f"""{wa_greet}

I'm Zaid from Zappko. I checked out {company} and spotted a few things that might be holding back your growth:

{issue_bullets}

We fix exactly these — {service_list}.

Quick 15-min call? No sales pitch, just a clear plan for what we'd improve at {company}.

— Zaid, Zappko 🚀"""

    return {"email": email.strip(), "whatsapp": whatsapp.strip()}
