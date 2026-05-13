"""
services/box_score_parser.py
Parses a Yardi-style "Box Score" PDF — monthly leasing/occupancy snapshot.

The Box Score has five sections per page:
  1. Availability (As of <date>)         — unit-type roll-up of occupancy
  2. Property Pulse                       — monthly leasing activity
  3. Lead Activity                        — leads by contact method
  4. Lead Conversions                     — application/lease funnel
  5. Make Ready Status                    — vacant unit ready/not-ready

We parse all five into a single dict.
"""
import re
from typing import Optional
import pdfplumber


PCT_RE = re.compile(r"^-?\d+(?:\.\d+)?%$")
NUM_RE = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def _to_num(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if PCT_RE.match(s):
        return float(s.replace("%", "")) / 100
    if NUM_RE.match(s):
        return float(s.replace(",", ""))
    return None


def _split_tokens(line: str) -> list[str]:
    """Split a Box Score data line into tokens (first token is unit type, rest are values)."""
    parts = line.strip().split()
    # First token might be the unit type label ("1x1", "2X2", "Total:", "Unknown", etc.)
    if not parts:
        return []
    return parts


def _parse_row(line: str, expected_numerics: int) -> Optional[tuple[str, list[float | None]]]:
    """
    Parse a row of the form: <label> <num> <num> ... where there are exactly
    `expected_numerics` numeric values. Returns (label, values) or None if the
    row doesn't fit.
    """
    parts = line.strip().split()
    if len(parts) < expected_numerics + 1:
        return None
    # Take the last N tokens as numeric values; everything before is the label
    nums_str = parts[-expected_numerics:]
    label = " ".join(parts[:-expected_numerics]).rstrip(":").strip()
    nums = [_to_num(n) for n in nums_str]
    # Sanity check: every numeric token should actually parse
    if any(_to_num(n) is None for n in nums_str):
        return None
    return label, nums


def parse_box_score(file_path: str) -> dict:
    """
    Parse a Box Score PDF.

    Returns
    -------
    {
        "property": str | None,
        "period":   str | None,
        "as_of_date_text": str | None,
        "availability": [
            {
                "unit_type": str,
                "avg_sqft": float, "avg_market_rent": float, "avg_scheduled_rent": float,
                "units": int, "excluded": int, "rentable": int,
                "occupied": int, "vacant": int, "available": int,
                "notice": int, "notice_rented": int, "notice_unrented": int,
                "vacant_rented": int, "vacant_unrented": int,
                "occupied_pct": float, "no_notice_pct": float,
                "leased_trend": float, "exposure": float,
            }, ...
        ],
        "availability_total": { ... same shape, unit_type="Total" },
        "property_pulse": [
            {
                "unit_type": str, "units": int,
                "move_ins": int, "mtm": int, "mtm_conversions": int,
                "renewal_offers_completed": int, "transfers": int,
                "notices": int, "move_outs": int,
                "renewal_transfers": int, "skips": int, "evictions": int,
                "leased": int,
            }, ...
        ],
        "property_pulse_total": {...},
        "make_ready": [{"status", "vacant_rented", "vacant_unrented", "total", "pct"}, ...],
        "errors":   [str],
        "warnings": [str],
    }
    """
    errors, warnings = [], []

    try:
        pdf = pdfplumber.open(file_path)
    except Exception as e:
        return {"errors": [f"Cannot open PDF: {e}"], "warnings": []}

    all_lines = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        all_lines.extend(text.split("\n"))
    pdf.close()

    # ── Metadata ──────────────────────────────────────────────────────────
    property_name = None
    period_str = None
    as_of_text = None
    for line in all_lines[:5]:
        s = line.strip()
        if not s or s == "Box Score":
            continue
        if property_name is None and "Box Score" not in s and "Availability" not in s:
            property_name = s
            continue
        if period_str is None and re.match(r"^\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}$", s):
            period_str = s
            break

    # Find as-of date from Availability header line
    for line in all_lines[:8]:
        m = re.search(r"Availability \(As of ([\d/]+)\)", line)
        if m:
            as_of_text = m.group(1)
            break

    # ── Locate section headers ────────────────────────────────────────────
    section_starts = {}
    for i, line in enumerate(all_lines):
        if "Availability (As of" in line and "availability" not in section_starts:
            section_starts["availability"] = i
        elif line.startswith("Property Pulse"):
            section_starts["property_pulse"] = i
        elif line.startswith("Lead Activity"):
            section_starts["lead_activity"] = i
        elif line.startswith("Lead Conversions"):
            section_starts["lead_conversions"] = i
        elif line.startswith("Make Ready Status"):
            section_starts["make_ready"] = i

    # ── Availability (18 numeric columns after unit-type label) ──────────
    # Real column layout (header wraps; "Occupied No Notice" is one logical
    # column even though "Notice" appears next to it visually):
    #
    #   avg_sqft | avg_market_rent | avg_scheduled_rent | units | excluded |
    #   rentable | occupied | vacant | available | occupied_no_notice |
    #   notice_rented | notice_unrented | vacant_rented | vacant_unrented |
    #   occupied_pct | leased_pct | trend_pct | exposure_pct
    availability_rows: list[dict] = []
    availability_total: Optional[dict] = None
    if "availability" in section_starts:
        start = section_starts["availability"]
        end = section_starts.get("property_pulse", len(all_lines))
        for line in all_lines[start + 1:end]:
            s = line.strip()
            if not s:
                continue
            parsed = _parse_row(s, 18)
            if not parsed:
                continue
            label, vals = parsed
            entry = {
                "unit_type":          label,
                "avg_sqft":           vals[0],
                "avg_market_rent":    vals[1],
                "avg_scheduled_rent": vals[2],
                "units":              vals[3],
                "excluded":           vals[4],
                "rentable":           vals[5],
                "occupied":           vals[6],
                "vacant":             vals[7],
                "available":          vals[8],
                "occupied_no_notice": vals[9],
                "notice_rented":      vals[10],
                "notice_unrented":    vals[11],
                "vacant_rented":      vals[12],
                "vacant_unrented":    vals[13],
                "occupied_pct":       vals[14],
                "leased_pct":         vals[15],
                "trend":              vals[16],
                "exposure":           vals[17],
            }
            # Derive notice = total occupied - occupied_no_notice
            if entry["occupied"] is not None and entry["occupied_no_notice"] is not None:
                entry["notice"] = entry["occupied"] - entry["occupied_no_notice"]
            else:
                entry["notice"] = None
            if label.lower().startswith("total"):
                availability_total = entry
            else:
                availability_rows.append(entry)

    # ── Property Pulse (12 numeric columns) ────────────────────────────────
    pulse_rows: list[dict] = []
    pulse_total: Optional[dict] = None
    if "property_pulse" in section_starts:
        start = section_starts["property_pulse"]
        end = section_starts.get("lead_activity", len(all_lines))
        for line in all_lines[start + 1:end]:
            s = line.strip()
            if not s:
                continue
            parsed = _parse_row(s, 12)
            if not parsed:
                continue
            label, vals = parsed
            entry = {
                "unit_type":                label,
                "units":                    vals[0],
                "move_ins":                 vals[1],
                "mtm":                      vals[2],
                "mtm_conversions":          vals[3],
                "renewal_offers_completed": vals[4],
                "transfers":                vals[5],
                "notices":                  vals[6],
                "move_outs":                vals[7],
                "renewal_transfers":        vals[8],
                "skips":                    vals[9],
                "evictions":                vals[10],
                "leased":                   vals[11],
            }
            if label.lower().startswith("total"):
                pulse_total = entry
            else:
                pulse_rows.append(entry)

    # ── Make Ready Status (4 numeric columns: vacant_rented, vacant_unrented, total, pct) ──
    make_ready: list[dict] = []
    if "make_ready" in section_starts:
        start = section_starts["make_ready"]
        end = len(all_lines)
        for line in all_lines[start + 1:end]:
            s = line.strip()
            if not s or "Box Score" in s or "generated" in s.lower():
                continue
            # Make Ready rows have 4 columns: vacant_rented vacant_unrented total pct
            # The "Total:" row has only 3 (no pct)
            parts = s.split()
            if not parts:
                continue
            # Try 4 first, then 3
            for n in (4, 3):
                parsed = _parse_row(s, n)
                if parsed:
                    label, vals = parsed
                    make_ready.append({
                        "status":          label,
                        "vacant_rented":   vals[0],
                        "vacant_unrented": vals[1],
                        "total":           vals[2],
                        "pct":             vals[3] if n == 4 else None,
                    })
                    break

    if not availability_rows and not pulse_rows:
        errors.append("Could not parse any tables from the Box Score PDF.")

    return {
        "property":            property_name,
        "period":              period_str,
        "as_of_date_text":     as_of_text,
        "availability":        availability_rows,
        "availability_total":  availability_total,
        "property_pulse":      pulse_rows,
        "property_pulse_total":pulse_total,
        "make_ready":          make_ready,
        "errors":              errors,
        "warnings":            warnings,
    }
