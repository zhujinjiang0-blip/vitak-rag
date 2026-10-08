from app.services.ingest import chunk_sections
from app.storage.database import MetadataStore


def test_chunking_preserves_locator_and_content():
    sections = [("第 1 页", "维生素K与凝血有关。\n\n菠菜含有维生素K1。")]

    chunks = chunk_sections(sections, max_chars=40, overlap=5)

    assert chunks
    assert chunks[0][0].startswith("第 1 页")
    assert "维生素K" in chunks[0][1]


def test_alias_answer_linking(engine):
    answer = engine.answer("维K和凝血有什么关系？")

    assert answer.intent == "functions"
    assert answer.claims
    assert any("凝血" in claim.text for claim in answer.claims)


def test_imported_sources_default_to_internal_private(tmp_path):
    store = MetadataStore(tmp_path / "metadata.sqlite3")
    store.initialize()
    store.add_source(
        source_id="SRC-TEST",
        title="内部测试材料",
        source_type="rct",
        source_classification="internal_rct",
        data_origin="internal",
        data_owner="测试课题组",
        access_scope="private",
        publisher="本地导入",
        is_demo=False,
        metadata={"imported_path": "/tmp/test.pdf"},
    )

    with store.connect() as connection:
        row = connection.execute(
            """
            SELECT data_origin, data_owner, access_scope, source_classification
            FROM sources WHERE id = 'SRC-TEST'
            """
        ).fetchone()

    assert dict(row) == {
        "data_origin": "internal",
        "data_owner": "测试课题组",
        "access_scope": "private",
        "source_classification": "internal_rct",
    }
