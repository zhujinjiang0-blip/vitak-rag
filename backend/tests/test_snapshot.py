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

