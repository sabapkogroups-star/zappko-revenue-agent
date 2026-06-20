def score_lead(audit: dict, website: str = "", country: str = "") -> dict:
    website_score: int = audit["websiteScore"]
    opportunity_score = max(0, min(100, 100 - website_score))

    # Detect deal currency from country hint first, then TLD
    tld = website.lower().rstrip("/").split(".")[-1] if website else ""
    country_lower = country.lower()
    is_uae = (
        country_lower in ("uae", "united arab emirates", "emirates")
        or any(kw in country_lower for kw in ("dubai", "abu dhabi", "sharjah"))
        or tld in ("ae",)
        or any(kw in website.lower() for kw in ("dubai", "uae", ".ae"))
    )
    is_india = (
        country_lower in ("india",)
        or any(kw in country_lower for kw in ("mumbai", "delhi", "bangalore", "hyderabad"))
        or tld in ("in",)
    )
    is_uk = country_lower in ("uk", "united kingdom") or tld in ("gb", "uk", "co.uk")

    if is_uae:
        if opportunity_score >= 50:
            deal_value = "AED 50,000"
        elif opportunity_score >= 30:
            deal_value = "AED 30,000"
        else:
            deal_value = "AED 15,000"
    elif is_india:
        if opportunity_score >= 50:
            deal_value = "₹75,000"
        elif opportunity_score >= 30:
            deal_value = "₹50,000"
        else:
            deal_value = "₹25,000"
    elif is_uk:
        if opportunity_score >= 50:
            deal_value = "£15,000"
        elif opportunity_score >= 30:
            deal_value = "£10,000"
        else:
            deal_value = "£5,000"
    else:
        if opportunity_score >= 50:
            deal_value = "$15,000"
        elif opportunity_score >= 30:
            deal_value = "$10,000"
        else:
            deal_value = "$5,000"

    issue_count = len(audit.get("issues", []))
    hot_lead_score = min(100, opportunity_score + (issue_count * 5))

    return {
        "opportunityScore": opportunity_score,
        "dealValue": deal_value,
        "hotLeadScore": hot_lead_score,
    }
