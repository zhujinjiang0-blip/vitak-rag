from app.services.ingest import chunk_sections


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

