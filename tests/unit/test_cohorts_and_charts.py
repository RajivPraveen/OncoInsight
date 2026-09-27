import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oncoinsight.analytics.cohorts import compare_cohorts, filter_frame

APP = Path(__file__).resolve().parents[2] / "app"
MANIFEST = Path(__file__).resolve().parents[2] / "dbt" / "oncoinsight" / "target" / "manifest.json"


def _cohort(n, scale, seed):
    rng = np.random.default_rng(seed)
    t = rng.exponential(scale, n)
    censor = rng.uniform(0, 150, n)
    return pd.DataFrame({"os_months": np.minimum(t, censor), "os_event": (t <= censor).astype(int),
                         "stage_major": rng.choice(["I", "II", "III"], n)})


def test_compare_detects_real_difference_and_rmst_sign():
    good, bad = _cohort(400, 200, 1), _cohort(400, 40, 2)
    comp = compare_cohorts(good, bad, horizon=60)
    assert comp.logrank_p < 1e-6
    assert comp.rmst_difference > 0  # better cohort lives longer within the horizon
    assert 0 < comp.a.rmst <= 60 and 0 < comp.b.rmst <= 60
    assert comp.a.survival_at[60] > comp.b.survival_at[60]
    assert len(comp.a.timeline) == len(comp.a.survival) == len(comp.a.at_risk)


def test_compare_same_population_not_significant():
    comp = compare_cohorts(_cohort(300, 100, 3), _cohort(300, 100, 4))
    assert comp.logrank_p > 0.01


def test_small_cohorts_are_not_estimated():
    comp = compare_cohorts(_cohort(5, 100, 5), _cohort(300, 100, 6))
    assert comp.a.timeline == [] and comp.logrank_p is None and comp.rmst_difference is None


def test_filter_frame_ignores_empty_and_unknown_columns():
    df = _cohort(50, 100, 7)
    assert len(filter_frame(df, {"stage_major": [], "nonexistent": ["x"]})) == 50
    assert set(filter_frame(df, {"stage_major": ["I"]}).stage_major) == {"I"}


@pytest.fixture(scope="module")
def charts():
    sys.path.insert(0, str(APP))
    import charts as c

    return c


def test_sankey_conserves_patients(charts):
    cohort = pd.DataFrame({"patient_id": ["a", "b", "c"], "os_event": [0, 1, 0],
                           "any_progression_or_recurrence": [False, False, True]})
    steps = pd.DataFrame({"patient_id": ["a", "a", "b", "c"], "step_number": [1, 2, 1, 1],
                          "pathway_group": ["Surgery", "Chemotherapy", "Surgery", "Surgery"]})
    fig = charts.sankey(steps, cohort, min_patients=1)
    labels = list(fig.data[0].node.label)
    src = [labels[i] for i in fig.data[0].link.source]
    out_of_dx = sum(v for s, v in zip(src, fig.data[0].link.value, strict=True) if s == "Diagnosis")
    assert out_of_dx == 3
    assert "Outcome: Deceased" in labels


def test_forest_colours_by_direction_and_significance(charts):
    df = pd.DataFrame({"term": ["harm", "protect", "ns"], "hr": [2.0, 0.5, 1.1], "lo": [1.5, 0.3, 0.8],
                       "hi": [2.6, 0.8, 1.5], "p": [0.001, 0.01, 0.4]})
    fig = charts.forest(df, "term", "hr", "lo", "hi", "p")
    colors = dict(zip(fig.data[0].y, fig.data[0].marker.color, strict=True))
    assert colors["harm"] == "#d03b3b" and colors["protect"] == "#2a78d6" and colors["ns"] == "#c3c2b7"


@pytest.mark.skipif(not MANIFEST.exists(), reason="dbt manifest not built")
def test_lineage_focus_contains_upstream_and_downstream(charts):
    fig = charts.lineage_graph(MANIFEST, focus="model.oncoinsight.int_treatment_events")
    names = {t for tr in fig.data[1:] for t in tr.text}
    assert {"int_treatment_events", "stg_fhir__procedures", "fact_treatment"} <= names
    assert "mart_metabric_cohort" not in names  # unrelated branch excluded


def test_apply_filters(charts):
    import theme

    df = pd.DataFrame({"year_of_diagnosis": [2005, 2010, None], "stage_major": ["I", "III", "II"],
                       "receptor_subtype": ["HR+/HER2-"] * 3})
    full = {"years": (1988, 2013), "year_bounds": (1988, 2013), "stage": [], "subtype": [], "age": [], "site": []}
    assert len(theme.apply_filters(df, full)) == 3  # full range keeps patients without a year
    narrowed = {**full, "years": (2008, 2013), "stage": ["III"]}
    assert theme.apply_filters(df, narrowed).year_of_diagnosis.tolist() == [2010]


def test_forest_without_p_uses_ci_excluding_reference(charts):
    df = pd.DataFrame({"site": ["worse", "unclear", "better"], "oe": [2.5, 1.3, 0.2], "lo": [1.5, 0.9, 0.0],
                       "hi": [4.0, 1.9, 0.4]})
    fig = charts.forest(df, "site", "oe", "lo", "hi", p=None, ref=1, log=False)
    colors = dict(zip(fig.data[0].y, fig.data[0].marker.color, strict=True))
    assert colors == {"worse": "#d03b3b", "unclear": "#c3c2b7", "better": "#2a78d6"}


def test_cost_scenario_default_is_exactly_zero_and_levers_move_the_right_lines():
    from oncoinsight.analytics.cost_scenarios import Scenario, reprice

    lines = pd.DataFrame({
        "price_id": ["cpt_77412_pfs_nf", "cpt_77427_pfs_nf", "j9355_asp", "j9000_asp", "cpt_19301_pfs_fac"],
        "cost_component": ["radiation", "radiation", "drug", "drug", "surgery"],
        "units": [33.0, 7.0, 714.0, 43.2, 0.5], "unit_price_usd": [443.56, 195.40, 68.871, 3.12, 632.61]})
    base = reprice(lines, Scenario())
    assert (base.scenario - base.baseline).abs().sum() == 0  # regression: untouched sliders must change nothing
    hypo = reprice(lines, Scenario(hypofractionation=True, fractions=16))
    assert hypo.scenario[0] == 16 * 443.56 and hypo.scenario[1] == 4 * 195.40
    bio = reprice(lines, Scenario(trastuzumab_discount_pct=50))
    assert bio.scenario[2] == pytest.approx(0.5 * 714 * 68.871) and bio.scenario[3] == bio.baseline[3]
