"""
components/charts.py
Reusable Plotly chart functions — dark CRE dashboard theme.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from components.theme import COLORS, CHART_COLORS

# ── Shared axis / layout helpers ──────────────────────────────────────────────
_AXIS = dict(
    gridcolor=COLORS["border"],
    linecolor=COLORS["border"],
    tickfont=dict(size=11, color=COLORS["text_secondary"]),
    zerolinecolor=COLORS["border"],
)

def _base_layout(height=320, margin=None, legend_y=-0.18, showlegend=True):
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLORS["text_secondary"], size=12),
        height=height,
        margin=margin or dict(l=50, r=20, t=20, b=50),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_secondary"], size=11),
            orientation="h",
            y=legend_y,
        ),
        showlegend=showlegend,
    )


# ── Revenue / Expense / NOI Trend ─────────────────────────────────────────────
def revenue_expense_noi_trend(month_labels, revenues, expenses, nois, height=340):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=month_labels, y=revenues, name="Total Revenue",
        line=dict(color=COLORS["accent_blue"], width=2.5),
        fill="tozeroy", fillcolor="rgba(30,111,235,0.08)",
        mode="lines+markers", marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=month_labels, y=expenses, name="Total Expenses",
        line=dict(color=COLORS["red"], width=2),
        mode="lines+markers", marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=month_labels, y=nois, name="NOI",
        line=dict(color=COLORS["accent_teal"], width=2.5),
        fill="tozeroy", fillcolor="rgba(10,223,180,0.06)",
        mode="lines+markers", marker=dict(size=4),
    ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=70, r=20, t=20, b=60)),
        xaxis=dict(**_AXIS, tickangle=-30),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
    )
    return fig


# ── NOI Margin Trend ──────────────────────────────────────────────────────────
def noi_margin_trend(month_labels, margins, height=280):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=month_labels,
        y=[m * 100 if m is not None else None for m in margins],
        name="NOI Margin",
        line=dict(color=COLORS["accent_cyan"], width=2.5),
        fill="tozeroy", fillcolor="rgba(0,194,255,0.07)",
        mode="lines+markers", marker=dict(size=4),
    ))
    fig.update_layout(
        **_base_layout(height=height, showlegend=False, margin=dict(l=55, r=20, t=20, b=50)),
        xaxis=dict(**_AXIS, tickangle=-30),
        yaxis=dict(**_AXIS, ticksuffix="%", tickformat=".1f", range=[0, 80]),
    )
    return fig


# ── T12/T6/T3/Current comparison bar ─────────────────────────────────────────
def t_period_comparison(periods, noi_vals, noi_margins, height=300):
    # Annualise T6→×2, T3→×4, T1→×12 for apples-to-apples comparison
    annualised = []
    multipliers = [1, 2, 4, 12]
    for v, m in zip(noi_vals, multipliers):
        annualised.append(v * m if v is not None else None)

    # Recompute margins from annualised (avoid wild T1 swings on the line)
    safe_margins = [m * 100 if m is not None else None for m in noi_margins]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    bar_colors = [COLORS["accent_blue"], COLORS["accent_cyan"], COLORS["accent_teal"], COLORS["yellow"]]
    fig.add_trace(go.Bar(
        x=periods, y=annualised, name="NOI Annualised ($)",
        marker_color=bar_colors,
        text=[f"${v:,.0f}" if v else "" for v in annualised],
        textposition="outside",
        textfont=dict(size=10, color=COLORS["text_primary"]),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=periods, y=safe_margins,
        name="NOI Margin (%)", mode="lines+markers",
        line=dict(color=COLORS["yellow"], width=2),
        marker=dict(size=6, color=COLORS["yellow"]),
    ), secondary_y=True)
    fig.update_yaxes(tickprefix="$", tickformat=",.0f", secondary_y=False,
                     gridcolor=COLORS["border"], tickfont=dict(size=11))
    fig.update_yaxes(ticksuffix="%", tickformat=".1f", secondary_y=True,
                     showgrid=False, range=[0, 80], tickfont=dict(size=11))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=70, r=60, t=20, b=50)),
        barmode="group",
        xaxis=_AXIS,
    )
    return fig


# ── Donut chart (shared by revenue & expense mix) ─────────────────────────────
def _mix_donut(labels, values, center_label, center_val, height, colors):
    """
    Clean donut: percentages only on slices, full labels in legend below.
    Avoids all label/legend collision issues.
    """
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.62,
        marker=dict(colors=colors, line=dict(color=COLORS["bg_primary"], width=2)),
        # Show percent only on slice — no label text on slice to avoid overlap
        textinfo="percent",
        textfont=dict(size=10, color="#FFFFFF"),
        textposition="inside",
        # Only show labels for slices > 3% to avoid tiny-slice clutter
        texttemplate="%{percent:.1%}",
        insidetextorientation="radial",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        showlegend=True,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLORS["text_secondary"], size=11),
        height=height,
        margin=dict(l=10, r=10, t=20, b=120),   # large bottom for legend
        annotations=[dict(
            text=f"<b>{center_val}</b><br><span style='font-size:11px;color:{COLORS['text_secondary']}'>{center_label}</span>",
            x=0.5, y=0.5,
            font=dict(size=14, color=COLORS["text_primary"]),
            showarrow=False,
        )],
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color=COLORS["text_secondary"]),
            orientation="h",
            y=-0.05,          # just below chart
            x=0.5,
            xanchor="center",
            itemwidth=40,
        ),
        showlegend=True,
    )
    return fig


def revenue_mix_donut(labels, values, center_label="Total Revenue", center_val="", height=340):
    return _mix_donut(labels, values, center_label, center_val, height, CHART_COLORS)


def expense_mix_donut(labels, values, center_label="Total Expenses", center_val="", height=340):
    # Use a slightly different palette starting from index 2 to differentiate from rev
    exp_colors = [
        COLORS.get("chart3", "#FF6B6B"),
        COLORS.get("chart4", "#4ECDC4"),
        COLORS.get("chart5", "#45B7D1"),
        COLORS.get("chart6", "#96CEB4"),
        COLORS.get("chart7", "#FFEAA7"),
        COLORS.get("chart1", "#DDA0DD"),
        COLORS.get("chart2", "#98D8C8"),
        "#F39C12", "#8E44AD", "#E74C3C",
    ]
    return _mix_donut(labels, values, center_label, center_val, height, exp_colors)


# ── NOI Bridge waterfall ──────────────────────────────────────────────────────
def noi_bridge(revenue, expenses, noi, height=320):
    """
    Proper waterfall: Revenue (blue) → Expenses drag down (red) → NOI total (teal).
    """
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "total"],
        x=["Total Revenue", "– Expenses", "NOI"],
        y=[revenue, -abs(expenses), 0],   # 0 for total — Plotly computes it
        text=[
            f"${revenue:,.0f}",
            f"–${abs(expenses):,.0f}",
            f"${noi:,.0f}",
        ],
        textposition="outside",
        textfont=dict(color=COLORS["text_primary"], size=11),
        increasing=dict(marker=dict(color=COLORS["accent_blue"])),
        decreasing=dict(marker=dict(color="#FF4560")),
        totals=dict(marker=dict(color=COLORS["accent_teal"])),
        connector=dict(line=dict(color=COLORS["border"], width=1, dash="dot")),
    ))
    fig.update_layout(
        **_base_layout(height=height, showlegend=False, margin=dict(l=70, r=20, t=40, b=40)),
        xaxis=dict(**_AXIS, fixedrange=True),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
    )
    return fig


# ── Occupancy status donut ────────────────────────────────────────────────────
def occupancy_donut(occ_count, vac_count, notice_count, model_count, total, height=300):
    labels = ["Occupied", "Vacant", "Notice", "Model/Admin"]
    values = [occ_count, vac_count, notice_count, model_count]
    colors_map = [COLORS["accent_blue"], "#FF4560", COLORS["yellow"], COLORS["purple"]]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors_map, line=dict(color=COLORS["bg_primary"], width=2)),
        textinfo="percent",
        textfont=dict(size=10, color="#FFFFFF"),
        textposition="inside",
        insidetextorientation="radial",
        hovertemplate="%{label}: %{value} units (%{percent})<extra></extra>",
        showlegend=True,
    ))
    occ_pct = occ_count / total * 100 if total > 0 else 0
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=0, r=0, t=10, b=80),
        annotations=[dict(
            text=f"<b>{occ_pct:.1f}%</b><br><span style='font-size:10px'>Occupied</span>",
            x=0.5, y=0.5, font=dict(size=15, color=COLORS["text_primary"]), showarrow=False,
        )],
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color=COLORS["text_secondary"]),
            orientation="h", y=-0.05, x=0.5, xanchor="center",
        ),
        font=dict(color=COLORS["text_secondary"]),
        showlegend=True,
    )
    return fig


# ── Unit mix horizontal bar ───────────────────────────────────────────────────
def unit_mix_bar(unit_types, counts, height=280):
    fig = go.Figure(go.Bar(
        y=unit_types, x=counts, orientation="h",
        marker_color=CHART_COLORS[:len(unit_types)],
        text=[f"{c}" for c in counts],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text_primary"]),
    ))
    fig.update_layout(
        **_base_layout(height=height, margin=dict(l=80, r=50, t=10, b=20), showlegend=False),
        xaxis=dict(**_AXIS),
        yaxis=dict(tickfont=dict(size=11, color=COLORS["text_primary"]), gridcolor="rgba(0,0,0,0)"),
    )
    return fig


# ── Avg In-Place vs Market Rent grouped bar ───────────────────────────────────
def rent_comparison_bar(unit_types, inplace_rents, market_rents, height=300):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="In-Place Rent", x=unit_types, y=inplace_rents,
        marker_color=COLORS["accent_blue"],
        text=[f"${v:,.0f}" for v in inplace_rents],
        textposition="outside", textfont=dict(size=10),
    ))
    fig.add_trace(go.Bar(
        name="Market Rent", x=unit_types, y=market_rents,
        marker_color=COLORS["accent_cyan"],
        text=[f"${v:,.0f}" for v in market_rents],
        textposition="outside", textfont=dict(size=10),
    ))
    fig.update_layout(
        barmode="group",
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=60, r=20, t=20, b=60)),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    return fig


# ── Lease expirations line ────────────────────────────────────────────────────
def lease_expiration_chart(months, counts, height=280):
    fig = go.Figure(go.Scatter(
        x=months, y=counts,
        mode="lines+markers+text",
        line=dict(color=COLORS["accent_blue"], width=2.5),
        marker=dict(size=7, color=COLORS["accent_cyan"]),
        text=[str(c) for c in counts],
        textposition="top center",
        textfont=dict(size=10, color=COLORS["text_primary"]),
        fill="tozeroy", fillcolor="rgba(30,111,235,0.08)",
    ))
    fig.update_layout(
        **_base_layout(height=height, showlegend=False, margin=dict(l=50, r=20, t=10, b=60)),
        yaxis=dict(**_AXIS),
        xaxis=dict(**_AXIS, tickangle=-45),
    )
    return fig


# ── Expiry buckets bar ────────────────────────────────────────────────────────
def expiry_buckets_bar(buckets, counts, height=280):
    colors = [
        COLORS["red"]          if ("0–3" in b or "Expired" in b) else
        COLORS["yellow"]       if "3–6" in b else
        COLORS["accent_blue"]
        for b in buckets
    ]
    fig = go.Figure(go.Bar(
        x=buckets, y=counts, marker_color=colors,
        text=counts, textposition="outside",
        textfont=dict(size=11, color=COLORS["text_primary"]),
    ))
    fig.update_layout(
        **_base_layout(height=height, showlegend=False, margin=dict(l=50, r=20, t=10, b=60)),
        yaxis=dict(**_AXIS),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=10), tickangle=-20),
    )
    return fig


# ── Rent per SF bar ───────────────────────────────────────────────────────────
def rent_per_sf_bar(unit_types, rpsf_vals, height=280):
    fig = go.Figure(go.Bar(
        x=unit_types, y=rpsf_vals,
        marker_color=CHART_COLORS[:len(unit_types)],
        text=[f"${v:.2f}" if v else "" for v in rpsf_vals],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text_primary"]),
    ))
    fig.update_layout(
        **_base_layout(height=height, showlegend=False, margin=dict(l=60, r=20, t=10, b=40)),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=".2f"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    return fig


# ── Capex by category bar ─────────────────────────────────────────────────────
def capex_by_category(categories, budgets, actuals, height=320):
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Budget", x=categories, y=budgets,
                         marker_color=COLORS["accent_blue"]))
    fig.add_trace(go.Bar(name="Actual", x=categories, y=actuals,
                         marker_color=COLORS["accent_teal"]))
    fig.update_layout(
        barmode="group",
        **_base_layout(height=height, legend_y=-0.30, margin=dict(l=70, r=20, t=20, b=80)),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
        xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
    )
    return fig


# ── Actual vs Budget (monthly bars + dashed budget line) ─────────────────────
def actual_vs_budget_bar(month_labels, actuals, budgets=None, height=340):
    """
    Actual monthly revenue (bars) overlaid with budget (dashed line).
    If `budgets` is None or all-None, renders bars only — caller can pre-decide
    whether to display.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=month_labels, y=actuals, name="Actual",
        marker_color=COLORS["accent_blue"],
        hovertemplate="<b>%{x}</b><br>Actual: $%{y:,.0f}<extra></extra>",
    ))
    if budgets and any(b is not None for b in budgets):
        fig.add_trace(go.Scatter(
            x=month_labels, y=budgets, name="Budget",
            mode="lines+markers",
            line=dict(color=COLORS["accent_cyan"], width=2, dash="dash"),
            marker=dict(size=5),
            hovertemplate="<b>%{x}</b><br>Budget: $%{y:,.0f}<extra></extra>",
        ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=70, r=20, t=20, b=60)),
        xaxis=dict(**_AXIS, tickangle=-30),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
        bargap=0.25,
    )
    return fig


# ── Delinquency by Unit Type (stacked bars: total balance + 30+ days) ─────
def delinquency_by_unit_type(unit_types, total_balances, plus30_balances, height=320):
    """
    Stacked bars: Total Balance (lighter) + 30+ Days Delinquent (darker accent).
    Mirrors chart #7 in the Image 3 reference.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=unit_types, y=total_balances, name="Total Balance",
        marker_color=COLORS["accent_blue"],
        hovertemplate="<b>%{x}</b><br>Total Balance: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=unit_types, y=plus30_balances, name="30+ Days Delinquent",
        marker_color=COLORS["red"],
        hovertemplate="<b>%{x}</b><br>30+ Days: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=70, r=20, t=20, b=60)),
        xaxis=dict(**_AXIS),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
        barmode="group",
        bargap=0.25,
    )
    return fig


# ── Aged-Receivables Aging Buckets (horizontal stacked bar) ───────────────
def ar_aging_buckets(labels, values, height=220):
    """
    Horizontal stacked bar showing $ in each aging bucket
    (0-30, 31-60, 61-90, 90+).
    """
    colors = [
        COLORS["accent_blue"],
        COLORS["yellow"],
        COLORS["orange"],
        COLORS["red"],
    ]
    # Render as a single stacked horizontal bar
    fig = go.Figure()
    for label, value, color in zip(labels, values, colors):
        fig.add_trace(go.Bar(
            x=[value], y=["Aging"], name=label,
            orientation="h", marker_color=color,
            hovertemplate=f"<b>{label}</b><br>$%{{x:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.30, margin=dict(l=20, r=20, t=20, b=80)),
        xaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f"),
        yaxis=dict(**_AXIS, showticklabels=False),
        barmode="stack",
    )
    return fig


# ── Lease Trade-Out by Lease Type (grouped bars: prior vs current rent) ───
def lease_tradeout_chart(lease_types, prior_rents, current_rents, rent_changes_pct, height=320):
    """
    Grouped bars: prior vs current rent by lease type, with a secondary line
    showing rent change %. Populates chart #8 in the Image 3 reference.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=lease_types, y=prior_rents, name="Prior Rent",
        marker_color=COLORS["accent_blue"], opacity=0.6,
        hovertemplate="<b>%{x}</b><br>Prior: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=lease_types, y=current_rents, name="Current Rent",
        marker_color=COLORS["accent_cyan"],
        hovertemplate="<b>%{x}</b><br>Current: $%{y:,.0f}<extra></extra>",
    ))
    # Secondary y-axis for % change
    fig.add_trace(go.Scatter(
        x=lease_types, y=[(p or 0) * 100 for p in rent_changes_pct],
        name="Rent Change %", yaxis="y2", mode="lines+markers",
        line=dict(color=COLORS["red"], width=2),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Change: %{y:+.2f}%<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=70, r=70, t=20, b=60)),
        xaxis=dict(**_AXIS),
        yaxis=dict(**_AXIS, tickprefix="$", tickformat=",.0f", title="Rent ($)"),
        yaxis2=dict(
            **_AXIS, overlaying="y", side="right",
            tickformat=".1f", ticksuffix="%", title="Δ%",
            showgrid=False,
        ),
        barmode="group",
        bargap=0.25,
    )
    return fig


# ── Leased vs Occupied by Unit Type (grouped bar) ─────────────────────────
def leased_vs_occupied_by_unit_type(unit_types, occupied, on_notice, vacant, height=320):
    """
    Stacked bars: occupied (without notice) + on-notice + vacant by unit type.
    For Box Score Availability section.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=unit_types, y=occupied, name="Occupied",
        marker_color=COLORS["accent_blue"],
        hovertemplate="<b>%{x}</b><br>Occupied: %{y:.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=unit_types, y=on_notice, name="On Notice",
        marker_color=COLORS["yellow"],
        hovertemplate="<b>%{x}</b><br>On Notice: %{y:.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=unit_types, y=vacant, name="Vacant",
        marker_color=COLORS["red"],
        hovertemplate="<b>%{x}</b><br>Vacant: %{y:.0f}<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=height, legend_y=-0.22, margin=dict(l=60, r=20, t=20, b=60)),
        xaxis=dict(**_AXIS),
        yaxis=dict(**_AXIS, title="Units"),
        barmode="stack",
        bargap=0.25,
    )
    return fig
