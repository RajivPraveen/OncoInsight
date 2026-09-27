import pandas as pd
import streamlit as st
from charts import forest, km_compare, km_from_table
from theme import (
    AGE_ORDER,
    BLUE,
    MAGENTA,
    ORANGE,
    STAGE_ORDER,
    SUBTYPE_COLORS,
    VIOLET,
    footer,
    kpi_cards,
    note,
    page_setup,
    query,
    show,
    table,
)

from oncoinsight.analytics.cohorts import compare_cohorts, filter_frame

page_setup("Survival & cohort lab", "Kaplan-Meier survival by clinical group, adjusted Cox models, and a live lab "
           "where you build any two cohorts and compare their survival instantly.", kicker="Outcomes",
           chips=["TCGA PanCancer CDR endpoints", "METABRIC 10-year follow-up", "log-rank · RMST · Cox PH"])

tab_lab, tab_km, tab_cox = st.tabs(["🧪 Cohort lab (live)", "📈 Survival curves", "🌲 Cox models"])

# ------------------------------------------------------------------ cohort lab
with tab_lab:
    surv = query("select * from marts.mart_survival")
    endpoints = {"Overall survival (OS)": ("os_months", "os_event"),
                 "Disease-specific survival (DSS)": ("dss_months", "dss_event"),
                 "Progression-free interval (PFI)": ("pfs_months", "pfs_event")}
    presets = {
        "Custom": ({}, {}),
        "Chemo started ≤ 90 vs > 90 days": ({"chemo_timing_group": ["0-30 days", "31-60 days", "61-90 days"]},
                                            {"chemo_timing_group": [">90 days"]}),
        "Triple negative vs HR+/HER2-": ({"receptor_subtype": ["Triple negative"]}, {"receptor_subtype": ["HR+/HER2-"]}),
        "Stage II vs stage III": ({"stage_major": ["II"]}, {"stage_major": ["III"]}),
        "Age < 50 vs 75+": ({"age_group": ["<40", "40-49"]}, {"age_group": ["75+"]}),
        "Received radiation vs not (stage I–III)": ({"received_radiation": [True], "stage_major": ["I", "II", "III"]},
                                                     {"received_radiation": [False], "stage_major": ["I", "II", "III"]}),
    }
    c = st.columns([2, 2, 1])
    preset = c[0].selectbox("Start from a preset", list(presets))
    ep = c[1].selectbox("Endpoint", list(endpoints))
    horizon = c[2].select_slider("RMST horizon (months)", [36, 60, 120], value=60)
    pa, pb = presets[preset]

    def cohort_form(col, title: str, init: dict, key: str) -> dict:
        with col:
            st.markdown(f"**{title}**")
            r1, r2 = st.columns(2), st.columns(3)
            return {
                "stage_major": r1[0].multiselect("Stage", STAGE_ORDER, default=init.get("stage_major", []), key=f"{key}_st"),
                "receptor_subtype": r1[1].multiselect("Subtype", [s for s in SUBTYPE_COLORS if s != "Unknown"],
                                                      default=init.get("receptor_subtype", []), key=f"{key}_sub"),
                "age_group": r2[0].multiselect("Age group", AGE_ORDER, default=init.get("age_group", []), key=f"{key}_age"),
                "chemo_timing_group": r2[1].multiselect("Chemo timing", ["Neoadjuvant", "0-30 days", "31-60 days", "61-90 days", ">90 days"],
                                                        default=init.get("chemo_timing_group", []), key=f"{key}_ct"),
                "received_radiation": r2[2].multiselect("Radiation", [True, False],
                                                        default=init.get("received_radiation", []), key=f"{key}_rt"),
            }

    ca, cb = st.columns(2)
    fa = cohort_form(ca, "🔵 Cohort A", pa, f"A_{preset}")
    fb = cohort_form(cb, "🟠 Cohort B", pb, f"B_{preset}")
    t, e = endpoints[ep]
    A, B = filter_frame(surv, fa), filter_frame(surv, fb)
    comp = compare_cohorts(A, B, t, e, "Cohort A", "Cohort B", horizon, ep.split("(")[1].rstrip(")"))
    if comp.a.n < 11 or comp.b.n < 11:
        st.warning("Each cohort needs at least 11 patients - adjust the filters.")
    else:
        def pct(v):
            return f"{v:.1%}" if v is not None else "not reached"

        kpi_cards([
            {"label": "Cohort A · n / events", "value": f"{comp.a.n} / {comp.a.events}", "sub": f"5-yr {pct(comp.a.survival_at.get(60))}", "color": BLUE, "icon": "🔵"},
            {"label": "Cohort B · n / events", "value": f"{comp.b.n} / {comp.b.events}", "sub": f"5-yr {pct(comp.b.survival_at.get(60))}", "color": ORANGE, "icon": "🟠"},
            {"label": f"RMST difference ({horizon} mo)", "value": f"{comp.rmst_difference:+.1f} mo" if comp.rmst_difference is not None else "—",
             "sub": "A minus B: extra event-free months", "color": VIOLET, "icon": "⏳"},
            {"label": "Log-rank p", "value": f"{comp.logrank_p:.3g}" if comp.logrank_p is not None else "—",
             "sub": "significant" if (comp.logrank_p or 1) < 0.05 else "not significant at 0.05", "color": MAGENTA, "icon": "🧮"},
        ])
        show(km_compare(comp), key="lab_km")
        note("<b>How to read this.</b> Each step down is an event. Shaded bands are 95% confidence intervals, so "
             "overlapping bands mean the data can't clearly separate the cohorts. <b>RMST</b> is the average "
             f"event-free time within {horizon} months; the difference is easy to explain (\"cohort A lived on average "
             "X months longer within 5 years\") and doesn't need the proportional-hazards assumption. These are "
             "unadjusted comparisons: use the Cox models tab for adjusted associations.", VIOLET)

# ------------------------------------------------------------------ precomputed curves
with tab_km:
    opts = query("select distinct cohort, endpoint, stratifier from analytics.km_summary order by 1,2,3")
    c = st.columns(3)
    cohort = c[0].selectbox("Cohort", sorted(opts.cohort.unique(), key=lambda x: x != "TCGA-BRCA"))
    eps = sorted(opts[opts.cohort == cohort].endpoint.unique(), key=lambda x: x != "OS")
    endpoint = c[1].selectbox("Endpoint", eps, key="km_ep")
    strats = opts[(opts.cohort == cohort) & (opts.endpoint == endpoint)].stratifier.unique().tolist()
    strat = c[2].selectbox("Compare by", strats, index=strats.index("stage_major") if "stage_major" in strats else 0)
    prm = {"c": cohort, "e": endpoint, "s": strat}
    curves = query("select * from analytics.km_curves where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s order by 1", prm)
    summ = query("select * from analytics.km_summary where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s", prm)
    summ = summ.sort_values("n", ascending=False).head(8)
    curves = curves[curves.group_value.isin(summ.group_value)]
    show(km_from_table(curves, summ, strat, f"Kaplan-Meier {endpoint} by {strat.replace('_', ' ')} ({cohort})",
                       180 if cohort == "TCGA-BRCA" else 240), key="km")
    test = query("select * from analytics.logrank_tests where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s", prm)
    if len(test):
        tt = test.iloc[0]
        st.markdown(f"**Log-rank test:** χ² = {tt.test_statistic:.1f}, df = {int(tt.degrees_of_freedom)}, p = {tt.p_value:.2g} (n = {int(tt.n)})")
    st.dataframe(summ[["group_value", "n", "events", "median_survival_months", "survival_5y", "survival_5y_ci_lower",
                       "survival_5y_ci_upper", "survival_10y"]].style.format(
        {"survival_5y": "{:.1%}", "survival_5y_ci_lower": "{:.1%}", "survival_5y_ci_upper": "{:.1%}",
         "survival_10y": "{:.1%}", "median_survival_months": "{:.1f}"}, na_rep="—"), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ cox
with tab_cox:
    fits = query("select * from analytics.cox_model_fit where status = 'fitted'")
    model = st.selectbox("Model", fits.model.tolist())
    fm = fits[fits.model == model].iloc[0]
    kpi_cards([
        {"label": "Patients", "value": f"{int(fm.n):,}", "color": BLUE, "icon": "👥"},
        {"label": "Events", "value": f"{int(fm.events):,}", "sub": f"{fm.events_per_variable:.1f} per covariate", "color": ORANGE, "icon": "📍"},
        {"label": "C-index", "value": f"{fm.concordance:.3f}", "sub": "0.5 = chance, 1 = perfect ranking", "color": MAGENTA, "icon": "🎯"},
        {"label": "Likelihood-ratio p", "value": f"{fm.log_likelihood_ratio_p:.2g}", "color": VIOLET, "icon": "🧮"},
    ])
    if isinstance(fm.caution, str) and fm.caution:
        st.warning(f"Interpret with caution: {fm.caution} ({fm.events_per_variable:.1f} events per covariate; guideline ≥ 10).")
    co = query("select * from analytics.cox_coefficients where model = %(m)s", {"m": model})
    show(forest(co, "covariate", "hazard_ratio", "ci_lower", "ci_upper",
                title="Adjusted hazard ratios - red: higher hazard, blue: lower, grey: not significant (p ≥ 0.05)"), key="cox")
    ph = query("select covariate, test_statistic, p_value, ph_assumption_ok from analytics.cox_ph_tests where model=%(m)s", {"m": model})
    bad = ph[~ph.ph_assumption_ok.astype(bool)] if len(ph) else pd.DataFrame()
    if len(bad):
        st.info("Proportional-hazards assumption questionable (Schoenfeld p < 0.05) for: " + ", ".join(bad.covariate))
    table(co, "Coefficients")
    note("Treatment indicators are <b>confounded by indication</b>: sicker patients receive more treatment. "
         "Hazard ratios are adjusted associations, not causal treatment effects.", MAGENTA)
footer()
