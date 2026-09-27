"""Flatten FHIR resources into typed, analysis-friendly rows (one Polars DataFrame per resource type).
The full resource JSON is retained in a ``resource`` column for audit / replay."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

import polars as pl

from oncoinsight.fhir.gdc_to_fhir import EXT


def _ext(resource: dict, name: str) -> object:
    for e in resource.get("extension") or []:
        if e.get("url") == f"{EXT}/{name}":
            for k, v in e.items():
                if k.startswith("value"):
                    return v
    return None


def _us_core(resource: dict, name: str) -> str | None:
    for e in resource.get("extension") or []:
        if e.get("url", "").endswith(f"us-core-{name}"):
            for sub in e.get("extension") or []:
                if sub.get("url") == "text":
                    return sub.get("valueString")
    return None


def _ref_id(ref: dict | None) -> str | None:
    if not ref or "reference" not in ref:
        return None
    return ref["reference"].split("/", 1)[1]


def _first_ref(refs: list | None) -> str | None:
    return _ref_id(refs[0]) if refs else None


def _coding(cc: dict | None, attr: str = "code") -> str | None:
    if not cc:
        return None
    codings = cc.get("coding") or []
    return codings[0].get(attr) if codings else None


def _qty(resource: dict, name: str) -> tuple[float | None, str | None]:
    q = _ext(resource, name)
    return (q.get("value"), q.get("unit")) if isinstance(q, dict) else (None, None)


def record_hash(resource: dict) -> str:
    return hashlib.sha256(json.dumps(resource, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def flat_patient(r: dict) -> dict:
    return {
        "id": r["id"],
        "gdc_barcode": (r.get("identifier") or [{}])[0].get("value"),
        "gender": r.get("gender"),
        "birth_year": int(r["birthDate"][:4]) if r.get("birthDate") else None,
        "deceased": bool(r.get("deceasedDateTime")) or bool(r.get("deceasedBoolean")),
        "deceased_date": r.get("deceasedDateTime"),
        "race": _us_core(r, "race"),
        "ethnicity": _us_core(r, "ethnicity"),
        "age_at_diagnosis_years": _ext(r, "age-at-diagnosis-years"),
        "age_is_obfuscated": _ext(r, "age-is-obfuscated"),
        "days_to_death": _ext(r, "days-to-death"),
        "vital_status": _ext(r, "gdc-vital-status"),
        "country_of_residence": _ext(r, "country-of-residence"),
        "organization_id": _ref_id(r.get("managingOrganization")),
    }


def flat_organization(r: dict) -> dict:
    return {"id": r["id"], "tss_code": (r.get("identifier") or [{}])[0].get("value"), "name": r.get("name"),
            "bcr_id": _ext(r, "bcr-id")}


def flat_condition(r: dict) -> dict:
    morph = _ext(r, "histology-morphology-behavior")
    stage = (r.get("stage") or [{}])[0].get("summary", {}).get("text")
    return {
        "id": r["id"], "patient_id": _ref_id(r.get("subject")),
        "icd10_code": _coding(r.get("code")), "diagnosis_text": (r.get("code") or {}).get("text"),
        "is_primary": _ext(r, "is-primary-diagnosis"),
        "days_from_index_diagnosis": _ext(r, "days-from-index-diagnosis"),
        "year_of_diagnosis": _ext(r, "year-of-diagnosis"),
        "morphology_code": _coding(morph) if isinstance(morph, dict) else None,
        "classification_of_tumor": _ext(r, "classification-of-tumor"),
        "ajcc_staging_edition": _ext(r, "ajcc-staging-edition"),
        "method_of_diagnosis": _ext(r, "method-of-diagnosis"),
        "prior_treatment": _ext(r, "prior-treatment"),
        "prior_malignancy": _ext(r, "prior-malignancy"),
        "laterality": ((r.get("bodySite") or [{}])[0].get("text") or "").replace(" breast", "") or None,
        "onset_date": r.get("onsetDateTime"),
        "stage_group": stage,
    }


def flat_observation(r: dict) -> dict:
    cats = r.get("category") or [{}]
    return {
        "id": r["id"], "patient_id": _ref_id(r.get("subject")), "condition_id": _first_ref(r.get("focus")),
        "encounter_id": _ref_id(r.get("encounter")), "category": _coding(cats[0]),
        "code": _coding(r.get("code")), "code_display": _coding(r.get("code"), "display"),
        "code_text": (r.get("code") or {}).get("text"),
        "value_text": (r.get("valueCodeableConcept") or {}).get("text"),
        "value_integer": r.get("valueInteger"),
        "method": (r.get("method") or {}).get("text"),
        "biomarker": _ext(r, "biomarker"),
        "days_from_diagnosis": _ext(r, "days-from-diagnosis"),
        "effective_date": r.get("effectiveDateTime"),
        "recurrence_site": _ext(r, "recurrence-anatomic-site"),
        "days_to_recurrence": _ext(r, "days-to-recurrence"),
        "days_to_progression": _ext(r, "days-to-progression"),
    }


def _treatment_common(r: dict) -> dict:
    return {
        "id": r["id"], "patient_id": _ref_id(r.get("subject")), "condition_id": _first_ref(r.get("reasonReference")),
        "status": r.get("status"), "modality": _ext(r, "treatment-modality"),
        "days_to_treatment_start": _ext(r, "days-to-treatment-start"),
        "days_to_treatment_end": _ext(r, "days-to-treatment-end"),
        "treatment_intent": _ext(r, "treatment-intent"), "treatment_outcome": _ext(r, "treatment-outcome"),
        "treatment_given": _ext(r, "treatment-given"), "initial_disease_status": _ext(r, "initial-disease-status"),
        "clinical_trial": _ext(r, "clinical-trial"), "regimen_or_line": _ext(r, "regimen-or-line"),
        "number_of_cycles": _ext(r, "number-of-cycles"), "course_number": _ext(r, "course-number"),
        "organization_id": _ref_id(((r.get("performer") or [{}])[0]).get("actor")),
    }


def flat_procedure(r: dict) -> dict:
    period = r.get("performedPeriod") or {}
    pdose, punit = _qty(r, "prescribed-dose")
    ddose, dunit = _qty(r, "delivered-dose")
    return {
        **_treatment_common(r),
        "treatment_type": (r.get("code") or {}).get("text"),
        "number_of_fractions": _ext(r, "number-of-fractions"),
        "prescribed_dose": pdose, "prescribed_dose_unit": punit,
        "delivered_dose": ddose, "delivered_dose_unit": dunit,
        "margin_status": _ext(r, "margin-status"),
        "body_sites": "; ".join(b.get("text", "") for b in r.get("bodySite") or []) or None,
        "period_start": period.get("start"), "period_end": period.get("end"),
    }


def flat_medication(r: dict) -> dict:
    period = r.get("effectivePeriod") or {}
    ddose, dunit = _qty(r, "delivered-dose")
    med = r.get("medicationCodeableConcept") or {}
    return {
        **_treatment_common(r),
        "fhir_resource_type": r["resourceType"],
        "agent": med.get("text"), "agent_code": _coding(med),
        "delivered_dose": ddose, "delivered_dose_unit": dunit, "route": _ext(r, "route"),
        "period_start": period.get("start"), "period_end": period.get("end"),
    }


def flat_encounter(r: dict) -> dict:
    return {
        "id": r["id"], "patient_id": _ref_id(r.get("subject")), "status": r.get("status"),
        "encounter_class": (r.get("class") or {}).get("code"),
        "timepoint": ((r.get("type") or [{}])[0]).get("text"),
        "days_from_diagnosis": _ext(r, "days-from-diagnosis"),
        "period_start": (r.get("period") or {}).get("start"),
        "organization_id": _ref_id(r.get("serviceProvider")),
        "condition_id": _first_ref(r.get("reasonReference")),
    }


I64, F64, STR, BOOL = pl.Int64, pl.Float64, pl.Utf8, pl.Boolean

# Target raw table -> (source resource types, flattener, explicit schema for non-string columns)
TABLES: dict[str, tuple[tuple[str, ...], Callable[[dict], dict], dict[str, pl.DataType]]] = {
    "fhir_patient": (("Patient",), flat_patient,
                     {"birth_year": I64, "deceased": BOOL, "age_at_diagnosis_years": I64, "age_is_obfuscated": BOOL,
                      "days_to_death": I64}),
    "fhir_organization": (("Organization",), flat_organization, {}),
    "fhir_condition": (("Condition",), flat_condition,
                       {"is_primary": BOOL, "days_from_index_diagnosis": I64, "year_of_diagnosis": I64}),
    "fhir_observation": (("Observation",), flat_observation,
                         {"value_integer": I64, "days_from_diagnosis": I64, "days_to_recurrence": I64,
                          "days_to_progression": I64}),
    "fhir_procedure": (("Procedure",), flat_procedure,
                       {"days_to_treatment_start": I64, "days_to_treatment_end": I64, "number_of_cycles": I64,
                        "course_number": I64, "number_of_fractions": I64, "prescribed_dose": F64, "delivered_dose": F64}),
    "fhir_medication": (("MedicationAdministration", "MedicationStatement"), flat_medication,
                        {"days_to_treatment_start": I64, "days_to_treatment_end": I64, "number_of_cycles": I64,
                         "course_number": I64, "delivered_dose": F64}),
    "fhir_encounter": (("Encounter",), flat_encounter, {"days_from_diagnosis": I64}),
}


def flatten(resources: dict[str, list[dict]], source_run_id: str) -> dict[str, pl.DataFrame]:
    frames: dict[str, pl.DataFrame] = {}
    for table, (rtypes, fn, typed) in TABLES.items():
        rows = []
        for rtype in rtypes:
            for r in resources.get(rtype, []):
                row = fn(r)
                row["resource"] = json.dumps(r, separators=(",", ":"))
                row["record_hash"] = record_hash(r)
                row["source_run_id"] = source_run_id
                rows.append(row)
        if not rows:
            continue
        cols = list(rows[0].keys())
        schema = {c: typed.get(c, STR) for c in cols}
        frames[table] = pl.DataFrame(rows, schema=schema, strict=False).unique(subset=["id"], keep="last")
    return frames
