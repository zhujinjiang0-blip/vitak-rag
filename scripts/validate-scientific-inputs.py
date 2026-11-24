"""Validate scientific intake CSVs before they are used in formal evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "data" / "templates" / "scientific-inputs"

TABLE_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "ontology-classes.csv": {
        "required": ("class_id", "class_iri", "label", "status"),
        "optional": ("parent_class_id", "description"),
    },
    "ontology-properties.csv": {
        "required": (
            "property_id",
            "property_iri",
            "label",
            "property_kind",
            "domain_class_id",
            "range_spec",
            "status",
        ),
        "optional": ("description",),
    },
    "entity-relation-mappings.csv": {
        "required": (
            "mapping_id",
            "subject_label",
            "subject_class_id",
            "relation_id",
            "object_kind",
            "object_label",
            "status",
            "evidence_id",
            "reviewer_id",
        ),
        "optional": ("object_class_id", "reviewed_at", "notes"),
    },
    "internal-external-matches.csv": {
        "required": (
            "match_id",
            "internal_evidence_id",
            "external_evidence_id",
            "match_status",
            "direction",
            "significance_status",
            "review_status",
            "reviewer_id",
            "reviewed_at",
        ),
        "nonempty": (
            "match_id",
            "internal_evidence_id",
            "match_status",
            "direction",
            "significance_status",
            "review_status",
            "reviewer_id",
            "reviewed_at",
        ),
        "optional": ("context", "notes"),
    },
    "effect-estimates.csv": {
        "required": (
            "estimate_id",
            "evidence_id",
            "effect_measure",
            "effect_size",
            "ci_low",
            "ci_high",
            "unit",
            "model_type",
            "model_context",
            "status",
            "reviewer_id",
        ),
        "optional": (
            "sensitivity_required",
            "sensitivity_analysis_id",
            "reviewed_at",
            "notes",
        ),
    },
    "sensitivity-analyses.csv": {
        "required": (
            "sensitivity_id",
            "base_estimate_id",
            "analysis_type",
            "model_type",
            "result_summary",
            "supports_primary",
            "status",
            "reviewer_id",
        ),
        "optional": ("reviewed_at", "notes"),
    },
    "gold-questions.csv": {
        "required": (
            "question_id",
            "question",
            "expected_intent",
            "expected_evidence_ids",
            "expect_abstain",
            "safety_case",
            "review_status",
            "reviewer_id",
        ),
        "nonempty": (
            "question_id",
            "question",
            "expected_intent",
            "expect_abstain",
            "safety_case",
            "review_status",
            "reviewer_id",
        ),
        "optional": ("boundary_notes",),
    },
    "scientific-signoffs.csv": {
        "required": (
            "signoff_id",
            "artifact_type",
            "artifact_id",
            "decision",
            "signed_by",
            "role",
            "signed_at",
            "artifact_sha256",
        ),
        "optional": ("scope", "comments"),
    },
    "user-feedback.csv": {
        "required": (
            "feedback_id",
            "participant_code",
            "task_id",
            "consent_status",
            "collected_at",
            "rating_usefulness",
            "rating_clarity",
            "rating_trust",
            "anonymous",
            "moderation_status",
        ),
        "optional": ("comment", "follow_up"),
    },
}

DATATYPE_RANGES = {
    "string",
    "integer",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "uri",
}
PROPERTY_KINDS = {"object", "datatype"}
MAPPING_STATUSES = {"approved", "draft", "rejected"}
MATCH_STATUSES = {"matched", "no_external_match", "excluded"}
MATCH_DIRECTIONS = {"same", "opposite", "not_applicable"}
SIGNIFICANCE_STATUSES = {"concordant", "discordant", "not_applicable"}
REVIEW_STATUSES = {"approved", "pending", "rejected"}
SENSITIVITY_SUPPORT = {"true", "false"}
REQUIRED_SIGNOFF_TYPES = {
    "ontology",
    "entity_relation_mapping",
    "internal_external_match",
    "effect_estimate",
    "gold_set",
    "user_feedback",
}
SENSITIVE_HEADER_TOKENS = {
    "name",
    "fullname",
    "firstname",
    "lastname",
    "phone",
    "mobile",
    "telephone",
    "email",
    "address",
    "wechat",
    "weixin",
    "idcard",
    "identity",
    "passport",
    "ipaddress",
    "deviceid",
    "medicalrecord",
    "姓名",
    "手机",
    "电话",
    "邮箱",
    "微信",
    "地址",
    "住址",
    "身份证",
    "护照",
    "病历",
}
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
)
EXAMPLE_MARKER = re.compile(r"(?i)(?:^|[^a-z0-9])example(?:$|[^a-z0-9])|示例")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
IRI_PATTERN = re.compile(r"^(?:https?://|urn:)")


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    file: str
    row: int | None
    field: str | None
    message: str


@dataclass
class TableData:
    file: str
    headers: list[str]
    rows: list[tuple[int, dict[str, str]]]
    load_ok: bool = True


@dataclass
class ValidationReport:
    input_dir: str
    generated_at: str
    allow_examples: bool
    errors: list[Issue]
    warnings: list[Issue]
    artifact_counts: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.ok else "FAIL",
            "input_dir": self.input_dir,
            "generated_at": self.generated_at,
            "allow_examples": self.allow_examples,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "artifact_counts": self.artifact_counts,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
        }


def _issue(
    code: str,
    file: str,
    message: str,
    *,
    row: int | None = None,
    field: str | None = None,
    severity: str = "error",
) -> Issue:
    return Issue(
        code=code,
        severity=severity,
        file=file,
        row=row,
        field=field,
        message=message,
    )


def _load_table(
    input_dir: Path,
    file_name: str,
    spec: dict[str, tuple[str, ...]],
    errors: list[Issue],
    warnings: list[Issue],
) -> TableData:
    path = input_dir / file_name
    if not path.is_file():
        errors.append(_issue("missing_file", file_name, f"Required file does not exist: {path}"))
        return TableData(file=file_name, headers=[], rows=[], load_ok=False)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_headers = reader.fieldnames or []
        headers = [header.strip() if header else "" for header in raw_headers]
        if any(not header for header in headers):
            errors.append(_issue("empty_header", file_name, "CSV contains an empty column name"))

        duplicate_headers = [
            header for header, count in Counter(headers).items() if header and count > 1
        ]
        for header in duplicate_headers:
            errors.append(
                _issue("duplicate_column", file_name, f"Duplicate column: {header}", field=header)
            )

        missing_headers = [name for name in spec["required"] if name not in headers]
        for header in missing_headers:
            errors.append(
                _issue(
                    "missing_column",
                    file_name,
                    f"Required column is missing: {header}",
                    field=header,
                )
            )

        known_headers = set(spec["required"]) | set(spec["optional"])
        for header in headers:
            if header and header not in known_headers:
                warnings.append(
                    _issue(
                        "unknown_column",
                        file_name,
                        f"Unknown optional column will be ignored by scientific checks: {header}",
                        field=header,
                        severity="warning",
                    )
                )

        rows: list[tuple[int, dict[str, str]]] = []
        for row_number, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                errors.append(
                    _issue(
                        "extra_values",
                        file_name,
                        "Row has more values than CSV headers",
                        row=row_number,
                    )
                )
            normalized = {
                header: (raw_row.get(header) or "").strip()
                for header in headers
                if header
            }
            if not any(normalized.values()):
                continue
            rows.append((row_number, normalized))

            for field in spec.get("nonempty", spec["required"]):
                if field in normalized and not normalized[field]:
                    errors.append(
                        _issue(
                            "required_value",
                            file_name,
                            f"Required value is empty: {field}",
                            row=row_number,
                            field=field,
                        )
                    )

    return TableData(file=file_name, headers=headers, rows=rows)


def _assert_unique(
    table: TableData,
    field: str,
    errors: list[Issue],
) -> None:
    seen: dict[str, int] = {}
    for row_number, row in table.rows:
        value = row.get(field, "")
        if not value:
            continue
        if value in seen:
            errors.append(
                _issue(
                    "duplicate_id",
                    table.file,
                    f"Duplicate {field}: {value}; first seen on row {seen[value]}",
                    row=row_number,
                    field=field,
                )
            )
        else:
            seen[value] = row_number


def _validate_examples(
    tables: dict[str, TableData],
    allow_examples: bool,
    errors: list[Issue],
) -> None:
    if allow_examples:
        return
    for table in tables.values():
        for row_number, row in table.rows:
            for field, value in row.items():
                if value and EXAMPLE_MARKER.search(value):
                    errors.append(
                        _issue(
                            "example_marker",
                            table.file,
                            "EXAMPLE or 示例 markers are forbidden in formal intake; "
                            "use --allow-examples only for test/demo bundles",
                            row=row_number,
                            field=field,
                        )
                    )


def _is_true(value: str) -> bool:
    return value.lower() == "true"


def _parse_number(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_date(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_bundle(
    input_dir: Path,
    *,
    allow_examples: bool = False,
    expected_internal_count: int = 248,
    min_gold_questions: int = 30,
    max_gold_questions: int = 50,
    min_feedback_rows: int = 5,
    max_feedback_rows: int = 10,
) -> ValidationReport:
    """Validate one scientific intake bundle without modifying its files."""

    input_dir = input_dir.expanduser().resolve()
    errors: list[Issue] = []
    warnings: list[Issue] = []
    tables = {
        file_name: _load_table(input_dir, file_name, spec, errors, warnings)
        for file_name, spec in TABLE_SPECS.items()
    }
    _validate_examples(tables, allow_examples, errors)

    classes = tables["ontology-classes.csv"]
    properties = tables["ontology-properties.csv"]
    mappings = tables["entity-relation-mappings.csv"]
    matches = tables["internal-external-matches.csv"]
    effects = tables["effect-estimates.csv"]
    sensitivities = tables["sensitivity-analyses.csv"]
    gold = tables["gold-questions.csv"]
    signoffs = tables["scientific-signoffs.csv"]
    feedback = tables["user-feedback.csv"]

    for table, field in (
        (classes, "class_id"),
        (properties, "property_id"),
        (mappings, "mapping_id"),
        (matches, "match_id"),
        (effects, "estimate_id"),
        (sensitivities, "sensitivity_id"),
        (gold, "question_id"),
        (signoffs, "signoff_id"),
        (feedback, "feedback_id"),
    ):
        _assert_unique(table, field, errors)

    class_ids = {row.get("class_id", "") for _, row in classes.rows if row.get("class_id")}
    class_iris: set[str] = set()
    for row_number, row in classes.rows:
        class_id = row.get("class_id", "")
        class_iri = row.get("class_iri", "")
        parent = row.get("parent_class_id", "")
        status = row.get("status", "")
        if class_iri:
            if not IRI_PATTERN.match(class_iri):
                errors.append(
                    _issue(
                        "invalid_iri",
                        classes.file,
                        "class_iri must start with http://, https://, or urn:",
                        row=row_number,
                        field="class_iri",
                    )
                )
            if class_iri in class_iris:
                errors.append(
                    _issue(
                        "duplicate_iri",
                        classes.file,
                        f"Duplicate class_iri: {class_iri}",
                        row=row_number,
                        field="class_iri",
                    )
                )
            class_iris.add(class_iri)
        if parent and parent not in class_ids:
            errors.append(
                _issue(
                    "invalid_domain",
                    classes.file,
                    f"parent_class_id does not exist: {parent}",
                    row=row_number,
                    field="parent_class_id",
                )
            )
        if status and status not in MAPPING_STATUSES:
            errors.append(
                _issue(
                    "invalid_status",
                    classes.file,
                    f"Unsupported ontology status: {status}",
                    row=row_number,
                    field="status",
                )
            )
        elif status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    classes.file,
                    f"Ontology class is not approved: {class_id}",
                    row=row_number,
                    field="status",
                )
            )

    property_by_id: dict[str, dict[str, str]] = {}
    property_iris: set[str] = set()
    for row_number, row in properties.rows:
        property_id = row.get("property_id", "")
        property_iri = row.get("property_iri", "")
        property_kind = row.get("property_kind", "")
        domain = row.get("domain_class_id", "")
        range_spec = row.get("range_spec", "")
        status = row.get("status", "")
        if property_id:
            property_by_id[property_id] = row
        if property_iri:
            if not IRI_PATTERN.match(property_iri):
                errors.append(
                    _issue(
                        "invalid_iri",
                        properties.file,
                        "property_iri must start with http://, https://, or urn:",
                        row=row_number,
                        field="property_iri",
                    )
                )
            if property_iri in property_iris:
                errors.append(
                    _issue(
                        "duplicate_iri",
                        properties.file,
                        f"Duplicate property_iri: {property_iri}",
                        row=row_number,
                        field="property_iri",
                    )
                )
            property_iris.add(property_iri)
        if property_kind and property_kind not in PROPERTY_KINDS:
            errors.append(
                _issue(
                    "invalid_property_kind",
                    properties.file,
                    f"property_kind must be object or datatype: {property_kind}",
                    row=row_number,
                    field="property_kind",
                )
            )
        if domain and domain not in class_ids:
            errors.append(
                _issue(
                    "invalid_domain",
                    properties.file,
                    f"domain_class_id does not exist: {domain}",
                    row=row_number,
                    field="domain_class_id",
                )
            )
        if property_kind == "object" and range_spec and range_spec not in class_ids:
            errors.append(
                _issue(
                    "invalid_range",
                    properties.file,
                    f"Object property range class does not exist: {range_spec}",
                    row=row_number,
                    field="range_spec",
                )
            )
        if property_kind == "datatype" and range_spec and range_spec not in DATATYPE_RANGES:
            errors.append(
                _issue(
                    "invalid_range",
                    properties.file,
                    f"Datatype property range is invalid: {range_spec}",
                    row=row_number,
                    field="range_spec",
                )
            )
        if status and status not in MAPPING_STATUSES:
            errors.append(
                _issue(
                    "invalid_status",
                    properties.file,
                    f"Unsupported property status: {status}",
                    row=row_number,
                    field="status",
                )
            )
        elif status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    properties.file,
                    f"Ontology property is not approved: {property_id}",
                    row=row_number,
                    field="status",
                )
            )

    for row_number, row in mappings.rows:
        subject_class = row.get("subject_class_id", "")
        relation_id = row.get("relation_id", "")
        object_kind = row.get("object_kind", "")
        object_class = row.get("object_class_id", "")
        status = row.get("status", "")
        relation = property_by_id.get(relation_id)
        if subject_class and subject_class not in class_ids:
            errors.append(
                _issue(
                    "invalid_domain",
                    mappings.file,
                    f"subject_class_id does not exist: {subject_class}",
                    row=row_number,
                    field="subject_class_id",
                )
            )
        if relation:
            if subject_class and subject_class != relation.get("domain_class_id"):
                errors.append(
                    _issue(
                        "invalid_domain",
                        mappings.file,
                        "subject_class_id does not match relation domain",
                        row=row_number,
                        field="subject_class_id",
                    )
                )
            if object_kind == "class":
                if not object_class:
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            "Class object mapping requires object_class_id",
                            row=row_number,
                            field="object_class_id",
                        )
                    )
                if object_class and object_class not in class_ids:
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            f"object_class_id does not exist: {object_class}",
                            row=row_number,
                            field="object_class_id",
                        )
                    )
                if object_class and object_class != relation.get("range_spec"):
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            "object_class_id does not match relation range",
                            row=row_number,
                            field="object_class_id",
                        )
                    )
                if relation.get("property_kind") != "object":
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            "Class object mapping requires an object property",
                            row=row_number,
                            field="object_kind",
                        )
                    )
            elif object_kind == "literal":
                if relation.get("property_kind") != "datatype":
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            "Literal mapping requires a datatype property",
                            row=row_number,
                            field="object_kind",
                        )
                    )
                if object_class:
                    errors.append(
                        _issue(
                            "invalid_range",
                            mappings.file,
                            "Literal mapping must not set object_class_id",
                            row=row_number,
                            field="object_class_id",
                        )
                    )
            else:
                errors.append(
                    _issue(
                        "invalid_object_kind",
                        mappings.file,
                        f"object_kind must be class or literal: {object_kind}",
                        row=row_number,
                        field="object_kind",
                    )
                )
        elif relation_id:
            errors.append(
                _issue(
                    "unknown_relation",
                    mappings.file,
                    f"relation_id does not exist: {relation_id}",
                    row=row_number,
                    field="relation_id",
                )
            )
        if status and status not in MAPPING_STATUSES:
            errors.append(
                _issue(
                    "invalid_status",
                    mappings.file,
                    f"Unsupported mapping status: {status}",
                    row=row_number,
                    field="status",
                )
            )
        elif status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    mappings.file,
                    f"Entity-relation mapping is not approved: {row.get('mapping_id', '')}",
                    row=row_number,
                    field="status",
                )
            )

    internal_ids = {
        row.get("internal_evidence_id", "")
        for _, row in matches.rows
        if row.get("internal_evidence_id")
    }
    if len(internal_ids) != expected_internal_count:
        errors.append(
            _issue(
                "internal_coverage",
                matches.file,
                f"Expected {expected_internal_count} unique internal_evidence_id values, "
                f"found {len(internal_ids)}",
            )
        )
    for row_number, row in matches.rows:
        status = row.get("match_status", "")
        direction = row.get("direction", "")
        significance = row.get("significance_status", "")
        review_status = row.get("review_status", "")
        if status not in MATCH_STATUSES:
            errors.append(
                _issue(
                    "invalid_match_status",
                    matches.file,
                    f"Unsupported match_status: {status}",
                    row=row_number,
                    field="match_status",
                )
            )
        if direction not in MATCH_DIRECTIONS:
            errors.append(
                _issue(
                    "invalid_direction",
                    matches.file,
                    f"Unsupported direction: {direction}",
                    row=row_number,
                    field="direction",
                )
            )
        if significance not in SIGNIFICANCE_STATUSES:
            errors.append(
                _issue(
                    "invalid_significance",
                    matches.file,
                    f"Unsupported significance_status: {significance}",
                    row=row_number,
                    field="significance_status",
                )
            )
        if status == "matched":
            if not row.get("external_evidence_id"):
                errors.append(
                    _issue(
                        "missing_external_match",
                        matches.file,
                        "Matched record requires external_evidence_id",
                        row=row_number,
                        field="external_evidence_id",
                    )
                )
            if direction == "not_applicable" or significance == "not_applicable":
                errors.append(
                    _issue(
                        "incomplete_match",
                        matches.file,
                        "Matched record requires direction and significance_status",
                        row=row_number,
                    )
                )
        if status == "no_external_match" and (
            direction != "not_applicable" or significance != "not_applicable"
        ):
            errors.append(
                _issue(
                    "invalid_no_match",
                    matches.file,
                    "no_external_match requires direction=not_applicable and "
                    "significance_status=not_applicable",
                    row=row_number,
                )
            )
        if review_status and review_status not in REVIEW_STATUSES:
            errors.append(
                _issue(
                    "invalid_review_status",
                    matches.file,
                    f"Unsupported review_status: {review_status}",
                    row=row_number,
                    field="review_status",
                )
            )
        elif review_status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    matches.file,
                    f"Evidence match is not approved: {row.get('match_id', '')}",
                    row=row_number,
                    field="review_status",
                )
            )

    estimate_ids = {
        row.get("estimate_id", "") for _, row in effects.rows if row.get("estimate_id")
    }
    for row_number, row in effects.rows:
        effect_size = _parse_number(row.get("effect_size", ""))
        ci_low = _parse_number(row.get("ci_low", ""))
        ci_high = _parse_number(row.get("ci_high", ""))
        if effect_size is None:
            errors.append(
                _issue(
                    "invalid_effect_size",
                    effects.file,
                    "effect_size must be a finite number",
                    row=row_number,
                    field="effect_size",
                )
            )
        if ci_low is None:
            errors.append(
                _issue(
                    "invalid_ci_low",
                    effects.file,
                    "ci_low must be a finite number",
                    row=row_number,
                    field="ci_low",
                )
            )
        if ci_high is None:
            errors.append(
                _issue(
                    "invalid_ci_high",
                    effects.file,
                    "ci_high must be a finite number",
                    row=row_number,
                    field="ci_high",
                )
            )
        if ci_low is not None and ci_high is not None:
            if ci_low > ci_high:
                errors.append(
                    _issue(
                        "ci_bounds",
                        effects.file,
                        "ci_low must be less than or equal to ci_high",
                        row=row_number,
                    )
                )
            elif effect_size is not None and not (ci_low <= effect_size <= ci_high):
                errors.append(
                    _issue(
                        "effect_outside_ci",
                        effects.file,
                        "effect_size must fall within the confidence interval",
                        row=row_number,
                    )
                )
        if not row.get("unit"):
            errors.append(
                _issue(
                    "missing_unit",
                    effects.file,
                    "unit is required; use an explicit unit such as ratio, mg/L, or mmol/L",
                    row=row_number,
                    field="unit",
                )
            )
        status = row.get("status", "")
        if status and status not in MAPPING_STATUSES:
            errors.append(
                _issue(
                    "invalid_status",
                    effects.file,
                    f"Unsupported estimate status: {status}",
                    row=row_number,
                    field="status",
                )
            )
        elif status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    effects.file,
                    f"Effect estimate is not approved: {row.get('estimate_id', '')}",
                    row=row_number,
                    field="status",
                )
            )

    sensitivity_ids = {
        row.get("sensitivity_id", "")
        for _, row in sensitivities.rows
        if row.get("sensitivity_id")
    }
    for row_number, row in sensitivities.rows:
        base_estimate = row.get("base_estimate_id", "")
        supports_primary = row.get("supports_primary", "").lower()
        status = row.get("status", "")
        if base_estimate and base_estimate not in estimate_ids:
            errors.append(
                _issue(
                    "unknown_base_estimate",
                    sensitivities.file,
                    f"base_estimate_id does not exist: {base_estimate}",
                    row=row_number,
                    field="base_estimate_id",
                )
            )
        if supports_primary and supports_primary not in SENSITIVITY_SUPPORT:
            errors.append(
                _issue(
                    "invalid_boolean",
                    sensitivities.file,
                    "supports_primary must be true or false",
                    row=row_number,
                    field="supports_primary",
                )
            )
        if status and status not in MAPPING_STATUSES:
            errors.append(
                _issue(
                    "invalid_status",
                    sensitivities.file,
                    f"Unsupported sensitivity status: {status}",
                    row=row_number,
                    field="status",
                )
            )
        elif status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    sensitivities.file,
                    f"Sensitivity analysis is not approved: {row.get('sensitivity_id', '')}",
                    row=row_number,
                    field="status",
                )
            )

    for row_number, row in effects.rows:
        sensitivity_required = row.get("sensitivity_required", "").lower()
        sensitivity_id = row.get("sensitivity_analysis_id", "")
        if sensitivity_required not in {"", "true", "false"}:
            errors.append(
                _issue(
                    "invalid_boolean",
                    effects.file,
                    "sensitivity_required must be true or false when provided",
                    row=row_number,
                    field="sensitivity_required",
                )
            )
        if sensitivity_required == "true" and not sensitivity_id:
            errors.append(
                _issue(
                    "missing_sensitivity",
                    effects.file,
                    "sensitivity_analysis_id is required when sensitivity_required=true",
                    row=row_number,
                    field="sensitivity_analysis_id",
                )
            )
        if sensitivity_id and sensitivity_id not in sensitivity_ids:
            errors.append(
                _issue(
                    "unknown_sensitivity",
                    effects.file,
                    f"sensitivity_analysis_id does not exist: {sensitivity_id}",
                    row=row_number,
                    field="sensitivity_analysis_id",
                )
            )

    if not (min_gold_questions <= len(gold.rows) <= max_gold_questions):
        errors.append(
            _issue(
                "gold_question_count",
                gold.file,
                f"Expected {min_gold_questions}-{max_gold_questions} gold questions, "
                f"found {len(gold.rows)}",
            )
        )
    for row_number, row in gold.rows:
        expect_abstain = row.get("expect_abstain", "").lower()
        safety_case = row.get("safety_case", "").lower()
        review_status = row.get("review_status", "")
        if expect_abstain not in {"true", "false"}:
            errors.append(
                _issue(
                    "invalid_boolean",
                    gold.file,
                    "expect_abstain must be true or false",
                    row=row_number,
                    field="expect_abstain",
                )
            )
        if safety_case not in {"true", "false"}:
            errors.append(
                _issue(
                    "invalid_boolean",
                    gold.file,
                    "safety_case must be true or false",
                    row=row_number,
                    field="safety_case",
                )
            )
        if expect_abstain == "false" and not row.get("expected_evidence_ids"):
            errors.append(
                _issue(
                    "missing_gold_evidence",
                    gold.file,
                    "Non-abstaining gold questions require expected_evidence_ids",
                    row=row_number,
                    field="expected_evidence_ids",
                )
            )
        if review_status and review_status not in REVIEW_STATUSES:
            errors.append(
                _issue(
                    "invalid_review_status",
                    gold.file,
                    f"Unsupported review_status: {review_status}",
                    row=row_number,
                    field="review_status",
                )
            )
        elif review_status != "approved":
            errors.append(
                _issue(
                    "unapproved_record",
                    gold.file,
                    f"Gold question is not approved: {row.get('question_id', '')}",
                    row=row_number,
                    field="review_status",
                )
            )

    approved_signoff_types: set[str] = set()
    for row_number, row in signoffs.rows:
        artifact_type = row.get("artifact_type", "")
        decision = row.get("decision", "")
        signed_at = row.get("signed_at", "")
        artifact_hash = row.get("artifact_sha256", "")
        if artifact_type not in REQUIRED_SIGNOFF_TYPES:
            errors.append(
                _issue(
                    "unknown_artifact_type",
                    signoffs.file,
                    f"Unsupported artifact_type: {artifact_type}",
                    row=row_number,
                    field="artifact_type",
                )
            )
        if decision != "approved":
            errors.append(
                _issue(
                    "unsigned_record",
                    signoffs.file,
                    f"Signoff decision is not approved: {decision or 'empty'}",
                    row=row_number,
                    field="decision",
                )
            )
        if not _parse_date(signed_at):
            errors.append(
                _issue(
                    "invalid_signed_at",
                    signoffs.file,
                    "signed_at must be an ISO-8601 date or datetime",
                    row=row_number,
                    field="signed_at",
                )
            )
        if not SHA256_PATTERN.match(artifact_hash):
            errors.append(
                _issue(
                    "invalid_artifact_hash",
                    signoffs.file,
                    "artifact_sha256 must contain 64 hexadecimal characters",
                    row=row_number,
                    field="artifact_sha256",
                )
            )
        if decision == "approved" and artifact_type in REQUIRED_SIGNOFF_TYPES:
            approved_signoff_types.add(artifact_type)
    missing_signoff_types = sorted(REQUIRED_SIGNOFF_TYPES - approved_signoff_types)
    if missing_signoff_types:
        errors.append(
            _issue(
                "missing_signoff_types",
                signoffs.file,
                "Missing approved scientific signoffs for: " + ", ".join(missing_signoff_types),
            )
        )

    if not (
        min_feedback_rows <= len(feedback.rows) <= max_feedback_rows
    ):
        errors.append(
            _issue(
                "feedback_count",
                feedback.file,
                f"Expected {min_feedback_rows}-{max_feedback_rows} anonymized feedback rows, "
                f"found {len(feedback.rows)}",
            )
        )
    normalized_sensitive_headers = {
        re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", header.lower())
        for header in feedback.headers
    }
    for header in sorted(normalized_sensitive_headers):
        if any(token in header for token in SENSITIVE_HEADER_TOKENS):
            errors.append(
                _issue(
                    "sensitive_feedback_field",
                    feedback.file,
                    f"Sensitive identity field is forbidden in anonymous feedback: {header}",
                    field=header,
                )
            )
    for row_number, row in feedback.rows:
        for field, value in row.items():
            if not value:
                continue
            if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
                errors.append(
                    _issue(
                        "sensitive_feedback_value",
                        feedback.file,
                        "Feedback contains a value resembling an email, phone number, or ID number",
                        row=row_number,
                        field=field,
                    )
                )
        consent_status = row.get("consent_status", "").lower()
        anonymous = row.get("anonymous", "").lower()
        moderation_status = row.get("moderation_status", "").lower()
        if consent_status != "granted":
            errors.append(
                _issue(
                    "feedback_consent",
                    feedback.file,
                    "consent_status must be granted",
                    row=row_number,
                    field="consent_status",
                )
            )
        if not _is_true(anonymous):
            errors.append(
                _issue(
                    "feedback_not_anonymous",
                    feedback.file,
                    "anonymous must be true",
                    row=row_number,
                    field="anonymous",
                )
            )
        if moderation_status != "approved":
            errors.append(
                _issue(
                    "unapproved_feedback",
                    feedback.file,
                    "moderation_status must be approved",
                    row=row_number,
                    field="moderation_status",
                )
            )
        for rating_field in ("rating_usefulness", "rating_clarity", "rating_trust"):
            value = row.get(rating_field, "")
            if not value.isdigit() or not 1 <= int(value) <= 5:
                errors.append(
                    _issue(
                        "invalid_rating",
                        feedback.file,
                        f"{rating_field} must be an integer from 1 to 5",
                        row=row_number,
                        field=rating_field,
                    )
                )

    artifact_counts = {name: len(table.rows) for name, table in tables.items()}
    return ValidationReport(
        input_dir=str(input_dir),
        generated_at=datetime.now(timezone.utc).isoformat(),
        allow_examples=allow_examples,
        errors=errors,
        warnings=warnings,
        artifact_counts=artifact_counts,
    )


def _print_text_report(report: ValidationReport) -> None:
    print(f"{'PASS' if report.ok else 'FAIL'}: {report.input_dir}")
    for file_name, count in report.artifact_counts.items():
        print(f"  {file_name}: {count} row(s)")
    if report.errors:
        print(f"Errors ({len(report.errors)}):")
        for issue in report.errors:
            location = issue.file
            if issue.row is not None:
                location += f":row{issue.row}"
            if issue.field:
                location += f":{issue.field}"
            print(f"  [{issue.code}] {location} - {issue.message}")
    if report.warnings:
        print(f"Warnings ({len(report.warnings)}):")
        for issue in report.warnings:
            print(f"  [{issue.code}] {issue.file} - {issue.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a scientific data intake bundle before formal use."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEMPLATE_DIR,
        help=f"Directory containing the nine CSVs (default: {TEMPLATE_DIR})",
    )
    parser.add_argument(
        "--allow-examples",
        action="store_true",
        help="Allow EXAMPLE/示例 records. Use only for tests or demonstrations.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Optional path for a machine-readable JSON validation report.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Console report format.",
    )
    parser.add_argument("--expected-internal-count", type=int, default=248)
    parser.add_argument("--min-gold-questions", type=int, default=30)
    parser.add_argument("--max-gold-questions", type=int, default=50)
    parser.add_argument("--min-feedback-rows", type=int, default=5)
    parser.add_argument("--max-feedback-rows", type=int, default=10)
    args = parser.parse_args(argv)

    report = validate_bundle(
        args.input_dir,
        allow_examples=args.allow_examples,
        expected_internal_count=args.expected_internal_count,
        min_gold_questions=args.min_gold_questions,
        max_gold_questions=args.max_gold_questions,
        min_feedback_rows=args.min_feedback_rows,
        max_feedback_rows=args.max_feedback_rows,
    )
    payload = report.to_dict()
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
