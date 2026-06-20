"""AI Sales Recommendations engine — purely deterministic, no LLM required."""

from datetime import datetime, timezone


def _parse_deal(dv: str) -> float:
    import re
    nums = re.findall(r"\d[\d,]*", dv.replace(",", ""))
    return float(nums[0]) if nums else 0.0


def _days_since(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return 0.0


def generate_recommendations(leads: list[dict]) -> dict:
    today = datetime.now(timezone.utc)
    recs: list[dict] = []

    new_leads       = [l for l in leads if l.get("status") == "new"]
    contacted_leads = [l for l in leads if l.get("status") == "contacted"]
    qualified_leads = [l for l in leads if l.get("status") == "qualified"]

    # 1. Hot leads sitting in "new" — highest urgency
    hot_new = sorted(
        [l for l in new_leads if l.get("hotLeadScore", 0) >= 60],
        key=lambda x: x.get("hotLeadScore", 0), reverse=True,
    )
    for lead in hot_new[:2]:
        recs.append({
            "priority":      "high",
            "action":        f"Contact {lead['company']} immediately",
            "company":       lead["company"],
            "reason":        f"Hot lead (score {lead.get('hotLeadScore', 0)}) with no outreach — highest chance of conversion",
            "expectedValue": lead.get("dealValue", "—"),
        })

    # 2. Overdue follow-ups
    due_leads = []
    for l in leads:
        nfd = l.get("nextFollowUpDate")
        if nfd:
            try:
                dt = datetime.fromisoformat(nfd.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt <= today:
                    due_leads.append(l)
            except Exception:
                pass
    for lead in due_leads[:2]:
        step = (lead.get("followUpCount") or 0) + 1
        recs.append({
            "priority":      "high",
            "action":        f"Send follow-up #{step} to {lead['company']}",
            "company":       lead["company"],
            "reason":        "Follow-up is overdue — each day of delay reduces reply rate by ~5%",
            "expectedValue": lead.get("dealValue", "—"),
        })

    # 3. Qualified leads — ready for proposal / close
    for lead in qualified_leads[:2]:
        if lead.get("opportunityScore", 0) >= 50:
            recs.append({
                "priority":      "medium",
                "action":        f"Generate proposal for {lead['company']}",
                "company":       lead["company"],
                "reason":        f"Qualified with {lead.get('opportunityScore', 0)} opportunity score — send proposal to close",
                "expectedValue": lead.get("dealValue", "—"),
            })

    # 4. Stale "contacted" leads (no activity > 7 days)
    stale: list[tuple[dict, float]] = []
    for lead in contacted_leads:
        last = lead.get("lastContactDate") or lead.get("savedAt", "")
        if last:
            days = _days_since(last)
            if days >= 7:
                stale.append((lead, days))
    stale.sort(key=lambda x: x[1], reverse=True)
    for lead, days in stale[:2]:
        if not any(r["company"] == lead["company"] for r in recs):
            recs.append({
                "priority":      "medium",
                "action":        f"Re-engage {lead['company']} — {int(days)}d since contact",
                "company":       lead["company"],
                "reason":        f"Lead going cold — {int(days)} days without follow-up",
                "expectedValue": lead.get("dealValue", "—"),
            })

    # 5. High-value new leads not yet contacted
    high_value_new = sorted(
        [l for l in new_leads if _parse_deal(l.get("dealValue", "0")) >= 1000],
        key=lambda x: _parse_deal(x.get("dealValue", "0")), reverse=True,
    )
    for lead in high_value_new[:2]:
        if not any(r["company"] == lead["company"] for r in recs):
            recs.append({
                "priority":      "low",
                "action":        f"Prepare audit report for {lead['company']}",
                "company":       lead["company"],
                "reason":        f"High-value deal ({lead.get('dealValue')}) — strengthen pitch with PDF audit",
                "expectedValue": lead.get("dealValue", "—"),
            })

    # Deduplicate by company, sort by priority, cap at 6
    seen: set[str] = set()
    unique: list[dict] = []
    for r in recs:
        if r["company"] not in seen:
            seen.add(r["company"])
            unique.append(r)
    order = {"high": 0, "medium": 1, "low": 2}
    unique.sort(key=lambda x: order.get(x["priority"], 3))
    final_recs = unique[:6]

    # Pipeline health
    total = len(leads)
    if total == 0:
        health = {"score": 0, "label": "Empty", "staleLeads": 0, "dueFollowUps": len(due_leads), "hotLeads": 0}
    else:
        hot_count = sum(1 for l in leads if l.get("hotLeadScore", 0) >= 60)
        active = sum(1 for l in leads if l.get("status") in ("contacted", "qualified", "closed"))
        stale_count = len(stale)

        active_rate   = (active / total) * 40
        hot_rate      = min(1.0, hot_count / total) * 30
        stale_penalty = min(30, stale_count * 5)
        score = min(100, int(active_rate + hot_rate + (30 - stale_penalty)))

        label = "Healthy" if score >= 70 else "At Risk" if score >= 40 else "Critical"
        health = {
            "score":       score,
            "label":       label,
            "staleLeads":  stale_count,
            "dueFollowUps": len(due_leads),
            "hotLeads":    hot_count,
        }

    return {"recommendations": final_recs, "pipelineHealth": health}
