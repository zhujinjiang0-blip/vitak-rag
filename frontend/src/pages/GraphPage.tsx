import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge as FlowEdge,
  type Node as FlowNode
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Box,
  Download,
  Filter,
  GitFork,
  Info,
  Network,
  RotateCcw,
  Search,
  X
} from "lucide-react";
import Graph3DView from "../components/Graph3DView";
import { getFullGraph, getGraphMeta, getSubgraph, searchGraph } from "../lib/api";
import {
  downloadPng,
  exportFlowGraphPng,
  exportThreeGraphPng
} from "../lib/graphExport";
import {
  buildGraphPathSubgraph,
  clearGraphPathHandoff,
  readGraphPathHandoff,
  type GraphPathHandoff
} from "../lib/graphPathHandoff";
import {
  DOMAIN_COLORS,
  RELATION_THEMES,
  graphDomainColor,
  graphRelationColor,
  graphRelationTheme
} from "../lib/graphTheme";
import type { GraphNode } from "../lib/types";

function GraphPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sourceIsAnswer = searchParams.get("source") === "answer";
  const [answerHandoff, setAnswerHandoff] = useState<GraphPathHandoff | null>(
    () => {
      if (!sourceIsAnswer) {
        clearGraphPathHandoff();
        return null;
      }
      return readGraphPathHandoff();
    }
  );
  const [answerPathUnavailable] = useState(
    sourceIsAnswer && !answerHandoff
  );
  const [query, setQuery] = useState("维生素K");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [enabledDomains, setEnabledDomains] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<"2d" | "3d">("3d");
  const [exportStatus, setExportStatus] = useState<
    "idle" | "working" | "done" | "error"
  >("idle");

  const meta = useQuery({ queryKey: ["graph-meta"], queryFn: getGraphMeta });
  const search = useQuery({
    queryKey: ["graph-search", submittedQuery],
    queryFn: () => searchGraph(submittedQuery),
    enabled: Boolean(submittedQuery)
  });
  const subgraph = useQuery({
    queryKey: ["subgraph", selectedIds, enabledDomains],
    queryFn: () => getSubgraph(selectedIds, 1, enabledDomains),
    enabled: selectedIds.length > 0 && !answerHandoff
  });
  const fullGraph = useQuery({
    queryKey: ["full-graph", enabledDomains],
    queryFn: () => getFullGraph(enabledDomains),
    enabled: !answerHandoff
  });
  const answerSubgraph = useMemo(
    () => (answerHandoff ? buildGraphPathSubgraph(answerHandoff) : null),
    [answerHandoff]
  );
  const visibleGraph =
    answerSubgraph ??
    (selectedIds.length > 0 ? subgraph.data : fullGraph.data);
  const graphLoading =
    !answerHandoff &&
    (selectedIds.length > 0 ? subgraph.isFetching : fullGraph.isFetching);
  const isAnswerMode = Boolean(answerHandoff);
  const isOverview = !isAnswerMode && selectedIds.length === 0;
  const graphScope = isAnswerMode ? "answer" : isOverview ? "all" : "focus";
  const versionMismatch =
    isAnswerMode &&
    Boolean(meta.data?.data_version.version) &&
    answerHandoff?.dataVersion !== meta.data?.data_version.version;
  const answerEvidenceCount = answerHandoff
    ? new Set(answerHandoff.paths.flatMap((path) => path.evidence_ids)).size
    : 0;

  const baseFlow = useMemo(() => {
    const items = visibleGraph;
    if (!items) return { nodes: [], edges: [] };

    const overview =
      !isAnswerMode && selectedIds.length === 0 && items.nodes.length > 200;
    const centerId = selectedIds[0] ?? items.nodes[0]?.id;
    const others = items.nodes.filter((node) => node.id !== centerId);
    const radius = Math.max(210, Math.min(320, others.length * 18));
    const orderedNodes = overview
      ? [...items.nodes].sort(
          (left, right) =>
            left.domain.localeCompare(right.domain, "zh-CN") ||
            left.name.localeCompare(right.name, "zh-CN")
        )
      : items.nodes;
    const columns = Math.max(1, Math.ceil(Math.sqrt(orderedNodes.length * 1.4)));
    const rows = Math.ceil(orderedNodes.length / columns);
    const nodes: FlowNode[] = orderedNodes.map((node, index) => {
      const isCenter = node.id === centerId;
      const angle = (Math.PI * 2 * index) / Math.max(others.length, 1);
      const domainColor = graphDomainColor(node.domain);
      const row = Math.floor(index / columns);
      const column = index % columns;
      return {
        id: node.id,
        position: overview
          ? {
              x: (column - (columns - 1) / 2) * 110,
              y: (row - (rows - 1) / 2) * 76
            }
          : isCenter
            ? { x: 0, y: 0 }
            : { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
        data: { label: overview ? "" : node.name },
        style: overview
          ? {
              width: 14,
              height: 14,
              minHeight: 14,
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.92)",
              background: `${domainColor}cc`,
              padding: 0,
              boxShadow: `0 0 0 2px ${domainColor}18`
            }
          : {
              width: isCenter ? 150 : 124,
              minHeight: 42,
              borderRadius: 8,
              border: `1px solid ${domainColor}99`,
              background: isCenter
                ? "rgba(15, 23, 42, 0.82)"
                : "rgba(255, 255, 255, 0.62)",
              color: isCenter ? "#ffffff" : "#172033",
              fontWeight: isCenter ? 700 : 600,
              padding: "10px 12px",
              backdropFilter: "blur(12px)",
              boxShadow: isCenter
                ? `0 16px 36px ${domainColor}45`
                : isAnswerMode
                  ? `0 10px 26px ${domainColor}38, 0 0 0 2px ${domainColor}35`
                  : "0 12px 30px rgba(15, 23, 42, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.72)"
            }
      };
    });
    const edges: FlowEdge[] = items.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      data: { predicate: edge.predicate },
      label: overview ? undefined : edge.predicate,
      animated: !overview && edge.is_demo,
      style: {
        stroke: graphRelationColor(edge.predicate),
        strokeWidth: overview ? 0.65 : isAnswerMode ? 2.15 : 1.35,
        opacity: overview ? 0.12 : isAnswerMode ? 0.92 : edge.is_demo ? 0.4 : 0.7
      },
      ...(overview
        ? {}
        : {
            labelStyle: {
              fontSize: 9,
              fill: graphRelationColor(edge.predicate)
            },
            labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.9 }
          })
    }));
    return { nodes, edges };
  }, [isAnswerMode, selectedIds, visibleGraph]);
  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const relationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    visibleGraph?.edges.forEach((edge) => {
      const theme = graphRelationTheme(edge.predicate);
      counts.set(theme.id, (counts.get(theme.id) ?? 0) + 1);
    });
    return counts;
  }, [visibleGraph?.edges]);

  useEffect(() => {
    setFlowNodes(baseFlow.nodes);
    setFlowEdges(baseFlow.edges);
  }, [baseFlow, setFlowEdges, setFlowNodes]);

  useEffect(() => {
    if (!answerPathUnavailable) return;
    setSearchParams({}, { replace: true });
  }, [answerPathUnavailable, setSearchParams]);

  useEffect(() => {
    if (sourceIsAnswer || !answerHandoff) return;
    clearGraphPathHandoff();
    setAnswerHandoff(null);
  }, [answerHandoff, sourceIsAnswer]);

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  function selectEntity(node: GraphNode) {
    if (answerHandoff) {
      clearGraphPathHandoff();
      setAnswerHandoff(null);
      setSearchParams({}, { replace: true });
    }
    setSelected(node);
    setSelectedIds([node.id]);
  }

  function toggleDomain(domain: string) {
    if (answerHandoff) {
      clearGraphPathHandoff();
      setAnswerHandoff(null);
      setSearchParams({}, { replace: true });
    }
    setEnabledDomains((current) =>
      current.includes(domain)
        ? current.filter((item) => item !== domain)
        : [...current, domain]
    );
  }

  function showAllGraph() {
    if (answerHandoff) {
      clearGraphPathHandoff();
      setAnswerHandoff(null);
      setSearchParams({}, { replace: true });
    }
    setSelected(null);
    setSelectedIds([]);
  }

  function resetLayout() {
    setFlowNodes(baseFlow.nodes);
  }

  async function downloadGraph() {
    if (!visibleGraph || exportStatus === "working") return;
    setExportStatus("working");
    try {
      const meta = {
        mode: viewMode,
        scope: isAnswerMode
          ? ("answer" as const)
          : isOverview
            ? ("all" as const)
            : ("focus" as const),
        entityCount: visibleGraph.nodes.length,
        relationCount: visibleGraph.edges.length,
        dataVersion: visibleGraph.data_version.version,
        focusName: selected?.name
      };
      let blob: Blob;
      if (viewMode === "3d") {
        const canvas = document.querySelector<HTMLCanvasElement>(
          ".graph-3d-canvas canvas"
        );
        if (!canvas) throw new Error("三维画布尚未加载");
        blob = await exportThreeGraphPng(canvas, meta);
      } else {
        blob = await exportFlowGraphPng(
          flowNodes,
          flowEdges,
          visibleGraph.nodes,
          meta
        );
      }
      const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
      downloadPng(
        blob,
        `vitak-graph-${viewMode}-${graphScope}-${date}.png`
      );
      setExportStatus("done");
    } catch {
      setExportStatus("error");
    } finally {
      window.setTimeout(() => setExportStatus("idle"), 1800);
    }
  }

  return (
    <div className="graph-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">属性图浏览</span>
          <h1>知识图谱</h1>
          <p>搜索实体、查看领域关系和证据覆盖情况。节点和边均来自当前数据版本。</p>
        </div>
        <div className="graph-heading-side">
          <div className="graph-view-switch" role="group" aria-label="图谱展示模式">
            <button
              type="button"
              className={viewMode === "2d" ? "active" : ""}
              onClick={() => setViewMode("2d")}
              aria-label="二维图谱"
            >
              <Network size={15} />
              <span>2D</span>
            </button>
            <button
              type="button"
              className={viewMode === "3d" ? "active" : ""}
              onClick={() => setViewMode("3d")}
              aria-label="三维图谱"
            >
              <Box size={15} />
              <span>3D</span>
            </button>
          </div>
          <div className="graph-stats">
            <span><strong>{visibleGraph?.nodes.length ?? "—"}</strong> 当前实体</span>
            <span><strong>{visibleGraph?.edges.length ?? "—"}</strong> 当前关系</span>
            <span><strong>{meta.data?.domains.length ?? 6}</strong> 领域</span>
          </div>
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
            <button
              type="button"
              className="graph-show-all"
              onClick={showAllGraph}
              disabled={isOverview}
            >
              <Network size={13} />
              全部
            </button>
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
                style={{ background: graphDomainColor(node.domain) }}
              />
              <span>
                <strong>{node.name}</strong>
                <small>{node.domain} · {node.type}</small>
              </span>
            </button>
          ))}
          {search.data?.items.length === 0 && <p className="muted">没有找到匹配实体。</p>}
        </aside>

        <section
          className={`graph-canvas ${viewMode === "3d" ? "is-3d" : ""}`}
          data-graph-scope={graphScope}
        >
          {graphLoading && (
            <div className="canvas-status">
              {isOverview ? "正在加载全部图谱..." : "正在查询邻居关系..."}
            </div>
          )}
          {isAnswerMode && answerHandoff && (
            <div className="graph-answer-context">
              <div className="graph-answer-context-icon">
                <Info size={16} />
              </div>
              <div className="graph-answer-context-copy">
                <span>来自智能问答 · {graphIntentLabel(answerHandoff.intent)}</span>
                <strong>{answerHandoff.query}</strong>
                <small>
                  {answerSubgraph?.nodes.length ?? 0} 个实体 ·{" "}
                  {answerSubgraph?.edges.length ?? 0} 条关系 ·{" "}
                  {answerEvidenceCount} 条证据 · {answerHandoff.dataVersion}
                </small>
                {versionMismatch && (
                  <em>
                    回答数据版本与当前图谱版本不同，当前展示回答生成时的路径快照。
                  </em>
                )}
              </div>
              <button
                type="button"
                onClick={showAllGraph}
                aria-label="退出回答路径并显示全部图谱"
              >
                <X size={14} />
                全部图谱
              </button>
            </div>
          )}
          {answerPathUnavailable && (
            <div className="graph-answer-context unavailable">
              <div className="graph-answer-context-icon">
                <Info size={16} />
              </div>
              <div className="graph-answer-context-copy">
                <strong>回答图谱路径已过期</strong>
                <small>已恢复当前完整知识图谱。</small>
              </div>
            </div>
          )}
          <div className="graph-legend-panel" aria-label="知识领域图例">
            <div className="graph-legend-heading">
              <strong>图例</strong>
              <div className="graph-legend-actions">
                <span className="graph-export-status" aria-live="polite">
                  {exportStatus === "working"
                    ? "导出中"
                    : exportStatus === "done"
                      ? "已下载"
                      : exportStatus === "error"
                        ? "导出失败"
                        : ""}
                </span>
                {viewMode === "2d" && (
                  <button
                    type="button"
                    onClick={resetLayout}
                    title="恢复默认布局"
                    aria-label="恢复默认布局"
                  >
                    <RotateCcw size={14} />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void downloadGraph()}
                  title="下载当前图谱 PNG"
                  aria-label="下载当前图谱 PNG"
                  disabled={graphLoading || !visibleGraph || exportStatus === "working"}
                >
                  <Download size={14} />
                </button>
              </div>
            </div>
            <span className="graph-legend-section-label">实体 · 节点颜色</span>
            <div className="graph-legend-grid">
              {meta.data?.domains.map((domain) => {
                const dimmed =
                  enabledDomains.length > 0 &&
                  !enabledDomains.includes(domain);
                return (
                  <span key={domain} className={dimmed ? "dimmed" : ""}>
                    <i
                      style={{
                        background: DOMAIN_COLORS[domain] ?? "#64748b"
                      }}
                    />
                    {domain}
                  </span>
                );
              })}
            </div>
            <span className="graph-legend-section-label relation-label">关系 · 边颜色</span>
            <div className="graph-relation-legend">
              {RELATION_THEMES.map((theme) => {
                const count = relationCounts.get(theme.id) ?? 0;
                return (
                  <span
                    key={theme.id}
                    className={count === 0 ? "dimmed" : ""}
                    title={
                      theme.predicates.length > 0
                        ? theme.predicates.join("、")
                        : undefined
                    }
                  >
                    <i
                      className="relation-swatch"
                      style={{ background: theme.color }}
                    />
                    <span>{theme.label}</span>
                    <small>{count}</small>
                  </span>
                );
              })}
            </div>
          </div>
          {viewMode === "3d" ? (
            <Graph3DView
              nodes={visibleGraph?.nodes ?? []}
              edges={visibleGraph?.edges ?? []}
              selectedId={selected?.id ?? selectedIds[0] ?? null}
              pathMode={isAnswerMode}
              onSelect={selectEntity}
            />
          ) : (
            <>
              <ReactFlow
                key={`${graphScope}-${selectedIds.join("-")}-${enabledDomains.join("-")}`}
                nodes={flowNodes}
                edges={flowEdges}
                fitView
                minZoom={isOverview ? 0.04 : 0.35}
                maxZoom={1.7}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => {
                  const entity = visibleGraph?.nodes.find((item) => item.id === node.id);
                  if (entity) selectEntity(entity);
                }}
                onNodeDragStart={(_, node) => {
                  const entity = visibleGraph?.nodes.find((item) => item.id === node.id);
                  if (entity) setSelected(entity);
                }}
                nodesDraggable={!isOverview}
                nodesConnectable={false}
                elementsSelectable
                panOnDrag
                zoomOnScroll
                elevateNodesOnSelect
              >
                <Background color="#d7dee8" gap={22} size={1} />
                <MiniMap
                  nodeColor={(node) => {
                    const entity = visibleGraph?.nodes.find((item) => item.id === node.id);
                    return graphDomainColor(entity?.domain ?? "");
                  }}
                />
                <Controls />
              </ReactFlow>
            </>
          )}
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
                style={{ color: graphDomainColor(selected.domain) }}
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

function graphIntentLabel(intent: string) {
  const labels: Record<string, string> = {
    food_sources: "食物来源",
    drug_interactions: "药物关系",
    deficiency: "缺乏风险",
    functions: "功能机制",
    lab_tests: "检测指标",
    recommendations: "建议信息",
    research: "研究证据",
    comparison: "关系比较",
    definition: "知识介绍",
    emergency: "紧急安全",
    medication: "用药安全",
    diagnosis: "诊断边界",
    general: "图谱检索",
    capabilities: "能力说明"
  };
  return labels[intent] ?? intent;
}

export default GraphPage;
