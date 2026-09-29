"""Shared dashboard theme, UI components, cohort filters and data access.

Design: calm and minimal. Neutral surfaces, one muted rose accent for the UI, and a muted data palette.
Colour system (validated with the dataviz palette validator against a white surface):
* Categorical slots in fixed order - colour follows the ENTITY (Chemotherapy is always terracotta), never its rank.
* Ordered categories (stage, age group) use a single-hue slate-blue ramp (validated with --ordinal).
* Status colours (good / warning / serious / critical) are reserved for alerts and flags, always with a label.
Slot 4 (ochre) is below 3:1 contrast on the surface, so charts carry direct labels, tooltips and a table view.
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from oncoinsight.common.db import read_sql

# ------------------------------------------------------------------ palette
SURFACE = "#ffffff"
PAGE = "#f7f7f5"
INK = "#1c1f24"
INK_2 = "#4b5563"
MUTED = "#8b9099"
GRID = "#ecebe7"
AXIS = "#d4d2cc"
DE_EMPHASIS = "#c9c7c1"
ACCENT = "#a8456b"          # muted rose: UI accent only (links, active nav, highlights), never a data series

SERIES = ["#3b6ea8", "#d0643c", "#2f9a7e", "#d19a1e", "#c8628b", "#5f8a2e", "#6a5aa8", "#b8433f"]
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = SERIES
STATUS = {"good": "#3f8f5f", "warning": "#d9a52b", "serious": "#d17a4a", "critical": "#b83c3c"}
SEQ_BLUE = ["#dde7f3", "#bccfe7", "#93b1d6", "#6590c4", "#3b6ea8", "#2a5285", "#1b3a61"]
# diverging blue <-> red with a neutral grey midpoint ("better" <-> "worse" than the network)
DIVERGING = [[0, "#2a5285"], [0.25, "#93b1d6"], [0.5, "#f1f0ed"], [0.75, "#e0a089"], [1, "#b83c3c"]]

MODALITY_COLORS = {"Surgery": BLUE, "Chemotherapy": ORANGE, "Radiation": AQUA, "Endocrine": YELLOW,
                   "HER2-targeted": MAGENTA, "Other systemic": GREEN}
SUBTYPE_COLORS = {"HR+/HER2-": BLUE, "HR+/HER2+": ORANGE, "HR-/HER2+": AQUA, "Triple negative": YELLOW,
                  "Unknown": DE_EMPHASIS}
SITE_TYPE_COLORS = {"Academic medical center": BLUE, "Cancer center": ORANGE, "Community health system": AQUA,
                    "Military medical center": YELLOW, "Biorepository / research institute": MAGENTA,
                    "Unclassified": DE_EMPHASIS}
STAGE_ORDER = ["I", "II", "III", "IV"]
STAGE_COLORS = {"I": "#93b1d6", "II": "#6590c4", "III": "#3b6ea8", "IV": "#1b3a61", "0": "#bccfe7",
                "Unknown": DE_EMPHASIS}                                      # ordinal ramp (validated)
AGE_ORDER = ["<40", "40-49", "50-64", "65-74", "75+"]
AGE_COLORS = dict(zip(AGE_ORDER, ["#93b1d6", "#6590c4", "#3b6ea8", "#2a5285", "#1b3a61"], strict=True))  # ordinal
# plain-English display names for treatment groups (data values stay unchanged)
MODALITY_LABELS = {"Endocrine": "Hormone therapy", "HER2-targeted": "HER2-targeted drugs", "Other systemic": "Other drugs"}


def plain(text: str) -> str:
    """Swap treatment-group jargon for plain names inside any label, e.g. 'Surgery → Endocrine'."""
    for k, v in MODALITY_LABELS.items():
        text = text.replace(k, v)
    return text


COST_COMPONENT_COLORS = {"Drug": BLUE, "Administration": ORANGE, "Radiation": AQUA, "Surgery": YELLOW}
OUTCOME_COLORS = {"Deceased": STATUS["critical"], "Recurrence / progression": STATUS["serious"],
                  "Alive, no recurrence recorded": STATUS["good"]}

FONT = 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif'

pio.templates["oncoinsight"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=INK_2, size=13), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=SERIES,
    xaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, ticks=""),
    yaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, ticks=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font_color=INK_2),
    hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(color=INK, family=FONT)),
    margin=dict(l=10, r=10, t=64, b=10), bargap=0.35,
    title=dict(font=dict(color=INK, size=14), x=0, xanchor="left", xref="paper", y=1, yanchor="top",
               yref="container", pad=dict(t=10)),
))
pio.templates.default = "oncoinsight"

DISCLAIMER = ("Real, public, de-identified research data (TCGA breast cancer study via the NCI Genomic Data Commons, "
              "and the METABRIC study via cBioPortal). Shows patterns, not cause and effect. Costs are estimates "
              "from 2026 Medicare prices. Not for clinical use.")

CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, .stApp, .stMarkdown, button, input, textarea {{ font-family: {FONT}; }}
  .stApp {{ background: {PAGE}; }}
  .block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
  section[data-testid="stSidebar"] > div {{ background: #fbfaf8; border-right: 1px solid {GRID}; }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{ color: {INK_2}; }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: #f3e9ed !important; }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: {ACCENT}; font-weight: 600; }}
  section[data-testid="stSidebar"] header, section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {{
      color: {MUTED}; text-transform: uppercase; letter-spacing: .08em; font-size: 11px; }}
  h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}
  .oi-head {{ margin: 0 0 18px 0; }}
  .oi-head .kicker {{ color: {ACCENT}; text-transform: uppercase; letter-spacing: .12em; font-size: 11.5px; font-weight: 600; }}
  .oi-head h1 {{ font-size: 30px; line-height: 1.2; font-weight: 650; margin: 4px 0 6px 0; padding: 0; }}
  .oi-head p {{ color: {INK_2}; font-size: 15.5px; margin: 0; max-width: 860px; line-height: 1.55; }}
  .oi-qa {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin: 4px 0 20px 0; background: {SURFACE};
            border: 1px solid {GRID}; border-radius: 12px; overflow: hidden; }}
  .oi-qa > div {{ padding: 14px 18px; }}
  .oi-qa > div + div {{ border-left: 1px solid {GRID}; }}
  .oi-qa .lab {{ color: {MUTED}; text-transform: uppercase; letter-spacing: .08em; font-size: 11px; font-weight: 600; }}
  .oi-qa .txt {{ color: {INK}; font-size: 15px; margin-top: 4px; line-height: 1.5; }}
  @media (max-width: 800px) {{ .oi-qa {{ grid-template-columns: 1fr; }} .oi-qa > div + div {{ border-left: 0; border-top: 1px solid {GRID}; }} }}
  .oi-card {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 12px; padding: 14px 16px 12px 16px; min-height: 104px; }}
  .oi-card .lab {{ color: {INK_2}; font-size: 13px; line-height: 1.35; }}
  .oi-card .val {{ color: {INK}; font-size: 26px; font-weight: 650; line-height: 1.2; margin-top: 6px; letter-spacing: -0.01em; }}
  .oi-card .sub {{ color: {MUTED}; font-size: 12.5px; margin-top: 3px; line-height: 1.35; }}
  .oi-section {{ margin: 30px 0 4px 0; }}
  .oi-section h3 {{ margin: 0; padding: 0; color: {INK}; font-size: 19px; font-weight: 650; }}
  .oi-section p {{ margin: 4px 0 0 0; color: {INK_2}; font-size: 14.5px; max-width: 900px; }}
  .oi-note {{ border-radius: 10px; padding: 12px 16px; margin: 6px 0 14px 0; background: {SURFACE};
             border: 1px solid {GRID}; border-left: 3px solid {ACCENT}; color: {INK_2}; font-size: 14.5px; line-height: 1.55; }}
  .oi-note b {{ color: {INK}; }}
  .oi-read {{ color: {INK_2}; font-size: 13.5px; margin: -4px 0 12px 0; line-height: 1.5; }}
  .oi-read b {{ color: {INK}; font-weight: 600; }}
  .oi-pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12.5px; margin: 2px 4px 2px 0;
             border: 1px solid {GRID}; background: {SURFACE}; color: {INK}; }}
  .oi-pill i {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; background: var(--dot); }}
  .oi-cohort {{ font-size: 13px; color: {MUTED}; margin: -6px 0 10px 0; }}
  .oi-step {{ background: {SURFACE}; border-radius: 12px; padding: 14px 16px; border: 1px solid {GRID}; margin-bottom: 10px; }}
  .oi-step .n {{ font-size: 11px; font-weight: 600; color: {ACCENT}; letter-spacing: .1em; }}
  .oi-step .t {{ font-size: 16px; font-weight: 650; color: {INK}; margin: 2px 0 4px 0; }}
  .oi-step .d {{ font-size: 14px; color: {INK_2}; line-height: 1.5; }}
  div[data-testid="stTabs"] button[aria-selected="true"] p {{ color: {ACCENT}; font-weight: 600; }}
  div[data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 12px; padding: 10px 14px; }}
  div[data-testid="stExpander"] details {{ border: 1px solid {GRID}; border-radius: 10px; background: {SURFACE}; }}
  [data-testid="stHeader"] {{ background: transparent; }}
</style>
"""


# ------------------------------------------------------------------ components
def page_setup(title: str, subtitle: str = "", kicker: str = "OncoInsight", chips: list[str] | None = None,
               question: str = "", answer: str = "") -> None:
    """Page header: a plain-English title, one line of context, and an optional question / short-answer panel.
    (`chips` is accepted for backwards compatibility and ignored - the header stays minimal.)"""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"""<div class="oi-head"><div class="kicker">{html.escape(kicker)}</div>
        <h1>{html.escape(title)}</h1><p>{subtitle}</p></div>""", unsafe_allow_html=True)
    if question or answer:
        st.markdown(f"""<div class="oi-qa"><div><div class="lab">The question</div><div class="txt">{question}</div></div>
            <div><div class="lab">The short answer</div><div class="txt">{answer}</div></div></div>""",
                    unsafe_allow_html=True)


def kpi_cards(items: list[dict], columns: int | None = None) -> None:
    """items: {label, value, sub?}. Cards are deliberately uniform (`color` / `icon` are accepted and ignored)."""
    cols = st.columns(columns or len(items))
    for col, it in zip(cols, items, strict=False):
        col.markdown(f"""<div class="oi-card">
            <div class="lab">{html.escape(str(it['label']))}</div>
            <div class="val">{html.escape(str(it['value']))}</div>
            <div class="sub">{html.escape(str(it.get('sub', '')))}</div></div>""", unsafe_allow_html=True)


def section(title: str, color: str = BLUE, icon: str = "", blurb: str = "") -> None:
    """Section heading with an optional one-sentence explanation (`color` / `icon` kept for compatibility)."""
    p = f"<p>{blurb}</p>" if blurb else ""
    st.markdown(f'<div class="oi-section"><h3>{html.escape(title)}</h3>{p}</div>', unsafe_allow_html=True)


def note(text_html: str, color: str = BLUE) -> None:
    """Explanatory callout ('why this matters'). text_html is authored in code, never user/data text."""
    st.markdown(f'<div class="oi-note">{text_html}</div>', unsafe_allow_html=True)


def how_to_read(text_html: str) -> None:
    """One-line 'how to read this chart' caption shown under a chart. Authored in code, never data text."""
    st.markdown(f'<div class="oi-read"><b>How to read this:</b> {text_html}</div>', unsafe_allow_html=True)


def step(n: int, title: str, text: str, color: str = BLUE) -> None:
    st.markdown(f"""<div class="oi-step"><div class="n">STEP {n}</div>
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


def cohort_filters(label: str = "patients") -> dict:
    """One row of cohort filters shared by every page. Values persist across page navigation (Streamlit drops
    widget state for widgets not rendered on a page, so the values are mirrored into plain session keys)."""
    p = patients()
    ymin, ymax = int(p.year_of_diagnosis.min()), int(p.year_of_diagnosis.max())
    s = st.session_state
    defaults = {"f_years": (ymin, ymax), "f_stage": [], "f_subtype": [], "f_age": [], "f_site": []}
    for k, v in defaults.items():
        s.setdefault(k, v)
    c = st.columns([2.2, 1.2, 1.7, 1.4, 1.9, 0.7])
    years = c[0].slider("Year diagnosed", ymin, ymax, value=tuple(s["f_years"]), key="w_years")
    stage = c[1].multiselect("Cancer stage", STAGE_ORDER + ["Unknown"], default=s["f_stage"], key="w_stage")
    subtype = c[2].multiselect("Tumour type", list(SUBTYPE_COLORS), default=s["f_subtype"], key="w_subtype")
    age = c[3].multiselect("Age group", AGE_ORDER, default=s["f_age"], key="w_age")
    site = c[4].multiselect("Hospital type", list(SITE_TYPE_COLORS)[:-1], default=s["f_site"], key="w_site")
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
    st.markdown(f"<div class='oi-cohort'>Showing <b>{n:,}</b> of {len(p):,} {label}"
                f"{' · ' + str(active) + ' filter(s) on - every chart on every page uses them' if active else ' · filters apply to every page'}</div>",
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
        st.warning(f"Only {n} patients match these filters. To protect privacy and avoid misleading numbers, results "
                   f"are hidden for groups smaller than {minimum}. Widen the filters above.")
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
    with st.expander(f"See the data: {label}"):
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False).encode(),
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
