"""Regenerate README images from the live warehouse and the running dashboard.

    make up && make pipeline          # warehouse populated
    make dashboard                    # in another terminal (serves :8503)
    uv run python scripts/make_readme_assets.py [--charts-only]

* Charts: the exact figure factories the dashboard uses (app/charts.py), rendered with kaleido.
* Screenshots: real full-page captures of the dashboard via Playwright driving the locally installed Chrome.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
sys.path.insert(0, str(ROOT / "app"))
warnings.filterwarnings("ignore")


def charts() -> None:
    import charts as c
    import plotly.io as pio
    import theme as t

    from oncoinsight.common.db import read_sql

    def q(sql, params=None):
        return read_sql(sql, params, readonly=True)

    def save(fig, name, w=1200, h=None):
        fig.update_layout(paper_bgcolor=t.SURFACE, plot_bgcolor=t.SURFACE, font=dict(family=t.FONT, color=t.INK_2))
        fig.update_xaxes(automargin=True)
        fig.update_yaxes(automargin=True)
        pio.write_image(fig, OUT / f"{name}.png", width=w, height=h or int(fig.layout.height or 500), scale=2)
        print("chart", name)

    p = q("select * from marts.mart_patient_360")
    steps = q("select * from marts.mart_patient_pathway_steps")
    save(c.sankey(steps, p, 4, 8), "sankey", h=560)
    km = q("select * from analytics.km_curves where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    ks = q("select * from analytics.km_summary where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    save(c.km_from_table(km, ks, "stage_major", "Overall survival by AJCC stage - TCGA-BRCA (shaded 95% CI)"), "km_stage", h=460)
    ra = q("select * from analytics.hospital_risk_adjusted_delay").rename(columns={"hospital_name": "site"})
    save(c.forest(ra, "site", "oe_ratio", "oe_ci_lower", "oe_ci_upper", p=None, ref=1, log=False,
                  title="Chemo started > 90 days: observed ÷ expected after case-mix adjustment (95% CI)",
                  xtitle="observed / expected"), "oe_delay", h=420)
    co = q("select * from analytics.cox_coefficients where model like %(m)s", {"m": "TCGA PFI%"})
    save(c.forest(co, "covariate", "hazard_ratio", "ci_lower", "ci_upper",
                  title="Progression-free interval - adjusted hazard ratios (red = higher risk, blue = lower, grey = n.s.)"),
         "cox_pfi", h=440)
    ca = q("select * from marts.mart_cost_analysis where dimension='Receptor subtype'")
    save(c.cost_stack(ca, "receptor subtype"), "cost_subtype", h=360)
    save(c.sunburst_journey(p), "sunburst", w=900, h=620)
    delay = q("select * from marts.mart_treatment_delay where interval_name = %(i)s", {"i": "Diagnosis → Chemotherapy"})
    save(c.delay_distribution(delay, "stage_major", 90, "Days from diagnosis to adjuvant chemotherapy, by stage"), "delay_stage", h=420)


SHOTS = [
    ("overview", "", None),
    ("story", "story", None),
    ("pathways", "pathways", None),
    ("time_to_treatment", "time_to_treatment", None),
    ("survival_lab", "survival", "preset"),
    ("cost_whatif", "cost", "whatif"),
    ("operations", "operations", None),
    ("lineage", "lineage", None),
]


def screenshots(base: str = "http://localhost:8503") -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1450}, device_scale_factor=1.25)
        for name, path, action in SHOTS:
            page.goto(f"{base}/{path}", wait_until="networkidle")
            page.wait_for_selector('[data-testid="stPlotlyChart"]', timeout=60_000)
            page.wait_for_timeout(3500)
            if action == "preset":
                page.get_by_role("combobox", name="Start from a preset").click()
                page.get_by_role("option", name="Triple negative vs HR+/HER2-").click()
                page.wait_for_timeout(4000)
            if action == "whatif":
                page.get_by_role("tab", name="What-if simulator").click()
                page.wait_for_timeout(2000)
                page.get_by_text("Hypofractionate whole-breast radiation").click()  # show a real scenario
                page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / f"screen_{name}.jpg"), type="jpeg", quality=80)
            print("screenshot", name)
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--charts-only", action="store_true")
    ap.add_argument("--base-url", default="http://localhost:8503")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    charts()
    if not a.charts_only:
        screenshots(a.base_url)
