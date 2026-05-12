"""utils/formatting.py — Number and date formatting helpers."""
from datetime import datetime, date


def fmt_currency(v, decimals=0) -> str:
    if v is None:
        return "—"
    try:
        v = float(v)
        sign = "-" if v < 0 else ""
        fmt = f"${abs(v):,.{decimals}f}"
        return f"{sign}{fmt}"
    except Exception:
        return "—"


def fmt_pct(v, decimals=1, already_pct=False) -> str:
    """Format a percentage. If v in (-1,1) and not already_pct, multiplies by 100."""
    if v is None:
        return "—"
    try:
        fv = float(v)
        if not already_pct and -1.0 < fv < 1.0:
            fv = fv * 100
        return f"{fv:.{decimals}f}%"
    except Exception:
        return "—"


def fmt_number(v, decimals=0) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{decimals}f}"
    except Exception:
        return "—"


def fmt_date(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, (datetime, date)):
        return v.strftime("%m/%d/%Y")
    try:
        from dateutil import parser as dp
        return dp.parse(str(v)).strftime("%m/%d/%Y")
    except Exception:
        return str(v)


def fmt_month_label(v) -> str:
    """Format a date as 'Jan '24' style."""
    if isinstance(v, (datetime, date)):
        return v.strftime("%b '%y")
    try:
        from dateutil import parser as dp
        return dp.parse(str(v)).strftime("%b '%y")
    except Exception:
        return str(v)


def variance_color(v) -> str:
    """Return CSS color string for variance value."""
    if v is None:
        return "#8BA3C7"
    try:
        return "#00C48C" if float(v) >= 0 else "#FF4560"
    except Exception:
        return "#8BA3C7"
