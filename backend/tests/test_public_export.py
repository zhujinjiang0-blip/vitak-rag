from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "export-public-evidence.py"
SPEC = importlib.util.spec_from_file_location("export_public_evidence", SCRIPT_PATH)
assert SPEC and SPEC.loader
export_public_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = export_public_evidence
SPEC.loader.exec_module(export_public_evidence)


def structured_row() -> dict[str, str]:
    row = {
        "edge_id": "STR_test",
        "subject_id": "ENT_food",
        "subject_label": "USDA_FDC:326162",
        "subject_type": "FoodEntity",
        "predicate": "contains",
        "object_id": "ENT_vk",
        "object_label": "Vitamin K (phylloquinone)",
        "object_type": "FoodEntity",
        "source_type": "structured",
        "source_record_id": "M000374:1",
        "source_locator": "结构化数据/USDA FoodData Central(FDC)/food.csv::row 2",
        "source_version": "Structured_Mapping_Report_Reviewed.csv@test",
        "source_sha256": "",
        "evidence_score": "",
        "evidence_grade": "",
        "confidence_score": "1.0",
        "effect_size": "",
        "ci_low": "",
        "ci_high": "",
        "p_value": "",
        "q_value": "",
        "sample_n": "",
        "model_type": "deterministic_mapping",
        "population_context": "",
        "dose_context": "",
        "time_context": "",
        "qualifiers_json": "{}",
        "fusion_status": "accepted",
        "retention_status": "",
        "conflict_id": "",
        "review_status": "accepted",
        "review_reason": "",
        "input_status": "adopted",
        "modification_codes": "",
        "merged_into": "",
        "test_family": "",
        "analysis_context": "",
        "evidence_status": "",
        "core_48_flag": "",
        "graph_display_role": "",
        "source_file": "structured_triples_final.csv",
        "source_row_value": "2",
    }
    return row


def test_structured_export_keeps_source_metadata_and_node_names():
    row = structured_row()
    metadata = {
        ("usda_fdc:326162", "FoodEntity"): {
            "name": "Kale - NFY1214SU",
            "description": "",
            "aliases": {"羽衣甘蓝"},
        }
    }

    payload = export_public_evidence.build_payload(
        [row],
        research_only_count=0,
        source_paths=[Path("structured_triples_final.csv")],
        structured_metadata=metadata,
        eligible_structured_records=1,
    )

    assert payload["export_metadata"]["source_types"] == {"structured": 1}
    assert payload["export_metadata"]["eligible_structured_records"] == 1
    assert payload["evidence"][0]["source_type"] == "structured"
    assert payload["evidence"][0]["answer_eligible"] is True
    assert any(node["name"] == "Kale - NFY1214SU" for node in payload["nodes"])
