from app.config import Settings
from app.services.external_triples import ExternalTripleImporter
from app.services.snapshot import DEMO_VERSION, SnapshotManager


def test_aligned_external_triples_imports_with_traceable_metadata(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    manager = SnapshotManager(settings)
    manager.create_demo_snapshot()
    manager.activate(DEMO_VERSION)
    csv_path = tmp_path / "aligned_triples.csv"
    csv_path.write_text(
        "\n".join(
            [
                "record_id,pmid,subject,subject_normalized,subject_matched_class,subject_match_type,predicate,object,object_normalized,object_matched_class,object_match_type,source_sentence,evidence_score,evidence_grade,confidence_score,confidence_grade",
                'VK0350,26875489,菠菜,菠菜,Food,alias,increases,维生素K水平,维生素K状态,VitaminKStatus,semantic,"菠菜摄入与维生素K状态相关。",0.9,high,92,very_high',
                'VK0351,30000000,华法林,华法林,Drug,exact,decreases,维生素K循环,维生素K循环,VitaminKCycle,exact,"华法林影响维生素K循环。",0.8,moderate,81,high',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = ExternalTripleImporter(manager).import_csv(csv_path)
    imported = manager.open(result["snapshot_version"])
    try:
        with imported.metadata.connect() as connection:
            source = connection.execute(
                "SELECT * FROM sources WHERE id = 'EXT-SRC-VK0350'"
            ).fetchone()
            evidence = connection.execute(
                """
                SELECT evidence_level, confidence, metadata_json
                FROM evidence
                WHERE source_id = 'EXT-SRC-VK0350'
                """
            ).fetchone()
        assert result["rows"] == 2
        assert result["edges_added"] == 2
        assert source["data_origin"] == "external"
        assert source["source_classification"] == "external_literature_triple"
        assert source["data_owner"] == "已发表维生素 K 研究文献"
        assert source["access_scope"] == "public"
        assert evidence["evidence_level"] == "high"
        assert evidence["confidence"] == 0.92
    finally:
        imported.close()

