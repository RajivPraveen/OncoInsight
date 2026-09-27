from oncoinsight.fhir.flatten import TABLES, flatten, record_hash
from oncoinsight.fhir.gdc_to_fhir import DateAnchor, classify_treatment, map_case, map_cases
from oncoinsight.fhir.validate import validate_resources


def test_all_generated_resources_are_valid_fhir_r4b(gdc_cases):
    report = validate_resources(map_cases(gdc_cases))
    assert report.quarantined == []
    assert report.counts["Patient"] == len(gdc_cases)
    assert report.counts["Organization"] >= 1


def test_invalid_resource_is_quarantined_not_dropped():
    # structural violation: Procedure.subject is required (1..1) and performedPeriod must be a Period.
    # Code value sets (e.g. status) are enforced separately by the Great Expectations gate.
    bad = {"Procedure": [{"resourceType": "Procedure", "id": "p1", "status": "completed",
                          "performedPeriod": "yesterday"}]}
    report = validate_resources(bad)
    assert report.valid["Procedure"] == []
    assert report.quarantined[0]["id"] == "p1"


def test_date_anchor_uses_mid_year_and_offsets():
    a = DateAnchor(2010)
    assert a.iso(0) == "2010-07-01"
    assert a.iso(65) == "2010-09-04"
    assert DateAnchor(None).iso(10) is None


def test_treatment_classification():
    assert classify_treatment("Surgery, NOS") == "surgery"
    assert classify_treatment("Radiation, External Beam") == "radiation"
    assert classify_treatment("Brachytherapy, High Dose") == "radiation"
    assert classify_treatment("Hormone Therapy") == "hormone_therapy"
    assert classify_treatment("Targeted Molecular Therapy") == "targeted_therapy"
    assert classify_treatment("Pharmaceutical Therapy, NOS") == "pharmaceutical_nos"


def test_patient_resource_carries_us_core_race_and_org(gdc_cases):
    case = next(c for c in gdc_cases if (c.get("demographic") or {}).get("race") == "white")
    out = map_case(case)
    patient = out["Patient"][0]
    race = [e for e in patient["extension"] if e["url"].endswith("us-core-race")]
    assert race and race[0]["extension"][0]["valueCoding"]["code"] == "2106-3"
    assert patient["managingOrganization"]["reference"].startswith("Organization/tss-")


def test_not_given_treatments_are_marked_not_done(gdc_cases):
    statuses = {r["status"] for c in gdc_cases for r in map_case(c).get("Procedure", [])
                if any(e.get("valueString") == "no" for e in r["extension"] if e["url"].endswith("treatment-given"))}
    assert statuses <= {"not-done"}


def test_biomarkers_use_loinc(gdc_cases):
    obs = [o for c in gdc_cases for o in map_case(c).get("Observation", []) if o["category"][0]["coding"][0]["code"] == "laboratory"]
    codes = {o["code"]["coding"][0]["code"] for o in obs}
    assert codes <= {"16112-5", "16113-3", "48676-1"}
    assert obs, "fixture should contain ER/PR/HER2 results"


def test_flatten_produces_every_table_with_hash(gdc_cases):
    frames = flatten(map_cases(gdc_cases), "test-run")
    assert set(frames) == set(TABLES)
    for df in frames.values():
        assert df["id"].n_unique() == df.height
        assert df["record_hash"].null_count() == 0


def test_record_hash_is_order_independent():
    assert record_hash({"a": 1, "b": [1, 2]}) == record_hash({"b": [1, 2], "a": 1})
    assert record_hash({"a": 1}) != record_hash({"a": 2})
