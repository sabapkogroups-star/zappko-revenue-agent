import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from audit import audit_website
from contact_finder import find_contacts
from data_quality import deduplicate_leads, is_valid_email, is_valid_phone, normalize_phone
from models import (
    DiscoveryRequest, FollowUpRequest, FollowUpResponse, FollowUpMessage,
    LeadResult, ProposalRequest, RecommendationRequest, RecommendationResponse,
)
from outreach import generate_outreach
from scorer import score_lead
from scraper import discover_companies

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Zappko Revenue Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MAX_AUDIT_WORKERS = 6


def _build_lead(index: int, company: dict, country: str = "") -> Optional[LeadResult]:
    """Audit one company, find contacts, score, and generate outreach. Thread-safe."""
    try:
        audit    = audit_website(company["website"], seed=index)
        contacts = find_contacts(company["website"])
        scores   = score_lead(audit, website=company["website"], country=country)

        # ── Contact data quality ──────────────────────────────────────────
        raw_phone = contacts.get("phone") or company.get("phone", "") or ""
        phone     = normalize_phone(raw_phone)
        phone_verified = is_valid_phone(raw_phone)

        raw_email = contacts.get("email") or company.get("email", "") or ""
        email_verified = is_valid_email(raw_email)
        # Only store the email if it passes validation — no fakes in the DB
        email = raw_email if email_verified else ""

        decision_maker = contacts.get("decisionMaker") or company.get("decisionMaker", "")

        # ── Outreach — always personalised to this company + audit ────────
        outreach = generate_outreach(
            company["company"],
            audit,
            decision_maker=decision_maker,
        )

        return LeadResult(
            company=company["company"],
            website=company["website"],
            decisionMaker=decision_maker,
            title=contacts.get("title", ""),
            email=email,
            phone=phone,
            linkedinUrl=contacts.get("linkedinUrl", ""),
            contactConfidence=contacts.get("confidence", 0.0),
            emailVerified=email_verified,
            phoneVerified=phone_verified,
            source=company.get("source", ""),
            confidence=company.get("confidence", 0.0),
            discoveredAt=datetime.now(timezone.utc).isoformat(),
            websiteScore=audit["websiteScore"],
            opportunityScore=scores["opportunityScore"],
            hotLeadScore=scores["hotLeadScore"],
            dealValue=scores["dealValue"],
            issues=audit["issues"],
            recommendedService=audit["recommendedService"],
            emailDraft=outreach["email"],
            whatsappDraft=outreach["whatsapp"],
        )
    except Exception as exc:
        logger.error("Failed to build lead for %s: %s", company.get("company"), exc)
        return None


@app.get("/")
def home():
    return {"status": "online", "app": "Zappko Revenue Agent", "version": "2.0.0"}


@app.post("/discover", response_model=list[LeadResult])
def discover(request: DiscoveryRequest):
    logger.info(
        "Discovery: industry=%s city=%s country=%s limit=%d page=%d",
        request.industry,
        request.city,
        request.country,
        request.limit,
        request.page,
    )

    companies = discover_companies(
        industry=request.industry,
        city=request.city,
        country=request.country,
        limit=request.limit,
        page=request.page,
    )

    if not companies:
        logger.warning("No companies found — check network or search engine availability")
        return []

    logger.info("Found %d companies, starting parallel audit …", len(companies))

    ordered: list[tuple[int, LeadResult]] = []

    with ThreadPoolExecutor(max_workers=_MAX_AUDIT_WORKERS) as pool:
        future_to_idx = {
            pool.submit(_build_lead, i, company, request.country): i
            for i, company in enumerate(companies)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            result = future.result()
            if result is not None:
                ordered.append((idx, result))

    # Restore original discovery ordering (highest confidence first)
    ordered.sort(key=lambda pair: pair[0])
    leads = [lead for _, lead in ordered]

    # Global deduplication pass — catches email/phone/linkedin collisions
    # that domain-level dedup in scraper.py cannot see
    leads_dicts  = [l.model_dump() for l in leads]
    deduped_dicts = deduplicate_leads(leads_dicts)
    deduped_websites = {d["website"] for d in deduped_dicts}
    leads = [l for l in leads if l.website in deduped_websites]

    logger.info("Returning %d leads (after dedup)", len(leads))
    return leads


@app.post("/follow-ups", response_model=FollowUpResponse)
def generate_follow_ups(request: FollowUpRequest) -> FollowUpResponse:
    from followup import generate_followups

    messages = generate_followups(
        company=request.company,
        website=request.website,
        decision_maker=request.decisionMaker or "",
        website_score=request.websiteScore,
        deal_value=request.dealValue,
        issues=request.issues,
        recommended_services=request.recommendedService,
    )
    return FollowUpResponse(followUps=[FollowUpMessage(**m) for m in messages])


@app.post("/proposal-pdf")
def generate_proposal(lead: ProposalRequest) -> Response:
    from proposal_generator import create_proposal_pdf

    pdf_bytes = create_proposal_pdf(lead.model_dump())
    slug = lead.company.lower().replace(" ", "-")[:40]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="zappko-proposal-{slug}.pdf"'},
    )


@app.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    from recommendations import generate_recommendations
    result = generate_recommendations(request.leads)
    return RecommendationResponse(**result)


@app.post("/audit-pdf")
def generate_pdf(lead: LeadResult) -> Response:
    from audit_pdf_generator import generate_audit_report

    pdf_bytes = generate_audit_report(lead.model_dump())
    slug = lead.company.lower().replace(" ", "-")[:40]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="zappko-audit-{slug}.pdf"'},
    )


@app.post("/generate-audit-pdf")
def generate_audit_pdf(lead: LeadResult) -> Response:
    """Alias for /audit-pdf — generates and streams the full audit PDF report."""
    from audit_pdf_generator import generate_audit_report

    pdf_bytes = generate_audit_report(lead.model_dump())
    slug = lead.company.lower().replace(" ", "-")[:40]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="zappko-audit-{slug}.pdf"'},
    )
