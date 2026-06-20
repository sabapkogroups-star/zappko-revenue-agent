"""
Zappko Proposal PDF Generator.

Produces a multi-page professional sales proposal:
  Cover         — Full-content dark branded cover
  1. Executive Summary
  2. Problems Found
  3. Recommended Solutions
  4. Packages & Pricing  (Starter / Growth ⭐ / Premium)
  5. Timeline
  6. Next Steps
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
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

C_DARK      = colors.HexColor("#09090b")
C_DARK2     = colors.HexColor("#18181b")
C_DARK3     = colors.HexColor("#27272a")
C_BLUE      = colors.HexColor("#2563eb")
C_BLUE_L    = colors.HexColor("#3b82f6")
C_BLUE_BG   = colors.HexColor("#eff6ff")
C_BLUE_HDBG = colors.HexColor("#1d4ed8")
C_GREEN     = colors.HexColor("#10b981")
C_AMBER     = colors.HexColor("#f59e0b")
C_RED       = colors.HexColor("#ef4444")
C_VIOLET    = colors.HexColor("#7c3aed")
C_VIOLET_L  = colors.HexColor("#a78bfa")
C_SURF      = colors.HexColor("#f8fafc")
C_SURF2     = colors.HexColor("#f1f5f9")
C_BORDER    = colors.HexColor("#e2e8f0")
C_TEXT      = colors.HexColor("#1e293b")
C_MUTED     = colors.HexColor("#64748b")
C_WHITE     = colors.white

PAGE_W, PAGE_H = A4
MARGIN     = 18 * mm
CONTENT_W  = PAGE_W - 2 * MARGIN
CONTENT_H  = PAGE_H - 2 * MARGIN
# SimpleDocTemplate applies 6 pt padding inside its frame on every side,
# reducing the usable area. The cover table must fit within these bounds.
_FP        = 6
AVAIL_W    = CONTENT_W - 2 * _FP
AVAIL_H    = CONTENT_H - 2 * _FP

# ---------------------------------------------------------------------------
# Service knowledge base
# ---------------------------------------------------------------------------

_SERVICE_DELIVERABLES: dict[str, list[str]] = {
    "WhatsApp Automation":      ["WhatsApp Business API integration", "Live chat widget on all pages", "Automated responders & chatbot", "Lead capture via WhatsApp flow"],
    "Lead Generation System":   ["Smart contact forms with validation", "Lead magnet landing page", "Email capture & subscriber list", "CRM pipeline connection"],
    "Conversion Optimization":  ["CTA buttons redesigned & A/B tested", "Above-the-fold optimisation", "Trust signals & social proof placement", "Conversion funnel setup"],
    "Website Optimization":     ["Page speed (Core Web Vitals)", "Mobile & tablet responsiveness", "Image compression & lazy loading", "CDN & caching configuration"],
    "SEO Optimization":         ["Technical SEO audit & fixes", "Meta title & description rewrites", "Schema markup (JSON-LD)", "Google Search Console setup"],
    "CRM Setup":                ["CRM platform selection & configuration", "Lead tracking pipeline", "Automated email sequences", "Activity reporting dashboard"],
    "Contact Optimization":     ["Click-to-call & tap-to-email", "Phone/email prominence on every page", "Business hours & location display", "Google Maps integration"],
    "Social Media Integration": ["All social profile links added", "Social share buttons", "Review / testimonial feed", "Facebook Pixel & tracking"],
}

_ISSUE_IMPACT: dict[str, tuple[str, str]] = {
    "No WhatsApp Integration":      ("High",   "Missing 40-60% of mobile-first enquiries"),
    "No Contact Form":              ("High",   "30-40% of visitors leave without contacting"),
    "No Lead Capture Form":         ("High",   "Zero email leads — no follow-up pipeline possible"),
    "No CRM Integration":           ("High",   "Leads fall through the cracks without tracking"),
    "No Email Address Visible":     ("Medium", "Trust erosion — visitors can't verify legitimacy"),
    "No Phone Number Visible":      ("Medium", "Phone visibility lifts conversions 15-25%"),
    "Weak Call-to-Action":          ("Medium", "Poor CTAs reduce conversions by 20-30%"),
    "Slow Page Performance":        ("Medium", "Each 1-second delay reduces conversions by 7%"),
    "Missing Meta Title":           ("Medium", "Reduces organic search clicks significantly"),
    "Missing Meta Description":     ("Low",    "Click-through rate drops 10-20% without snippets"),
    "No Social Media Links":        ("Low",    "Reduces trust, retargeting, and brand awareness"),
    "Site Unreachable or Too Slow": ("High",   "Zero conversions — visitors cannot access the site"),
}

_IMPACT_C = {"High": C_RED, "Medium": C_AMBER, "Low": C_MUTED}

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def _pricing(deal_value: str) -> dict[str, str]:
    dv = deal_value
    if "AED" in dv:
        return {"s": "AED 2,999", "g": "AED 5,999", "p": "AED 9,999"}
    if "₹" in dv or "INR" in dv.upper():
        return {"s": "₹45,000", "g": "₹95,000", "p": "₹1,65,000"}
    if "SAR" in dv:
        return {"s": "SAR 3,499", "g": "SAR 7,499", "p": "SAR 12,499"}
    if "QAR" in dv:
        return {"s": "QAR 3,499", "g": "QAR 7,499", "p": "QAR 11,999"}
    return {"s": "$999", "g": "$2,499", "p": "$4,999"}


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _S(name: str, **kw) -> ParagraphStyle:
    defaults = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=C_TEXT)
    return ParagraphStyle(name, **{**defaults, **kw})


def _styles() -> dict[str, ParagraphStyle]:
    return {
        # Cover styles
        "cov_brand":   _S("cov_brand",  fontName="Helvetica-Bold", fontSize=9,  textColor=C_BLUE_L,  leading=12),
        "cov_pre":     _S("cov_pre",    fontName="Helvetica",      fontSize=10, textColor=colors.HexColor("#6b7280"), leading=14, alignment=TA_CENTER),
        "cov_title":   _S("cov_title",  fontName="Helvetica",      fontSize=14, textColor=colors.HexColor("#d1d5db"), leading=18, alignment=TA_CENTER, spaceAfter=2),
        "cov_big":     _S("cov_big",    fontName="Helvetica-Bold", fontSize=54, textColor=C_WHITE,    leading=60, alignment=TA_CENTER),
        "cov_company": _S("cov_company",fontName="Helvetica-Bold", fontSize=30, textColor=C_WHITE,    leading=36, alignment=TA_CENTER),
        "cov_domain":  _S("cov_domain", fontName="Helvetica",      fontSize=12, textColor=C_BLUE_L,   leading=16, alignment=TA_CENTER),
        "cov_meta":    _S("cov_meta",   fontName="Helvetica",      fontSize=9,  textColor=colors.HexColor("#6b7280"), leading=13, alignment=TA_CENTER),
        # Interior
        "section":     _S("section",    fontName="Helvetica-Bold", fontSize=11, textColor=C_BLUE,     leading=16, spaceBefore=4),
        "body":        _S("body",       fontSize=9.5, leading=14),
        "body_sm":     _S("body_sm",    fontSize=8.5, leading=13, textColor=C_MUTED),
        "label":       _S("label",      fontName="Helvetica-Bold", fontSize=8.5, textColor=C_MUTED, leading=12),
        "svc_name":    _S("svc_name",   fontName="Helvetica-Bold", fontSize=10,  textColor=C_BLUE, leading=14),
        "svc_del":     _S("svc_del",    fontSize=8.5, leading=12, textColor=C_TEXT),
        "pkg_hdr":     _S("pkg_hdr",    fontName="Helvetica-Bold", fontSize=10,  textColor=C_WHITE,   leading=14, alignment=TA_CENTER),
        "pkg_hdr_b":   _S("pkg_hdr_b",  fontName="Helvetica-Bold", fontSize=10,  textColor=C_WHITE,   leading=14, alignment=TA_CENTER),
        "pkg_feat":    _S("pkg_feat",   fontName="Helvetica-Bold", fontSize=8.5, textColor=C_MUTED,  leading=12),
        "pkg_val":     _S("pkg_val",    fontSize=8.5, leading=12, textColor=C_TEXT, alignment=TA_CENTER),
        "pkg_val_b":   _S("pkg_val_b",  fontName="Helvetica-Bold", fontSize=8.5, textColor=C_BLUE, leading=12, alignment=TA_CENTER),
        "pkg_price":   _S("pkg_price",  fontName="Helvetica-Bold", fontSize=15,  textColor=C_TEXT,   leading=18, alignment=TA_CENTER),
        "pkg_price_b": _S("pkg_price_b",fontName="Helvetica-Bold", fontSize=15,  textColor=C_BLUE,   leading=18, alignment=TA_CENTER),
        "tl_week":     _S("tl_week",    fontName="Helvetica-Bold", fontSize=9,   textColor=C_WHITE,  leading=12, alignment=TA_CENTER),
        "tl_phase":    _S("tl_phase",   fontName="Helvetica-Bold", fontSize=9,   textColor=C_TEXT,   leading=12),
        "tl_deliv":    _S("tl_deliv",   fontSize=8.5, leading=12, textColor=C_MUTED),
        "ns_step":     _S("ns_step",    fontName="Helvetica-Bold", fontSize=9.5, textColor=C_TEXT,   leading=14),
        "ns_body":     _S("ns_body",    fontSize=9,   leading=13, textColor=C_MUTED),
        "footer":      _S("footer",     fontSize=8,   leading=12, textColor=C_MUTED, alignment=TA_CENTER),
    }


def _hr(color: Any = C_BORDER, thick: float = 0.5) -> HRFlowable:
    return HRFlowable(width="100%", thickness=thick, color=color, spaceAfter=4, spaceBefore=4)


def _sp(h: float = 4) -> Spacer:
    return Spacer(1, h * mm)


def _check(yes: bool) -> str:
    return "✓" if yes else "—"


# ---------------------------------------------------------------------------
# Interior header (canvas callback)
# ---------------------------------------------------------------------------

def _draw_interior_header(canvas: Any, doc: Any, company: str) -> None:
    if doc.page < 2:
        return
    canvas.saveState()
    y = PAGE_H - MARGIN / 2
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(MARGIN, y, "ZAPPKO REVENUE AGENT")
    canvas.drawRightString(PAGE_W - MARGIN, y, f"{company.upper()} · PROPOSAL")
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.3)
    canvas.line(MARGIN, y - 6, PAGE_W - MARGIN, y - 6)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(PAGE_W / 2, MARGIN / 2, str(doc.page))
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def _build_cover(data: dict, styles: dict) -> list:
    company  = data.get("company", "Company")
    website  = data.get("website", "")
    domain   = website.replace("https://", "").replace("http://", "").rstrip("/")
    dm       = data.get("decisionMaker", "") or ""
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    month_id = datetime.now(timezone.utc).strftime("%Y%m")
    slug     = company[:6].upper().replace(" ", "")
    prop_id  = f"ZAP-{month_id}-{slug}"

    COVER_PAD = 14 * mm

    cell = [
        _sp(10),
        Paragraph("ZAPPKO REVENUE AGENT", styles["cov_brand"]),
        _sp(1),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.8, color=C_BLUE_L, spaceAfter=0),
        _sp(10),
        Paragraph("DIGITAL TRANSFORMATION", styles["cov_title"]),
        Paragraph("PROPOSAL", styles["cov_big"]),
        _sp(10),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.3, color=colors.HexColor("#374151"), spaceAfter=0),
        _sp(7),
        Paragraph("PREPARED EXCLUSIVELY FOR", styles["cov_pre"]),
        _sp(3),
        Paragraph(company.upper(), styles["cov_company"]),
        Paragraph(domain, styles["cov_domain"]),
    ]
    if dm:
        cell.extend([_sp(2), Paragraph(f"Attn: {dm}", styles["cov_meta"])])

    cell.extend([
        _sp(10),
        HRFlowable(width=AVAIL_W - 2 * COVER_PAD, thickness=0.3, color=colors.HexColor("#374151"), spaceAfter=0),
        _sp(5),
        Paragraph("BY: ZAID · FOUNDER, ZAPPKO", styles["cov_meta"]),
        _sp(2),
        Paragraph(f"Date: {date_str}   ·   Valid for 30 Days", styles["cov_meta"]),
        _sp(2),
        Paragraph(f"Proposal ID: {prop_id}", styles["cov_meta"]),
        _sp(8),
    ])

    cover_tbl = Table([[cell]], colWidths=[AVAIL_W], rowHeights=[AVAIL_H])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), COVER_PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), COVER_PAD),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    return [cover_tbl, PageBreak()]


# ---------------------------------------------------------------------------
# Executive Summary
# ---------------------------------------------------------------------------

def _build_exec_summary(data: dict, styles: dict) -> list:
    company   = data.get("company", "Company")
    score     = data.get("websiteScore", 0)
    opp       = data.get("opportunityScore", 0)
    issues    = data.get("issues", [])
    services  = data.get("recommendedService", [])
    deal      = data.get("dealValue", "")
    n         = len(issues)
    primary   = issues[0] if issues else "website gaps"

    quality = "good" if score >= 75 else "developing" if score >= 50 else "critically under-performing"

    summary = (
        f"This proposal outlines Zappko's recommended strategy to transform "
        f"<b>{company}'s</b> digital presence into a consistent lead generation engine. "
        f"Our automated audit scored your website <b>{score}/100</b>, indicating a {quality} "
        f"digital setup. We identified <b>{n} specific issues</b> — led by "
        f"<b>{primary}</b> — that are collectively costing your business an estimated "
        f"<b>{deal}</b> in uncontacted leads per month.<br/><br/>"
        f"The good news: every identified problem is fixable with proven Zappko systems. "
        f"Our recommended solutions ({', '.join(services[:3])}) are not full website rebuilds — "
        f"they are surgical, targeted implementations designed to deliver measurable results "
        f"within 30 days of launch."
    )

    # 3 key metrics row
    metrics = Table([
        [
            [Paragraph("WEBSITE SCORE", styles["label"]), Paragraph(f"{score}/100", _S("m1s", fontName="Helvetica-Bold", fontSize=22, textColor=C_RED if score < 50 else C_AMBER if score < 75 else C_GREEN, leading=28, alignment=TA_CENTER))],
            [Paragraph("OPPORTUNITY SCORE", styles["label"]), Paragraph(f"{opp}/100", _S("m2s", fontName="Helvetica-Bold", fontSize=22, textColor=C_GREEN if opp >= 75 else C_AMBER, leading=28, alignment=TA_CENTER))],
            [Paragraph("ISSUES FOUND", styles["label"]), Paragraph(str(n), _S("m3s", fontName="Helvetica-Bold", fontSize=22, textColor=C_RED, leading=28, alignment=TA_CENTER))],
        ]
    ], colWidths=[CONTENT_W / 3] * 3)
    metrics.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURF),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LINEAFTER",     (0, 0), (1, 0),   0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))

    return [
        Paragraph("1. EXECUTIVE SUMMARY", styles["section"]),
        _hr(), _sp(2),
        Paragraph(summary, styles["body"]),
        _sp(4),
        metrics,
        _sp(5),
    ]


# ---------------------------------------------------------------------------
# Problems Found
# ---------------------------------------------------------------------------

def _build_problems(data: dict, styles: dict) -> list:
    issues = data.get("issues", [])
    if not issues:
        return []

    rows = [[
        Paragraph("<b>Issue</b>", styles["body_sm"]),
        Paragraph("<b>Impact</b>", styles["body_sm"]),
        Paragraph("<b>Business Consequence</b>", styles["body_sm"]),
    ]]
    bgs = []
    for i, issue in enumerate(issues):
        impact, effect = _ISSUE_IMPACT.get(issue, ("Medium", "Potential revenue leakage"))
        ic = _IMPACT_C[impact]
        rows.append([
            Paragraph(issue, _S(f"ip{i}", fontSize=9, leading=13)),
            Paragraph(impact.upper(), _S(f"imp{i}", fontName="Helvetica-Bold", fontSize=8, textColor=ic, leading=12)),
            Paragraph(effect, styles["body_sm"]),
        ])
        bgs.append((i + 1, colors.HexColor("#fef2f2") if impact == "High" else colors.HexColor("#fffbeb") if impact == "Medium" else C_SURF))

    t = Table(rows, colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.14, CONTENT_W * 0.48])
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),   C_DARK2),
        ("TEXTCOLOR",     (0, 0), (-1, 0),   C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),   8),
        ("BOX",           (0, 0), (-1, -1),  0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1),  0.3, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1),  6),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  6),
        ("LEFTPADDING",   (0, 0), (-1, -1),  8),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
        ("VALIGN",        (0, 0), (-1, -1),  "TOP"),
    ]
    for row_i, bg in bgs:
        cmds.append(("BACKGROUND", (0, row_i), (-1, row_i), bg))
    t.setStyle(TableStyle(cmds))

    return [
        Paragraph("2. PROBLEMS FOUND", styles["section"]),
        _hr(), _sp(2), t, _sp(5),
    ]


# ---------------------------------------------------------------------------
# Recommended Solutions
# ---------------------------------------------------------------------------

def _build_solutions(data: dict, styles: dict) -> list:
    services = data.get("recommendedService", [])
    if not services:
        return []

    items: list = [
        Paragraph("3. RECOMMENDED SOLUTIONS", styles["section"]),
        _hr(), _sp(2),
    ]

    per_row = 2
    for i in range(0, len(services), per_row):
        chunk = services[i : i + per_row]
        cells = []
        for svc in chunk:
            delivs = _SERVICE_DELIVERABLES.get(svc, ["Custom implementation"])
            deliv_text = "<br/>".join(f"• {d}" for d in delivs)
            cells.append([
                Paragraph(f"✦  {svc}", styles["svc_name"]),
                Paragraph(deliv_text, styles["svc_del"]),
            ])
        while len(cells) < per_row:
            cells.append(["", ""])

        row_tbl = Table(
            [cells],
            colWidths=[CONTENT_W / per_row] * per_row,
        )
        row_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_SURF),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
            ("LINEAFTER",     (0, 0), (0, -1),  0.5, C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        items.append(row_tbl)
        items.append(_sp(2))

    items.append(_sp(3))
    return items


# ---------------------------------------------------------------------------
# Packages & Pricing
# ---------------------------------------------------------------------------

_PKG_FEATURES = [
    ("Included Services",   lambda s, g, p: (s, g, p)),
    ("Implementation",      lambda *_: ("Basic",         "Advanced",      "Full Suite")),
    ("Support Channel",     lambda *_: ("Email only",    "Priority Email", "Dedicated Line")),
    ("Revisions",           lambda *_: ("1 Round",       "2 Rounds",       "Unlimited")),
    ("Timeline",            lambda *_: ("2 Weeks",       "4 Weeks",        "6 Weeks")),
    ("Monthly Report",      lambda *_: ("—",             "✓",              "✓")),
    ("Strategy Call",       lambda *_: ("—",             "✓ Included",     "✓ Included")),
]


def _build_packages(data: dict, styles: dict) -> list:
    services = data.get("recommendedService", [])
    deal     = data.get("dealValue", "")
    prices   = _pricing(deal)
    n        = len(services)

    s_svcs = f"{min(2, n)} Core Service{'s' if min(2, n) != 1 else ''}"
    g_svcs = f"{n} Service{'s' if n != 1 else ''}"
    p_svcs = f"{n} Services + Analytics"

    feat_vals = [fn(s_svcs, g_svcs, p_svcs) for _, fn in _PKG_FEATURES]

    COL_W = [CONTENT_W * 0.28, CONTENT_W * 0.24, CONTENT_W * 0.25, CONTENT_W * 0.23]

    header_row = [
        Paragraph("", styles["pkg_hdr"]),
        Paragraph("STARTER", styles["pkg_hdr"]),
        Paragraph("GROWTH\n★ Recommended", styles["pkg_hdr_b"]),
        Paragraph("PREMIUM", styles["pkg_hdr"]),
    ]

    rows = [header_row]
    for (feat_name, _), (s_val, g_val, p_val) in zip(_PKG_FEATURES, feat_vals):
        rows.append([
            Paragraph(feat_name, styles["pkg_feat"]),
            Paragraph(s_val, styles["pkg_val"]),
            Paragraph(g_val, styles["pkg_val_b"] if "✓" in g_val else styles["pkg_val"]),
            Paragraph(p_val, styles["pkg_val"]),
        ])

    rows.append([
        Paragraph("PRICE", _S("pfeat", fontName="Helvetica-Bold", fontSize=9, textColor=C_MUTED, leading=12)),
        Paragraph(prices["s"], styles["pkg_price"]),
        Paragraph(prices["g"], styles["pkg_price_b"]),
        Paragraph(prices["p"], _S("pprem", fontName="Helvetica-Bold", fontSize=15, textColor=C_VIOLET, leading=18, alignment=TA_CENTER)),
    ])

    n_rows = len(rows)
    tbl = Table(rows, colWidths=COL_W)

    tbl_style = [
        # Header row
        ("BACKGROUND",    (0, 0), (0, 0),         C_DARK),
        ("BACKGROUND",    (1, 0), (1, 0),         C_DARK3),
        ("BACKGROUND",    (2, 0), (2, 0),         C_BLUE),
        ("BACKGROUND",    (3, 0), (3, 0),         colors.HexColor("#4c1d95")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),        C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),        "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),        9),
        # Feature column (col 0)
        ("BACKGROUND",    (0, 1), (0, -2),        C_SURF),
        # Starter column
        ("BACKGROUND",    (1, 1), (1, -2),        C_WHITE),
        # Growth column highlight
        ("BACKGROUND",    (2, 1), (2, -2),        C_BLUE_BG),
        # Premium column
        ("BACKGROUND",    (3, 1), (3, -2),        colors.HexColor("#f5f3ff")),
        # Price row
        ("BACKGROUND",    (0, -1), (-1, -1),      C_SURF),
        ("TOPPADDING",    (0, -1), (-1, -1),      12),
        ("BOTTOMPADDING", (0, -1), (-1, -1),      12),
        ("FONTNAME",      (0, -1), (-1, -1),      "Helvetica-Bold"),
        # Borders
        ("BOX",           (0, 0), (-1, -1),       1.0, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1),       0.3, C_BORDER),
        ("LINEBELOW",     (0, -2), (-1, -2),      1.0, C_BORDER),
        # Padding
        ("TOPPADDING",    (0, 0), (-1, -1),       7),
        ("BOTTOMPADDING", (0, 0), (-1, -1),       7),
        ("LEFTPADDING",   (0, 0), (-1, -1),       8),
        ("RIGHTPADDING",  (0, 0), (-1, -1),       8),
        ("VALIGN",        (0, 0), (-1, -1),       "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, 0),        10),
        ("BOTTOMPADDING", (0, 0), (-1, 0),        10),
    ]
    tbl.setStyle(TableStyle(tbl_style))

    note = (
        f"All packages include a 30-day launch guarantee. Pricing is one-time unless stated. "
        f"Monthly retainer options available on request."
    )

    return [
        Paragraph("4. PACKAGES & PRICING", styles["section"]),
        _hr(), _sp(2), tbl, _sp(3),
        Paragraph(note, styles["body_sm"]),
        _sp(4),
    ]


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

_TIMELINE_ROWS = [
    ("Week 1", "Discovery & Strategy",    "Audit review, goal alignment, scope finalisation, environment setup"),
    ("Week 2", "Core Implementation",      "Primary services deployed: WhatsApp, contact forms, CTA redesign"),
    ("Week 3", "Advanced Features",        "SEO fixes, page speed, secondary integrations, CRM setup"),
    ("Week 4", "Testing & Launch",         "QA testing, client review, 2 rounds of revisions, go-live, handover"),
]

_TIMELINE_PREMIUM = [
    ("Week 5", "Optimisation Cycle",       "Performance monitoring, conversion rate analysis, first A/B test"),
    ("Week 6", "Strategy & Handover",      "Analytics dashboard delivery, training session, 90-day roadmap call"),
]


def _build_timeline(data: dict, styles: dict) -> list:
    rows = [[
        Paragraph("<b>Period</b>", styles["body_sm"]),
        Paragraph("<b>Phase</b>", styles["body_sm"]),
        Paragraph("<b>Deliverables</b>", styles["body_sm"]),
    ]]

    for week, phase, delivs in _TIMELINE_ROWS:
        rows.append([
            Paragraph(week, styles["tl_week"]),
            Paragraph(phase, styles["tl_phase"]),
            Paragraph(delivs, styles["tl_deliv"]),
        ])

    tbl = Table(rows, colWidths=[CONTENT_W * 0.14, CONTENT_W * 0.30, CONTENT_W * 0.56])
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  C_SURF),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(rows)):
        bg = C_BLUE if (i % 2 == 1) else C_BLUE_BG
        cmds.append(("BACKGROUND", (0, i), (0, i), bg))
        cmds.append(("BACKGROUND", (1, i), (-1, i), C_WHITE if i % 2 == 0 else C_SURF))
    tbl.setStyle(TableStyle(cmds))

    premium_note = (
        "★  <b>Premium package</b> adds Weeks 5–6: Optimisation Cycle + Strategy Handover with 90-day roadmap call."
    )

    return [
        Paragraph("5. TIMELINE  (Growth Package — 4 Weeks)", styles["section"]),
        _hr(), _sp(2), tbl, _sp(3),
        Paragraph(premium_note, styles["body_sm"]),
        _sp(4),
    ]


# ---------------------------------------------------------------------------
# Next Steps
# ---------------------------------------------------------------------------

def _build_next_steps(data: dict, styles: dict) -> list:
    company  = data.get("company", "Company")
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    dm       = data.get("decisionMaker", "") or ""
    greeting = f"Hi {dm.split()[0]}," if dm else "Hi,"

    steps = [
        ("Step 1", "Select your package",         "Reply to this proposal with \"Starter\", \"Growth\", or \"Premium\""),
        ("Step 2", "Receive contract & invoice",   "We'll send the agreement and invoice within 24 hours"),
        ("Step 3", "Confirm your start date",      "50% deposit locks in your project slot"),
        ("Step 4", "Kickoff call",                 "Scheduled within 48 hours of deposit — we're ready to move fast"),
    ]

    step_rows = []
    for num, title, detail in steps:
        step_rows.append([
            Paragraph(num, _S("sn", fontName="Helvetica-Bold", fontSize=9, textColor=C_BLUE, leading=12, alignment=TA_CENTER)),
            [Paragraph(title, styles["ns_step"]), Paragraph(detail, styles["ns_body"])],
        ])

    step_tbl = Table(step_rows, colWidths=[CONTENT_W * 0.14, CONTENT_W * 0.86])
    step_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
        ("BACKGROUND",    (0, 0), (-1, -1), C_BLUE_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_BORDER),
    ]))

    closing = (
        f"{greeting}<br/><br/>"
        f"Thank you for the opportunity to present this proposal for <b>{company}</b>. "
        f"We're confident in our ability to deliver measurable results quickly — "
        f"and we're ready to start as soon as you are.<br/><br/>"
        f"<b>This proposal is valid for 30 days from {date_str}.</b><br/><br/>"
        f"Questions or ready to proceed?<br/>"
        f"<b>Zaid · Founder, Zappko</b><br/>"
        f"zaid@zappko.com · zappko.com"
    )

    close_tbl = Table([[Paragraph(closing, styles["body"])]], colWidths=[CONTENT_W])
    close_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURF),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))

    return [
        Paragraph("6. NEXT STEPS", styles["section"]),
        _hr(), _sp(2), step_tbl, _sp(4), close_tbl, _sp(5),
        _hr(),
        Paragraph(
            f"Zappko Revenue Agent  ·  zappko.com  ·  Proposal ID: ZAP-{datetime.now(timezone.utc).strftime('%Y%m')}-{company[:6].upper().replace(' ', '')}",
            styles["footer"],
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_proposal_pdf(data: dict) -> bytes:
    """
    Generate a professional multi-page proposal PDF from lead data.

    Args:
        data: dict matching LeadResult fields.

    Returns:
        Raw PDF bytes.
    """
    buf     = BytesIO()
    company = data.get("company", "")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=f"Zappko Proposal — {company}",
        author="Zappko Revenue Agent",
    )

    st    = _styles()
    story: list = []

    story.extend(_build_cover(data, st))
    story.extend(_build_exec_summary(data, st))
    story.extend(_build_problems(data, st))
    story.append(PageBreak())
    story.extend(_build_solutions(data, st))
    story.append(PageBreak())
    story.extend(_build_packages(data, st))
    story.append(PageBreak())
    story.extend(_build_timeline(data, st))
    story.extend(_build_next_steps(data, st))

    def _on_later(canvas: Any, doc: Any) -> None:
        _draw_interior_header(canvas, doc, company)

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=_on_later)
    return buf.getvalue()
