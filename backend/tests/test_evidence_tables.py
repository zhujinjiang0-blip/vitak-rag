import csv
import uuid

from app.config import Settings
from app.services.evidence_tables import EXPECTED_FIELDS, EvidenceTableImporter
from app.services.qa import GraphAnswerEngine
from app.services.snapshot import SnapshotManager


def make_row(**overrides: str) -> dict[str, str]:
    row = {field: "" for field in EXPECTED_FIELDS}
    row.update(
        {
            "edge_id": "EDGE-001",
            "subject_id": "SUBJ-1",
            "subject_label": "实体甲",
            "subject_type": "BiomarkerEntity",
            "predicate": "regulates_expression_of",
            "object_id": "OBJ-1",
            "object_label": "实体乙",
            "object_type": "MeasurableEntity",
            "source_type": "literature",
            "source_record_id": "VK0001:12345678",
            "source_locator": "PMID 12345678 | 实体甲影响实体乙。",
            "source_version": "literature@abc123",
            "source_sha256": "hash-1",
            "evidence_grade": "A",
            "confidence_score": "0.9",
            "review_status": "accepted",
            "input_status": "adopted",
            "fusion_status": "accepted",
            "evidence_status": "positive",
            "graph_display_role": "core_main_edge",
        }
    )
    row.update(overrides)
    return row


def write_table(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_unified_evidence_import_keeps_literals_and_status(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    manager = SnapshotManager(settings)
    literature = tmp_path / "literature.csv"
    structured = tmp_path / "structured.csv"
    internal = tmp_path / "internal.csv"
    write_table(
        literature,
        [
            make_row(edge_id="LIT-1"),
            make_row(
                edge_id="LIT-2",
                subject_id="PENDING-1",
                subject_label="待审实体甲",
                object_id="PENDING-2",
                object_label="待审实体乙",
                review_status="manual_pending",
                input_status="deferred",
                evidence_status="candidate",
            ),
        ],
    )
    write_table(
        structured,
        [
            make_row(
                edge_id="STRUCT-1",
                subject_id="FOOD-1",
                subject_label='菠菜 "Cocktail" 研究',
                subject_type="FoodEntity",
                predicate="VitaminKContent",
                object_id="",
                object_label="321",
                object_type="string",
                source_type="structured",
                source_record_id="M000001:1",
                source_locator="food.csv::row 2::value",
                source_version="structured@def456",
                review_status="accepted",
                input_status="adopted",
                fusion_status="accepted",
            )
        ],
    )
    write_table(
        internal,
        [
            make_row(
                edge_id="INT-1",
                subject_id="INT-A",
                subject_label="内部指标甲",
                predicate="no_significant_association_observed_with",
                object_id="INT-B",
                object_label="内部指标乙",
                source_type="internal",
                source_record_id="INT-1",
                source_locator="step4.csv row 2",
                source_version="internal@ghi789",
                review_status="accepted_internal_ledger",
                input_status="adopted",
                evidence_status="negative",
                retention_status="Internal_Kept",
            )
        ],
    )

    version = f"test-real-{uuid.uuid4().hex[:8]}"
    importer = EvidenceTableImporter(manager)
    result = importer.import_files(
        [literature, structured, internal],
        version=version,
        build_vectors=False,
    )
    snapshot = manager.open(version)
    try:
        assert result["rows"] == 4
        assert result["graph_edges"] == 4
        assert result["literal_nodes"] == 1
        assert result["origins"] == {"external": 3, "internal": 1}
        assert result["answer_eligible"] == 3
        assert snapshot.graph.stats()["edges"] == 4

        with snapshot.metadata.connect() as connection:
            pending = connection.execute(
                "SELECT answer_eligible, review_status FROM evidence WHERE edge_id = 'LIT-2'"
            ).fetchone()
        assert pending["answer_eligible"] == 0
        assert pending["review_status"] == "manual_pending"

        engine = GraphAnswerEngine(settings, snapshot)
        refused = engine.answer("待审实体甲和待审实体乙有什么关系？")
        assert refused.claims == []
        assert refused.sufficiency == "none"
    finally:
        snapshot.close()


def test_evidence_audit_counts_literal_and_ineligible_rows(tmp_path):
    path = tmp_path / "structured.csv"
    write_table(
        path,
        [
            make_row(
                edge_id="S-1",
                source_type="structured",
                object_id="",
                object_label="literal",
                object_type="string",
            ),
            make_row(
                edge_id="S-2",
                source_type="structured",
                review_status="provisional",
                input_status="deferred",
            ),
        ],
    )
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    stats = EvidenceTableImporter(SnapshotManager(settings)).audit([path])

    assert stats["rows"] == 2
    assert stats["literal_nodes"] == 1
    assert stats["graph_edges"] == 2
    assert stats["answer_eligible"] == 1
    assert stats["answer_ineligible"] == 1
