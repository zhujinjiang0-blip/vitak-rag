import pytest

from app.config import Settings
from app.services.snapshot import SnapshotManager


def test_bootstrap_does_not_reset_active_snapshot_on_database_lock(
    tmp_path, monkeypatch
):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    settings.active_manifest.write_text("{}", encoding="utf-8")
    manager = SnapshotManager(settings)
    reset_calls = 0

    def fail_open():
        raise RuntimeError("database is locked")

    def record_reset():
        nonlocal reset_calls
        reset_calls += 1

    monkeypatch.setattr(manager, "open_active", fail_open)
    monkeypatch.setattr(manager, "create_demo_snapshot", record_reset)

    with pytest.raises(RuntimeError, match="database is locked"):
        manager.bootstrap()

    assert reset_calls == 0


def test_demo_snapshot_meets_prototype_scale(demo_context):
    _, manager, context = demo_context
    validation = manager.validate(context.version)

    assert validation["valid"] is True
    assert validation["counts"]["nodes"] >= 120
    assert validation["counts"]["edges"] >= 300
    assert validation["counts"]["sources"] >= 40
    assert validation["counts"]["chunks"] >= 120


def test_graph_search_supports_aliases(demo_context):
    _, _, context = demo_context

    items = context.graph.search_nodes("华法林")

    assert items
    assert items[0].name == "华法林"


def test_demo_sources_are_classified_by_origin(demo_context):
    _, _, context = demo_context
    with context.metadata.connect() as connection:
        rows = connection.execute(
            """
            SELECT data_origin, COUNT(*) AS count
            FROM sources
            GROUP BY data_origin
            """
        ).fetchall()
        classifications = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM sources
            WHERE source_classification = ''
            """
        ).fetchone()["count"]

    counts = {row["data_origin"]: row["count"] for row in rows}
    assert counts == {
        "internal": 1,
        "external": 1,
        "public": 28,
        "synthetic": 10,
    }
    assert classifications == 0


def test_evidence_chunk_index_is_created(demo_context):
    _, _, context = demo_context
    with context.metadata.connect() as connection:
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert "idx_evidence_chunk" in indexes
