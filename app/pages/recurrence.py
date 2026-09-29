import json

import joblib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    AGE_COLORS,
    BLUE,
    INK_2,
    SERIES,
    STAGE_COLORS,
    STATUS,
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

from oncoinsight.common.config import get_settings

page_setup("Cancer returning",
           "How often the cancer comes back after treatment, who is most at risk, and whether we can predict it.",
           kicker="Results",
           question="Which patients are most likely to have their cancer come back?",
           answer="Risk rises steeply with stage and with triple-negative tumours. A prediction model gets it right "
                  "about <b>7 times in 10</b>, which is typical when you only have clinical information and no "
                  "genetic tests.")

rs = query("select * from marts.mart_recurrence_summary")
overall = rs[rs.factor == "All patients"].iloc[0]
kpi_cards([
    {"label": "Patients analysed", "value": f"{int(overall.n_patients):,}", "sub": "stage I–III"},
    {"label": "Cancer came back or grew", "value": f"{overall.crude_recurrence_pct:.0f}%", "sub": f"{int(overall.n_recurrences)} patients"},
    {"label": "Typical time until it came back", "value": f"{overall.median_months_to_recurrence:.0f} months"},
    {"label": "Typical follow-up", "value": f"{overall.median_follow_up_months:.0f} months"},
])

tab1, TAB_CALC, TAB_MODEL = st.tabs(["Who is most at risk", "Try the risk calculator", "How good is the prediction?"])
with tab1:
    FACTOR = {"Tumour (T) category": "Tumour size (T)", "Nodal (N) category": "Lymph nodes affected (N)"}
    factor = st.radio("Split patients by", [f for f in rs.factor.unique() if f != "All patients"], horizontal=True,
                      format_func=lambda f: FACTOR.get(f, f))
    d = rs[(rs.factor == factor) & (rs.n_patients >= 11)].sort_values("crude_recurrence_pct")
    cmap = {"Stage": STAGE_COLORS, "Receptor subtype": SUBTYPE_COLORS, "Age group": AGE_COLORS}.get(factor, {})
    colors = [cmap.get(v, SERIES[i % 8]) for i, v in enumerate(d.factor_value)]
    fig = go.Figure(go.Bar(x=d.crude_recurrence_pct, y=d.factor_value, orientation="h", marker=dict(color=colors, line=RING),
                           text=[f"{v:.0f}%  ({n} patients)" for v, n in zip(d.crude_recurrence_pct, d.n_patients, strict=True)],
                           textposition="outside", hovertemplate="%{y}: <b>%{x:.1f}%</b><extra></extra>"))
    fig.add_vline(x=overall.crude_recurrence_pct, line_color=INK_2, line_width=1, annotation_text=f"all patients {overall.crude_recurrence_pct:.0f}%")
    fig.update_layout(height=140 + 40 * len(d), margin=dict(r=110), bargap=0.35, showlegend=False,
                      xaxis_title="% whose cancer came back or grew", title=f"By {FACTOR.get(factor, factor).lower()}")
    show(fig, key="rates")
    how_to_read("longer bars = the cancer came back more often in that group. The grey line is the average for "
                "all patients. These are raw rates, not adjusted for other factors.")
    table(d)

with TAB_MODEL:
    mm = query("select * from analytics.recurrence_model_metrics")
    st.markdown("Three machine-learning models were trained to predict whether cancer returns within 5 years. The "
                "score (AUC) runs from 0.5 (a coin flip) to 1.0 (perfect).")
    kpi_cards([{"label": r.model, "value": f"{r.cv_roc_auc_mean:.2f}", "sub": f"accuracy score (AUC) · on unseen patients {r.holdout_roc_auc:.2f}"}
               for r in mm.itertuples()])
    c1, c2 = st.columns(2)
    with c1:
        cal = query("select * from analytics.recurrence_model_calibration")
        fig = go.Figure()
        for i, (name, g) in enumerate(cal.groupby("model")):
            fig.add_trace(go.Scatter(x=g.mean_predicted, y=g.observed_rate, mode="lines+markers", name=name,
                                     line=dict(color=SERIES[i], width=2.5), marker=dict(size=9, line=RING)))
        fig.add_trace(go.Scatter(x=[0, 0.8], y=[0, 0.8], mode="lines", line=dict(color=INK_2, width=1), name="perfect"))
        fig.update_layout(height=400, title="Does predicted risk match what actually happened?", xaxis_title="predicted risk",
                          yaxis_title="actual rate", hovermode="x unified", xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        show(fig, key="cal")
        how_to_read("points close to the grey diagonal mean the model's risk estimates are honest: when it says 30%, "
                    "about 30% of those patients actually relapsed.")
    with c2:
        fi = query("select * from analytics.recurrence_feature_importance")
        model = st.selectbox("Model", fi.model.unique())
        f = fi[fi.model == model].sort_values("importance_mean")
        FEAT = {"receptor_subtype": "Tumour type", "breast_surgery": "Type of surgery", "pam50_claudin_subtype": "Genetic subtype (PAM50)",
                "received_radiotherapy": "Had radiation", "tumor_grade": "Tumour grade", "received_hormone_therapy": "Had hormone therapy",
                "received_chemotherapy": "Had chemotherapy", "age_at_diagnosis": "Age", "menopausal_state": "Menopause status",
                "tumor_size_mm": "Tumour size", "lymph_nodes_positive": "Lymph nodes with cancer"}
        fig = go.Figure(go.Bar(x=f.importance_mean, y=f.feature.map(lambda x: FEAT.get(x, x)), orientation="h", marker=dict(color=BLUE, line=RING),
                               error_x=dict(type="data", array=f.importance_sd, color="#d4d2cc", thickness=1.5),
                               hovertemplate="%{y}: accuracy drops by <b>%{x:.3f}</b> without it<extra></extra>"))
        fig.update_layout(height=400, title="Which information the model relies on most", bargap=0.35,
                          xaxis_title="drop in accuracy when this is scrambled")
        show(fig, key="fi")
        how_to_read("longer bar = the model leans on that factor more. Lymph nodes and tumour size matter most.")
    note("Trained on a separate UK/Canadian study (METABRIC: 2,185 patients whose 5-year outcome is known, 604 "
         "relapses). A score around 0.71 is normal with clinical information alone; genetic tests add the rest.")

with TAB_CALC:
    path = get_settings().data_dir / "models" / "recurrence_5y_model.joblib"
    if not path.exists():
        st.info("The prediction model hasn't been built yet - run the analytics step of the pipeline.")
    else:
        meta = json.loads(path.with_suffix(".json").read_text())
        model = joblib.load(path)
        st.markdown("Describe a patient and see the model's estimate of the chance their cancer returns within 5 years.")
        a, b, c = st.columns(3)
        row = {"age_at_diagnosis": a.slider("Age", 25, 90, 55), "tumor_size_mm": a.slider("Tumour size (mm)", 5, 120, 25),
               "tumor_grade": b.select_slider("Tumour grade (3 = fastest-growing)", [1, 2, 3], value=3),
               "lymph_nodes_positive": b.slider("Lymph nodes with cancer", 0, 30, 1),
               "receptor_subtype": c.selectbox("Tumour type", ["HR+/HER2-", "HR+/HER2+", "HR-/HER2+", "Triple negative"]),
               "pam50_claudin_subtype": None, "menopausal_state": c.radio("Menopausal state", ["Post", "Pre"], horizontal=True),
               "breast_surgery": c.radio("Surgery", ["BREAST CONSERVING", "MASTECTOMY"], horizontal=True,
                                         format_func=lambda x: {"BREAST CONSERVING": "Lumpectomy", "MASTECTOMY": "Mastectomy"}[x]),
               "received_chemotherapy": float(a.toggle("Chemotherapy")),
               "received_hormone_therapy": float(b.toggle("Hormone therapy")),
               "received_radiotherapy": float(c.toggle("Radiation"))}
        prob = float(model.predict_proba(pd.DataFrame([row])[meta["features"]])[0, 1])
        color = STATUS["good"] if prob < 0.2 else (STATUS["warning"] if prob < 0.35 else STATUS["critical"])
        fig = go.Figure(go.Indicator(mode="gauge+number", value=prob * 100, number=dict(suffix="%", font=dict(size=46)),
                                     gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=color, thickness=0.35),
                                                steps=[dict(range=[0, 20], color="#e9f3ec"), dict(range=[20, 35], color="#f8f0dc"),
                                                       dict(range=[35, 100], color="#f6e3e3")],
                                                threshold=dict(line=dict(color=INK_2, width=2), value=27.6)),
                                     title=dict(text="Estimated chance the cancer returns within 5 years (line = average patient, 28%)")))
        fig.update_layout(height=320)
        show(fig, key="gauge")
        st.caption(f"{meta['model']} model trained on {meta['training_cohort']} (accuracy score {meta['holdout_roc_auc']:.2f} on "
                   "unseen patients). A demonstration only - not for decisions about real patients.")
footer()
