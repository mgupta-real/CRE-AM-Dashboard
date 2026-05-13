"""
services/aged_receivables_parser.py
Parses a Yardi "Resident Aged Receivables" PDF.

Each detail line has the pattern:
  <Bldg-Unit> <Resident Name, possibly with comma> <Lease Status>
  <7 numeric columns: Unallocated, 0-30, 31-60, 61-90, 90+, Pre-Payments, Balance>
  [optional delinquency note]

Numbers in parentheses are negative (Yardi convention).
Multi-word lease statuses ("Current - Renewed", "Current - Month To Month")
sometimes wrap to the next line — the parser handles both forms.

Returns aged-bucket totals, a per-resident detail list, and the property total.
"""
import re
from typing import Optional
import pdfplumber


# A run of 7 numeric tokens (possibly negative in parens), space-separated
NUM_PATTERN = r"\(?-?[\d,]+\.\d{2}\)?"
SEVEN_NUMS_RE = re.compile(
    rf"(?P<unalloc>{NUM_PATTERN})\s+"
    rf"(?P<d0_30>{NUM_PATTERN})\s+"
    rf"(?P<d31_60>{NUM_PATTERN})\s+"
    rf"(?P<d61_90>{NUM_PATTERN})\s+"
    rf"(?P<d90>{NUM_PATTERN})\s+"
    rf"(?P<prepay>{NUM_PATTERN})\s+"
    rf"(?P<balance>{NUM_PATTERN})"
)

# Lease statuses we recognize. Order matters — match longest first so
# "Current - Month To Month" is preferred over "Current".
LEASE_STATUSES = (
    "Current - Month To Month",
    "Current - Renewed",
    "Current",
    "Notice",
    "Past",
    "Eviction",
    "Future",
)

# Bldg-Unit identifier: 1+ digits, dash, 1+ alphanumeric
BLDG_UNIT_RE = re.compile(r"^([\w\d]+-[\w\d]+)\s+(.+)$")


def _parse_num(s: str) -> Optional[float]:
    if not s:
        return None
    s = s.strip().replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        sign = -1
        s = s[1:-1]
    else:
        sign = 1
    try:
        return sign * float(s)
    except ValueError:
        return None


def _split_status_from_residue(residue: str) -> tuple[str, str, str]:
    """
    Given "Resident Name Status ...numbers...", split into (name, status, rest).
    Some residents have status that wraps across lines, in which case the status
    may be missing on this line — return ("", "", residue) for the caller to handle.
    """
    for status in LEASE_STATUSES:
        # Use the trailing-status pattern: "...Name <Status> <numbers...>"
        m = re.search(rf"\s({re.escape(status)})\s+(?={NUM_PATTERN})", residue)
        if m:
            name = residue[:m.start()].strip(", ").strip()
            rest = residue[m.end():].strip()
            return name, status, rest
    return "", "", residue


def parse_aged_receivables(file_path: str) -> dict:
    """
    Parse a Resident Aged Receivables PDF.

    Returns
    -------
    {
        "property": str | None,
        "period":   str | None,                 # e.g. "Apr 2026"
        "items": [
            {
                "bldg_unit": str,
                "resident":  str,
                "lease_status": str,
                "unallocated_charges": float|None,
                "d_0_30":   float|None,
                "d_31_60":  float|None,
                "d_61_90":  float|None,
                "d_90_plus": float|None,
                "prepay":   float|None,
                "balance":  float|None,
            }, ...
        ],
        "totals": {
            "unallocated_charges": float,
            "d_0_30":   float,
            "d_31_60":  float,
            "d_61_90":  float,
            "d_90_plus": float,
            "prepay":   float,
            "balance":  float,   # net (positive = owed to property)
            "delinquent_balance": float,   # sum of positive resident balances only
            "delinquent_count":   int,     # number of residents with balance > 0
        },
        "errors":   [str],
        "warnings": [str],
    }
    """
    errors, warnings = [], []
    items: list[dict] = []
    property_name = None
    period_str = None

    try:
        pdf = pdfplumber.open(file_path)
    except Exception as e:
        return {"errors": [f"Cannot open PDF: {e}"], "warnings": []}

    raw_lines: list[str] = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        raw_lines.extend(text.split("\n"))

    # Locate metadata
    for line in raw_lines[:10]:
        line = line.strip()
        if not line:
            continue
        if line == "Resident Aged Receivables":
            continue
        if property_name is None and "Aged Receivables" not in line:
            property_name = line
            continue
        if period_str is None and re.match(r"^[A-Z][a-z]{2,8}\s+\d{4}$", line):
            period_str = line
            break

    # Walk through lines. When we see a Bldg-Unit start, glue together with the
    # next line if status wraps; then run the 7-number regex.
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        i += 1
        if not line:
            continue

        # Two valid line shapes: (a) starts with Bldg-Unit identifier,
        # (b) starts with "Collections," — the property-wide write-off row.
        bldg_match = BLDG_UNIT_RE.match(line)
        is_collections = line.lower().startswith("collections,")
        if not bldg_match and not is_collections:
            continue

        if bldg_match:
            bldg_unit = bldg_match.group(1)
            residue = bldg_match.group(2)
        else:
            # Collections, Collections row
            bldg_unit = "COLLECTIONS"
            residue = line

        # Try to find status + 7 numbers on this line. If status isn't found,
        # the status probably wrapped onto the next line.
        name, status, rest = _split_status_from_residue(residue)
        nums_match = SEVEN_NUMS_RE.search(rest) if rest else None

        if not nums_match:
            # Numbers may be on this line but the status wrapped: glue with prev/next
            # Strategy: if the *current* line has 7 numbers but no recognized status,
            # try looking back/forward for the status fragment.
            inline_nums = SEVEN_NUMS_RE.search(residue)
            if inline_nums and not status:
                # Status fragment likely on previous line (e.g. "Current -")
                # Look back up to 2 lines for a status prefix
                status_prefix = None
                for look_back in range(1, 3):
                    j = i - 1 - look_back
                    if j < 0:
                        break
                    prev = raw_lines[j].strip()
                    if prev in ("Current -", "Current"):
                        # Look forward for the suffix
                        nxt = raw_lines[i].strip() if i < len(raw_lines) else ""
                        if prev == "Current -" and nxt in ("Renewed", "Month"):
                            if nxt == "Month":
                                # "Current - Month / To Month"
                                nxt2 = raw_lines[i + 1].strip() if i + 1 < len(raw_lines) else ""
                                if nxt2 == "To Month":
                                    status_prefix = "Current - Month To Month"
                                    i += 2
                                else:
                                    status_prefix = "Current - Month To Month"
                                    i += 1
                            else:
                                status_prefix = "Current - Renewed"
                                i += 1
                            break
                if status_prefix:
                    status = status_prefix
                    # Strip out the resident name from residue (everything before the numbers)
                    name = residue[:inline_nums.start()].strip(", ").strip()
                    nums_match = inline_nums

        if not nums_match:
            continue

        unalloc  = _parse_num(nums_match.group("unalloc"))
        d_0_30   = _parse_num(nums_match.group("d0_30"))
        d_31_60  = _parse_num(nums_match.group("d31_60"))
        d_61_90  = _parse_num(nums_match.group("d61_90"))
        d_90     = _parse_num(nums_match.group("d90"))
        prepay   = _parse_num(nums_match.group("prepay"))
        balance  = _parse_num(nums_match.group("balance"))

        items.append({
            "bldg_unit":           bldg_unit,
            "resident":            name or "",
            "lease_status":        status or "",
            "unallocated_charges": unalloc,
            "d_0_30":              d_0_30,
            "d_31_60":             d_31_60,
            "d_61_90":             d_61_90,
            "d_90_plus":           d_90,
            "prepay":              prepay,
            "balance":             balance,
        })

    pdf.close()

    if not items:
        errors.append("No resident-balance rows could be parsed from the PDF.")

    # Compute totals
    def _sum(key):
        return sum((it[key] or 0) for it in items)

    delinquent_items = [it for it in items if (it.get("balance") or 0) > 0]
    totals = {
        "unallocated_charges":  _sum("unallocated_charges"),
        "d_0_30":               _sum("d_0_30"),
        "d_31_60":              _sum("d_31_60"),
        "d_61_90":              _sum("d_61_90"),
        "d_90_plus":            _sum("d_90_plus"),
        "prepay":               _sum("prepay"),
        "balance":              _sum("balance"),
        "delinquent_balance":   sum(it["balance"] for it in delinquent_items),
        "delinquent_count":     len(delinquent_items),
    }

    return {
        "property":  property_name,
        "period":    period_str,
        "items":     items,
        "totals":    totals,
        "errors":    errors,
        "warnings":  warnings,
    }
