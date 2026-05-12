"""
services/insights_engine.py
Rules-based insights engine for CRE asset management.
Every insight shows the metric that triggered it — no black-box scores.
"""
from datetime import date


def generate_insights(t12_data: dict | None, rr_data: dict | None,
                      loans: list | None, capex: list | None,
                      comps: list | None) -> list[dict]:
    """
    Returns a list of insight dicts:
    {
        "type": str,
        "severity": "info" | "warning" | "alert",
        "message": str,
        "metric_label": str,
        "metric_value": float | None,
    }
    """
    insights = []

    # ── T12 / Financial Insights ──────────────────────────────────────────
    if t12_data:
        s = t12_data.get("summary", {})
        noi_t12  = s.get("noi_t12")
        rev_t12  = s.get("total_revenue_t12")
        exp_t12  = s.get("total_expenses_t12")
        noi_margin = s.get("noi_margin_t12")
        noi_t6   = s.get("noi_t6")
        noi_t3   = s.get("noi_t3")

        if noi_t12 and noi_t6 and noi_t6 > 0:
            annualized_t6 = noi_t6 * 2
            chg = (noi_t12 - annualized_t6) / annualized_t6 * 100
            if abs(chg) > 3:
                sev = "info" if chg > 0 else "warning"
                insights.append({
                    "type": "noi_trend",
                    "severity": sev,
                    "message": f"T12 NOI is {chg:+.1f}% vs annualized T6 run-rate, indicating {'improving' if chg > 0 else 'declining'} performance.",
                    "metric_label": "NOI T12 vs Ann. T6 Change",
                    "metric_value": round(chg, 2),
                })

        if noi_margin is not None:
            if noi_margin < 0.38:
                insights.append({
                    "type": "noi_margin_low",
                    "severity": "alert",
                    "message": f"NOI margin of {noi_margin*100:.1f}% is below the typical 38% threshold for multifamily — review expense controls.",
                    "metric_label": "NOI Margin T12",
                    "metric_value": round(noi_margin * 100, 2),
                })
            elif noi_margin > 0.50:
                insights.append({
                    "type": "noi_margin_strong",
                    "severity": "info",
                    "message": f"NOI margin of {noi_margin*100:.1f}% is above 50% — strong operating performance.",
                    "metric_label": "NOI Margin T12",
                    "metric_value": round(noi_margin * 100, 2),
                })

        if rev_t12 and exp_t12:
            exp_ratio = exp_t12 / rev_t12
            if exp_ratio > 0.62:
                insights.append({
                    "type": "expense_ratio_high",
                    "severity": "warning",
                    "message": f"Operating expense ratio of {exp_ratio*100:.1f}% is above 62% — expenses may be outpacing revenue growth.",
                    "metric_label": "Expense Ratio T12",
                    "metric_value": round(exp_ratio * 100, 2),
                })

        # Revenue mix: check RUBS contribution
        rev_mix = t12_data.get("revenue_mix", {})
        if rev_mix and rev_t12:
            rubs = rev_mix.get("RUBS", 0)
            if rubs / rev_t12 > 0.08:
                insights.append({
                    "type": "rubs_high",
                    "severity": "info",
                    "message": f"RUBS/utility rebill contributes {rubs/rev_t12*100:.1f}% of revenue — monitor tenant satisfaction risk.",
                    "metric_label": "RUBS % of Revenue",
                    "metric_value": round(rubs / rev_t12 * 100, 2),
                })

    # ── Rent Roll Insights ────────────────────────────────────────────────
    if rr_data:
        s = rr_data.get("summary", {})
        occ   = s.get("physical_occ", 1.0)
        ltl   = s.get("loss_to_lease", 0)
        ltl_p = s.get("loss_to_lease_pct", 0)
        avg_ip= s.get("avg_inplace_rent", 0)
        total = s.get("total_units", 0)
        vac   = s.get("vacant_units", 0)
        notice= s.get("notice_units", 0)

        if occ < 0.92:
            insights.append({
                "type": "occupancy_low",
                "severity": "warning",
                "message": f"Physical occupancy of {occ*100:.1f}% is below 92% — leasing velocity and concession strategy warrant review.",
                "metric_label": "Physical Occupancy",
                "metric_value": round(occ * 100, 2),
            })
        elif occ >= 0.97:
            insights.append({
                "type": "occupancy_high",
                "severity": "info",
                "message": f"Physical occupancy of {occ*100:.1f}% is above 97% — evaluate pricing power and reduce concessions.",
                "metric_label": "Physical Occupancy",
                "metric_value": round(occ * 100, 2),
            })

        if ltl and avg_ip and ltl > 0:
            insights.append({
                "type": "loss_to_lease",
                "severity": "info",
                "message": f"Loss-to-lease of ${ltl:,.0f}/unit ({ltl_p:.1f}%) indicates potential rent upside as leases renew.",
                "metric_label": "Loss-to-Lease per Unit",
                "metric_value": round(ltl, 2),
            })

        # Expiry pressure: >15% expiring in next 90 days
        buckets = rr_data.get("expiry_buckets", {})
        short_term = buckets.get("0–3 Months", 0) + buckets.get("Expired", 0)
        if total and short_term / total > 0.15:
            insights.append({
                "type": "lease_expiry_risk",
                "severity": "alert",
                "message": f"{short_term} leases ({short_term/total*100:.0f}% of portfolio) expire within 90 days — prioritize renewal outreach.",
                "metric_label": "Leases Expiring <90 Days",
                "metric_value": short_term,
            })
        elif total and short_term / total > 0.08:
            insights.append({
                "type": "lease_expiry_watch",
                "severity": "warning",
                "message": f"{short_term} leases expire in the next 90 days — monitor renewal pipeline closely.",
                "metric_label": "Leases Expiring <90 Days",
                "metric_value": short_term,
            })

        if notice and total and notice / total > 0.08:
            insights.append({
                "type": "notice_units_high",
                "severity": "warning",
                "message": f"{notice} units ({notice/total*100:.0f}%) have given notice — ensure replacement leases are in pipeline.",
                "metric_label": "Notice Units",
                "metric_value": notice,
            })

    # ── Loan Insights ─────────────────────────────────────────────────────
    if loans:
        today = date.today()
        for loan in loans:
            mat = loan.get("maturity_date")
            if mat:
                try:
                    from dateutil import parser as dp
                    mat_dt = dp.parse(str(mat)).date()
                    days_to_mat = (mat_dt - today).days
                    if days_to_mat < 0:
                        insights.append({
                            "type": "loan_matured",
                            "severity": "alert",
                            "message": f"Loan from {loan.get('lender','[lender]')} matured on {mat_dt} — immediate attention required.",
                            "metric_label": "Days Past Maturity",
                            "metric_value": abs(days_to_mat),
                        })
                    elif days_to_mat <= 180:
                        insights.append({
                            "type": "loan_maturity_near",
                            "severity": "alert",
                            "message": f"Loan from {loan.get('lender','[lender]')} matures in {days_to_mat} days ({mat_dt}) — begin refinance process.",
                            "metric_label": "Days to Maturity",
                            "metric_value": days_to_mat,
                        })
                    elif days_to_mat <= 365:
                        insights.append({
                            "type": "loan_maturity_watch",
                            "severity": "warning",
                            "message": f"Loan from {loan.get('lender','[lender]')} matures in {days_to_mat} days — plan refinance strategy.",
                            "metric_label": "Days to Maturity",
                            "metric_value": days_to_mat,
                        })
                except Exception:
                    pass

    # ── Capex Insights ─────────────────────────────────────────────────────
    if capex:
        over_budget = [p for p in capex if p.get("budget") and p.get("actual_spent", 0) > p["budget"]]
        if over_budget:
            insights.append({
                "type": "capex_over_budget",
                "severity": "warning",
                "message": f"{len(over_budget)} capex project(s) are over budget — review cost controls and change orders.",
                "metric_label": "Over-Budget Projects",
                "metric_value": len(over_budget),
            })

    return insights
