"""Map GDC TCGA-BRCA clinical records to FHIR R4 (R4B) resources, loosely following the HL7 mCODE
(minimal Common Oncology Data Elements) patterns.

Resources produced:  Organization (tissue source site / hospital), Patient, Condition (primary cancer),
Observation (AJCC stage group + TNM, ER/PR/HER2, lymph node counts, disease status, recurrence),
Procedure (surgery, radiation), MedicationAdministration (dated drug therapy), MedicationStatement
(undated / not-given drug therapy), Encounter (follow-up visits).

Dates: TCGA publishes day offsets from the index diagnosis plus ``year_of_diagnosis`` only. For FHIR
dateTimes we anchor day 0 at 1 July of the diagnosis year (a standard de-identification convention)
and ALWAYS also carry the exact relative offset in the ``days-from-diagnosis`` extension. All interval
analytics in the warehouse use the exact offsets, never the anchored dates.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

BASE = "https://oncoinsight.dev/fhir"
EXT = f"{BASE}/StructureDefinition"
CS = f"{BASE}/CodeSystem"
GDC_CASE_SYSTEM = "https://portal.gdc.cancer.gov/cases"
TSS_SYSTEM = "https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/tissue-source-site-codes"
LOINC = "http://loinc.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"
ICDO3_MORPH = "urn:oid:2.16.840.1.113883.6.43.1"
OMB_RACE = "urn:oid:2.16.840.1.113883.6.238"
DAR = "http://hl7.org/fhir/StructureDefinition/data-absent-reason"

MISSING = {None, "", "not reported", "Not Reported", "unknown", "Unknown", "Not Applicable", "not applicable", "--"}

# LOINC codes used by the mCODE implementation guide
LOINC_STAGE_GROUP_PATH = ("21902-2", "Stage group.pathology Cancer")
LOINC_T_PATH = ("21899-0", "Primary tumor.pathology Cancer")
LOINC_N_PATH = ("21900-6", "Regional lymph nodes.pathology Cancer")
LOINC_M_PATH = ("21901-4", "Distant metastases.pathology Cancer")
LOINC_NODES_POS = ("21893-3", "Regional lymph nodes positive [#] Specimen")
LOINC_NODES_EXAM = ("21894-1", "Regional lymph nodes examined [#] Specimen")
LOINC_DISEASE_STATUS = ("97509-4", "Cancer disease progression")
BIOMARKER_LOINC = {
    "ESR1": ("16112-5", "Estrogen receptor [Interpretation] in Tissue", "ER"),
    "PGR": ("16113-3", "Progesterone receptor [Interpretation] in Tissue", "PR"),
    "ERBB2": ("48676-1", "HER2 [Interpretation] in Tissue", "HER2"),
}
INTERPRETABLE = {"Positive", "Negative", "Equivocal"}

OMB_RACE_CODES = {
    "white": ("2106-3", "White"),
    "black or african american": ("2054-5", "Black or African American"),
    "asian": ("2028-9", "Asian"),
    "american indian or alaska native": ("1002-5", "American Indian or Alaska Native"),
    "native hawaiian or other pacific islander": ("2076-8", "Native Hawaiian or Other Pacific Islander"),
}
OMB_ETHNICITY_CODES = {
    "hispanic or latino": ("2135-2", "Hispanic or Latino"),
    "not hispanic or latino": ("2186-5", "Not Hispanic or Latino"),
}

PROCEDURE_TYPES = ("surgery", "radiation", "brachytherapy")


def _norm(v: object) -> object:
    """GDC returns some fields as lists (e.g. route_of_administration); flatten them to text."""
    if isinstance(v, list):
        vals = [str(x) for x in v if x not in MISSING]
        return "; ".join(vals) if vals else None
    return v


def _present(v: object) -> bool:
    return _norm(v) not in MISSING


def _ext(name: str, value_key: str, value: object) -> dict:
    return {"url": f"{EXT}/{name}", value_key: value}


def _day_ext(name: str, days: int | float | None) -> list[dict]:
    return [] if days is None else [_ext(name, "valueInteger", int(days))]


def _str_ext(name: str, v: object) -> list[dict]:
    return [_ext(name, "valueString", str(_norm(v)))] if _present(v) else []


def _cc(system: str | None, code: str | None, display: str | None = None, text: str | None = None) -> dict:
    cc: dict = {}
    if code:
        coding = {"code": code}
        if system:
            coding["system"] = system
        if display:
            coding["display"] = display
        cc["coding"] = [coding]
    if text or display:
        cc["text"] = text or display
    return cc


def _slug(v: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in v.lower()).strip("-")


class DateAnchor:
    """Converts day offsets into ISO dates relative to the anchored diagnosis date."""

    def __init__(self, year_of_diagnosis: int | None):
        self.day0 = date(int(year_of_diagnosis), 7, 1) if year_of_diagnosis else None

    def iso(self, days: int | float | None) -> str | None:
        if self.day0 is None or days is None:
            return None
        return (self.day0 + timedelta(days=int(days))).isoformat()


def classify_treatment(treatment_type: str) -> str:
    """Collapse GDC ``treatment_type`` values into the modality used for pathways."""
    t = (treatment_type or "").lower()
    if "surgery" in t:
        return "surgery"
    if "radiation" in t or "brachytherapy" in t:
        return "radiation"
    if "chemotherapy" in t:
        return "chemotherapy"
    if "hormone" in t:
        return "hormone_therapy"
    if "targeted" in t:
        return "targeted_therapy"
    if "immunotherapy" in t:
        return "immunotherapy"
    if "bisphosphonate" in t:
        return "bisphosphonate"
    if "ancillary" in t:
        return "ancillary"
    return "pharmaceutical_nos"


def _status(given: str | None, outcome: str | None, kind: str) -> str:
    if given == "yes":
        if outcome == "Treatment Ongoing":
            return "in-progress"
        return "completed"
    if given == "no":
        return {"procedure": "not-done", "admin": "not-done", "statement": "not-taken"}[kind]
    return "unknown"


def _primary_diagnoses(case: dict) -> list[dict]:
    dx = case.get("diagnoses") or []
    return [d for d in dx if d.get("diagnosis_is_primary_disease") is not False]


def map_case(case: dict) -> dict[str, list[dict]]:
    """Map one GDC case (with expansions) into FHIR resources grouped by resourceType."""
    out: dict[str, list[dict]] = defaultdict(list)
    case_id = case["case_id"]
    barcode = case["submitter_id"]
    patient_ref = {"reference": f"Patient/{case_id}"}
    demo = case.get("demographic") or {}
    tss = case.get("tissue_source_site") or {}
    primaries = _primary_diagnoses(case)
    index_dx = next((d for d in primaries if d.get("days_to_diagnosis") == 0), primaries[0] if primaries else None)
    anchor = DateAnchor(index_dx.get("year_of_diagnosis") if index_dx else None)

    # ---------------- Organization (hospital / tissue source site) ----------------
    org_ref = None
    if tss.get("code"):
        org_id = f"tss-{tss['code']}"
        org_ref = {"reference": f"Organization/{org_id}", "display": tss.get("name")}
        out["Organization"].append({
            "resourceType": "Organization", "id": org_id, "active": True,
            "identifier": [{"system": TSS_SYSTEM, "value": tss["code"]}],
            "name": tss.get("name"),
            "type": [_cc("http://terminology.hl7.org/CodeSystem/organization-type", "prov", "Healthcare Provider")],
            "extension": _str_ext("bcr-id", tss.get("bcr_id")),
        })

    # ---------------- Patient ----------------
    ext: list[dict] = []
    race = (demo.get("race") or "").lower()
    if race in OMB_RACE_CODES:
        code, disp = OMB_RACE_CODES[race]
        ext.append({"url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race", "extension": [
            {"url": "ombCategory", "valueCoding": {"system": OMB_RACE, "code": code, "display": disp}},
            {"url": "text", "valueString": disp}]})
    eth = (demo.get("ethnicity") or "").lower()
    if eth in OMB_ETHNICITY_CODES:
        code, disp = OMB_ETHNICITY_CODES[eth]
        ext.append({"url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity", "extension": [
            {"url": "ombCategory", "valueCoding": {"system": OMB_RACE, "code": code, "display": disp}},
            {"url": "text", "valueString": disp}]})
    if demo.get("age_at_index") is not None:
        ext.append(_ext("age-at-diagnosis-years", "valueInteger", int(demo["age_at_index"])))
    if demo.get("age_is_obfuscated") is not None:
        ext.append(_ext("age-is-obfuscated", "valueBoolean", bool(demo["age_is_obfuscated"])))
    ext += _day_ext("days-to-death", demo.get("days_to_death"))
    ext += _str_ext("country-of-residence", demo.get("country_of_residence_at_enrollment"))
    ext += _str_ext("gdc-vital-status", demo.get("vital_status"))

    patient: dict = {
        "resourceType": "Patient", "id": case_id,
        "identifier": [{"system": GDC_CASE_SYSTEM, "value": barcode}],
        "gender": {"female": "female", "male": "male"}.get((demo.get("sex_at_birth") or demo.get("gender") or "").lower(), "unknown"),
        "extension": ext,
    }
    if anchor.day0 and demo.get("age_at_index") is not None:
        patient["birthDate"] = str(anchor.day0.year - int(demo["age_at_index"]))
    if demo.get("vital_status") == "Dead":
        dod = anchor.iso(demo.get("days_to_death"))
        patient["deceasedDateTime" if dod else "deceasedBoolean"] = dod or True
    elif demo.get("vital_status") == "Alive":
        patient["deceasedBoolean"] = False
    if org_ref:
        patient["managingOrganization"] = org_ref
    out["Patient"].append(patient)

    # ---------------- Conditions + stage/TNM/node observations + treatments ----------------
    for dx in case.get("diagnoses") or []:
        dx_id = dx["diagnosis_id"]
        is_primary = dx.get("diagnosis_is_primary_disease") is not False
        dx_days = dx.get("days_to_diagnosis")
        dx_anchor = anchor if is_primary else DateAnchor(dx.get("year_of_diagnosis"))
        cond_ref = {"reference": f"Condition/{dx_id}"}
        cond: dict = {
            "resourceType": "Condition", "id": dx_id,
            "clinicalStatus": _cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"),
            "verificationStatus": _cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed"),
            "category": [_cc("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item")],
            "code": _cc(ICD10, dx.get("icd_10_code"), None, dx.get("primary_diagnosis")),
            "subject": patient_ref,
            "extension": [
                _ext("is-primary-diagnosis", "valueBoolean", is_primary),
                *_day_ext("days-from-index-diagnosis", dx_days),
                *( [_ext("year-of-diagnosis", "valueInteger", int(dx["year_of_diagnosis"]))] if dx.get("year_of_diagnosis") else []),
                *( [_ext("histology-morphology-behavior", "valueCodeableConcept", _cc(ICDO3_MORPH, dx["morphology"]))] if _present(dx.get("morphology")) else []),
                *_str_ext("classification-of-tumor", dx.get("classification_of_tumor")),
                *_str_ext("ajcc-staging-edition", dx.get("ajcc_staging_system_edition")),
                *_str_ext("method-of-diagnosis", dx.get("method_of_diagnosis")),
                *_str_ext("prior-treatment", dx.get("prior_treatment")),
                *_str_ext("prior-malignancy", dx.get("prior_malignancy")),
            ],
        }
        if _present(dx.get("laterality")):
            cond["bodySite"] = [{"text": f"{dx['laterality']} breast"}]
        if dx_anchor.iso(dx_days if dx_days is not None else 0):
            cond["onsetDateTime"] = dx_anchor.iso(dx_days if dx_days is not None else 0)
        if _present(dx.get("ajcc_pathologic_stage")):
            cond["stage"] = [{"summary": {"text": dx["ajcc_pathologic_stage"]},
                              "type": _cc(LOINC, *LOINC_STAGE_GROUP_PATH)}]
        out["Condition"].append(cond)

        def obs(obs_id: str, loinc: tuple[str, str], value: dict, category: str, day: int | None, extra: list | None = None) -> dict:
            o = {"resourceType": "Observation", "id": obs_id, "status": "final",
                 "category": [_cc(f"{CS}/observation-category", category, category.replace("-", " ").title())],
                 "code": _cc(LOINC, *loinc), "subject": patient_ref, "focus": [cond_ref],
                 "extension": _day_ext("days-from-diagnosis", day) + (extra or []), **value}
            if dx_anchor.iso(day):
                o["effectiveDateTime"] = dx_anchor.iso(day)
            return o

        day0 = dx_days if dx_days is not None else 0
        if is_primary:
            for field, loinc in (("ajcc_pathologic_stage", LOINC_STAGE_GROUP_PATH), ("ajcc_pathologic_t", LOINC_T_PATH),
                                 ("ajcc_pathologic_n", LOINC_N_PATH), ("ajcc_pathologic_m", LOINC_M_PATH)):
                if _present(dx.get(field)):
                    out["Observation"].append(obs(f"{dx_id}-{loinc[0]}", loinc, {"valueCodeableConcept": {"text": dx[field]}},
                                                  "tnm-staging", day0))
            for pd in dx.get("pathology_details") or []:
                for field, loinc in (("lymph_nodes_positive", LOINC_NODES_POS), ("lymph_nodes_tested", LOINC_NODES_EXAM)):
                    if pd.get(field) is not None:
                        out["Observation"].append(obs(f"{pd['pathology_detail_id']}-{loinc[0]}", loinc,
                                                      {"valueInteger": int(pd[field])}, "pathology", day0))

        # treatments
        for t in dx.get("treatments") or []:
            modality = classify_treatment(t.get("treatment_type", ""))
            start, end = t.get("days_to_treatment_start"), t.get("days_to_treatment_end")
            common_ext = [
                _ext("treatment-modality", "valueCode", modality),
                *_day_ext("days-to-treatment-start", start),
                *_day_ext("days-to-treatment-end", end),
                *_str_ext("treatment-intent", t.get("treatment_intent_type")),
                *_str_ext("treatment-outcome", t.get("treatment_outcome")),
                *_str_ext("treatment-given", t.get("treatment_or_therapy")),
                *_str_ext("initial-disease-status", t.get("initial_disease_status")),
                *_str_ext("clinical-trial", t.get("clinical_trial_indicator")),
                *_str_ext("regimen-or-line", t.get("regimen_or_line_of_therapy")),
                *( [_ext("number-of-cycles", "valueInteger", int(t["number_of_cycles"]))] if t.get("number_of_cycles") is not None else []),
                *( [_ext("course-number", "valueInteger", int(t["course_number"]))] if t.get("course_number") is not None else []),
            ]
            period = {k: v for k, v in (("start", dx_anchor.iso(start)), ("end", dx_anchor.iso(end))) if v}
            ttype_cc = _cc(f"{CS}/gdc-treatment-type", _slug(t.get("treatment_type", "unknown")), t.get("treatment_type"))
            if modality in ("surgery", "radiation"):
                p: dict = {
                    "resourceType": "Procedure", "id": t["treatment_id"],
                    "status": _status(t.get("treatment_or_therapy"), t.get("treatment_outcome"), "procedure"),
                    "category": _cc(f"{CS}/treatment-modality", modality, modality.title()),
                    "code": ttype_cc, "subject": patient_ref, "reasonReference": [cond_ref],
                    "extension": common_ext + [
                        *( [_ext("number-of-fractions", "valueInteger", int(t["number_of_fractions"]))] if t.get("number_of_fractions") is not None else []),
                        *( [_ext("prescribed-dose", "valueQuantity", {"value": float(t["prescribed_dose"]), "unit": t.get("prescribed_dose_units")})] if t.get("prescribed_dose") is not None else []),
                        *( [_ext("delivered-dose", "valueQuantity", {"value": float(t["treatment_dose"]), "unit": t.get("treatment_dose_units")})] if t.get("treatment_dose") is not None else []),
                        *_str_ext("margin-status", t.get("margin_status")),
                    ],
                }
                if t.get("treatment_anatomic_sites"):
                    p["bodySite"] = [{"text": s} for s in t["treatment_anatomic_sites"]]
                if period:
                    p["performedPeriod"] = period
                if _present(t.get("treatment_outcome")):
                    p["outcome"] = {"text": t["treatment_outcome"]}
                if org_ref:
                    p["performer"] = [{"actor": org_ref}]
                out["Procedure"].append(p)
            else:
                agent = t.get("therapeutic_agents")
                med_cc = _cc(f"{CS}/therapeutic-agent", _slug(agent), agent) if _present(agent) else {"text": t.get("treatment_type")}
                category = _cc(f"{CS}/treatment-modality", modality, modality.replace("_", " ").title())
                dose_ext = []
                if t.get("treatment_dose") is not None:
                    dose_ext.append(_ext("delivered-dose", "valueQuantity",
                                         {"value": float(t["treatment_dose"]), "unit": t.get("treatment_dose_units")}))
                if _present(t.get("route_of_administration")):
                    dose_ext.append(_ext("route", "valueString", _norm(t["route_of_administration"])))
                if period:
                    m: dict = {"resourceType": "MedicationAdministration", "id": t["treatment_id"],
                               "status": _status(t.get("treatment_or_therapy"), t.get("treatment_outcome"), "admin"),
                               "category": category, "medicationCodeableConcept": med_cc, "subject": patient_ref,
                               "reasonReference": [cond_ref], "effectivePeriod": period,
                               "extension": common_ext + dose_ext}
                    if org_ref:
                        m["performer"] = [{"actor": org_ref}]
                    out["MedicationAdministration"].append(m)
                else:
                    status = _status(t.get("treatment_or_therapy"), t.get("treatment_outcome"), "statement")
                    out["MedicationStatement"].append({
                        "resourceType": "MedicationStatement", "id": t["treatment_id"],
                        # MedicationStatement has no "in-progress"; the equivalent is "active"
                        "status": "active" if status == "in-progress" else status,
                        "category": category, "medicationCodeableConcept": med_cc, "subject": patient_ref,
                        "reasonReference": [cond_ref], "extension": common_ext + dose_ext})

    # ---------------- follow-ups: Encounters, disease status, recurrence, biomarkers ----------------
    primary_ref = {"reference": f"Condition/{index_dx['diagnosis_id']}"} if index_dx else None
    for fu in case.get("follow_ups") or []:
        fu_id = fu["follow_up_id"]
        day = fu.get("days_to_follow_up")
        if fu.get("timepoint_category"):
            enc: dict = {"resourceType": "Encounter", "id": fu_id, "status": "finished",
                         "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
                         "type": [_cc(f"{CS}/follow-up-timepoint", _slug(fu["timepoint_category"]), fu["timepoint_category"])],
                         "subject": patient_ref, "extension": _day_ext("days-from-diagnosis", day)}
            if anchor.iso(day):
                enc["period"] = {"start": anchor.iso(day)}
            if org_ref:
                enc["serviceProvider"] = org_ref
            if primary_ref:
                enc["reasonReference"] = [primary_ref]
            out["Encounter"].append(enc)
        if _present(fu.get("disease_response")):
            o = {"resourceType": "Observation", "id": f"{fu_id}-status", "status": "final",
                 "category": [_cc(f"{CS}/observation-category", "disease-status", "Disease Status")],
                 "code": _cc(LOINC, *LOINC_DISEASE_STATUS), "subject": patient_ref,
                 "valueCodeableConcept": _cc(f"{CS}/gdc-disease-response", _slug(fu["disease_response"]), fu["disease_response"]),
                 "encounter": {"reference": f"Encounter/{fu_id}"} if fu.get("timepoint_category") else None,
                 "extension": _day_ext("days-from-diagnosis", day)}
            if primary_ref:
                o["focus"] = [primary_ref]
            if anchor.iso(day):
                o["effectiveDateTime"] = anchor.iso(day)
            out["Observation"].append({k: v for k, v in o.items() if v is not None})
        if fu.get("progression_or_recurrence") == "Yes":
            rday = fu.get("days_to_recurrence") if fu.get("days_to_recurrence") is not None else fu.get("days_to_progression")
            o = {"resourceType": "Observation", "id": f"{fu_id}-recurrence", "status": "final",
                 "category": [_cc(f"{CS}/observation-category", "recurrence", "Recurrence")],
                 "code": _cc(f"{CS}/oncology-event", "progression-or-recurrence", "Progression or recurrence event"),
                 "subject": patient_ref,
                 "valueCodeableConcept": {"text": fu.get("progression_or_recurrence_type") or "Recurrence"},
                 "extension": _day_ext("days-from-diagnosis", rday)
                 + _str_ext("recurrence-anatomic-site", fu.get("progression_or_recurrence_anatomic_site"))
                 + _day_ext("days-to-recurrence", fu.get("days_to_recurrence"))
                 + _day_ext("days-to-progression", fu.get("days_to_progression"))}
            if primary_ref:
                o["focus"] = [primary_ref]
            if anchor.iso(rday):
                o["effectiveDateTime"] = anchor.iso(rday)
            out["Observation"].append(o)
        for mt in fu.get("molecular_tests") or []:
            gene, result = mt.get("gene_symbol"), mt.get("test_result")
            if gene not in BIOMARKER_LOINC or result not in INTERPRETABLE:
                continue
            code, disp, short = BIOMARKER_LOINC[gene]
            o = {"resourceType": "Observation", "id": mt["molecular_test_id"], "status": "final",
                 "category": [_cc("http://terminology.hl7.org/CodeSystem/observation-category", "laboratory", "Laboratory")],
                 "code": _cc(LOINC, code, disp, short), "subject": patient_ref,
                 "valueCodeableConcept": {"text": result},
                 "method": {"text": mt.get("molecular_analysis_method") or "Not reported"},
                 "extension": [_ext("biomarker", "valueCode", short), _ext("gene-symbol", "valueCode", gene)]}
            if primary_ref:
                o["focus"] = [primary_ref]
            out["Observation"].append(o)
    return out


def map_cases(cases: list[dict]) -> dict[str, list[dict]]:
    merged: dict[str, dict[str, dict]] = defaultdict(dict)
    for case in cases:
        for rtype, resources in map_case(case).items():
            for r in resources:
                merged[rtype][r["id"]] = r  # de-duplicate (e.g. Organizations shared by many patients)
    return {rtype: list(by_id.values()) for rtype, by_id in merged.items()}
