import pandas as pd
import streamlit as st
from charts import forest, km_compare, km_from_table
from theme import (
    AGE_ORDER,
    STAGE_ORDER,
    SUBTYPE_COLORS,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    query,
    show,
    table,
)

from oncoinsight.analytics.cohorts import compare_cohorts, filter_frame

page_setup("Survival",
           "How patients do in the years after diagnosis, and which factors make the biggest difference.",
           kicker="Results",
           question="Do patients who wait longer, or who have certain tumour types, live shorter lives?",
           answer="Stage matters most: about <b>91%</b> of stage I patients are alive after 5 years, versus "
                  "<b>27%</b> at stage IV. Triple-negative tumours have the lowest survival of the tumour types.")

tab_lab, tab_km, tab_cox = st.tabs(["Compare two groups", "Survival by group", "What matters most"])

# ------------------------------------------------------------------ cohort lab
with tab_lab:
    surv = query("select * from marts.mart_survival")
    endpoints = {"Still alive (OS)": ("os_months", "os_event"),
                 "Not died of breast cancer (DSS)": ("dss_months", "dss_event"),
                 "Cancer hasn't grown or returned (PFI)": ("pfs_months", "pfs_event")}
    presets = {
        "Custom": ({}, {}),
        "Chemo within 90 days vs. after 90 days": ({"chemo_timing_group": ["0-30 days", "31-60 days", "61-90 days"]},
                                            {"chemo_timing_group": [">90 days"]}),
        "Triple negative vs. HR+/HER2-": ({"receptor_subtype": ["Triple negative"]}, {"receptor_subtype": ["HR+/HER2-"]}),
        "Stage II vs. stage III": ({"stage_major": ["II"]}, {"stage_major": ["III"]}),
        "Under 50 vs. 75 and over": ({"age_group": ["<40", "40-49"]}, {"age_group": ["75+"]}),
        "Had radiation vs. didn't (stage I–III)": ({"received_radiation": [True], "stage_major": ["I", "II", "III"]},
                                                     {"received_radiation": [False], "stage_major": ["I", "II", "III"]}),
    }
    st.markdown("Pick two groups of patients and see how their survival compares over time.")
    c = st.columns([2, 2, 1])
    preset = c[0].selectbox("Start from an example", list(presets), index=1)
    ep = c[1].selectbox("Measure", list(endpoints))
    horizon = c[2].select_slider("Look over (months)", [36, 60, 120], value=60)
    pa, pb = presets[preset]

    def cohort_form(col, title: str, init: dict, key: str) -> dict:
        with col:
            st.markdown(f"**{title}**")
            r1, r2 = st.columns(2), st.columns(3)
            return {
                "stage_major": r1[0].multiselect("Cancer stage", STAGE_ORDER, default=init.get("stage_major", []), key=f"{key}_st"),
                "receptor_subtype": r1[1].multiselect("Tumour type", [s for s in SUBTYPE_COLORS if s != "Unknown"],
                                                      default=init.get("receptor_subtype", []), key=f"{key}_sub"),
                "age_group": r2[0].multiselect("Age group", AGE_ORDER, default=init.get("age_group", []), key=f"{key}_age"),
                "chemo_timing_group": r2[1].multiselect("When chemo started", ["Neoadjuvant", "0-30 days", "31-60 days", "61-90 days", ">90 days"],
                                                        default=init.get("chemo_timing_group", []), key=f"{key}_ct"),
                "received_radiation": r2[2].multiselect("Radiation", [True, False],
                                                        default=init.get("received_radiation", []), key=f"{key}_rt"),
            }

    ca, cb = st.columns(2)
    fa = cohort_form(ca, "Group A (blue)", pa, f"A_{preset}")
    fb = cohort_form(cb, "Group B (orange)", pb, f"B_{preset}")
    t, e = endpoints[ep]
    A, B = filter_frame(surv, fa), filter_frame(surv, fb)
    comp = compare_cohorts(A, B, t, e, "Group A", "Group B", horizon, ep.split(" (")[0])
    if comp.a.n < 11 or comp.b.n < 11:
        st.warning("Each group needs at least 11 patients - widen the choices.")
    else:
        def pct(v):
            return f"{v:.0%}" if v is not None else "not reached"

        sig = (comp.logrank_p or 1) < 0.05
        kpi_cards([
            {"label": "Group A: 5 years later", "value": pct(comp.a.survival_at.get(60)), "sub": f"{comp.a.n} patients"},
            {"label": "Group B: 5 years later", "value": pct(comp.b.survival_at.get(60)), "sub": f"{comp.b.n} patients"},
            {"label": f"Extra time for A in the first {horizon} months",
             "value": f"{comp.rmst_difference:+.1f} months" if comp.rmst_difference is not None else "—",
             "sub": "negative = group B did better"},
            {"label": "Is the difference real?", "value": "Yes, clearly" if sig else "Can't tell",
             "sub": f"log-rank test p = {comp.logrank_p:.2g}" if comp.logrank_p is not None else ""},
        ])
        show(km_compare(comp), key="lab_km")
        how_to_read("both lines start at 100% and step down each time a patient has the event. The higher line did "
                    "better. Shaded bands show uncertainty: if they overlap a lot, the groups may not really differ. "
                    "This is a simple comparison; the <b>What matters most</b> tab adjusts for other factors.")

# ------------------------------------------------------------------ precomputed curves
with tab_km:
    opts = query("select distinct cohort, endpoint, stratifier from analytics.km_summary order by 1,2,3")
    c = st.columns(3)
    cohort = c[0].selectbox("Patient group", sorted(opts.cohort.unique(), key=lambda x: x != "TCGA-BRCA"),
                            format_func=lambda x: {"TCGA-BRCA": "Main group (US, 1,098 patients)"}.get(x, f"{x} (check group)"))
    eps = sorted(opts[opts.cohort == cohort].endpoint.unique(), key=lambda x: x != "OS")
    EP = {"OS": "Still alive", "DSS": "Not died of breast cancer", "PFI": "Cancer hasn't grown or returned",
          "DFI": "Disease-free", "RFS": "Cancer hasn't returned"}
    endpoint = c[1].selectbox("Measure", eps, key="km_ep", format_func=lambda x: EP.get(x, x))
    strats = opts[(opts.cohort == cohort) & (opts.endpoint == endpoint)].stratifier.unique().tolist()
    STRAT = {"stage_major": "Cancer stage", "receptor_subtype": "Tumour type", "age_group": "Age group",
             "chemo_timing_group": "When chemo started", "pathway_group": "Treatment path"}
    strat = c[2].selectbox("Compare by", strats, index=strats.index("stage_major") if "stage_major" in strats else 0,
                           format_func=lambda x: STRAT.get(x, x.replace("_", " ").capitalize()))
    prm = {"c": cohort, "e": endpoint, "s": strat}
    curves = query("select * from analytics.km_curves where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s order by 1", prm)
    summ = query("select * from analytics.km_summary where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s", prm)
    summ = summ.sort_values("n", ascending=False).head(8)
    curves = curves[curves.group_value.isin(summ.group_value)]
    show(km_from_table(curves, summ, strat, f"{EP.get(endpoint, endpoint)}, by {STRAT.get(strat, strat.replace('_', ' ')).lower()}",
                       180 if cohort == "TCGA-BRCA" else 240), key="km")
    how_to_read("each line is a group of patients. It starts at 100% and steps down over time; a higher line "
                "means that group did better.")
    test = query("select * from analytics.logrank_tests where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s", prm)
    if len(test):
        tt = test.iloc[0]
        verdict = "the groups clearly differ" if tt.p_value < 0.05 else "the difference could be chance"
        st.markdown(f"**Are the groups really different?** {verdict.capitalize()} (log-rank test p = {tt.p_value:.2g}, "
                    f"{int(tt.n):,} patients).")
    st.dataframe(summ[["group_value", "n", "events", "median_survival_months", "survival_5y", "survival_5y_ci_lower",
                       "survival_5y_ci_upper", "survival_10y"]].rename(columns={
        "group_value": "group", "n": "patients", "median_survival_months": "median months",
        "survival_5y": "alive at 5 yrs", "survival_5y_ci_lower": "5 yr low", "survival_5y_ci_upper": "5 yr high",
        "survival_10y": "alive at 10 yrs"}).style.format(
        {"alive at 5 yrs": "{:.0%}", "5 yr low": "{:.0%}", "5 yr high": "{:.0%}",
         "alive at 10 yrs": "{:.0%}", "median months": "{:.0f}"}, na_rep="—"), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ cox
with tab_cox:
    st.markdown("A statistical model (Cox regression) that weighs every factor at once, so you can see each "
                "factor's effect with the others held equal.")
    fits = query("select * from analytics.cox_model_fit where status = 'fitted'")
    model = st.selectbox("Model", fits.model.tolist())
    fm = fits[fits.model == model].iloc[0]
    kpi_cards([
        {"label": "Patients", "value": f"{int(fm.n):,}"},
        {"label": "Events", "value": f"{int(fm.events):,}", "sub": "deaths or recurrences counted"},
        {"label": "How well it ranks patients", "value": f"{fm.concordance:.2f}", "sub": "0.5 = coin flip, 1 = perfect"},
    ])
    if isinstance(fm.caution, str) and fm.caution:
        st.warning(f"Treat this model with caution: it has only {fm.events_per_variable:.1f} events per factor "
                   f"(10 or more is recommended). {fm.caution}")
    co = query("select * from analytics.cox_coefficients where model = %(m)s", {"m": model})
    show(forest(co, "covariate", "hazard_ratio", "ci_lower", "ci_upper",
                title="How each factor changes the risk, with the others held equal",
                xtitle="risk multiplier  (1 = no effect, 2 = double the risk)"), key="cox")
    how_to_read("right of the line = higher risk (<b>red</b> when clear), left = lower risk (<b>blue</b>), grey = no "
                "clear effect. The line through each dot is the range we're 95% confident in.")
    ph = query("select covariate, test_statistic, p_value, ph_assumption_ok from analytics.cox_ph_tests where model=%(m)s", {"m": model})
    bad = ph[~ph.ph_assumption_ok.astype(bool)] if len(ph) else pd.DataFrame()
    if len(bad):
        st.caption("Technical note: the model's 'constant effect over time' assumption may not hold for: "
                   + ", ".join(bad.covariate) + " (Schoenfeld test).")
    table(co, "Model numbers")
    note("<b>Careful with treatments.</b> Sicker patients get more treatment, so a treatment can look 'risky' simply "
         "because of who receives it. These are patterns, not proof of what a treatment does.")
footer()
