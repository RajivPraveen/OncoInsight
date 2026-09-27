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
    MAGENTA,
    ORANGE,
    SERIES,
    STAGE_COLORS,
    STATUS,
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

from oncoinsight.common.config import get_settings

page_setup("Recurrence & risk", "Which factors are associated with recurrence or progression, and how well can "
           "5-year relapse be predicted? Descriptive rates first, then the predictive layer.", kicker="Outcomes")

rs = query("select * from marts.mart_recurrence_summary")
overall = rs[rs.factor == "All patients"].iloc[0]
kpi_cards([
    {"label": "Stage I–III patients analysed", "value": f"{int(overall.n_patients):,}", "color": BLUE, "icon": "👥"},
    {"label": "Recurrence / progression events", "value": f"{int(overall.n_recurrences)}", "sub": f"{overall.crude_recurrence_pct:.1f}% crude", "color": MAGENTA, "icon": "🔁"},
    {"label": "Median months to event", "value": f"{overall.median_months_to_recurrence:.0f}", "sub": "among patients who recurred", "color": ORANGE, "icon": "⏳"},
    {"label": "Median follow-up", "value": f"{overall.median_follow_up_months:.0f} mo", "color": VIOLET, "icon": "📅"},
])

tab1, tab2, tab3 = st.tabs(["📊 Rates by factor", "🤖 Model performance", "🧮 Risk calculator"])
with tab1:
    factor = st.radio("Factor", [f for f in rs.factor.unique() if f != "All patients"], horizontal=True)
    d = rs[(rs.factor == factor) & (rs.n_patients >= 11)].sort_values("crude_recurrence_pct")
    cmap = {"Stage": STAGE_COLORS, "Receptor subtype": SUBTYPE_COLORS, "Age group": AGE_COLORS}.get(factor, {})
    colors = [cmap.get(v, SERIES[i % 8]) for i, v in enumerate(d.factor_value)]
    fig = go.Figure(go.Bar(x=d.crude_recurrence_pct, y=d.factor_value, orientation="h", marker=dict(color=colors, line=RING),
                           text=[f"{v:.1f}%  (n={n})" for v, n in zip(d.crude_recurrence_pct, d.n_patients, strict=True)],
                           textposition="outside", hovertemplate="%{y}: <b>%{x:.1f}%</b><extra></extra>"))
    fig.add_vline(x=overall.crude_recurrence_pct, line_color=INK_2, line_width=1, annotation_text=f"all {overall.crude_recurrence_pct:.1f}%")
    fig.update_layout(height=140 + 40 * len(d), margin=dict(r=110), bargap=0.35, showlegend=False,
                      xaxis_title="% with recurrence / progression", title=f"Crude recurrence by {factor.lower()}")
    show(fig, key="rates")
    table(d)

with tab2:
    mm = query("select * from analytics.recurrence_model_metrics")
    kpi_cards([{"label": r.model, "value": f"AUC {r.cv_roc_auc_mean:.3f}", "sub": f"5-fold CV ± {r.cv_roc_auc_sd:.3f} · hold-out {r.holdout_roc_auc:.3f}",
                "color": SERIES[i], "icon": "🤖"} for i, r in enumerate(mm.itertuples())])
    c1, c2 = st.columns(2)
    with c1:
        cal = query("select * from analytics.recurrence_model_calibration")
        fig = go.Figure()
        for i, (name, g) in enumerate(cal.groupby("model")):
            fig.add_trace(go.Scatter(x=g.mean_predicted, y=g.observed_rate, mode="lines+markers", name=name,
                                     line=dict(color=SERIES[i], width=2.5), marker=dict(size=9, line=RING)))
        fig.add_trace(go.Scatter(x=[0, 0.8], y=[0, 0.8], mode="lines", line=dict(color=INK_2, width=1), name="perfect"))
        fig.update_layout(height=400, title="Calibration: predicted vs observed relapse (hold-out)", xaxis_title="predicted risk",
                          yaxis_title="observed rate", hovermode="x unified")
        show(fig, key="cal")
    with c2:
        fi = query("select * from analytics.recurrence_feature_importance")
        model = st.selectbox("Importance for", fi.model.unique())
        f = fi[fi.model == model].sort_values("importance_mean")
        fig = go.Figure(go.Bar(x=f.importance_mean, y=f.feature, orientation="h", marker=dict(color=BLUE, line=RING),
                               error_x=dict(type="data", array=f.importance_sd, color="#c3c2b7", thickness=1.5),
                               hovertemplate="%{y}: ΔAUC <b>%{x:.3f}</b><extra></extra>"))
        fig.update_layout(height=400, title="Permutation importance (drop in AUC when shuffled)", bargap=0.35)
        show(fig, key="fi")
    note("Trained on METABRIC (2,185 patients with known 5-year status, 604 relapses). An AUC of about 0.71 is typical "
         "for clinicopathologic-only models; genomic assays add the rest.", BLUE)

with tab3:
    path = get_settings().data_dir / "models" / "recurrence_5y_model.joblib"
    if not path.exists():
        st.info("Model artefact not found - run the analytics step.")
    else:
        meta = json.loads(path.with_suffix(".json").read_text())
        model = joblib.load(path)
        a, b, c = st.columns(3)
        row = {"age_at_diagnosis": a.slider("Age", 25, 90, 55), "tumor_size_mm": a.slider("Tumour size (mm)", 5, 120, 25),
               "tumor_grade": b.select_slider("Grade", [1, 2, 3], value=3),
               "lymph_nodes_positive": b.slider("Positive lymph nodes", 0, 30, 1),
               "receptor_subtype": c.selectbox("Subtype", ["HR+/HER2-", "HR+/HER2+", "HR-/HER2+", "Triple negative"]),
               "pam50_claudin_subtype": None, "menopausal_state": c.radio("Menopausal state", ["Post", "Pre"], horizontal=True),
               "breast_surgery": c.radio("Surgery", ["BREAST CONSERVING", "MASTECTOMY"], horizontal=True),
               "received_chemotherapy": float(a.toggle("Chemotherapy")),
               "received_hormone_therapy": float(b.toggle("Endocrine therapy")),
               "received_radiotherapy": float(c.toggle("Radiotherapy"))}
        prob = float(model.predict_proba(pd.DataFrame([row])[meta["features"]])[0, 1])
        color = STATUS["good"] if prob < 0.2 else (STATUS["warning"] if prob < 0.35 else STATUS["critical"])
        fig = go.Figure(go.Indicator(mode="gauge+number", value=prob * 100, number=dict(suffix="%", font=dict(size=46)),
                                     gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=color, thickness=0.35),
                                                steps=[dict(range=[0, 20], color="#e8f5e8"), dict(range=[20, 35], color="#fdf3dc"),
                                                       dict(range=[35, 100], color="#fbe3e3")],
                                                threshold=dict(line=dict(color=INK_2, width=2), value=27.6)),
                                     title=dict(text="Estimated 5-year relapse probability (line = cohort average 27.6%)")))
        fig.update_layout(height=320)
        show(fig, key="gauge")
        st.caption(f"{meta['model']} trained on {meta['training_cohort']} (hold-out AUC {meta['holdout_roc_auc']:.2f}). "
                   "Demonstration of cohort risk stratification - not for clinical decisions.")
footer()
