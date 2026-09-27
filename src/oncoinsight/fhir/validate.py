"""Structural validation of generated FHIR resources against the R4B schema (fhir.resources / pydantic).
Invalid resources are quarantined rather than silently dropped."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field

MODEL_MODULES = {
    "Patient": "patient", "Organization": "organization", "Condition": "condition",
    "Observation": "observation", "Procedure": "procedure", "Encounter": "encounter",
    "MedicationAdministration": "medicationadministration", "MedicationStatement": "medicationstatement",
}


@dataclass
class ValidationReport:
    valid: dict[str, list[dict]] = field(default_factory=dict)
    quarantined: list[dict] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.valid.items()}


def _model(resource_type: str):
    mod = importlib.import_module(f"fhir.resources.R4B.{MODEL_MODULES[resource_type]}")
    return getattr(mod, resource_type)


def validate_resources(resources: dict[str, list[dict]]) -> ValidationReport:
    report = ValidationReport()
    for rtype, items in resources.items():
        model = _model(rtype)
        ok: list[dict] = []
        for r in items:
            try:
                model.model_validate(r)
                ok.append(r)
            except Exception as exc:  # pydantic.ValidationError, plus fhir.resources value errors
                report.quarantined.append({"resourceType": rtype, "id": r.get("id"), "error": str(exc)[:2000], "resource": r})
        report.valid[rtype] = ok
    return report
