"""
services/insights_rules.py
A rules-based insights engine.

Given parsed dashboard data and a config dict of thresholds, returns a list of
Finding objects with (severity, category, message). Severity is one of:
  'critical' (red), 'warning' (yellow), 'positive' (green), 'neutral' (gray).

The engine is intentionally simple and auditable — every finding traces to one
specific rule + threshold from the config file. No model calls, no surprises.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json


# ──────────────────────────────────────────────────────────────────────────────
# Public types
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Finding:
    severity: str       # 'critical' | 'warning' | 'positive' | 'neutral'
    rule_id:  str       # e.g. 'noi_variance' — matches the JSON key
    label:    str       # short user-facing label, from config
    message:  str       # the sentence that goes into the narrative

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "rule_id":  self.rule_id,
            "label":    self.label,
            "message":  self.message,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Config loading
# ──────────────────────────────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent.parent / "data" / "insights_config.json"


def load_config(path: Path | str | None = None) -> dict:
    p = Path(path) if path else _CONFIG_PATH
    if not p.exists():
        return {"financials": {}, "rent_roll": {}}
    try:
        with open(p, "r") as f:
            return json.load(f)
    except Exception:
        return {"financials": {}, "rent_roll": {}}


def save_config(cfg: dict, path: Path | str | None = None) -> None:
    p = Path(path) if path else _CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v*100:+.1f}%" if abs(v) < 10 else f"{v*100:+.0f}%"


def _fmt_dollar(v) -> str:
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    n = abs(v)
    if n >= 1_000_000:
        return f"{sign}${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{sign}${n/1_000:.0f}k"
    return f"{sign}${n:.0f}"


def _signed_dollar(v) -> str:
    """Always include explicit sign for variance values."""
    if v is None:
        return "—"
    return ("+" if v >= 0 else "") + _fmt_dollar(v)


def _classify_pct(abs_pct: float, rule: dict, *, is_favorable: bool) -> str:
    """
    Bucket a magnitude (|variance %|) using warn/critical thresholds.
    `is_favorable` flips the meaning: a 'positive' classification means
    favorable direction (no warning at all).
    """
    crit = rule.get("critical_threshold_pct", 999)
    warn = rule.get("warn_threshold_pct", 999)
    if abs_pct >= crit:
        return "positive" if is_favorable else "critical"
    if abs_pct >= warn:
        return "positive" if is_favorable else "warning"
    return "neutral"


# ──────────────────────────────────────────────────────────────────────────────
# Financials rules
# ──────────────────────────────────────────────────────────────────────────────
def evaluate_financials(t12_data: dict | None,
                        budget_data: dict | None,
                        config: dict) -> list[Finding]:
    """Run all financials rules and return ordered findings."""
    findings: list[Finding] = []
    if not t12_data:
        return findings

    rules = config.get("financials", {})
    s = t12_data.get("summary") or {}

    actual_rev = s.get("total_revenue_t12") or 0
    actual_exp = s.get("total_expenses_t12") or 0
    actual_noi = s.get("noi_t12") or 0
    margin     = s.get("noi_margin_t12")  # fraction, e.g. 0.55

    # ── NOI Margin (always runs, no budget needed) ────────────────────────
    r = rules.get("noi_margin", {})
    if r.get("enabled") and margin is not None:
        m_pct = margin * 100
        crit = r.get("critical_below_pct", 0)
        warn = r.get("warn_below_pct", 0)
        if m_pct < crit:
            findings.append(Finding(
                "critical", "noi_margin", r.get("label", "NOI Margin"),
                f"NOI margin is {m_pct:.1f}%, below the critical threshold of {crit:.0f}%."
            ))
        elif m_pct < warn:
            findings.append(Finding(
                "warning", "noi_margin", r.get("label", "NOI Margin"),
                f"NOI margin of {m_pct:.1f}% is below the {warn:.0f}% comfort threshold."
            ))
        else:
            findings.append(Finding(
                "positive", "noi_margin", r.get("label", "NOI Margin"),
                f"NOI margin is healthy at {m_pct:.1f}%."
            ))

    # ── T3 annualized vs T12 trend ────────────────────────────────────────
    # Note: the T12 template stores T3/T6 as already-annualised equivalents
    # (the same row's T12/T6/T3/T1 columns all express the same units), so we
    # compare them directly without re-multiplying.
    r = rules.get("t3_vs_t12_trend", {})
    if r.get("enabled"):
        rev_t3 = s.get("total_revenue_t3")
        if rev_t3 is not None and actual_rev:
            delta    = (rev_t3 - actual_rev) / abs(actual_rev)
            abs_pct  = abs(delta) * 100
            favorable = delta > 0
            cls = _classify_pct(abs_pct, r, is_favorable=favorable)
            if cls != "neutral":
                direction = "ahead of" if favorable else "behind"
                findings.append(Finding(
                    "positive" if favorable else cls,
                    "t3_vs_t12_trend", r.get("label", "T3 vs T12"),
                    f"Recent 3-month pace is {abs_pct:.1f}% {direction} the trailing-12 baseline."
                ))

    # ── Bad Debt as % of GPR ───────────────────────────────────────────────
    r = rules.get("bad_debt", {})
    if r.get("enabled"):
        gpr, bad_debt = _find_gpr_and_bad_debt(t12_data)
        if gpr and bad_debt is not None and gpr > 0:
            bd_pct = abs(bad_debt) / gpr * 100
            crit = r.get("critical_threshold_pct", 999)
            warn = r.get("warn_threshold_pct", 999)
            if bd_pct >= crit:
                sev = "critical"
            elif bd_pct >= warn:
                sev = "warning"
            else:
                sev = "positive"
            findings.append(Finding(
                sev, "bad_debt", r.get("label", "Bad Debt"),
                f"Bad debt is {bd_pct:.2f}% of gross potential rent ({_fmt_dollar(abs(bad_debt))} on {_fmt_dollar(gpr)} GPR)."
            ))

    # ── Budget-dependent rules ─────────────────────────────────────────────
    if budget_data:
        bs = budget_data.get("summary") or {}
        budget_rev = bs.get("total_revenue_t12") or 0
        budget_exp = bs.get("total_expenses_t12") or 0
        budget_noi = bs.get("noi_t12") or 0

        # Revenue variance
        r = rules.get("revenue_variance", {})
        if r.get("enabled") and budget_rev:
            diff = actual_rev - budget_rev
            pct  = diff / abs(budget_rev) * 100
            findings.append(_make_variance_finding(
                rule_id="revenue_variance", rule=r,
                diff=diff, pct=pct,
                metric="Revenue",
                higher_is_favorable=True,
            ))

        # Expense variance — flip: spending less is favorable
        r = rules.get("expense_variance", {})
        if r.get("enabled") and budget_exp:
            diff = actual_exp - budget_exp
            pct  = diff / abs(budget_exp) * 100
            findings.append(_make_variance_finding(
                rule_id="expense_variance", rule=r,
                diff=diff, pct=pct,
                metric="Operating Expenses",
                higher_is_favorable=False,
            ))

        # NOI variance
        r = rules.get("noi_variance", {})
        if r.get("enabled") and budget_noi:
            diff = actual_noi - budget_noi
            pct  = diff / abs(budget_noi) * 100
            findings.append(_make_variance_finding(
                rule_id="noi_variance", rule=r,
                diff=diff, pct=pct,
                metric="NOI",
                higher_is_favorable=True,
            ))

        # Per-category variances
        r = rules.get("category_variance", {})
        if r.get("enabled"):
            findings.extend(_per_category_findings(t12_data, budget_data, r))

    return [f for f in findings if f is not None]


def _make_variance_finding(*, rule_id: str, rule: dict,
                           diff: float, pct: float,
                           metric: str, higher_is_favorable: bool) -> Finding | None:
    min_dollar = rule.get("min_dollar_threshold", 0)
    if abs(diff) < min_dollar:
        return None
    abs_pct = abs(pct)
    is_favorable = (diff > 0) if higher_is_favorable else (diff < 0)
    cls = _classify_pct(abs_pct, rule, is_favorable=is_favorable)
    if cls == "neutral":
        return None
    direction = "above" if diff > 0 else "below"
    favorability = "favorable" if is_favorable else "unfavorable"
    label = rule.get("label", metric)
    msg = (
        f"{metric} is {_signed_dollar(diff)} ({pct:+.1f}%) {direction} budget — "
        f"{favorability} variance."
    )
    return Finding(cls, rule_id, label, msg)


def _per_category_findings(t12_data: dict, budget_data: dict, rule: dict) -> list[Finding]:
    """Find the top N most-out-of-whack categories."""
    from views.financials import _category_totals  # reuse the helper
    a = _category_totals(t12_data)
    b = _category_totals(budget_data)

    min_dollar = rule.get("min_dollar_threshold", 1000)
    max_findings = rule.get("max_findings", 5)
    crit_pct = rule.get("critical_threshold_pct", 999)
    warn_pct = rule.get("warn_threshold_pct", 999)

    candidates = []
    for cat in (set(a) | set(b)):
        ai = a.get(cat, {})
        bi = b.get(cat, {})
        act = ai.get("t12") or 0
        bud = bi.get("t12") or 0
        if not bud:
            continue
        diff = act - bud
        if abs(diff) < min_dollar:
            continue
        pct = diff / abs(bud) * 100
        kind = (ai.get("kind") or bi.get("kind") or "?").lower()
        higher_is_favorable = (kind == "revenue")
        is_favorable = (diff > 0) if higher_is_favorable else (diff < 0)
        abs_pct = abs(pct)
        if abs_pct < warn_pct:
            continue
        sev = (
            ("positive" if is_favorable else "critical")
            if abs_pct >= crit_pct
            else ("positive" if is_favorable else "warning")
        )
        candidates.append((abs_pct, cat, act, bud, diff, pct, kind, sev, is_favorable))

    # Sort by severity (critical first) then magnitude
    sev_order = {"critical": 0, "warning": 1, "positive": 2}
    candidates.sort(key=lambda c: (sev_order.get(c[7], 99), -c[0]))

    findings = []
    for abs_pct, cat, act, bud, diff, pct, kind, sev, is_fav in candidates[:max_findings]:
        direction = "above" if diff > 0 else "below"
        favorability = "favorable" if is_fav else "unfavorable"
        msg = (
            f"{cat}: {_fmt_dollar(act)} actual vs {_fmt_dollar(bud)} budget — "
            f"{_signed_dollar(diff)} ({pct:+.1f}%) {direction} budget ({favorability})."
        )
        findings.append(Finding(sev, "category_variance", rule.get("label", "Category Variance"), msg))
    return findings


def _find_gpr_and_bad_debt(t12_data: dict) -> tuple[float | None, float | None]:
    """Return (gross_potential_rent_t12, bad_debt_t12_absolute) using both
    line_item and category lookups so we handle both T12 file styles."""
    gpr = None
    bad_debt = None
    # Line-item pass
    for li in (t12_data.get("line_items") or []):
        name = (li.get("line_item") or "").lower()
        v = li.get("t12")
        if v is None or v == 0:
            continue
        if gpr is None and "gross potential rent" in name:
            gpr = v
        if bad_debt is None and (
            "bad debt" in name or "tenant uncollect" in name or "rent write off" in name
        ):
            bad_debt = v

    # Category fallback
    if gpr is None or bad_debt is None:
        from views.financials import _category_totals
        cats = _category_totals(t12_data)
        for cname, e in cats.items():
            lc = cname.lower()
            if gpr is None and "gross potential" in lc:
                gpr = e.get("t12")
            if bad_debt is None and "bad debt" in lc:
                bad_debt = e.get("t12")
    return gpr, bad_debt


# ──────────────────────────────────────────────────────────────────────────────
# Rent Roll rules
# ──────────────────────────────────────────────────────────────────────────────
def evaluate_rent_roll(rr_data: dict | None,
                       box_score_data: dict | None,
                       ar_data: dict | None,
                       lto_data: dict | None,
                       config: dict) -> list[Finding]:
    findings: list[Finding] = []
    if not rr_data:
        return findings
    rules = config.get("rent_roll", {})
    rs = rr_data.get("summary") or {}

    # ── Physical occupancy ────────────────────────────────────────────────
    r = rules.get("occupancy", {})
    if r.get("enabled") and rs.get("physical_occ") is not None:
        occ_pct = rs["physical_occ"] * 100
        crit = r.get("critical_below_pct", 0)
        warn = r.get("warn_below_pct", 0)
        positive = r.get("positive_above_pct", 100)
        if occ_pct < crit:
            sev, msg = "critical", f"Occupancy is {occ_pct:.1f}%, well below the {crit:.0f}% critical threshold."
        elif occ_pct < warn:
            sev, msg = "warning", f"Occupancy of {occ_pct:.1f}% is below the {warn:.0f}% comfort threshold."
        elif occ_pct >= positive:
            sev, msg = "positive", f"Occupancy is strong at {occ_pct:.1f}% (target {positive:.0f}%+)."
        else:
            sev, msg = "neutral", f"Occupancy is {occ_pct:.1f}%."
        if sev != "neutral":
            findings.append(Finding(sev, "occupancy", r.get("label", "Occupancy"), msg))

    # ── Loss to lease ─────────────────────────────────────────────────────
    r = rules.get("loss_to_lease", {})
    if r.get("enabled") and rs.get("loss_to_lease_pct") is not None:
        ltl_pct = abs(rs["loss_to_lease_pct"]) * 100
        crit = r.get("critical_threshold_pct", 999)
        warn = r.get("warn_threshold_pct", 999)
        if ltl_pct >= crit:
            sev = "critical"
        elif ltl_pct >= warn:
            sev = "warning"
        else:
            sev = "positive"
        findings.append(Finding(
            sev, "loss_to_lease", r.get("label", "Loss to Lease"),
            f"Loss-to-lease is {ltl_pct:.1f}% of in-place rent — "
            f"{'significant rent upside' if sev != 'positive' else 'minimal gap to market'}."
        ))

    # ── Exposure (Vacant + Notice Unrented from Box Score) ────────────────
    r = rules.get("exposure", {})
    if r.get("enabled") and box_score_data:
        at = (box_score_data.get("availability_total") or {})
        expo = at.get("exposure")
        if expo is not None:
            exp_pct = expo * 100
            crit = r.get("critical_threshold_pct", 999)
            warn = r.get("warn_threshold_pct", 999)
            if exp_pct >= crit:
                sev = "critical"
            elif exp_pct >= warn:
                sev = "warning"
            else:
                sev = "positive"
            findings.append(Finding(
                sev, "exposure", r.get("label", "Exposure"),
                f"Vacancy exposure (vacant + notice unrented) is {exp_pct:.2f}% of units."
            ))

    # ── Delinquency % of GPR ──────────────────────────────────────────────
    r = rules.get("delinquency", {})
    if r.get("enabled") and ar_data and rs.get("annual_sched_rent"):
        del_bal = (ar_data.get("totals") or {}).get("delinquent_balance") or 0
        gpr_proxy = rs["annual_sched_rent"] / 12  # one-month GPR proxy
        if gpr_proxy > 0:
            d_pct = del_bal / gpr_proxy * 100
            crit = r.get("critical_threshold_pct", 999)
            warn = r.get("warn_threshold_pct", 999)
            if d_pct >= crit:
                sev = "critical"
            elif d_pct >= warn:
                sev = "warning"
            else:
                sev = "positive"
            count = (ar_data.get("totals") or {}).get("delinquent_count", 0)
            findings.append(Finding(
                sev, "delinquency", r.get("label", "Delinquency"),
                f"{count} residents owe a combined {_fmt_dollar(del_bal)} — "
                f"{d_pct:.1f}% of monthly GPR."
            ))

    # ── 90+ days aged receivables ─────────────────────────────────────────
    r = rules.get("aged_90_plus", {})
    if r.get("enabled") and ar_data:
        d90 = (ar_data.get("totals") or {}).get("d_90_plus") or 0
        crit = r.get("critical_dollar_threshold", 999_999_999)
        warn = r.get("warn_dollar_threshold", 999_999_999)
        if abs(d90) >= crit:
            sev = "critical"
        elif abs(d90) >= warn:
            sev = "warning"
        else:
            sev = "neutral"
        if sev != "neutral":
            findings.append(Finding(
                sev, "aged_90_plus", r.get("label", "90+ Days A/R"),
                f"{_fmt_dollar(abs(d90))} sits in the 90+ days aging bucket and is at risk of write-off."
            ))

    # ── Lease expirations concentration ───────────────────────────────────
    r = rules.get("lease_expirations_concentration", {})
    if r.get("enabled"):
        buckets = rr_data.get("expiry_buckets") or {}
        total = rs.get("total_units") or 0
        if total > 0:
            short_term = (buckets.get("0–3 Months") or 0) + (buckets.get("3–6 Months") or 0)
            pct = short_term / total * 100
            crit = r.get("critical_threshold_pct", 999)
            warn = r.get("warn_threshold_pct", 999)
            if pct >= crit:
                sev = "critical"
            elif pct >= warn:
                sev = "warning"
            else:
                sev = "neutral"
            if sev != "neutral":
                findings.append(Finding(
                    sev, "lease_expirations_concentration", r.get("label", "Lease Expirations"),
                    f"{short_term} units ({pct:.1f}% of portfolio) have leases expiring in the next 6 months — concentration risk."
                ))

    # ── Make-Ready not-ready % ────────────────────────────────────────────
    r = rules.get("make_ready_not_ready", {})
    if r.get("enabled") and box_score_data:
        mr = box_score_data.get("make_ready") or []
        not_ready = next((m for m in mr if m["status"].lower().startswith("not ready")), None)
        if not_ready and not_ready.get("pct") is not None:
            nr_pct = not_ready["pct"] * 100
            crit = r.get("critical_threshold_pct", 999)
            warn = r.get("warn_threshold_pct", 999)
            if nr_pct >= crit:
                sev = "critical"
            elif nr_pct >= warn:
                sev = "warning"
            else:
                sev = "positive"
            findings.append(Finding(
                sev, "make_ready_not_ready", r.get("label", "Make-Ready"),
                f"{nr_pct:.0f}% of vacant units are NOT ready to lease — "
                f"{'turnover backlog is impacting absorption' if sev != 'positive' else 'turnover pipeline is healthy'}."
            ))

    # ── Net absorption ────────────────────────────────────────────────────
    r = rules.get("net_absorption", {})
    if r.get("enabled") and box_score_data:
        pt = box_score_data.get("property_pulse_total") or {}
        mi = pt.get("move_ins") or 0
        mo = pt.get("move_outs") or 0
        net = int(mi - mo)
        crit = r.get("critical_threshold_units", -999)
        warn = r.get("warn_threshold_units", -999)
        if net <= crit:
            sev = "critical"
        elif net <= warn:
            sev = "warning"
        elif net > 0:
            sev = "positive"
        else:
            sev = "neutral"
        if sev != "neutral":
            findings.append(Finding(
                sev, "net_absorption", r.get("label", "Net Absorption"),
                f"Net absorption this period is {net:+d} units ({int(mi)} move-ins, {int(mo)} move-outs)."
            ))

    # ── Rent trade-out ────────────────────────────────────────────────────
    r = rules.get("rent_tradeout", {})
    if r.get("enabled") and lto_data:
        total = lto_data.get("total") or {}
        chg_pct = total.get("lease_rent_change_pct")
        if chg_pct is not None:
            chg_p = chg_pct * 100
            crit = r.get("critical_below_pct", -999)
            warn = r.get("warn_below_pct", 999)
            positive = r.get("positive_above_pct", 999)
            if chg_p <= crit:
                sev, dirn = "critical", "decline"
            elif chg_p < warn:
                sev, dirn = "warning", "soft pricing"
            elif chg_p >= positive:
                sev, dirn = "positive", "strong rent growth"
            else:
                sev, dirn = "neutral", "flat pricing"
            if sev != "neutral":
                findings.append(Finding(
                    sev, "rent_tradeout", r.get("label", "Rent Trade-Out"),
                    f"Average rent change is {chg_p:+.2f}% on {total.get('leases', 0):.0f} leases — {dirn}."
                ))

    return findings


# ──────────────────────────────────────────────────────────────────────────────
# Severity sorting helper for the narrative
# ──────────────────────────────────────────────────────────────────────────────
SEVERITY_ORDER = {"critical": 0, "warning": 1, "positive": 2, "neutral": 3}


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
