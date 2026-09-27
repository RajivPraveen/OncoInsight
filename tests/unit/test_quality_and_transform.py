import polars as pl
import pytest

from oncoinsight.fhir.flatten import flatten
from oncoinsight.fhir.gdc_to_fhir import map_cases
from oncoinsight.loading.cbioportal_transform import pivot_clinical
from oncoinsight.quality.expectations import DataQualityError, enforce, validate_frame


@pytest.fixture(scope="module")
def frames(gdc_cases):
    return flatten(map_cases(gdc_cases), "t")


def test_clean_fixture_passes_all_critical_expectations(frames):
    results = [r for name, df in frames.items() for r in validate_frame(name, df)]
    assert results
    enforce(results)  # raises on any critical failure


def test_critical_failure_blocks_load(frames):
    df = frames["fhir_procedure"]
    corrupted = pl.concat([df, df.head(1)])  # duplicate primary key
    with pytest.raises(DataQualityError, match="expect_column_values_to_be_unique"):
        enforce(validate_frame("fhir_procedure", corrupted))


def test_bad_domain_value_detected(frames):
    df = frames["fhir_patient"].with_columns(pl.lit("robot").alias("gender"))
    failed = [r for r in validate_frame("fhir_patient", df) if not r.success]
    assert any(r.column == "gender" and r.severity == "critical" for r in failed)


def test_cbioportal_pivot_long_to_wide(metabric_patient_rows):
    wide = pivot_clinical(metabric_patient_rows, "patient", "run")
    assert wide["patient_id"].n_unique() == wide.height
    assert {"os_months", "rfs_status", "record_hash", "source_run_id"} <= set(wide.columns)
    assert wide["id"].str.starts_with("brca_metabric:").all()
    assert validate_frame("cbio_brca_metabric_patient", wide)
