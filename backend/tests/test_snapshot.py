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
