from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import kuzu

from app.schemas import GraphEdge, GraphNode, GraphPath


class KuzuGraphStore:
    backend_name = "kuzu"

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.database = kuzu.Database(str(self.path))
        self.connection = kuzu.Connection(self.database)
        self._node_cache: dict[str, GraphNode] | None = None

    def initialize(self) -> None:
        self.connection.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Entity(
                id STRING,
                name STRING,
                type STRING,
                domain STRING,
                summary STRING,
                aliases STRING,
                is_demo BOOLEAN,
                PRIMARY KEY(id)
            )
            """
        )
        self.connection.execute(
            """
            CREATE REL TABLE IF NOT EXISTS RELATES(
                FROM Entity TO Entity,
                id STRING,
                predicate STRING,
                evidence_ids STRING,
                evidence_level STRING,
                confidence DOUBLE,
                is_demo BOOLEAN
            )
            """
        )

    def add_node(self, node: GraphNode) -> None:
        self.connection.execute(
            """
            CREATE (:Entity {
                id: $id,
                name: $name,
                type: $type,
                domain: $domain,
                summary: $summary,
                aliases: $aliases,
                is_demo: $is_demo
            })
            """,
            {
                "id": node.id,
                "name": node.name,
                "type": node.type,
                "domain": node.domain,
                "summary": node.summary,
                "aliases": json.dumps(node.aliases, ensure_ascii=False),
                "is_demo": node.is_demo,
            },
        )
        self._node_cache = None

    def add_edge(self, edge: GraphEdge) -> None:
        self.connection.execute(
            """
            MATCH (a:Entity), (b:Entity)
            WHERE a.id = $source AND b.id = $target
            CREATE (a)-[:RELATES {
                id: $id,
                predicate: $predicate,
                evidence_ids: $evidence_ids,
                evidence_level: $evidence_level,
                confidence: $confidence,
                is_demo: $is_demo
            }]->(b)
            """,
            {
                "source": edge.source,
                "target": edge.target,
                "id": edge.id,
                "predicate": edge.predicate,
                "evidence_ids": json.dumps(edge.evidence_ids, ensure_ascii=False),
                "evidence_level": edge.evidence_level,
                "confidence": edge.confidence,
                "is_demo": edge.is_demo,
            },
        )

    @staticmethod
    def _row_to_node(row: list[Any]) -> GraphNode:
        aliases_value = row[5] or "[]"
        try:
            aliases = json.loads(aliases_value)
        except (json.JSONDecodeError, TypeError):
            aliases = [item for item in str(aliases_value).split("|") if item]
        return GraphNode(
            id=row[0],
            name=row[1],
            type=row[2],
            domain=row[3],
            summary=row[4] or "",
            aliases=aliases,
            is_demo=bool(row[6]),
        )

    @staticmethod
    def _row_to_edge(row: list[Any]) -> GraphEdge:
        try:
            evidence_ids = json.loads(row[3] or "[]")
        except (json.JSONDecodeError, TypeError):
            evidence_ids = [item for item in str(row[3]).split("|") if item]
        return GraphEdge(
            id=row[0],
            source=row[1],
            target=row[2],
            evidence_ids=evidence_ids,
            predicate=row[4],
            evidence_level=row[5],
            confidence=float(row[6] or 0),
            is_demo=bool(row[7]),
        )

    def all_nodes(self, refresh: bool = False) -> list[GraphNode]:
        if self._node_cache is not None and not refresh:
            return list(self._node_cache.values())
        result = self.connection.execute(
            """
            MATCH (n:Entity)
            RETURN n.id, n.name, n.type, n.domain, n.summary, n.aliases, n.is_demo
            ORDER BY n.domain, n.name
            """
        )
        nodes: dict[str, GraphNode] = {}
        while result.has_next():
            node = self._row_to_node(result.get_next())
            nodes[node.id] = node
        self._node_cache = nodes
        return list(nodes.values())

    def get_node(self, entity_id: str) -> GraphNode | None:
        result = self.connection.execute(
            """
            MATCH (n:Entity)
            WHERE n.id = $id
            RETURN n.id, n.name, n.type, n.domain, n.summary, n.aliases, n.is_demo
            """,
            {"id": entity_id},
        )
        if not result.has_next():
            return None
        return self._row_to_node(result.get_next())

    def search_nodes(self, query: str, limit: int = 20) -> list[GraphNode]:
        needle = query.strip().lower()
        if not needle:
            return self.all_nodes()[:limit]

        exact: list[GraphNode] = []
        prefix: list[GraphNode] = []
        contains: list[GraphNode] = []
        for node in self.all_nodes():
            haystacks = [node.id, node.name, *node.aliases]
            lowered = [item.lower() for item in haystacks]
            if needle in lowered:
                exact.append(node)
            elif any(item.startswith(needle) for item in lowered):
                prefix.append(node)
            elif any(needle in item for item in lowered):
                contains.append(node)
        return (exact + prefix + contains)[:limit]

    def neighbors(
        self,
        entity_id: str,
        predicates: set[str] | None = None,
    ) -> list[tuple[GraphEdge, GraphNode, str]]:
        output: list[tuple[GraphEdge, GraphNode, str]] = []
        queries = [
            (
                """
                MATCH (a:Entity)-[r:RELATES]->(b:Entity)
                WHERE a.id = $id
                RETURN r.id AS rel_id, a.id AS source_id, b.id AS target_id,
                       r.evidence_ids AS evidence_ids, r.predicate AS predicate,
                       r.evidence_level AS evidence_level, r.confidence AS confidence,
                       r.is_demo AS rel_is_demo,
                       b.id AS node_id, b.name AS node_name, b.type AS node_type,
                       b.domain AS node_domain, b.summary AS node_summary,
                       b.aliases AS node_aliases, b.is_demo AS node_is_demo
                """,
                "out",
            ),
            (
                """
                MATCH (a:Entity)<-[r:RELATES]-(b:Entity)
                WHERE a.id = $id
                RETURN r.id AS rel_id, b.id AS source_id, a.id AS target_id,
                       r.evidence_ids AS evidence_ids, r.predicate AS predicate,
                       r.evidence_level AS evidence_level, r.confidence AS confidence,
                       r.is_demo AS rel_is_demo,
                       b.id AS node_id, b.name AS node_name, b.type AS node_type,
                       b.domain AS node_domain, b.summary AS node_summary,
                       b.aliases AS node_aliases, b.is_demo AS node_is_demo
                """,
                "in",
            ),
        ]
        for query, direction in queries:
            result = self.connection.execute(query, {"id": entity_id})
            while result.has_next():
                row = result.get_next()
                edge = self._row_to_edge(row[:8])
                node = self._row_to_node(row[8:15])
                if predicates and edge.predicate not in predicates:
                    continue
                output.append((edge, node, direction))
        return output

    def all_edges(self) -> list[GraphEdge]:
        result = self.connection.execute(
            """
            MATCH (a:Entity)-[r:RELATES]->(b:Entity)
            RETURN r.id, a.id, b.id, r.evidence_ids, r.predicate, r.evidence_level,
                   r.confidence, r.is_demo
            ORDER BY r.id
            """
        )
        edges = []
        while result.has_next():
            edges.append(self._row_to_edge(result.get_next()))
        return edges

    def subgraph(
        self,
        entity_ids: list[str],
        depth: int = 1,
        limit: int = 80,
        domains: set[str] | None = None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        visited = set(entity_ids)
        frontier = list(entity_ids)
        edges: dict[str, GraphEdge] = {}
        for _ in range(depth):
            next_frontier: list[str] = []
            for entity_id in frontier:
                for edge, node, _ in self.neighbors(entity_id):
                    if domains and node.domain not in domains:
                        continue
                    edges[edge.id] = edge
                    if node.id not in visited:
                        visited.add(node.id)
                        next_frontier.append(node.id)
                    if len(visited) >= limit:
                        break
                if len(visited) >= limit:
                    break
            frontier = next_frontier
            if not frontier or len(visited) >= limit:
                break
        nodes = [self.get_node(entity_id) for entity_id in visited]
        return [node for node in nodes if node], list(edges.values())

    def paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 2,
        limit: int = 3,
    ) -> list[GraphPath]:
        if source_id == target_id:
            node = self.get_node(source_id)
            return [GraphPath(nodes=[node], edges=[]) ] if node else []

        queue: deque[tuple[str, list[GraphNode], list[GraphEdge]]] = deque()
        source_node = self.get_node(source_id)
        if not source_node:
            return []
        queue.append((source_id, [source_node], []))
        output: list[GraphPath] = []

        while queue and len(output) < limit:
            current, nodes, path_edges = queue.popleft()
            if len(path_edges) >= max_hops:
                continue
            for edge, neighbor, _ in self.neighbors(current):
                if any(node.id == neighbor.id for node in nodes):
                    continue
                next_nodes = [*nodes, neighbor]
                next_edges = [*path_edges, edge]
                if neighbor.id == target_id:
                    output.append(
                        GraphPath(
                            nodes=next_nodes,
                            edges=next_edges,
                            evidence_ids=list(
                                dict.fromkeys(
                                    evidence_id
                                    for item in next_edges
                                    for evidence_id in item.evidence_ids
                                )
                            ),
                        )
                    )
                    if len(output) >= limit:
                        break
                else:
                    queue.append((neighbor.id, next_nodes, next_edges))
        return output

    def stats(self) -> dict[str, int]:
        node_result = self.connection.execute("MATCH (n:Entity) RETURN COUNT(n)")
        edge_result = self.connection.execute("MATCH ()-[r:RELATES]->() RETURN COUNT(r)")
        return {
            "nodes": int(node_result.get_next()[0]) if node_result.has_next() else 0,
            "edges": int(edge_result.get_next()[0]) if edge_result.has_next() else 0,
        }
