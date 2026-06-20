"""
Zappko Audit PDF Generator.

Produces a professional A4 PDF report from a lead audit result.

Sections:
  1. Executive Summary
  2. Website Score
  3. Issues Found
  4. Revenue Opportunities
  5. Recommended Services
  6. Estimated ROI
  7. Zappko Recommendation
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------

C_DARK       = colors.HexColor("#09090b")
C_DARK2      = colors.HexColor("#18181b")
C_BLUE       = colors.HexColor("#2563eb")
C_BLUE_LIGHT = colors.HexColor("#3b82f6")
C_GREEN      = colors.HexColor("#10b981")
C_AMBER      = colors.HexColor("#f59e0b")
C_RED        = colors.HexColor("#ef4444")
C_SURFACE    = colors.HexColor("#f8fafc")
C_BORDER     = colors.HexColor("#e2e8f0")
C_TEXT       = colors.HexColor("#1e293b")
C_MUTED      = colors.HexColor("#64748b")
C_WHITE      = colors.white
C_LIGHT_BLUE = colors.HexColor("#eff6ff")
C_LIGHT_RED  = colors.HexColor("#fef2f2")
C_LIGHT_AMB  = colors.HexColor("#fffbeb")

# ---------------------------------------------------------------------------
# Issue metadata
# ---------------------------------------------------------------------------

_ISSUE_META: dict[str, tuple[str, str]] = {
    "No WhatsApp Integration":     ("High",   "40-60% of mobile leads go uncontacted"),
    "No Contact Form":             ("High",   "30-40% of visitors leave without enquiring"),
    "No Lead Capture Form":        ("High",   "Zero email subscribers = zero follow-up pipeline"),
    "No CRM Integration":          ("High",   "Leads fall through the cracks without tracking"),
    "No Email Address Visible":    ("Medium", "Trust drops — visitors can't verify legitimacy"),
    "No Phone Number Visible":     ("Medium", "Phone visibility lifts conversions 15-25%"),
    "Weak Call-to-Action":         ("Medium", "Weak CTAs reduce conversions by 20-30%"),
    "Slow Page Performance":       ("Medium", "Each 1s delay reduces conversions by 7%"),
    "Missing Meta Title":          ("Medium", "Poor SEO title cuts organic search clicks"),
    "Missing Meta Description":    ("Low",    "Missing snippet reduces click-through by 10-20%"),
    "No Social Media Links":       ("Low",    "Social proof builds brand trust and retargeting"),
    "Site Unreachable or Too Slow":("High",   "Unreachable site converts zero visitors"),
}

_OPPORTUNITY_TEXT: dict[str, str] = {
    "WhatsApp Automation":
        "Install a WhatsApp chat widget to capture mobile-first enquiries 24/7. "
        "Typical result: 40% more leads contacted within 30 days.",
    "Lead Generation System":
        "Add smart contact forms and lead magnets so visitors leave their details "
        "before exiting. Typical result: 2–3× more captured leads per month.",
    "CRM Setup":
        "Connect a CRM to track, nurture and close every lead systematically. "
        "Stop losing deals to manual follow-up gaps.",
    "Conversion Optimization":
        "Redesign calls-to-action to guide visitors toward booking or buying. "
        "Typical result: 20–35% more conversions from the same traffic.",
    "Website Optimization":
        "Fix page speed, mobile performance and Core Web Vitals. "
        "Fast sites rank higher on Google and convert significantly better.",
    "SEO Optimization":
        "Fix technical SEO gaps — title tags, meta descriptions, structured data — "
        "to improve ranking and drive sustainable organic traffic.",
    "Contact Optimization":
        "Display phone and email prominently to reduce friction and immediately "
        "signal to prospects that you're easy to reach.",
    "Social Media Integration":
        "Add social profile links to build credibility, enable retargeting ads "
        "and grow your audience without extra ad spend.",
}

_IMPACT_COLOR = {
    "High":   C_RED,
    "Medium": C_AMBER,
    "Low":    C_MUTED,
}

# ---------------------------------------------------------------------------
# Style factory
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _styles() -> dict[str, ParagraphStyle]:
    base = dict(
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=C_TEXT,
    )

    def S(name: str, **kw) -> ParagraphStyle:
        merged = {**base, **kw}
        return ParagraphStyle(name, **merged)

    return {
        "h_company": S("h_company", fontName="Helvetica-Bold", fontSize=18,
                        textColor=C_WHITE, leading=22),
        "h_sub":     S("h_sub",     fontName="Helvetica",      fontSize=10,
                        textColor=colors.HexColor("#94a3b8"), leading=14),
        "section":   S("section",   fontName="Helvetica-Bold", fontSize=11,
                        textColor=C_BLUE, leading=16, spaceBefore=4),
        "body":      S("body",      fontSize=9.5, leading=14, textColor=C_TEXT),
        "body_sm":   S("body_sm",   fontSize=8.5, leading=13, textColor=C_MUTED),
        "score_big": S("score_big", fontName="Helvetica-Bold", fontSize=48,
                        textColor=C_TEXT, alignment=TA_CENTER, leading=56),
        "score_lbl": S("score_lbl", fontName="Helvetica-Bold", fontSize=11,
                        alignment=TA_CENTER, leading=16),
        "issue_txt": S("issue_txt", fontSize=9, leading=13, textColor=C_TEXT),
        "impact_hi": S("impact_hi", fontName="Helvetica-Bold", fontSize=8,
                        textColor=C_RED,   leading=11),
        "impact_md": S("impact_md", fontName="Helvetica-Bold", fontSize=8,
                        textColor=C_AMBER, leading=11),
        "impact_lo": S("impact_lo", fontName="Helvetica-Bold", fontSize=8,
                        textColor=C_MUTED, leading=11),
        "opp_title": S("opp_title", fontName="Helvetica-Bold", fontSize=9.5,
                        textColor=C_BLUE,  leading=13),
        "opp_body":  S("opp_body",  fontSize=8.5, leading=13, textColor=C_MUTED),
        "svc":       S("svc",       fontName="Helvetica-Bold", fontSize=9.5,
                        textColor=C_TEXT, leading=14),
        "rec_body":  S("rec_body",  fontSize=9.5, leading=15, textColor=C_TEXT),
        "footer":    S("footer",    fontSize=8, textColor=C_MUTED,
                        alignment=TA_CENTER, leading=12),
        "meta_key":  S("meta_key",  fontName="Helvetica-Bold", fontSize=9,
                        textColor=C_MUTED, leading=13),
        "meta_val":  S("meta_val",  fontSize=9, textColor=C_TEXT, leading=13),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(color: Any = C_BORDER, thickness: float = 0.5) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=thickness, color=color,
        spaceAfter=4, spaceBefore=4,
    )


def _sp(h: float = 4) -> Spacer:
    return Spacer(1, h * mm)


def _score_color(score: int) -> Any:
    return C_GREEN if score >= 75 else C_AMBER if score >= 50 else C_RED


def _score_label(score: int) -> str:
    return "Good Performance" if score >= 75 else (
        "Needs Improvement" if score >= 50 else "Critical — Urgent Action Required"
    )


def _score_bar(score: int, width: float = CONTENT_W) -> Table:
    """Renders a colour-filled progress bar using a two-column table."""
    fill = max(4, int(width * score / 100))
    empty = int(width) - fill
    t = Table([["", ""]], colWidths=[fill, empty], rowHeights=[10])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), _score_color(score)),
        ("BACKGROUND",    (1, 0), (1, 0), C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return t


def _impact_style(impact: str, styles: dict) -> ParagraphStyle:
    return styles.get(f"impact_{impact[0].lower()}") or styles["impact_lo"]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(data: dict, styles: dict) -> list:
    """Dark full-width header band with company name and report title."""
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    company  = data.get("company", "Company")
    website  = data.get("website", "")
    domain   = website.replace("https://", "").replace("http://", "").rstrip("/")

    # Two-column header table: company left, report info right
    left  = [
        Paragraph("ZAPPKO REVENUE AGENT", ParagraphStyle(
            "brand", fontName="Helvetica-Bold", fontSize=8,
            textColor=colors.HexColor("#60a5fa"), leading=11)),
        Paragraph(company, styles["h_company"]),
        Paragraph(domain,  styles["h_sub"]),
    ]
    right_text = ParagraphStyle(
        "hdr_r", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#94a3b8"), alignment=TA_RIGHT, leading=14,
    )
    right = [
        Paragraph("Website Audit Report", ParagraphStyle(
            "hdr_rt", fontName="Helvetica-Bold", fontSize=11,
            textColor=C_WHITE, alignment=TA_RIGHT, leading=16)),
        Paragraph(f"Generated {date_str}", right_text),
        Paragraph("Confidential", right_text),
    ]

    hdr_table = Table(
        [[left, right]],
        colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4],
    )
    hdr_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING",   (0, 0), (0, 0),   14),
        ("RIGHTPADDING",  (-1, 0), (-1, 0), 14),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [hdr_table, _sp(4)]


def _build_meta_row(data: dict, styles: dict) -> list:
    """Single-row table with decision maker, email, phone metadata."""
    dm    = data.get("decisionMaker", "") or "—"
    title = data.get("title", "")
    email = data.get("email", "") or "—"
    phone = data.get("phone", "") or "—"
    dm_label = f"{dm} · {title}" if title else dm

    cells = [
        [Paragraph("DECISION MAKER", styles["meta_key"]),
         Paragraph(dm_label, styles["meta_val"])],
        [Paragraph("EMAIL", styles["meta_key"]),
         Paragraph(email, styles["meta_val"])],
        [Paragraph("PHONE", styles["meta_key"]),
         Paragraph(phone, styles["meta_val"])],
    ]
    col_w = CONTENT_W / 3
    t = Table(cells, colWidths=[col_w] * 3)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, _sp(5)]


def _build_executive_summary(data: dict, styles: dict) -> list:
    company = data.get("company", "this company")
    score   = data.get("websiteScore", 0)
    issues  = data.get("issues", [])
    deal    = data.get("dealValue", "")
    n       = len(issues)
    primary = issues[0] if issues else "website optimisation opportunities"

    summary = (
        f"Our automated audit of <b>{company}</b> identified <b>{n} specific issues</b> "
        f"affecting lead generation and revenue. The website scored <b>{score}/100</b>, "
        f"indicating {_score_label(score).lower().replace(' — urgent action required', '')}. "
        f"The most impactful problem is <b>{primary}</b>, which alone typically costs businesses "
        f"30–40% of potential enquiries. With targeted Zappko interventions, we project an "
        f"additional <b>{deal}</b> in recovered monthly revenue within 30–60 days."
    )
    return [
        Paragraph("1. EXECUTIVE SUMMARY", styles["section"]),
        _hr(),
        _sp(1),
        Paragraph(summary, styles["body"]),
        _sp(5),
    ]


def _build_score_section(data: dict, styles: dict) -> list:
    score = data.get("websiteScore", 0)
    opp   = data.get("opportunityScore", 0)
    hot   = data.get("hotLeadScore", 0)
    label = _score_label(score)
    clr   = _score_color(score)

    score_para = Paragraph(str(score), ParagraphStyle(
        "score_num", fontName="Helvetica-Bold", fontSize=52,
        textColor=clr, alignment=TA_CENTER, leading=60,
    ))
    label_para = Paragraph(
        f"<font color='#{clr.hexval()[2:]}'>■</font>  {label}",
        ParagraphStyle("score_lbl2", fontName="Helvetica-Bold", fontSize=10,
                       alignment=TA_CENTER, textColor=C_TEXT, leading=14),
    )

    score_col = [score_para, Paragraph("/100", ParagraphStyle(
        "slash", fontSize=10, textColor=C_MUTED, alignment=TA_CENTER, leading=12)),
        _sp(1), label_para, _sp(2), _score_bar(score, CONTENT_W * 0.35)]

    def _mini(label: str, val: int, c: Any) -> list:
        return [
            Paragraph(label, ParagraphStyle(
                "ml", fontSize=8, textColor=C_MUTED, alignment=TA_CENTER, leading=11)),
            Paragraph(str(val), ParagraphStyle(
                "mv", fontName="Helvetica-Bold", fontSize=28, textColor=c,
                alignment=TA_CENTER, leading=34)),
            _score_bar(val, CONTENT_W * 0.25),
        ]

    opp_col = _mini("OPPORTUNITY SCORE", opp,
                    C_GREEN if opp >= 75 else C_AMBER if opp >= 50 else C_RED)
    hot_col = _mini("HOT LEAD SCORE", hot,
                    C_RED if hot >= 70 else C_AMBER if hot >= 50 else C_BLUE_LIGHT)

    row = Table([[score_col, opp_col, hot_col]],
                colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.31, CONTENT_W * 0.31])
    row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LINEAFTER",     (0, 0), (1, 0),   0.5, C_BORDER),
    ]))

    return [
        Paragraph("2. WEBSITE SCORE", styles["section"]),
        _hr(), _sp(2), row, _sp(5),
    ]


def _build_issues_section(data: dict, styles: dict) -> list:
    issues = data.get("issues", [])
    if not issues:
        return []

    rows = [
        [
            Paragraph("<b>Issue</b>", styles["body_sm"]),
            Paragraph("<b>Impact</b>", styles["body_sm"]),
            Paragraph("<b>Business Effect</b>", styles["body_sm"]),
        ]
    ]
    bg_colors = []

    for i, issue in enumerate(issues):
        impact, effect = _ISSUE_META.get(issue, ("Medium", "Potential revenue leakage"))
        impact_st = _impact_style(impact, styles)
        rows.append([
            Paragraph(issue, styles["issue_txt"]),
            Paragraph(impact.upper(), impact_st),
            Paragraph(effect, styles["body_sm"]),
        ])
        bg = C_LIGHT_RED if impact == "High" else C_LIGHT_AMB if impact == "Medium" else C_SURFACE
        bg_colors.append((i + 1, bg))

    col_w = [CONTENT_W * 0.38, CONTENT_W * 0.13, CONTENT_W * 0.49]
    t = Table(rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),   C_DARK2),
        ("TEXTCOLOR",     (0, 0), (-1, 0),   C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),   8),
        ("TOPPADDING",    (0, 0), (-1, -1),  6),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  6),
        ("LEFTPADDING",   (0, 0), (-1, -1),  8),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
        ("BOX",           (0, 0), (-1, -1),  0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1),  0.4, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1),  "TOP"),
    ]
    for row_i, bg in bg_colors:
        style_cmds.append(("BACKGROUND", (0, row_i), (-1, row_i), bg))

    t.setStyle(TableStyle(style_cmds))
    return [
        Paragraph("3. ISSUES FOUND", styles["section"]),
        _hr(), _sp(2), t, _sp(5),
    ]


def _build_opportunities_section(data: dict, styles: dict) -> list:
    services = data.get("recommendedService", [])
    if not services:
        return []

    items = []
    for svc in services:
        text = _OPPORTUNITY_TEXT.get(svc, f"Address {svc} to improve lead conversion.")
        items.append(
            Table(
                [[Paragraph(f"✦  {svc}", styles["opp_title"]),
                  Paragraph(text, styles["opp_body"])]],
                colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.70],
            )
        )
        items[-1].setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        items.append(_hr(C_BORDER, 0.3))

    return [
        Paragraph("4. REVENUE OPPORTUNITIES", styles["section"]),
        _hr(), _sp(2),
        *items,
        _sp(3),
    ]


def _build_services_section(data: dict, styles: dict) -> list:
    services = data.get("recommendedService", [])
    if not services:
        return []

    rows = [[Paragraph(f"✦  {svc}", styles["svc"])] for svc in services]
    # Split into two columns if >3 services
    if len(services) > 3:
        mid = (len(services) + 1) // 2
        left_rows  = [[Paragraph(f"✦  {s}", styles["svc"])] for s in services[:mid]]
        right_rows = [[Paragraph(f"✦  {s}", styles["svc"])] for s in services[mid:]]
        # Pad to equal length
        while len(right_rows) < len(left_rows):
            right_rows.append([Paragraph("", styles["svc"])])
        combined = [[l[0], r[0]] for l, r in zip(left_rows, right_rows)]
        t = Table(combined, colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    else:
        t = Table(rows, colWidths=[CONTENT_W])

    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    return [
        Paragraph("5. RECOMMENDED SERVICES", styles["section"]),
        _hr(), _sp(2), t, _sp(5),
    ]


def _build_roi_section(data: dict, styles: dict) -> list:
    deal   = data.get("dealValue", "—")
    issues = data.get("issues", [])
    n      = len(issues)

    timeline = "30 days" if n >= 5 else "45–60 days"
    uplift   = "2–3×"   if n >= 4 else "1.5–2×"

    rows = [
        ["Potential Revenue Uplift",  deal],
        ["Expected Lead Increase",    uplift],
        ["Implementation Timeline",   timeline],
        ["Issues to Resolve",         f"{n} identified gaps"],
    ]

    t = Table(rows, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5])
    style_cmds = [
        ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
        ("FONTNAME",      (1, 0), (1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (1, 0), (1, 0),   12),
        ("TEXTCOLOR",     (1, 0), (1, 0),   C_GREEN),
        ("TEXTCOLOR",     (0, 0), (0, -1),  C_MUTED),
        ("TEXTCOLOR",     (1, 1), (1, -1),  C_TEXT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#f0fdf4")),
    ]
    t.setStyle(TableStyle(style_cmds))

    return [
        Paragraph("6. ESTIMATED ROI", styles["section"]),
        _hr(), _sp(2), t, _sp(5),
    ]


def _build_recommendation(data: dict, styles: dict) -> list:
    company  = data.get("company", "your business")
    issues   = data.get("issues", [])
    services = data.get("recommendedService", [])
    dm       = data.get("decisionMaker", "")
    deal     = data.get("dealValue", "")

    greeting = f"Hi {dm.split()[0]}," if dm else "Hi,"
    primary  = issues[0] if issues else "your website gaps"
    svc_list = ", ".join(services[:3]) if services else "digital automation"

    text = (
        f"<b>{greeting}</b><br/><br/>"
        f"Based on our analysis, <b>{company}</b> has a clear, addressable revenue gap. "
        f"The <b>{primary}</b> alone is costing you enquiries every single day. "
        f"Combined with the other {len(issues) - 1} issues we identified, you're likely "
        f"leaving <b>{deal}</b> per month on the table — without even changing your traffic.<br/><br/>"
        f"At Zappko, we fix exactly these issues — specifically <b>{svc_list}</b> — "
        f"for businesses like yours. We don't rebuild websites from scratch. "
        f"We surgically implement the systems that convert existing visitors into paying clients.<br/><br/>"
        f"I'd love to walk you through a 15-minute plan for <b>{company}</b> specifically. "
        f"No pitch — just a clear breakdown of what we'd do, what it costs, and what you'd get back.<br/><br/>"
        f"<b>Zaid · Founder, Zappko · zappko.com</b>"
    )

    box = Table([[Paragraph(text, styles["rec_body"])]],
                colWidths=[CONTENT_W])
    box.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT_BLUE),
        ("BOX",           (0, 0), (-1, -1), 1.0, C_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))

    return [
        Paragraph("7. ZAPPKO RECOMMENDATION", styles["section"]),
        _hr(), _sp(2), box, _sp(5),
    ]


def _build_next_steps(data: dict, styles: dict) -> list:
    """Section 8 — Next Steps: concrete action items for the prospect."""
    company = data.get("company", "your business")
    dm      = data.get("decisionMaker", "")
    first   = dm.split()[0] if dm else "there"

    header_style = ParagraphStyle(
        "ns_hdr", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=C_TEXT, leading=14,
    )
    sub_style = ParagraphStyle(
        "ns_sub", fontSize=9, textColor=C_MUTED, leading=13,
        leftIndent=12,
    )
    cta_style = ParagraphStyle(
        "ns_cta", fontName="Helvetica-Bold", fontSize=10,
        textColor=C_BLUE, leading=15,
    )
    contact_style = ParagraphStyle(
        "ns_contact", fontSize=9, textColor=C_TEXT, leading=13,
    )

    step_rows = [
        (
            "Step 1 — Book a 15-Minute Discovery Call",
            [
                f"Hi {first} — no pitch, no pressure.",
                "We'll walk through what we found, what we'd fix, and what it would cost.",
                "Agenda: your goals → our findings → a clear implementation plan.",
            ],
        ),
        (
            "Step 2 — Receive a Custom Proposal (48 hrs)",
            [
                f"Tailored exclusively to {company}.",
                "Fixed pricing, no surprises. ROI projections based on your traffic.",
                "Includes a full implementation timeline and deliverable list.",
            ],
        ),
        (
            "Step 3 — Implementation Starts Within 5 Days",
            [
                "Typical project launch: within 5 business days of proposal acceptance.",
                "Weekly progress updates — you'll always know where things stand.",
                "Results tracked against agreed KPIs with a 30-day review call.",
            ],
        ),
    ]

    items: list = []
    for i, (title, bullets) in enumerate(step_rows, 1):
        row_content = [Paragraph(title, header_style)]
        for b in bullets:
            row_content.append(Paragraph(f"→  {b}", sub_style))
        row_content.append(_sp(1))

        step_table = Table([[row_content]], colWidths=[CONTENT_W])
        bg = C_LIGHT_BLUE if i == 1 else C_SURFACE
        step_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BLUE if i == 1 else C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))
        items.append(step_table)
        items.append(_sp(2))

    # Contact block
    contact_rows = [
        ["Email",    "zaid@zappko.com"],
        ["WhatsApp", "+971 XX XXX XXXX"],
        ["Website",  "zappko.com"],
    ]
    contact_table = Table(contact_rows, colWidths=[CONTENT_W * 0.2, CONTENT_W * 0.8])
    contact_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",     (0, 0), (0, -1), C_MUTED),
        ("TEXTCOLOR",     (1, 0), (1, -1), C_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_BORDER),
    ]))

    return [
        Paragraph("8. NEXT STEPS", styles["section"]),
        _hr(), _sp(2),
        *items,
        Paragraph("CONTACT ZAPPKO", ParagraphStyle(
            "ns_cl", fontName="Helvetica-Bold", fontSize=8.5,
            textColor=C_MUTED, leading=13, spaceBefore=4,
        )),
        _sp(1),
        contact_table,
        _sp(4),
    ]


def _build_footer(styles: dict) -> list:
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return [
        _hr(C_BORDER, 0.5),
        _sp(2),
        Paragraph(
            f"Zappko Revenue Agent  ·  zappko.com  ·  Generated {date_str}<br/>"
            f"This report is confidential and prepared exclusively for the recipient company.",
            styles["footer"],
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_audit_pdf(data: dict) -> bytes:
    """
    Generate a professional A4 audit PDF from lead data.

    Args:
        data: dict matching LeadResult fields.

    Returns:
        Raw PDF bytes, ready to stream to the client.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=f"Zappko Audit — {data.get('company', '')}",
        author="Zappko Revenue Agent",
    )

    st = _styles()
    story: list = []

    story.extend(_build_header(data, st))
    story.extend(_build_meta_row(data, st))
    story.extend(_build_executive_summary(data, st))
    story.extend(_build_score_section(data, st))
    story.extend(_build_issues_section(data, st))
    story.extend(_build_opportunities_section(data, st))
    story.extend(_build_services_section(data, st))
    story.extend(_build_roi_section(data, st))
    story.extend(_build_recommendation(data, st))
    story.extend(_build_footer(st))

    doc.build(story)
    return buf.getvalue()
