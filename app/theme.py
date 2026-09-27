"""Shared dashboard theme, UI components, cohort filters and data access.

Colour system (validated with the dataviz palette validator):
* Categorical slots in fixed order - colour follows the ENTITY (Chemotherapy is always orange), never its rank.
* Ordered categories (stage, age group) use a single-hue ordinal blue ramp (validated with --ordinal).
* Status colours (good / warning / serious / critical) are reserved for alerts and flags, always with an icon + label.
Slots 3-5 are below 3:1 contrast on the surface, so charts carry direct labels, tooltips and a table view.
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from oncoinsight.common.db import read_sql

# ------------------------------------------------------------------ palette
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
DE_EMPHASIS = "#c3c2b7"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = SERIES
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# diverging blue <-> red with a neutral grey midpoint ("better" <-> "worse" than the network)
DIVERGING = [[0, "#1c5cab"], [0.25, "#6da7ec"], [0.5, "#f0efec"], [0.75, "#ec835a"], [1, "#d03b3b"]]

MODALITY_COLORS = {"Surgery": BLUE, "Chemotherapy": ORANGE, "Radiation": AQUA, "Endocrine": YELLOW,
                   "HER2-targeted": MAGENTA, "Other systemic": GREEN}
SUBTYPE_COLORS = {"HR+/HER2-": BLUE, "HR+/HER2+": ORANGE, "HR-/HER2+": AQUA, "Triple negative": YELLOW,
                  "Unknown": DE_EMPHASIS}
SITE_TYPE_COLORS = {"Academic medical center": BLUE, "Cancer center": ORANGE, "Community health system": AQUA,
                    "Military medical center": YELLOW, "Biorepository / research institute": MAGENTA,
                    "Unclassified": DE_EMPHASIS}
STAGE_ORDER = ["I", "II", "III", "IV"]
STAGE_COLORS = {"I": "#86b6ef", "II": "#5598e7", "III": "#256abf", "IV": "#104281", "0": "#b7d3f6",
                "Unknown": DE_EMPHASIS}                                      # ordinal ramp (validated)
AGE_ORDER = ["<40", "40-49", "50-64", "65-74", "75+"]
AGE_COLORS = dict(zip(AGE_ORDER, ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"], strict=True))  # ordinal
COST_COMPONENT_COLORS = {"Drug": BLUE, "Administration": ORANGE, "Radiation": AQUA, "Surgery": YELLOW}
OUTCOME_COLORS = {"Deceased": STATUS["critical"], "Recurrence / progression": STATUS["serious"],
                  "Alive, no recurrence recorded": STATUS["good"]}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

pio.templates["oncoinsight"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=INK_2, size=13), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=SERIES,
    xaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, ticks=""),
    yaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, ticks=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font_color=INK_2),
    hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(color=INK, family=FONT)),
    margin=dict(l=10, r=10, t=84, b=10), bargap=0.35,
    title=dict(font=dict(color=INK, size=15), x=0, xanchor="left", xref="paper", y=1, yanchor="top",
               yref="container", pad=dict(t=10)),
))
pio.templates.default = "oncoinsight"

DISCLAIMER = ("Real public research data (TCGA-BRCA via NCI GDC, TCGA PanCancer CDR, METABRIC via cBioPortal). "
              "Observational associations only · costs are CMS 2026 reference-price estimates · not for clinical use.")

CSS = f"""
<style>
  .stApp {{ background: {PAGE}; }}
  section[data-testid="stSidebar"] > div {{ background: linear-gradient(180deg, #0d366b 0%, #184f95 50%, #4a3aa7 100%); }}
  section[data-testid="stSidebar"] * {{ color: #ffffff !important; }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(255,255,255,0.18) !important; }}
  .oi-hero {{ border-radius: 18px; padding: 26px 30px 22px 30px; margin: 0 0 16px 0; color: #fff;
             background: linear-gradient(115deg, #0d366b 0%, #2a78d6 42%, #4a3aa7 78%, #e87ba4 118%);
             box-shadow: 0 8px 24px rgba(13,54,107,0.18); }}
  .oi-hero .kicker {{ text-transform: uppercase; letter-spacing: .12em; font-size: 12px; opacity: .85; }}
  .oi-hero h1 {{ color: #fff; font-size: 32px; line-height: 1.15; margin: 6px 0 8px 0; padding: 0; }}
  .oi-hero p {{ color: rgba(255,255,255,.93); font-size: 15.5px; margin: 0; max-width: 1000px; }}
  .oi-hero .chips span {{ display: inline-block; margin: 12px 8px 0 0; padding: 4px 11px; border-radius: 999px;
             background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28); font-size: 12.5px; }}
  .oi-card {{ background: {SURFACE}; border: 1px solid rgba(11,11,11,.08); border-radius: 14px; padding: 14px 16px 12px 16px;
             border-top: 5px solid var(--accent); box-shadow: 0 2px 8px rgba(11,11,11,.04); min-height: 112px; }}
  .oi-card .lab {{ color: {INK_2}; font-size: 13px; }}
  .oi-card .val {{ color: {INK}; font-size: 27px; font-weight: 650; line-height: 1.2; margin-top: 4px; }}
  .oi-card .sub {{ color: {MUTED}; font-size: 12.5px; margin-top: 2px; }}
  .oi-section {{ display: flex; align-items: center; gap: 10px; margin: 24px 0 6px 0; }}
  .oi-section .bar {{ width: 6px; height: 26px; border-radius: 3px; background: var(--accent); }}
  .oi-section h3 {{ margin: 0; padding: 0; color: {INK}; font-size: 21px; }}
  .oi-note {{ border-radius: 12px; padding: 12px 16px; margin: 6px 0 12px 0; background: {SURFACE};
             border: 1px solid rgba(11,11,11,.08); border-left: 5px solid var(--accent); color: {INK_2}; font-size: 14.5px; }}
  .oi-note b {{ color: {INK}; }}
  .oi-pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12.5px; margin: 2px 4px 2px 0;
             border: 1px solid rgba(11,11,11,.12); background: {SURFACE}; color: {INK}; }}
  .oi-pill i {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; background: var(--dot); }}
  .oi-cohort {{ font-size: 13.5px; color: {INK_2}; margin: -6px 0 6px 0; }}
  .oi-step {{ background: {SURFACE}; border-radius: 14px; padding: 14px 16px; border: 1px solid rgba(11,11,11,.08);
             border-left: 6px solid var(--accent); margin-bottom: 10px; }}
  .oi-step .n {{ font-size: 12px; font-weight: 700; color: var(--accent); letter-spacing: .08em; }}
  .oi-step .t {{ font-size: 17px; font-weight: 650; color: {INK}; margin: 2px 0 4px 0; }}
  .oi-step .d {{ font-size: 14px; color: {INK_2}; }}
  div[data-testid="stTabs"] button[aria-selected="true"] p {{ color: {BLUE}; font-weight: 650; }}
  div[data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid rgba(11,11,11,.08); border-radius: 12px; padding: 10px 14px; }}
</style>
"""


# ------------------------------------------------------------------ components
def page_setup(title: str, subtitle: str = "", kicker: str = "OncoInsight", chips: list[str] | None = None) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    chip_html = "".join(f"<span>{html.escape(c)}</span>" for c in (chips or []))
    st.markdown(f"""<div class="oi-hero"><div class="kicker">{html.escape(kicker)}</div>
        <h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p><div class="chips">{chip_html}</div></div>""",
                unsafe_allow_html=True)


def kpi_cards(items: list[dict], columns: int | None = None) -> None:
    """items: {label, value, sub?, color?, icon?}. The accent colour is decoration; values stay in ink."""
    cols = st.columns(columns or len(items))
    for col, it in zip(cols, items, strict=False):
        col.markdown(f"""<div class="oi-card" style="--accent:{it.get('color', BLUE)}">
            <div class="lab">{it.get('icon', '')} {html.escape(str(it['label']))}</div>
            <div class="val">{html.escape(str(it['value']))}</div>
            <div class="sub">{html.escape(str(it.get('sub', '')))}</div></div>""", unsafe_allow_html=True)


def section(title: str, color: str = BLUE, icon: str = "") -> None:
    st.markdown(f"""<div class="oi-section" style="--accent:{color}"><div class="bar"></div>
        <h3>{icon} {html.escape(title)}</h3></div>""", unsafe_allow_html=True)


def note(text_html: str, color: str = BLUE) -> None:
    """Explanatory callout ('why this matters'). text_html is authored in code, never user/data text."""
    st.markdown(f'<div class="oi-note" style="--accent:{color}">{text_html}</div>', unsafe_allow_html=True)


def step(n: int, title: str, text: str, color: str = BLUE) -> None:
    st.markdown(f"""<div class="oi-step" style="--accent:{color}"><div class="n">STEP {n}</div>
        <div class="t">{html.escape(title)}</div><div class="d">{text}</div></div>""", unsafe_allow_html=True)


def pills(mapping: dict[str, str]) -> None:
    st.markdown("".join(f'<span class="oi-pill" style="--dot:{c}"><i></i>{html.escape(k)}</span>'
                        for k, c in mapping.items()), unsafe_allow_html=True)


# ------------------------------------------------------------------ data access
@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Read-only query (onco_reader role)."""
    return read_sql(sql, params, readonly=True)


def patients() -> pd.DataFrame:
    return query("select * from marts.mart_patient_360")


# ------------------------------------------------------------------ cohort filters (one row, above the charts)
_WIDGETS = {"f_years": "w_years", "f_stage": "w_stage", "f_subtype": "w_subtype", "f_age": "w_age", "f_site": "w_site"}


def cohort_filters(label: str = "TCGA-BRCA patients") -> dict:
    """One row of cohort filters shared by every page. Values persist across page navigation (Streamlit drops
    widget state for widgets not rendered on a page, so the values are mirrored into plain session keys)."""
    p = patients()
    ymin, ymax = int(p.year_of_diagnosis.min()), int(p.year_of_diagnosis.max())
    s = st.session_state
    defaults = {"f_years": (ymin, ymax), "f_stage": [], "f_subtype": [], "f_age": [], "f_site": []}
    for k, v in defaults.items():
        s.setdefault(k, v)
    c = st.columns([2.2, 1.2, 1.7, 1.4, 1.9, 0.7])
    years = c[0].slider("🗓️ Diagnosis year", ymin, ymax, value=tuple(s["f_years"]), key="w_years")
    stage = c[1].multiselect("Stage", STAGE_ORDER + ["Unknown"], default=s["f_stage"], key="w_stage")
    subtype = c[2].multiselect("Receptor subtype", list(SUBTYPE_COLORS), default=s["f_subtype"], key="w_subtype")
    age = c[3].multiselect("Age group", AGE_ORDER, default=s["f_age"], key="w_age")
    site = c[4].multiselect("Site type", list(SITE_TYPE_COLORS)[:-1], default=s["f_site"], key="w_site")
    c[5].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if c[5].button("Reset", use_container_width=True, help="Clear all cohort filters"):
        for k, w in _WIDGETS.items():
            s[k] = defaults[k]
            s.pop(w, None)
        st.rerun()
    s["f_years"], s["f_stage"], s["f_subtype"], s["f_age"], s["f_site"] = tuple(years), stage, subtype, age, site
    f = {"years": tuple(years), "year_bounds": (ymin, ymax), "stage": stage, "subtype": subtype, "age": age, "site": site}
    n = len(apply_filters(p, f))
    active = sum(bool(f[k]) for k in ("stage", "subtype", "age", "site")) + (tuple(years) != (ymin, ymax))
    st.markdown(f"<div class='oi-cohort'>👥 Cohort: <b>{n:,}</b> of {len(p):,} {label}"
                f"{' · <b>' + str(active) + '</b> filter(s) active - every chart below uses this cohort' if active else ' · no filters applied'}</div>",
                unsafe_allow_html=True)
    return f


def apply_filters(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply the cohort filters to any frame carrying the relevant columns."""
    out = df
    if f.get("years") and "year_of_diagnosis" in out.columns and tuple(f["years"]) != f.get("year_bounds"):
        lo, hi = f["years"]  # only filter when narrowed, so patients without a diagnosis year aren't dropped
        out = out[out.year_of_diagnosis.between(lo, hi)]
    for key, col in (("stage", "stage_major"), ("subtype", "receptor_subtype"), ("age", "age_group"),
                     ("site", "site_type")):
        if f.get(key) and col in out.columns:
            out = out[out[col].isin(f[key])]
    return out


def small_cohort_guard(n: int, minimum: int = 11) -> bool:
    if n < minimum:
        st.warning(f"This cohort has {n} patients - statistics are suppressed below {minimum} (small-cell rule). "
                   "Widen the filters above.")
        return False
    return True


# ------------------------------------------------------------------ rendering helpers
def show(fig: go.Figure, key: str | None = None, select: bool = False):
    """Render with explicit house-style layout (Streamlit's chart theming overrides template defaults).
    With select=True the chart is clickable and the selection event is returned."""
    fig.update_layout(paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(family=FONT, color=INK_2, size=13))
    fig.update_xaxes(automargin=True, gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    fig.update_yaxes(automargin=True, gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    if select:
        return st.plotly_chart(fig, use_container_width=True, theme=None, key=key, on_select="rerun",
                               selection_mode=("points",))
    st.plotly_chart(fig, use_container_width=True, theme=None, key=key)
    return None


def selected_points(event) -> list[dict]:
    """Points clicked in a plotly chart rendered with show(..., select=True)."""
    if not event:
        return []
    sel = event.get("selection") if isinstance(event, dict) else getattr(event, "selection", None)
    if not sel:
        return []
    return list(sel.get("points", []) if isinstance(sel, dict) else getattr(sel, "points", []))


def table(df: pd.DataFrame, label: str = "Data table") -> None:
    with st.expander(f"🗂️ {label}"):
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"{label.lower().replace(' ', '_')}.csv", mime="text/csv",
                           key=f"dl_{label}_{len(df)}_{len(df.columns)}")


def fmt_usd(v: float | None, signed: bool = False) -> str:
    """$950 · $15.3K · $16.8M, with a leading sign for negatives (and '+' when signed=True)."""
    if v is None or pd.isna(v):
        return "—"
    sign = "-" if v < 0 else ("+" if signed and v > 0 else "")
    a = abs(v)
    body = f"${a / 1e6:,.2f}M" if a >= 1e6 else (f"${a / 1e3:,.1f}K" if a >= 1e3 else f"${a:,.0f}")
    return sign + body


def footer() -> None:
    st.divider()
    st.caption(DISCLAIMER)
