"""
services/excel_exporter.py
Generates a professionally formatted Excel export workbook.
"""
import io
from datetime import datetime
import pandas as pd
from utils.formatting import fmt_currency, fmt_pct, fmt_date


def generate_excel(
    t12_data: dict | None,
    rr_data:  dict | None,
    loans:    list | None,
    capex:    list | None,
    comps:    list | None,
    insights: list | None,
    property_name: str = "Property",
    client_name:   str = "Client",
) -> bytes:
    """Return Excel workbook as bytes."""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Formats ────────────────────────────────────────────────────────
        hdr_fmt = wb.add_format({
            "bold": True, "bg_color": "#0D1526", "font_color": "#00C2FF",
            "border": 1, "border_color": "#1E2D4A",
        })
        title_fmt = wb.add_format({
            "bold": True, "font_size": 14, "font_color": "#F0F4FF",
            "bg_color": "#0A0E1A",
        })
        money_fmt = wb.add_format({"num_format": "$#,##0", "bg_color": "#111827", "font_color": "#F0F4FF"})
        pct_fmt   = wb.add_format({"num_format": "0.0%",   "bg_color": "#111827", "font_color": "#F0F4FF"})
        base_fmt  = wb.add_format({"bg_color": "#111827",  "font_color": "#F0F4FF"})
        pos_fmt   = wb.add_format({"bg_color": "#111827",  "font_color": "#00C48C", "num_format": "$#,##0"})
        neg_fmt   = wb.add_format({"bg_color": "#111827",  "font_color": "#FF4560", "num_format": "$#,##0"})

        # ── 1. Executive Summary ──────────────────────────────────────────
        ws = wb.add_worksheet("Executive Summary")
        ws.set_tab_color("#1E6FEB")
        ws.hide_gridlines(2)
        ws.set_column("A:A", 30)
        ws.set_column("B:B", 20)

        ws.write("A1", f"CRE Asset Management Dashboard", title_fmt)
        ws.write("A2", f"Property: {property_name}", base_fmt)
        ws.write("A3", f"Client: {client_name}", base_fmt)
        ws.write("A4", f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}", base_fmt)

        row = 6
        if t12_data:
            s = t12_data.get("summary", {})
            ws.write(row, 0, "KEY METRICS", hdr_fmt); ws.write(row, 1, "", hdr_fmt); row += 1
            for label, val in [
                ("Total Revenue T12",   fmt_currency(s.get("total_revenue_t12"))),
                ("Total Expenses T12",  fmt_currency(s.get("total_expenses_t12"))),
                ("Net Operating Income",fmt_currency(s.get("noi_t12"))),
                ("NOI Margin",          fmt_pct(s.get("noi_margin_t12") * 100 if s.get("noi_margin_t12") else None)),
            ]:
                ws.write(row, 0, label, base_fmt)
                ws.write(row, 1, val, base_fmt)
                row += 1

        if rr_data:
            s = rr_data.get("summary", {})
            row += 1
            ws.write(row, 0, "RENT ROLL SUMMARY", hdr_fmt); ws.write(row, 1, "", hdr_fmt); row += 1
            for label, val in [
                ("Total Units",      s.get("total_units", 0)),
                ("Occupied Units",   s.get("occupied_units", 0)),
                ("Physical Occ.",    f"{s.get('physical_occ', 0)*100:.1f}%"),
                ("Avg In-Place Rent",fmt_currency(s.get("avg_inplace_rent"))),
                ("Avg Market Rent",  fmt_currency(s.get("avg_market_rent"))),
                ("Loss-to-Lease",    fmt_currency(s.get("loss_to_lease"))),
                ("Annual Sched Rent",fmt_currency(s.get("annual_sched_rent"))),
            ]:
                ws.write(row, 0, label, base_fmt)
                ws.write(row, 1, str(val), base_fmt)
                row += 1

        # ── 2. T12 Financial Data ─────────────────────────────────────────
        if t12_data:
            line_items = t12_data.get("line_items", [])
            if line_items:
                rows = []
                for li in line_items:
                    rows.append({
                        "Category":    li.get("category", ""),
                        "Line Item":   li.get("line_item", ""),
                        "T12":         li.get("t12"),
                        "T6":          li.get("t6"),
                        "T3":          li.get("t3"),
                        "T1 (Current)":li.get("t1"),
                        "Confidence":  li.get("confidence"),
                    })
                df = pd.DataFrame(rows)
                df.to_excel(writer, sheet_name="T12 Statement", index=False)
                _auto_fit(writer.sheets["T12 Statement"], df)

        # ── 3. Rent Roll ───────────────────────────────────────────────────
        if rr_data:
            units = rr_data.get("units", [])
            rows  = []
            for u in units:
                rows.append({
                    "Unit No":      u.get("unit_no"),
                    "Unit Type":    u.get("unit_type"),
                    "Sq Ft":        u.get("unit_size_sf"),
                    "Status":       u.get("status"),
                    "Tenant":       u.get("tenant_name"),
                    "Market Rent":  u.get("market_rent"),
                    "Eff. Rent":    u.get("effective_rent"),
                    "Delta $":      u.get("delta_amt"),
                    "Delta %":      u.get("delta_pct"),
                    "Lease End":    fmt_date(u.get("lease_end")),
                    "Move In":      fmt_date(u.get("move_in_date")),
                    "Expiry Bucket":u.get("expiry_bucket"),
                    "Rent/SF":      u.get("rent_per_sf"),
                })
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Rent Roll", index=False)
            _auto_fit(writer.sheets["Rent Roll"], df)

        # ── 4. Loans ──────────────────────────────────────────────────────
        if loans:
            rows = [{
                "Lender":        l.get("lender"),
                "Type":          l.get("loan_type"),
                "Orig Balance":  l.get("original_balance"),
                "Curr Balance":  l.get("current_balance"),
                "Rate":          l.get("interest_rate"),
                "Rate Type":     l.get("rate_type"),
                "Maturity":      fmt_date(l.get("maturity_date")),
                "Extensions":    l.get("extension_options"),
                "Amort":         l.get("amortization_type"),
                "Monthly DS":    l.get("monthly_debt_svc"),
                "Notes":         l.get("notes"),
            } for l in loans]
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Loans", index=False)

        # ── 5. CapEx ──────────────────────────────────────────────────────
        if capex:
            rows = [{
                "Project":    p.get("project_name"),
                "Category":   p.get("category"),
                "Budget":     p.get("budget"),
                "Actual":     p.get("actual_spent"),
                "Remaining":  (p.get("budget") or 0) - (p.get("actual_spent") or 0),
                "Status":     p.get("status"),
                "Vendor":     p.get("vendor"),
                "Start":      fmt_date(p.get("start_date")),
                "Est. End":   fmt_date(p.get("expected_end")),
                "Notes":      p.get("notes"),
            } for p in capex]
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="CapEx", index=False)

        # ── 6. Comparables ────────────────────────────────────────────────
        if comps:
            rows = [{
                "Property":    c.get("comp_name"),
                "City/State":  f"{c.get('city','')}, {c.get('state','')}",
                "Distance mi": c.get("distance_miles"),
                "Year Built":  c.get("year_built"),
                "Units":       c.get("units"),
                "Class":       c.get("property_class"),
                "Apts URL":    c.get("apts_url"),
                "Notes":       c.get("notes"),
            } for c in comps]
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Comparables", index=False)

        # ── 7. Insights ───────────────────────────────────────────────────
        if insights:
            rows = [{
                "Type":    i.get("type"),
                "Severity":i.get("severity"),
                "Message": i.get("message"),
                "Metric":  i.get("metric_label"),
                "Value":   i.get("metric_value"),
            } for i in insights]
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name="Insights", index=False)

    return output.getvalue()


def _auto_fit(ws, df: pd.DataFrame, extra: int = 4):
    for i, col in enumerate(df.columns):
        vals = df[col].fillna("").astype(str); max_len = max(len(str(col)), int(vals.str.len().max()) if len(df) > 0 else 0)
        ws.set_column(i, i, min(max_len + extra, 40))
