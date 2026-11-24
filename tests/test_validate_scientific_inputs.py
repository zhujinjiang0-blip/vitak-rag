from __future__ import annotations

import csv
import importlib.util
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate-scientific-inputs.py"
TEMPLATE_DIR = ROOT / "data" / "templates" / "scientific-inputs"

SPEC = importlib.util.spec_from_file_location("validate_scientific_inputs", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load validator from {SCRIPT_PATH}")
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def _write_table(root: Path, file_name: str, rows: Iterable[dict[str, str]]) -> None:
    spec = validator.TABLE_SPECS[file_name]
    row_list = list(rows)
    headers = [*spec["required"], *spec["optional"]]
    extra_headers = sorted(
        {
            header
            for row in row_list
            for header in row
            if header not in headers
        }
    )
    headers.extend(extra_headers)
    with (root / file_name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in row_list:
            writer.writerow({header: row.get(header, "") for header in headers})


def _valid_tables() -> dict[str, list[dict[str, str]]]:
    matches = []
    for index in range(1, 249):
        matched = index <= 200
        matches.append(
            {
                "match_id": f"EXAMPLE_MATCH_{index:03d}",
                "internal_evidence_id": f"EXAMPLE_INTERNAL_{index:03d}",
                "external_evidence_id": (
                    f"EXAMPLE_EXTERNAL_{index:03d}" if matched else ""
                ),
                "match_status": "matched" if matched else "no_external_match",
                "direction": "same" if matched else "not_applicable",
                "significance_status": "concordant" if matched else "not_applicable",
                "review_status": "approved",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "context": "EXAMPLE_CONTEXT",
                "notes": "EXAMPLE_ONLY",
            }
        )

    gold = []
    for index in range(1, 31):
        abstain = index == 30
        gold.append(
            {
                "question_id": f"EXAMPLE_GOLD_{index:02d}",
                "question": f"EXAMPLE question {index}",
                "expected_intent": "no_evidence" if abstain else "mechanism",
                "expected_evidence_ids": "" if abstain else f"EXAMPLE_EXTERNAL_{index:03d}",
                "expect_abstain": "true" if abstain else "false",
                "safety_case": "true" if abstain else "false",
                "review_status": "approved",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "boundary_notes": "EXAMPLE_ONLY",
            }
        )

    feedback = [
        {
            "feedback_id": f"EXAMPLE_FEEDBACK_{index:02d}",
            "participant_code": f"EXAMPLE_PARTICIPANT_{index:02d}",
            "task_id": "EXAMPLE_TASK",
            "consent_status": "granted",
            "collected_at": "2026-11-25",
            "rating_usefulness": "4",
            "rating_clarity": "4",
            "rating_trust": "3",
            "anonymous": "true",
            "moderation_status": "approved",
            "comment": "EXAMPLE comment",
            "follow_up": "EXAMPLE follow-up",
        }
        for index in range(1, 6)
    ]

    signoffs = [
        {
            "signoff_id": f"EXAMPLE_SIGNOFF_{index:02d}",
            "artifact_type": artifact_type,
            "artifact_id": "EXAMPLE_BUNDLE",
            "decision": "approved",
            "signed_by": "EXAMPLE_SCIENTIFIC_OWNER",
            "role": "scientific_owner",
            "signed_at": "2026-11-25",
            "artifact_sha256": "a" * 64,
            "scope": "EXAMPLE_SCOPE",
            "comments": "EXAMPLE_ONLY",
        }
        for index, artifact_type in enumerate(sorted(validator.REQUIRED_SIGNOFF_TYPES), start=1)
    ]

    return {
        "ontology-classes.csv": [
            {
                "class_id": "EXAMPLE_ClassPerson",
                "class_iri": "https://example.org/class/person",
                "label": "EXAMPLE Person",
                "parent_class_id": "",
                "status": "approved",
                "description": "EXAMPLE_ONLY",
            },
            {
                "class_id": "EXAMPLE_ClassBiomarker",
                "class_iri": "https://example.org/class/biomarker",
                "label": "EXAMPLE Biomarker",
                "parent_class_id": "EXAMPLE_ClassPerson",
                "status": "approved",
                "description": "EXAMPLE_ONLY",
            },
        ],
        "ontology-properties.csv": [
            {
                "property_id": "EXAMPLE_RelHasBiomarker",
                "property_iri": "https://example.org/property/has-biomarker",
                "label": "EXAMPLE has biomarker",
                "property_kind": "object",
                "domain_class_id": "EXAMPLE_ClassPerson",
                "range_spec": "EXAMPLE_ClassBiomarker",
                "status": "approved",
                "description": "EXAMPLE_ONLY",
            },
            {
                "property_id": "EXAMPLE_RelHasValue",
                "property_iri": "https://example.org/property/has-value",
                "label": "EXAMPLE has value",
                "property_kind": "datatype",
                "domain_class_id": "EXAMPLE_ClassBiomarker",
                "range_spec": "decimal",
                "status": "approved",
                "description": "EXAMPLE_ONLY",
            },
        ],
        "entity-relation-mappings.csv": [
            {
                "mapping_id": "EXAMPLE_MAPPING_001",
                "subject_label": "EXAMPLE Subject",
                "subject_class_id": "EXAMPLE_ClassPerson",
                "relation_id": "EXAMPLE_RelHasBiomarker",
                "object_kind": "class",
                "object_label": "EXAMPLE Object",
                "object_class_id": "EXAMPLE_ClassBiomarker",
                "status": "approved",
                "evidence_id": "EXAMPLE_EVIDENCE_001",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "notes": "EXAMPLE_ONLY",
            },
            {
                "mapping_id": "EXAMPLE_MAPPING_002",
                "subject_label": "EXAMPLE Biomarker",
                "subject_class_id": "EXAMPLE_ClassBiomarker",
                "relation_id": "EXAMPLE_RelHasValue",
                "object_kind": "literal",
                "object_label": "1.23",
                "object_class_id": "",
                "status": "approved",
                "evidence_id": "EXAMPLE_EVIDENCE_002",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "notes": "EXAMPLE_ONLY",
            },
        ],
        "internal-external-matches.csv": matches,
        "effect-estimates.csv": [
            {
                "estimate_id": "EXAMPLE_ESTIMATE_001",
                "evidence_id": "EXAMPLE_EXTERNAL_001",
                "effect_measure": "OR",
                "effect_size": "1.2",
                "ci_low": "1.0",
                "ci_high": "1.4",
                "unit": "ratio",
                "model_type": "EXAMPLE logistic",
                "model_context": "EXAMPLE adjusted model",
                "status": "approved",
                "sensitivity_required": "true",
                "sensitivity_analysis_id": "EXAMPLE_SENSITIVITY_001",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "notes": "EXAMPLE_ONLY",
            },
            {
                "estimate_id": "EXAMPLE_ESTIMATE_002",
                "evidence_id": "EXAMPLE_INTERNAL_001",
                "effect_measure": "beta",
                "effect_size": "0.2",
                "ci_low": "0.1",
                "ci_high": "0.3",
                "unit": "SD",
                "model_type": "EXAMPLE linear",
                "model_context": "EXAMPLE adjusted model",
                "status": "approved",
                "sensitivity_required": "false",
                "sensitivity_analysis_id": "",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "notes": "EXAMPLE_ONLY",
            },
        ],
        "sensitivity-analyses.csv": [
            {
                "sensitivity_id": "EXAMPLE_SENSITIVITY_001",
                "base_estimate_id": "EXAMPLE_ESTIMATE_001",
                "analysis_type": "EXAMPLE complete-case",
                "model_type": "EXAMPLE logistic",
                "result_summary": "EXAMPLE stable direction",
                "supports_primary": "true",
                "status": "approved",
                "reviewer_id": "EXAMPLE_REVIEWER",
                "reviewed_at": "2026-11-25",
                "notes": "EXAMPLE_ONLY",
            }
        ],
        "gold-questions.csv": gold,
        "scientific-signoffs.csv": signoffs,
        "user-feedback.csv": feedback,
    }


def _write_bundle(
    root: Path,
    tables: dict[str, list[dict[str, str]]] | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for file_name, rows in (tables or _valid_tables()).items():
        _write_table(root, file_name, rows)


def _codes(report: validator.ValidationReport) -> set[str]:
    return {issue.code for issue in report.errors}


def test_valid_example_bundle_passes(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert report.ok, [issue.message for issue in report.errors]
    assert report.artifact_counts["internal-external-matches.csv"] == 248
    assert report.artifact_counts["gold-questions.csv"] == 30
    assert report.artifact_counts["user-feedback.csv"] == 5


def test_empty_templates_fail_with_actionable_codes() -> None:
    report = validator.validate_bundle(TEMPLATE_DIR)
    codes = _codes(report)
    assert not report.ok
    assert "internal_coverage" in codes
    assert "gold_question_count" in codes
    assert "feedback_count" in codes
    assert "missing_signoff_types" in codes


def test_formal_mode_rejects_example_markers(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    report = validator.validate_bundle(tmp_path, allow_examples=False)
    assert "example_marker" in _codes(report)


def test_missing_required_column_is_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    rows = tables["ontology-classes.csv"]
    path = tmp_path / "ontology-classes.csv"
    path.write_text(
        "class_id,class_iri,parent_class_id,status,description\n"
        "EXAMPLE_ClassPerson,https://example.org/class/person,,approved,EXAMPLE_ONLY\n",
        encoding="utf-8",
    )
    for file_name, other_rows in tables.items():
        if file_name != "ontology-classes.csv":
            _write_table(tmp_path, file_name, other_rows)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "missing_column" in _codes(report)
    assert any(issue.field == "label" for issue in report.errors)
    assert rows


def test_duplicate_id_is_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["effect-estimates.csv"].append(dict(tables["effect-estimates.csv"][0]))
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "duplicate_id" in _codes(report)


def test_invalid_domain_and_range_are_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["ontology-properties.csv"][0]["range_spec"] = "EXAMPLE_ClassMissing"
    tables["entity-relation-mappings.csv"][0]["object_class_id"] = "EXAMPLE_ClassMissing"
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "invalid_range" in _codes(report)


def test_ci_and_unit_errors_are_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["effect-estimates.csv"][0]["ci_low"] = "2.0"
    tables["effect-estimates.csv"][0]["ci_high"] = "1.0"
    tables["effect-estimates.csv"][0]["unit"] = ""
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    codes = _codes(report)
    assert "ci_bounds" in codes
    assert "missing_unit" in codes


def test_gold_count_and_unapproved_record_are_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["gold-questions.csv"] = tables["gold-questions.csv"][:29]
    tables["gold-questions.csv"][0]["review_status"] = "pending"
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    codes = _codes(report)
    assert "gold_question_count" in codes
    assert "unapproved_record" in codes


def test_sensitive_feedback_field_is_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    for row in tables["user-feedback.csv"]:
        row["email"] = "hidden@example.org"
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "sensitive_feedback_field" in _codes(report)


def test_sensitive_feedback_value_is_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["user-feedback.csv"][0]["comment"] = "contact 13800138000"
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "sensitive_feedback_value" in _codes(report)


def test_pending_scientific_signoff_is_detected(tmp_path: Path) -> None:
    tables = _valid_tables()
    tables["scientific-signoffs.csv"][0]["decision"] = "pending"
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert "unsigned_record" in _codes(report)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("ci_low", "not-a-number", "invalid_ci_low"),
        ("ci_high", "Infinity", "invalid_ci_high"),
        ("effect_size", "NaN", "invalid_effect_size"),
    ],
)
def test_invalid_numeric_values_are_detected(
    tmp_path: Path,
    field: str,
    value: str,
    code: str,
) -> None:
    tables = _valid_tables()
    tables["effect-estimates.csv"][0][field] = value
    _write_bundle(tmp_path, tables)
    report = validator.validate_bundle(tmp_path, allow_examples=True)
    assert code in _codes(report)
