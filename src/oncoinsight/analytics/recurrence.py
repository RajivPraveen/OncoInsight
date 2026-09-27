"""Recurrence risk modelling on METABRIC (5-year relapse, n~1,900 with complete data).

Label: relapse within 60 months. Patients censored before 60 months without relapse are excluded
(their 5-year status is unknown). Models: L2 logistic regression, random forest and gradient boosting
(XGBoost when its OpenMP runtime is available, otherwise scikit-learn HistGradientBoosting).
Evaluation: stratified 5-fold cross-validated ROC-AUC / PR-AUC / Brier, plus a 25% hold-out with
calibration bins and permutation feature importance.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

HORIZON_MONTHS = 60
NUMERIC = ["age_at_diagnosis", "tumor_size_mm", "tumor_grade", "lymph_nodes_positive"]
CATEGORICAL = ["receptor_subtype", "pam50_claudin_subtype", "menopausal_state", "breast_surgery"]
BINARY = ["received_chemotherapy", "received_hormone_therapy", "received_radiotherapy"]
FEATURES = NUMERIC + CATEGORICAL + BINARY
SEED = 42


def build_label(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["rfs_months", "rfs_event"]).copy()
    relapsed = (d["rfs_event"] == 1) & (d["rfs_months"] <= HORIZON_MONTHS)
    known = relapsed | (d["rfs_months"] > HORIZON_MONTHS)
    d = d[known].copy()
    d["relapse_5y"] = relapsed[known].astype(int)
    for c in BINARY:
        d[c] = d[c].astype(float)
    return d


def _gbm():
    try:
        from xgboost import XGBClassifier

        XGBClassifier(n_estimators=1).fit(np.zeros((4, 1)), [0, 1, 0, 1])  # probe OpenMP runtime
        return "XGBoost", XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
                                        colsample_bytree=0.8, eval_metric="logloss", random_state=SEED)
    except Exception:  # libomp missing (macOS without Homebrew) -> equivalent sklearn implementation
        return "HistGradientBoosting", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                                      random_state=SEED)


def _pipeline(model, scale: bool) -> Pipeline:
    num = Pipeline([("impute", SimpleImputer(strategy="median"))] + ([("scale", StandardScaler())] if scale else []))
    cat = Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    binary = SimpleImputer(strategy="most_frequent")
    pre = ColumnTransformer([("num", num, NUMERIC), ("cat", cat, CATEGORICAL), ("bin", binary, BINARY)])
    return Pipeline([("pre", pre), ("model", model)])


def run_recurrence_models(metabric: pd.DataFrame, model_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    d = build_label(metabric)
    X, y = d[FEATURES], d["relapse_5y"]
    gbm_name, gbm = _gbm()
    models = {
        "Logistic regression": _pipeline(LogisticRegression(max_iter=2000, C=1.0), scale=True),
        "Random forest": _pipeline(RandomForestClassifier(n_estimators=400, min_samples_leaf=10, random_state=SEED, n_jobs=-1), scale=False),
        gbm_name: _pipeline(gbm, scale=False),
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)

    metrics, calib, importance = [], [], []
    best_name, best_auc, best_model = None, -1.0, None
    for name, pipe in models.items():
        scores = cross_validate(pipe, X, y, cv=cv, scoring={"auc": "roc_auc", "ap": "average_precision",
                                                           "brier": "neg_brier_score"})
        pipe.fit(X_tr, y_tr)
        p = pipe.predict_proba(X_te)[:, 1]
        auc = roc_auc_score(y_te, p)
        metrics.append({
            "model": name, "n_total": len(d), "n_events": int(y.sum()), "event_rate": float(y.mean()),
            "cv_roc_auc_mean": float(scores["test_auc"].mean()), "cv_roc_auc_sd": float(scores["test_auc"].std()),
            "cv_pr_auc_mean": float(scores["test_ap"].mean()), "cv_brier_mean": float(-scores["test_brier"].mean()),
            "holdout_roc_auc": float(auc), "holdout_pr_auc": float(average_precision_score(y_te, p)),
            "holdout_brier": float(brier_score_loss(y_te, p)),
        })
        frac_pos, mean_pred = calibration_curve(y_te, p, n_bins=8, strategy="quantile")
        calib.append(pd.DataFrame({"model": name, "bin": range(len(frac_pos)), "mean_predicted": mean_pred,
                                   "observed_rate": frac_pos}))
        pi = permutation_importance(pipe, X_te, y_te, scoring="roc_auc", n_repeats=15, random_state=SEED, n_jobs=-1)
        importance.append(pd.DataFrame({"model": name, "feature": FEATURES, "importance_mean": pi.importances_mean,
                                        "importance_sd": pi.importances_std}))
        log.info("recurrence_model_evaluated", model=name, cv_auc=round(scores["test_auc"].mean(), 3), holdout_auc=round(auc, 3))
        if auc > best_auc:
            best_name, best_auc, best_model = name, auc, pipe

    if model_dir is not None and best_model is not None:
        model_dir.mkdir(parents=True, exist_ok=True)
        best_model.fit(X, y)  # refit on all labelled data for serving
        joblib.dump(best_model, model_dir / "recurrence_5y_model.joblib")
        (model_dir / "recurrence_5y_model.json").write_text(json.dumps({
            "model": best_name, "holdout_roc_auc": best_auc, "features": FEATURES, "numeric": NUMERIC,
            "categorical": CATEGORICAL, "binary": BINARY, "horizon_months": HORIZON_MONTHS,
            "training_cohort": "METABRIC (cBioPortal brca_metabric)", "n_train": int(len(d)),
            "intended_use": "Portfolio demonstration of cohort risk stratification. Not for clinical decisions.",
        }, indent=2))
    return {"recurrence_model_metrics": pd.DataFrame(metrics),
            "recurrence_model_calibration": pd.concat(calib, ignore_index=True),
            "recurrence_feature_importance": pd.concat(importance, ignore_index=True)}
