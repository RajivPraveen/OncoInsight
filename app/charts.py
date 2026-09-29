"""Figure factories shared by the dashboard pages and scripts/make_readme_assets.py (so README images are the
exact charts the dashboard renders)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from theme import (
    AGE_COLORS,
    AXIS,
    DE_EMPHASIS,
    DIVERGING,
    INK,
    INK_2,
    MODALITY_COLORS,
    OUTCOME_COLORS,
    SEQ_BLUE,
    SERIES,
    SITE_TYPE_COLORS,
    STAGE_COLORS,
    STATUS,
    SUBTYPE_COLORS,
    SURFACE,
    plain,
)

RING = dict(color=SURFACE, width=2)


def rgba(h: str, a: float) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def color_for(dim: str, value: str, i: int = 0) -> str:
    maps = {"receptor_subtype": SUBTYPE_COLORS, "stage_major": STAGE_COLORS, "age_group": AGE_COLORS,
            "site_type": SITE_TYPE_COLORS, "pathway_group": MODALITY_COLORS}
    return maps.get(dim, {}).get(value, SERIES[i % len(SERIES)])


# ------------------------------------------------------------------ journey
def sankey(steps: pd.DataFrame, cohort: pd.DataFrame, max_steps: int = 5, min_patients: int = 5,
           title: str = "") -> go.Figure:
    """Build a Sankey from patient-level steps for any cohort (links keep the colour of the step they leave)."""
    ids = set(cohort.patient_id)
    s = steps[steps.patient_id.isin(ids) & (steps.step_number <= max_steps)].copy()
    s["label"] = s.step_number.astype(str) + ". " + s.pathway_group
    outcome = cohort.set_index("patient_id").apply(
        lambda r: "Deceased" if r.os_event == 1 else ("Recurrence / progression" if r.any_progression_or_recurrence
                                                      else "Alive, no recurrence recorded"), axis=1)
    seqs = s.sort_values(["patient_id", "step_number"]).groupby("patient_id").label.apply(list)
    rows = []
    for pid in ids:
        seq = ["Diagnosis", *seqs.get(pid, []), f"Outcome: {outcome[pid]}"]
        rows += list(zip(seq[:-1], seq[1:], strict=True))
    edges = pd.DataFrame(rows, columns=["source", "target"]).value_counts().reset_index(name="n")
    edges = edges[edges.n >= min_patients]
    labels = sorted(set(edges.source) | set(edges.target),
                    key=lambda x: (x != "Diagnosis", x.startswith("Outcome"), x))
    idx = {lab: i for i, lab in enumerate(labels)}

    def node_color(lab: str) -> str:
        if lab == "Diagnosis":
            return INK_2
        if lab.startswith("Outcome: "):
            return OUTCOME_COLORS[lab.replace("Outcome: ", "")]
        return MODALITY_COLORS.get(lab.split(". ", 1)[-1], DE_EMPHASIS)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[plain(x) for x in labels], color=[node_color(x) for x in labels], pad=16, thickness=16, line=RING,
                  hovertemplate="%{label}<br><b>%{value}</b> patients<extra></extra>"),
        link=dict(source=[idx[x] for x in edges.source], target=[idx[x] for x in edges.target], value=edges.n,
                  color=[rgba(node_color(x), 0.12 if x == "Diagnosis" else 0.28) for x in edges.source],
                  hovertemplate="%{source.label} → %{target.label}<br><b>%{value}</b> patients<extra></extra>"),
    ))
    fig.update_layout(height=600, title=title)
    return fig


def sunburst_journey(p: pd.DataFrame) -> go.Figure:
    d = p.assign(first_step=p.pathway.str.split(" → ").str[1].fillna("Surgery only / undated"),
                 stage=p.stage_major.replace({"Unknown": "Stage unknown"}).radd("Stage ").str.replace("Stage Stage", "Stage"))
    d = d.groupby(["receptor_subtype", "stage", "first_step"], as_index=False).size()
    fig = px.sunburst(d, path=["receptor_subtype", "stage", "first_step"], values="size", color="receptor_subtype",
                      color_discrete_map=SUBTYPE_COLORS | {"(?)": DE_EMPHASIS})
    fig.update_traces(marker=dict(line=RING), insidetextorientation="radial",
                      hovertemplate="%{id}<br><b>%{value}</b> patients (%{percentRoot:.1%})<extra></extra>")
    fig.update_layout(height=520, title="Who are the patients? Subtype → stage → first treatment after surgery",
                      margin=dict(t=60, l=0, r=0, b=0))
    return fig


def pathway_treemap(pw: pd.DataFrame, metric: str = "crude_recurrence_pct", metric_label: str | None = None) -> go.Figure:
    d = pw[~pw.pathway.str.startswith("Other")].copy()
    d["steps"] = d.pathway.str.count("→") + 1
    d["root"] = "All treatment paths"
    d["pathway"] = d.pathway.map(plain)
    fig = px.treemap(d, path=["root", "pathway"], values="n_patients", color=metric,
                     color_continuous_scale=SEQ_BLUE[1:], hover_data={"median_estimated_cost_usd": ":,.0f"})
    label = metric_label or metric.replace("_", " ")
    fig.update_traces(marker=dict(line=RING), texttemplate="<b>%{label}</b><br>%{value} patients",
                      hovertemplate="<b>%{label}</b><br>%{value} patients<br>" + label + ": %{color:,.1f}<extra></extra>")
    fig.update_layout(height=460, coloraxis_colorbar=dict(title=""), margin=dict(t=20, l=0, r=0, b=0))
    return fig


def world_map(p: pd.DataFrame) -> go.Figure:
    d = p[p.country_of_residence != "Not reported"].groupby("country_of_residence", as_index=False).size()
    fig = px.choropleth(d, locations="country_of_residence", locationmode="country names", color="size",
                        color_continuous_scale=SEQ_BLUE[1:], hover_name="country_of_residence",
                        labels={"size": "patients"})
    fig.update_geos(showframe=False, showcoastlines=False, projection_type="natural earth", bgcolor=SURFACE,
                    landcolor="#f1f0ed", showland=True, showcountries=True, countrycolor="#ecebe7")
    fig.update_layout(height=380, title="Where TCGA-BRCA patients lived at enrollment",
                      margin=dict(t=50, l=0, r=0, b=0), coloraxis_colorbar=dict(title="patients"))
    return fig


# ------------------------------------------------------------------ survival
def km_from_table(curves: pd.DataFrame, summary: pd.DataFrame, dim: str, title: str, xmax: int = 180) -> go.Figure:
    fig = go.Figure()
    groups = summary.sort_values("group_value").group_value.tolist()
    for i, g in enumerate(groups):
        d = curves[curves.group_value == g]
        col = color_for(dim, g, i)
        fig.add_trace(go.Scatter(x=list(d.time_months) + list(d.time_months[::-1]),
                                 y=list(d.ci_upper) + list(d.ci_lower[::-1]), fill="toself",
                                 fillcolor=rgba(col, 0.10), line=dict(width=0), hoverinfo="skip", showlegend=False))
        n = int(summary.loc[summary.group_value == g, "n"].iloc[0])
        fig.add_trace(go.Scatter(x=d.time_months, y=d.survival, mode="lines", name=(f"Stage {g}" if dim == "stage_major" and g in STAGE_COLORS and g != "Unknown" else plain(str(g))) + f" ({n})",
                                 line=dict(color=col, width=2.5, shape="hv"), customdata=d.at_risk,
                                 hovertemplate=f"<b>%{{y:.1%}}</b> {g} · at risk %{{customdata}}<extra></extra>"))
    fig.update_layout(height=480, title=title, hovermode="x unified",
                      yaxis=dict(range=[0, 1.02], tickformat=".0%", title="% of patients"),
                      xaxis=dict(title="months since diagnosis", range=[0, xmax]))
    return fig


def km_compare(comp, colors=(SERIES[0], SERIES[1])) -> go.Figure:
    fig = go.Figure()
    for c, col in zip((comp.a, comp.b), colors, strict=True):
        if not c.timeline:
            continue
        fig.add_trace(go.Scatter(x=c.timeline + c.timeline[::-1], y=c.ci_upper + c.ci_lower[::-1], fill="toself",
                                 fillcolor=rgba(col, 0.12), line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=c.timeline, y=c.survival, mode="lines", name=f"{c.label} ({c.n} patients)",
                                 line=dict(color=col, width=3, shape="hv"), customdata=c.at_risk,
                                 hovertemplate=f"<b>%{{y:.1%}}</b> {c.label} · at risk %{{customdata}}<extra></extra>"))
    fig.add_vline(x=comp.horizon_months, line_color=AXIS, line_width=1,
                  annotation_text=f"{comp.horizon_months} months", annotation_font_color=INK_2)
    fig.update_layout(height=470, hovermode="x unified", title=f"{comp.endpoint}: group A vs. group B",
                      yaxis=dict(range=[0, 1.02], tickformat=".0%", title="% of patients"),
                      xaxis=dict(title="months since diagnosis", range=[0, 180]))
    return fig


def forest(df: pd.DataFrame, label: str, est: str, lo: str, hi: str, p: str | None = "p_value", ref: float = 1.0,
           log: bool = True, title: str = "", xtitle: str = "risk multiplier (1 = no effect)") -> go.Figure:
    d = df.sort_values(est)
    # significant = p < 0.05, or (without p-values) the 95% CI excludes the reference line
    sig = d[p] < 0.05 if p else (d[lo] > ref) | (d[hi] < ref)
    harmful = d[est] > ref
    colors = np.where(~sig, DE_EMPHASIS, np.where(harmful, STATUS["critical"], SERIES[0]))
    fig = go.Figure()
    for r, c in zip(d.itertuples(), colors, strict=True):
        fig.add_shape(type="line", x0=getattr(r, lo), x1=getattr(r, hi), y0=getattr(r, label), y1=getattr(r, label),
                      line=dict(color=rgba(c, 0.7) if c != DE_EMPHASIS else DE_EMPHASIS, width=3))
    fig.add_trace(go.Scatter(x=d[est], y=d[label], mode="markers", marker=dict(size=12, color=colors, line=RING),
                             customdata=d[[lo, hi] + ([p] if p else [])],
                             hovertemplate="%{y}<br><b>%{x:.2f}</b> (95% CI %{customdata[0]:.2f}–%{customdata[1]:.2f})"
                                           + (", p=%{customdata[2]:.3g}" if p else "") + "<extra></extra>"))
    fig.add_vline(x=ref, line_color=INK_2, line_width=1)
    xa = dict(title=xtitle)
    if log:
        xa |= dict(type="log", tickvals=[0.1, 0.25, 0.5, 1, 2, 4, 8, 16], ticktext=["0.1", "0.25", "0.5", "1", "2", "4", "8", "16"])
    fig.update_layout(height=130 + 32 * len(d), xaxis=xa, showlegend=False, title=title)
    return fig


# ------------------------------------------------------------------ time to treatment
def delay_distribution(d: pd.DataFrame, dim: str, threshold: int, title: str) -> go.Figure:
    fig = go.Figure()
    order = {"stage_major": ["I", "II", "III", "IV"], "age_group": list(AGE_COLORS)}.get(dim)
    groups = [g for g in (order or sorted(d[dim].dropna().unique())) if g in set(d[dim])]
    for i, g in enumerate(groups):
        v = d.loc[d[dim] == g, "interval_days"]
        if len(v) < 11:
            continue
        col = color_for(dim, g, i)
        shown = f"Stage {g}" if dim == "stage_major" and g != "Unknown" else str(g)
        fig.add_trace(go.Violin(y=v, name=f"{shown} ({len(v)})", line_color=col, fillcolor=rgba(col, 0.25),
                                box_visible=True, meanline_visible=False, points=False, spanmode="hard",
                                hoveron="violins", hovertemplate=f"{shown}<br>typical wait %{{median}} days<extra></extra>"))
    fig.add_hline(y=threshold, line_color="#b83c3c", line_width=1,
                  annotation_text=f"{threshold}-day mark", annotation_font_color=INK_2)
    top = max(threshold * 1.3, float(d.interval_days.quantile(0.97)) * 1.1) if len(d) else threshold * 2
    fig.update_layout(height=430, title=title, yaxis=dict(title="days waited", range=[0, top]), showlegend=False)
    return fig


def scorecard_heatmap(m: pd.DataFrame, rows: str, cols: list[str], labels: dict[str, str], higher_is_worse: dict,
                      title: str) -> go.Figure:
    """Rows x KPIs; cell colour = z-score vs network (red = worse, blue = better), text = actual value."""
    z = pd.DataFrame(index=m[rows])
    for c in cols:
        v = m[c].astype(float)
        zz = (v - v.mean()) / (v.std(ddof=0) or 1)
        z[labels[c]] = (zz if higher_is_worse[c] else -zz).to_numpy()
    text = m[cols].map(lambda v: f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}").to_numpy()
    fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=list(z.columns), y=list(z.index), zmid=0, zmin=-2.5, zmax=2.5,
                               colorscale=DIVERGING, text=text, texttemplate="%{text}", xgap=3, ygap=3,
                               textfont=dict(color=INK, size=12),
                               colorbar=dict(title="vs. other<br>hospitals", tickvals=[-2, 0, 2], ticktext=["better", "average", "worse"]),
                               hovertemplate="%{y}<br>%{x}: <b>%{text}</b><extra></extra>"))
    fig.update_layout(height=160 + 40 * len(z), title=title, yaxis=dict(autorange="reversed"),
                      xaxis=dict(tickangle=-25, side="top"), margin=dict(t=110))
    return fig


def animated_sites(k: pd.DataFrame) -> go.Figure:
    d = k[(k.entity_type == "Hospital") & k.median_days_to_chemotherapy.notna() & (k.n_timed_chemotherapy >= 3)].copy()
    d = d.sort_values("year_of_diagnosis")
    fig = px.scatter(d, x="median_days_to_chemotherapy", y="pct_chemo_over_90d", size="new_diagnoses", color="entity",
                     animation_frame="year_of_diagnosis", hover_name="entity", size_max=48,
                     range_x=[20, 180], range_y=[-5, 105], color_discrete_sequence=SERIES,
                     labels={"median_days_to_chemotherapy": "typical days to chemotherapy",
                             "pct_chemo_over_90d": "% waiting over 90 days", "new_diagnoses": "patients",
                             "year_of_diagnosis": "year", "entity": "hospital"})
    fig.update_traces(marker=dict(line=RING, opacity=0.85))
    fig.add_vline(x=90, line_color="#b83c3c", line_width=1)
    fig.update_layout(height=520, margin=dict(t=30),
                      legend=dict(orientation="v", y=0.5, x=1.02, yanchor="middle"))
    return fig


# ------------------------------------------------------------------ cost
def cost_stack(d: pd.DataFrame, dim: str) -> go.Figure:
    d = d.sort_values("mean_cost_usd")
    fig = go.Figure()
    for comp, col in (("Drug", "pct_drug"), ("Administration", "pct_administration"), ("Radiation", "pct_radiation"),
                      ("Surgery", "pct_surgery")):
        shown = {"Drug": "Drugs", "Administration": "Giving the drugs"}.get(comp, comp)
        fig.add_trace(go.Bar(y=d.dimension_value, x=d.mean_cost_usd * d[col].fillna(0) / 100, name=shown, orientation="h",
                             marker=dict(color={"Drug": SERIES[0], "Administration": SERIES[1], "Radiation": SERIES[2],
                                                "Surgery": SERIES[3]}[comp], line=RING),
                             hovertemplate="%{y}<br>" + shown + ": <b>$%{x:,.0f}</b><extra></extra>"))
    fig.add_trace(go.Scatter(y=d.dimension_value, x=d.mean_cost_usd, mode="text", textposition="middle right",
                             text=[f"${v / 1000:,.1f}K" for v in d.mean_cost_usd], showlegend=False, hoverinfo="skip",
                             textfont=dict(color=INK)))
    fig.update_layout(barmode="stack", height=140 + 38 * len(d), bargap=0.35, margin=dict(r=80),
                      title=f"Average estimated cost per patient, by {dim.lower()}", xaxis_title="$ per patient",
                      legend_traceorder="normal")
    return fig


# ------------------------------------------------------------------ lineage
LAYER_X = {"source": 0, "seed": 0, "staging": 1, "intermediate": 2, "core": 3, "analytics": 4}
LAYER_COLOR = {"source": SERIES[6], "seed": SERIES[3], "staging": SERIES[0], "intermediate": SERIES[2],
               "core": SERIES[1], "analytics": SERIES[4]}


def lineage_graph(manifest_path: Path, focus: str | None = None) -> go.Figure:
    m = json.loads(manifest_path.read_text())
    nodes, edges = {}, []

    def layer(uid: str, n: dict) -> str:
        if uid.startswith("source."):
            return "source"
        if n.get("resource_type") == "seed":
            return "seed"
        path = n.get("path", "")
        for key in ("staging", "intermediate", "core", "analytics"):
            if path.startswith(key) or f"/{key}/" in f"/{path}":
                return key
        return "analytics"

    for uid, n in {**m["nodes"], **m["sources"]}.items():
        if n.get("resource_type") not in ("model", "seed", "source"):
            continue
        nodes[uid] = {"name": n["name"], "layer": layer(uid, n), "desc": (n.get("description") or "")[:160]}
    for uid, n in m["nodes"].items():
        if uid in nodes:
            edges += [(p, uid) for p in n.get("depends_on", {}).get("nodes", []) if p in nodes]
    if focus:
        keep = {focus}
        frontier = {focus}
        while frontier:  # upstream closure
            frontier = {s for s, t in edges if t in frontier} - keep
            keep |= frontier
        frontier = {focus}
        while frontier:  # downstream closure
            frontier = {t for s, t in edges if s in frontier} - keep
            keep |= frontier
        nodes = {k: v for k, v in nodes.items() if k in keep}
        edges = [(s, t) for s, t in edges if s in keep and t in keep]
    by_layer: dict[str, list[str]] = {}
    for uid, n in sorted(nodes.items(), key=lambda kv: kv[1]["name"]):
        by_layer.setdefault(n["layer"], []).append(uid)
    by_col: dict[int, list[str]] = {}
    for lay in ("source", "seed", "staging", "intermediate", "core", "analytics"):  # seeds stack under sources
        by_col.setdefault(LAYER_X[lay], []).extend(by_layer.get(lay, []))
    pos = {}
    for x, uids in by_col.items():
        for i, uid in enumerate(uids):
            pos[uid] = (x, 1 - (i + 1) / (len(uids) + 1))
    fig = go.Figure()
    ex, ey = [], []
    for s, t in edges:
        (x0, y0), (x1, y1) = pos[s], pos[t]
        ex += [x0, (x0 + x1) / 2, x1, None]
        ey += [y0, (y0 + y1) / 2, y1, None]
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="rgba(139,144,153,0.35)", width=1),
                             hoverinfo="skip", showlegend=False))
    for lay, uids in by_layer.items():
        fig.add_trace(go.Scatter(
            x=[pos[u][0] for u in uids], y=[pos[u][1] for u in uids], mode="markers+text", name=lay,
            marker=dict(size=14, color=LAYER_COLOR[lay], line=RING), text=[nodes[u]["name"] for u in uids],
            textposition="middle right", textfont=dict(size=10, color=INK_2),
            customdata=[nodes[u]["desc"] for u in uids],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra>" + lay + "</extra>"))
    fig.update_layout(height=max(520, 24 * max(len(v) for v in by_col.values())), hovermode="closest",
                      xaxis=dict(visible=False, range=[-0.2, 4.9]), yaxis=dict(visible=False),
                      title="dbt lineage: sources → staging → intermediate → core star schema → marts")
    return fig
