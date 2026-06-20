"""
Zappko Enhanced Audit PDF Generator.

Generates a professional multi-page audit report with:
  Cover page  — company name, score, date, audit ID
  Section 1   — Executive Summary
  Section 2   — Website Health Score breakdown
  Section 3   — Issues Found (severity-coded)
  Section 4   — Revenue Opportunities
  Section 5   — Recommended Services
  Section 6   — ROI Estimate
  Section 7   — Zappko Recommendation

This module wraps the core logic from pdf_generator.py and adds a
full-bleed dark cover page with the score prominently displayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Re-use all build helpers from the core module
from pdf_generator import (
    _build_executive_summary,
    _build_footer,
    _build_issues_section,
    _build_meta_row,
    _build_next_steps,
    _build_opportunities_section,
    _build_recommendation,
    _build_roi_section,
    _build_score_section,
    _build_services_section,
    _styles,
    CONTENT_W,
    MARGIN,
    C_DARK,
    C_DARK2,
    C_BLUE,
    C_BLUE_LIGHT,
    C_GREEN,
    C_AMBER,
    C_RED,
    C_WHITE,
    C_MUTED,
    C_BORDER,
    C_TEXT,
)

# CONTENT_H derived from page size (not exported from pdf_generator)
CONTENT_H = A4[1] - 2 * MARGIN

PAGE_W, PAGE_H = A4
_FP = 6  # SimpleDocTemplate internal frame padding

AVAIL_W = CONTENT_W - 2 * _FP
AVAIL_H = CONTENT_H - 2 * _FP

COVER_PAD = 14 * mm

# ---------------------------------------------------------------------------
# Brand colours (same palette)
# ---------------------------------------------------------------------------

C_SCORE_GOOD = C_GREEN
C_SCORE_MED  = C_AMBER
C_SCORE_BAD  = C_RED

# ---------------------------------------------------------------------------
# Interior header/footer callback
# ---------------------------------------------------------------------------


def _interior_header(canvas, doc, company: str) -> None:
    if doc.page < 2:
        return
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(MARGIN, PAGE_H - MARGIN + 6 * mm, "ZAPPKO REVENUE AGENT  ·  WEBSITE AUDIT")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(
        PAGE_W - MARGIN, PAGE_H - MARGIN + 6 * mm,
        f"{company.upper()}  ·  AUDIT REPORT",
    )
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN, PAGE_H - MARGIN + 4 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN + 4 * mm)
    # Page number
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(PAGE_W / 2, MARGIN - 8 * mm, f"— {doc.page} —")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------


def _build_cover(data: dict) -> list:
    company = data.get("company", "Company")
    website = data.get("website", "").replace("https://", "").replace("http://", "")
    score   = data.get("websiteScore", 0)
    issues  = data.get("issues", [])
    deal    = data.get("dealValue", "—")
    dm      = data.get("decisionMaker", "")
    date_s  = datetime.now(timezone.utc).strftime("%B %d, %Y")
    audit_id = f"ZA-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"

    score_color = C_SCORE_GOOD if score >= 70 else (C_SCORE_MED if score >= 50 else C_SCORE_BAD)
    score_label = "GOOD" if score >= 70 else ("NEEDS WORK" if score >= 50 else "CRITICAL")

    cover_style = ParagraphStyle("cov", fontName="Helvetica", fontSize=9, textColor=C_WHITE, leading=14)
    cover_small = ParagraphStyle("covs", fontName="Helvetica", fontSize=7.5, textColor=colors.HexColor("#71717a"), leading=12)
    cover_big   = ParagraphStyle("covb", fontName="Helvetica-Bold", fontSize=34, textColor=C_WHITE, leading=40, alignment=TA_CENTER)
    cover_tag   = ParagraphStyle("covt", fontName="Helvetica-Bold", fontSize=9.5, textColor=C_BLUE_LIGHT, leading=14, alignment=TA_CENTER, spaceAfter=4)
    cover_sub   = ParagraphStyle("covsu", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#a1a1aa"), leading=16, alignment=TA_CENTER)
    cover_score = ParagraphStyle("covsc", fontName="Helvetica-Bold", fontSize=64, textColor=score_color, leading=72, alignment=TA_CENTER)
    cover_score_label = ParagraphStyle("covsl", fontName="Helvetica-Bold", fontSize=11, textColor=score_color, leading=16, alignment=TA_CENTER)
    cover_meta  = ParagraphStyle("covm", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#71717a"), leading=13, alignment=TA_CENTER)

    # Build inner cell content
    inner = [
        Spacer(1, COVER_PAD),
        Paragraph("ZAPPKO REVENUE AGENT", cover_tag),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.5, color=colors.HexColor("#3f3f46")),
        Spacer(1, 8 * mm),
        Paragraph("WEBSITE AUDIT REPORT", ParagraphStyle(
            "covh", fontName="Helvetica-Bold", fontSize=11,
            textColor=colors.HexColor("#a1a1aa"), alignment=TA_CENTER, leading=16,
        )),
        Spacer(1, 4 * mm),
        Paragraph(company, cover_big),
        Spacer(1, 2 * mm),
        Paragraph(website, cover_sub),
        Spacer(1, 10 * mm),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.3, color=colors.HexColor("#27272a")),
        Spacer(1, 8 * mm),
        # Score box
        Paragraph("WEBSITE HEALTH SCORE", ParagraphStyle(
            "scl", fontName="Helvetica-Bold", fontSize=8.5,
            textColor=colors.HexColor("#71717a"), alignment=TA_CENTER, leading=12,
        )),
        Spacer(1, 2 * mm),
        Paragraph(str(score), cover_score),
        Paragraph(score_label, cover_score_label),
        Spacer(1, 8 * mm),
        # Stats row
        Table(
            [[
                Paragraph(f"{len(issues)}<br/><font size='8' color='#71717a'>Issues Found</font>", ParagraphStyle(
                    "cs", fontName="Helvetica-Bold", fontSize=20, textColor=C_WHITE, alignment=TA_CENTER, leading=26,
                )),
                Paragraph(f"{deal}<br/><font size='8' color='#71717a'>Revenue Opportunity</font>", ParagraphStyle(
                    "cd", fontName="Helvetica-Bold", fontSize=20, textColor=C_GREEN, alignment=TA_CENTER, leading=26,
                )),
                Paragraph(f"{datetime.now(timezone.utc).strftime('%b %Y')}<br/><font size='8' color='#71717a'>Audit Date</font>", ParagraphStyle(
                    "ca", fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#a1a1aa"), alignment=TA_CENTER, leading=20,
                )),
            ]],
            colWidths=[(AVAIL_W - 2 * COVER_PAD) / 3] * 3,
        ),
        Spacer(1, 10 * mm),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.3, color=colors.HexColor("#27272a")),
        Spacer(1, 6 * mm),
        Paragraph(f"Audit ID: {audit_id}  ·  Prepared: {date_s}", cover_meta),
        Paragraph("Prepared exclusively by Zappko Revenue Agent · zappko.com", cover_meta),
        Spacer(1, COVER_PAD),
    ]

    # Wrap in full-bleed dark cover table
    cell = Table([[col] for col in inner], colWidths=[AVAIL_W])
    cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("LEFTPADDING",   (0, 0), (-1, -1), COVER_PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), COVER_PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    cover_table = Table([[cell]], colWidths=[AVAIL_W], rowHeights=[AVAIL_H])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    return [cover_table, PageBreak()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_audit_report(data: dict) -> bytes:
    """
    Generate a professional enhanced audit report PDF.

    Args:
        data: dict matching LeadResult model fields.

    Returns:
        Raw PDF bytes.
    """
    company = data.get("company", "")
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=f"Zappko Audit — {company}",
        author="Zappko Revenue Agent",
    )

    def make_header(canvas, doc):
        _interior_header(canvas, doc, company)

    st = _styles()
    story: list = []

    # Cover page (no header/footer)
    story.extend(_build_cover(data))

    # Interior sections
    story.extend(_build_meta_row(data, st))       # Contact Intelligence block
    story.extend(_build_executive_summary(data, st))
    story.extend(_build_score_section(data, st))
    story.extend(_build_issues_section(data, st))
    story.extend(_build_opportunities_section(data, st))
    story.extend(_build_services_section(data, st))
    story.extend(_build_roi_section(data, st))
    story.extend(_build_recommendation(data, st))
    story.extend(_build_next_steps(data, st))
    story.extend(_build_footer(st))

    doc.build(story, onFirstPage=make_header, onLaterPages=make_header)
    return buf.getvalue()


# Alias for backwards compatibility
create_audit_pdf = generate_audit_report
