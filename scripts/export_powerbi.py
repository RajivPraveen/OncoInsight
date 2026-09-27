"""Export the Power BI model tables to Parquet (offline alternative to a live PostgreSQL connection).

    uv run python scripts/export_powerbi.py
"""

from __future__ import annotations

from oncoinsight.common.config import get_settings
from oncoinsight.common.db import read_sql

TABLES = [
    "core.fact_treatment", "core.fact_estimated_cost", "core.fact_diagnosis", "core.fact_encounter", "core.fact_outcome",
    "core.dim_patient", "core.dim_hospital", "core.dim_stage", "core.dim_biomarker", "core.dim_cancer", "core.dim_treatment",
    "marts.mart_patient_360", "marts.mart_kpi_annual", "marts.mart_pathway_transitions", "marts.mart_treatment_pathways",
    "marts.mart_delay_by_hospital", "marts.mart_cost_analysis", "marts.mart_disparities", "analytics.km_curves",
    "analytics.hospital_risk_adjusted_delay", "ops.kpi_alerts",
]


def main() -> None:
    out = get_settings().data_dir / "exports" / "powerbi"
    out.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        df = read_sql(f"select * from {t}", readonly=True)  # table names are a fixed allow-list above
        df.to_parquet(out / f"{t.split('.')[1]}.parquet", index=False)
        print(f"{t}: {len(df):,} rows")
    print(f"exported to {out}")


if __name__ == "__main__":
    main()
