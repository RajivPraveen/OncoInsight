"""Pivot cBioPortal long-format clinical records (patient x attribute) into wide tables with Polars."""

from __future__ import annotations

import polars as pl

from oncoinsight.fhir.flatten import record_hash


def pivot_clinical(rows: list[dict], level: str, source_run_id: str) -> pl.DataFrame:
    """``level`` is 'patient' or 'sample'. Output: one row per entity, attributes as lower-case text columns."""
    if not rows:
        return pl.DataFrame()
    long = pl.DataFrame(rows).select(
        pl.col("studyId").alias("study_id"),
        pl.col("patientId").alias("patient_id"),
        *( [pl.col("sampleId").alias("sample_id")] if level == "sample" else [] ),
        pl.col("clinicalAttributeId").str.to_lowercase().alias("attribute"),
        pl.col("value").cast(pl.Utf8),
    )
    index = ["study_id", "patient_id"] + (["sample_id"] if level == "sample" else [])
    wide = long.pivot(on="attribute", index=index, values="value", aggregate_function="first").sort(index)
    key = "patient_id" if level == "patient" else "sample_id"
    wide = wide.with_columns((pl.col("study_id") + ":" + pl.col(key)).alias("id"))
    attr_cols = sorted(c for c in wide.columns if c not in {*index, "id"})
    wide = wide.select(["id", *index, *attr_cols])
    hashes = [record_hash(r) for r in wide.iter_rows(named=True)]
    return wide.with_columns(pl.Series("record_hash", hashes), pl.lit(source_run_id).alias("source_run_id"))
