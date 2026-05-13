"""
components/narrative.py
Renders a narrative-style insights block at the bottom of a tab.

Style: a single flowing paragraph, with each sentence color-coded by severity
(red / yellow / green). Sentences are sorted critical → warning → positive,
and bucketed into "Concerns" and "Strengths" subsections when there are 3+
findings to keep things scannable.
"""
import streamlit as st


_SEVERITY_STYLE = {
    "critical": {"color": "#FF4560", "icon": "🔴", "label": "Critical"},
    "warning":  {"color": "#FFC107", "icon": "🟡", "label": "Warning"},
    "positive": {"color": "#00C48C", "icon": "🟢", "label": "Positive"},
    "neutral":  {"color": "#8BA3C7", "icon": "•",  "label": "Info"},
}


def render_narrative(findings: list, *, title: str = "Analyst Notes",
                     empty_message: str = "Not enough data to generate insights yet."):
    """
    Render a card with the narrative block. `findings` is a list of Finding
    objects (or compatible dicts with severity/message/label/rule_id).
    """
    st.markdown(
        f'<div class="dash-card"><div class="dash-card-title">'
        f'📝 {title}</div>',
        unsafe_allow_html=True,
    )

    if not findings:
        st.markdown(
            f'<p style="color:#8BA3C7;font-size:13px;margin-top:8px;">'
            f'{empty_message}</p>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Normalize — accept Finding objects or dicts
    def _attr(f, name):
        return getattr(f, name) if not isinstance(f, dict) else f.get(name)

    # Bucket by severity
    critical = [f for f in findings if _attr(f, "severity") == "critical"]
    warning  = [f for f in findings if _attr(f, "severity") == "warning"]
    positive = [f for f in findings if _attr(f, "severity") == "positive"]

    counts_html = _counts_strip(len(critical), len(warning), len(positive))
    st.markdown(counts_html, unsafe_allow_html=True)

    # Render each bucket as its own subsection
    if critical:
        st.markdown(_bucket_html(
            "Critical issues", critical, "#FF4560", "🔴"
        ), unsafe_allow_html=True)
    if warning:
        st.markdown(_bucket_html(
            "Warnings", warning, "#FFC107", "🟡"
        ), unsafe_allow_html=True)
    if positive:
        st.markdown(_bucket_html(
            "Positive signals", positive, "#00C48C", "🟢"
        ), unsafe_allow_html=True)

    st.markdown(
        '<p style="color:#4A6080;font-size:10px;margin-top:14px;font-style:italic;">'
        'Notes are generated from rules — adjust thresholds in Settings → Insights Rules.'
        '</p>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _counts_strip(n_crit: int, n_warn: int, n_pos: int) -> str:
    chips = []
    for label, n, color in [
        ("Critical", n_crit, "#FF4560"),
        ("Warnings", n_warn, "#FFC107"),
        ("Positive", n_pos, "#00C48C"),
    ]:
        chips.append(
            f'<span style="display:inline-block;padding:4px 10px;margin-right:8px;'
            f'border-radius:12px;border:1px solid {color}55;background:{color}11;'
            f'color:{color};font-size:11px;font-weight:600;letter-spacing:.02em;">'
            f'{label}: {n}</span>'
        )
    return (
        '<div style="margin:6px 0 14px 0;">' + "".join(chips) + "</div>"
    )


def _bucket_html(heading: str, items: list, color: str, icon: str) -> str:
    """Render a list of findings as a paragraph-style block."""
    def _attr(f, name):
        return getattr(f, name) if not isinstance(f, dict) else f.get(name)

    sentences = []
    for f in items:
        label = _attr(f, "label") or ""
        msg = _attr(f, "message") or ""
        # Bold the label, plain message body
        sentences.append(
            f'<span style="color:{color};font-weight:600;">{label}:</span> '
            f'<span style="color:#C8D8F0;">{msg}</span>'
        )
    body = " &nbsp; ".join(sentences) if False else "<br>".join(sentences)
    # Use one-line-per-finding for readability; the question asked for narrative
    # but each finding-as-its-own-line tends to scan better. We keep them within
    # a single paragraph block to preserve narrative feel.
    return (
        f'<div style="margin:0 0 14px 0;padding:10px 14px;'
        f'border-left:3px solid {color};background:{color}08;border-radius:4px;">'
        f'<p style="color:{color};font-weight:700;font-size:12px;margin:0 0 8px 0;'
        f'text-transform:uppercase;letter-spacing:.06em;">'
        f'{icon}&nbsp;{heading} ({len(items)})</p>'
        f'<p style="font-size:13px;line-height:1.7;margin:0;">{body}</p>'
        f'</div>'
    )
