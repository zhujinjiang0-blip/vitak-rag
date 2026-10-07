import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge as FlowEdge,
  type Node as FlowNode
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { FormEvent, useMemo, useState } from "react";
import { Filter, GitFork, Search, X } from "lucide-react";
import { getGraphMeta, getSubgraph, searchGraph } from "../lib/api";
import type { GraphNode } from "../lib/types";

const DOMAIN_COLORS: Record<string, string> = {
  生理代谢: "#0f766e",
  食物营养: "#ca8a04",
  药物相互作用: "#be123c",
  临床疾病: "#b45309",
  检测评估: "#0369a1",
  指南与RCT: "#6d28d9"
};

function GraphPage() {
  const [query, setQuery] = useState("维生素K");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>(["vitamin-k"]);
  const [enabledDomains, setEnabledDomains] = useState<string[]>([]);

  const meta = useQuery({ queryKey: ["graph-meta"], queryFn: getGraphMeta });
  const search = useQuery({
    queryKey: ["graph-search", submittedQuery],
    queryFn: () => searchGraph(submittedQuery),
    enabled: Boolean(submittedQuery)
  });
  const subgraph = useQuery({
    queryKey: ["subgraph", selectedIds, enabledDomains],
    queryFn: () => getSubgraph(selectedIds, 1, enabledDomains),
    enabled: selectedIds.length > 0
  });

  const flow = useMemo(() => {
    const items = subgraph.data;
    if (!items) return { nodes: [], edges: [] };

    const centerId = selectedIds[0] ?? items.nodes[0]?.id;
    const others = items.nodes.filter((node) => node.id !== centerId);
    const radius = Math.max(210, Math.min(320, others.length * 18));
    const nodes: FlowNode[] = items.nodes.map((node, index) => {
      const isCenter = node.id === centerId;
      const angle = (Math.PI * 2 * index) / Math.max(others.length, 1);
      return {
        id: node.id,
        position: isCenter
          ? { x: 0, y: 0 }
          : { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
        data: { label: node.name },
        style: {
          width: isCenter ? 150 : 124,
          minHeight: 42,
          borderRadius: 8,
          border: `1px solid ${DOMAIN_COLORS[node.domain] ?? "#334155"}`,
          background: isCenter ? "#0f172a" : "#ffffff",
          color: isCenter ? "#ffffff" : "#172033",
          fontWeight: isCenter ? 700 : 600,
          padding: "10px 12px",
          boxShadow: "0 8px 20px rgba(15, 23, 42, 0.08)"
        }
      };
    });
    const edges: FlowEdge[] = items.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.predicate,
      animated: edge.is_demo,
      style: { stroke: edge.is_demo ? "#94a3b8" : "#0f766e", strokeWidth: 1.4 },
      labelStyle: { fontSize: 9, fill: "#64748b" },
      labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.9 }
    }));
    return { nodes, edges };
  }, [selectedIds, subgraph.data]);

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  function selectEntity(node: GraphNode) {
    setSelected(node);
    setSelectedIds([node.id]);
  }

  function toggleDomain(domain: string) {
    setEnabledDomains((current) =>
      current.includes(domain)
        ? current.filter((item) => item !== domain)
        : [...current, domain]
    );
  }

  return (
    <div className="graph-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">属性图浏览</span>
          <h1>知识图谱</h1>
          <p>搜索实体、查看领域关系和证据覆盖情况。节点和边均来自当前数据版本。</p>
        </div>
        <div className="graph-stats">
          <span><strong>{meta.data?.stats.nodes ?? "—"}</strong> 实体</span>
          <span><strong>{meta.data?.stats.edges ?? "—"}</strong> 关系</span>
          <span><strong>{meta.data?.domains.length ?? 6}</strong> 领域</span>
        </div>
      </section>

      <div className="graph-toolbar">
        <form onSubmit={handleSearch}>
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索实体，例如：华法林、纳豆、INR"
          />
          <button type="submit">搜索</button>
        </form>
        <div className="domain-filter">
          <Filter size={17} />
          <span>领域</span>
          <div className="filter-chips">
            {meta.data?.domains.map((domain) => (
              <button
                key={domain}
                className={enabledDomains.includes(domain) ? "active" : ""}
                onClick={() => toggleDomain(domain)}
              >
                {domain}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="graph-workspace">
        <aside className="entity-results">
          <div className="panel-title">
            <GitFork size={17} />
            <h2>实体结果</h2>
          </div>
          {search.isFetching && <p className="muted">正在搜索...</p>}
          {search.data?.items.map((node) => (
            <button
              key={node.id}
              className={`entity-result ${selected?.id === node.id ? "active" : ""}`}
              onClick={() => selectEntity(node)}
            >
              <span
                className="entity-domain-dot"
                style={{ background: DOMAIN_COLORS[node.domain] }}
              />
              <span>
                <strong>{node.name}</strong>
                <small>{node.domain} · {node.type}</small>
              </span>
            </button>
          ))}
          {search.data?.items.length === 0 && <p className="muted">没有找到匹配实体。</p>}
        </aside>

        <section className="graph-canvas">
          {subgraph.isFetching && <div className="canvas-status">正在查询邻居关系...</div>}
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            fitView
            minZoom={0.35}
            maxZoom={1.7}
            onNodeClick={(_, node) => {
              const entity = subgraph.data?.nodes.find((item) => item.id === node.id);
              if (entity) setSelected(entity);
            }}
            nodesDraggable
            nodesConnectable={false}
            elementsSelectable
          >
            <Background color="#d7dee8" gap={22} size={1} />
            <MiniMap
              nodeColor={(node) => {
                const entity = subgraph.data?.nodes.find((item) => item.id === node.id);
                return DOMAIN_COLORS[entity?.domain ?? ""] ?? "#64748b";
              }}
            />
            <Controls />
          </ReactFlow>
        </section>

        <aside className="node-inspector">
          <div className="panel-title">
            <h2>节点详情</h2>
            {selected && (
              <button
                className="icon-button"
                onClick={() => setSelected(null)}
                aria-label="关闭节点详情"
              >
                <X size={16} />
              </button>
            )}
          </div>
          {!selected ? (
            <p className="muted">选择画布或搜索结果中的实体以查看详情。</p>
          ) : (
            <>
              <span
                className="domain-label"
                style={{ color: DOMAIN_COLORS[selected.domain] }}
              >
                {selected.domain}
              </span>
              <h3>{selected.name}</h3>
              <span className="node-type">{selected.type}</span>
              <p>{selected.summary || "当前节点暂无摘要。"}</p>
              {selected.aliases.length > 0 && (
                <div className="alias-list">
                  {selected.aliases.map((alias) => (
                    <span key={alias}>{alias}</span>
                  ))}
                </div>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

export default GraphPage;

