import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Download,
  FileJson2,
  FlaskConical,
  LockKeyhole,
  Search,
  ShieldCheck
} from "lucide-react";
import EvidenceJsonDialog from "../components/EvidenceJsonDialog";
import {
  getResearchFacets,
  getResearchInsights,
  getResearchOverview,
  searchResearchEvidence
} from "../lib/api";
import type {
  ResearchDistributionItem,
  ResearchEffectSeries,
  SearchResult
} from "../lib/types";

const FAMILY_LABELS: Record<string, string> = {
  postprandial: "餐后动力学",
  vk_vd_interaction: "维生素K×维生素D",
  sex_interaction: "性别交互",
  obesity_interaction: "肥胖状态交互",
  reverse_causality: "反向因果探索",
  dose_response: "剂量反应",
  mediation: "中介分析",
  cross_sectional: "基线横断面",
  longitudinal: "纵向变化"
};

function ResearchPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [collection, setCollection] = useState("all");
  const [testFamily, setTestFamily] = useState("");
  const [outcome, setOutcome] = useState("");
  const [evidenceLevel, setEvidenceLevel] = useState("");
  const [resultStatus, setResultStatus] = useState("");
  const [jsonItem, setJsonItem] = useState<SearchResult | null>(null);
  const [seriesId, setSeriesId] = useState("");

  const overview = useQuery({
    queryKey: ["research-overview"],
    queryFn: getResearchOverview
  });
  const facets = useQuery({
    queryKey: ["research-facets"],
    queryFn: getResearchFacets
  });
  const insights = useQuery({
    queryKey: ["research-insights"],
    queryFn: getResearchInsights
  });
  const results = useQuery({
    queryKey: [
      "research-evidence",
      submittedQuery,
      collection,
      testFamily,
      outcome,
      evidenceLevel,
      resultStatus
    ],
    queryFn: () =>
      searchResearchEvidence({
        q: submittedQuery,
        collection,
        test_family: testFamily,
        outcome,
        evidence_level: evidenceLevel,
        result_status: resultStatus,
        page: 1,
        page_size: 50
      })
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  const data = overview.data;
  const selectedSeries =
    insights.data?.effect_series.find((series) => series.id === seriesId) ??
    insights.data?.effect_series[0];
  return (
    <div className="research-page">
      <section className="page-heading research-heading">
        <div>
          <span className="eyebrow">授权研究环境 · internal/private</span>
          <h1>内部研究证据</h1>
          <p>
            395 例高代谢风险成人干预队列。全量、核心与情境化集合允许重叠，
            页面分别报告，不把三个数字相加。
          </p>
        </div>
        <div className="research-lock-badge">
          <LockKeyhole size={17} />
          授权会话
        </div>
      </section>

      <section className="research-metrics" aria-label="内部队列证据集合">
        <Metric
          icon={<Database size={18} />}
          label="全量内部证据"
          value={data?.total_internal_records ?? "—"}
          note="internal / private"
        />
        <Metric
          icon={<FlaskConical size={18} />}
          label="核心证据"
          value={data?.core_records ?? "—"}
          note="core_main_edge"
        />
        <Metric
          icon={<Activity size={18} />}
          label="情境化分析"
          value={data?.contextual_records ?? "—"}
          note="七个分析族"
        />
        <Metric
          icon={<BarChart3 size={18} />}
          label="集合交集"
          value={data?.core_contextual_overlap ?? "—"}
          note="核心 ∩ 情境化"
        />
      </section>

      <section className="research-overview-band">
        <div>
          <span className="eyebrow">证据等级</span>
          <div className="grade-distribution">
            {Object.entries(data?.grade_distribution ?? {}).map(([label, count]) => (
              <span key={label}>
                <strong>{label}</strong>
                {count}
              </span>
            ))}
          </div>
        </div>
        <div>
          <span className="eyebrow">分析族</span>
          <div className="family-distribution">
            {Object.entries(data?.test_family_distribution ?? {}).map(
              ([family, count]) => (
                <span key={family}>
                  {FAMILY_LABELS[family] ?? family}
                  <strong>{count}</strong>
                </span>
              )
            )}
          </div>
        </div>
        <div className="research-review-note">
          <ShieldCheck size={18} />
          <p>
            自动检查验证来源绑定、集合口径和拒答边界。科研语义与临床结论仍需
            科研负责人签认。
          </p>
        </div>
      </section>

      {insights.isError ? (
        <div className="error-banner">研究图件与匹配概览加载失败，请稍后重试。</div>
      ) : (
        <section className="research-insights">
          <div className="research-panel-heading">
            <div>
              <span className="eyebrow">真实数据概览</span>
              <h2>结果分布与证据对照</h2>
            </div>
            <span>{insights.data?.total_records ?? "—"} 条内部证据</span>
          </div>
          <div className="research-insights-grid">
            <article className="research-chart-panel">
              <h3>结果状态分布</h3>
              <DistributionBars
                items={insights.data?.status_distribution ?? []}
                total={insights.data?.total_records ?? 0}
              />
            </article>
            <article className="research-chart-panel">
              <h3>内外部匹配</h3>
              <DistributionBars
                items={insights.data?.match_categories ?? []}
                total={insights.data?.total_records ?? 0}
              />
              <p className="research-chart-note">
                {insights.data?.match_note ?? "正在载入匹配字段状态。"}
              </p>
              <div className="research-governance-breakdown">
                {(insights.data?.governance_categories ?? []).map((item) => (
                  <span key={item.key}>
                    {item.label}
                    <strong>{item.count}</strong>
                  </span>
                ))}
              </div>
            </article>
          </div>
          <article className="research-effect-panel">
            <div className="research-panel-heading">
              <div>
                <span className="eyebrow">效应量点图</span>
                <h3>{selectedSeries?.title ?? "暂无可绘制的同组效应量"}</h3>
              </div>
              {insights.data?.effect_series.length ? (
                <select
                  aria-label="选择科研图件"
                  value={selectedSeries?.id ?? ""}
                  onChange={(event) => setSeriesId(event.target.value)}
                >
                  {insights.data.effect_series.map((series) => (
                    <option key={series.id} value={series.id}>
                      {series.title} ({series.points.length})
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
            {selectedSeries ? (
              <EffectPlot series={selectedSeries} />
            ) : (
              <p className="research-chart-note">
                当前数据没有同一结局、模型和分析口径下的可比较效应量。
              </p>
            )}
            {insights.data?.limitations.length ? (
              <div className="research-chart-limits">
                <AlertTriangle size={17} />
                <div>
                  {insights.data.limitations.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
        </section>
      )}

      <form className="research-search" onSubmit={submit}>
        <div className="research-query-row">
          <Search size={19} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="检索实体、结局或分析场景，例如 HOMA-IR、餐后、交互"
          />
          <button type="submit">
            <Search size={16} />
            检索
          </button>
        </div>
        <div className="research-filters">
          <label>
            <span>集合</span>
            <select value={collection} onChange={(event) => setCollection(event.target.value)}>
              <option value="all">全量</option>
              <option value="core">核心</option>
              <option value="contextual">情境化</option>
            </select>
          </label>
          <label>
            <span>分析族</span>
            <select value={testFamily} onChange={(event) => setTestFamily(event.target.value)}>
              <option value="">全部</option>
              {facets.data?.test_families.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>代谢结局</span>
            <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
              <option value="">全部</option>
              {facets.data?.outcomes.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>证据等级</span>
            <select
              value={evidenceLevel}
              onChange={(event) => setEvidenceLevel(event.target.value)}
            >
              <option value="">全部</option>
              {facets.data?.evidence_levels.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>结果状态</span>
            <select
              value={resultStatus}
              onChange={(event) => setResultStatus(event.target.value)}
            >
              <option value="">全部</option>
              {facets.data?.result_statuses.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </label>
        </div>
      </form>

      <div className="research-result-heading">
        <div>
          <span className="eyebrow">逐条证据</span>
          <h2>{results.data ? `${results.data.total} 条匹配记录` : "正在加载研究证据"}</h2>
        </div>
        {results.isFetching && <span className="research-loading">正在更新筛选结果</span>}
      </div>

      {results.isError ? (
        <div className="error-banner">研究证据加载失败，请重新登录或检查后端服务。</div>
      ) : (
        <div className="research-result-list">
          {results.data?.items.map((item) => (
            <article className="research-result-card" key={item.chunk_id}>
              <div className="research-result-topline">
                <span className="origin-pill internal">内部数据</span>
                <span>{item.test_family || "未分类"}</span>
                <span>{item.evidence_level || String(item.evidence_json.evidence_level ?? "等级未知")}</span>
                {item.core_48 && <span className="core-pill">核心证据</span>}
                <span className="private-pill">internal/private</span>
              </div>
              <h3>
                {String(item.evidence_json.subject_label ?? item.title)}{" "}
                <small>{item.predicate}</small>{" "}
                {String(item.evidence_json.object_label ?? "")}
              </h3>
              <p>{item.snippet}</p>
              <div className="research-stat-grid">
                <span><small>效应量</small>{item.effect_size || "—"}</span>
                <span><small>95% CI</small>{formatInterval(item.ci_low, item.ci_high)}</span>
                <span><small>P 值</small>{item.p_value || "—"}</span>
                <span><small>Q 值</small>{item.q_value || "—"}</span>
                <span><small>样本量</small>{item.sample_n || "—"}</span>
                <span><small>模型</small>{item.model_type || "—"}</span>
              </div>
              <div className="research-result-footer">
                <span>{item.analysis_context || item.source_locator}</span>
                <div>
                  {item.conflict_id && <span>冲突 {item.conflict_id}</span>}
                  <button type="button" onClick={() => setJsonItem(item)}>
                    <FileJson2 size={14} />
                    原始证据
                  </button>
                </div>
              </div>
            </article>
          ))}
          {results.data?.items.length === 0 && (
            <div className="research-empty">
              <Search size={30} />
              <p>当前筛选条件没有匹配记录。</p>
            </div>
          )}
        </div>
      )}
      {jsonItem && (
        <EvidenceJsonDialog item={jsonItem} onClose={() => setJsonItem(null)} />
      )}
    </div>
  );
}

function DistributionBars({
  items,
  total
}: {
  items: ResearchDistributionItem[];
  total: number;
}) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className="research-distribution">
      {items.map((item) => (
        <div key={item.key}>
          <div>
            <span>{item.label}</span>
            <strong>
              {item.count}
              <small>{item.percentage.toFixed(1)}%</small>
            </strong>
          </div>
          <div className="research-bar-track" aria-hidden="true">
            <span style={{ width: `${(item.count / maximum) * 100}%` }} />
          </div>
        </div>
      ))}
      {!items.length && <p className="research-chart-note">暂无 {total || 0} 条汇总数据。</p>}
    </div>
  );
}

function EffectPlot({ series }: { series: ResearchEffectSeries }) {
  const values = series.points.flatMap((point) => [
    point.value,
    point.ci_low ?? point.value,
    point.ci_high ?? point.value,
    series.reference_value
  ]);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = Math.max(0.1, rawMax - rawMin);
  const minimum = Math.min(rawMin - span * 0.12, series.reference_value - 0.05);
  const maximum = Math.max(rawMax + span * 0.12, series.reference_value + 0.05);
  const range = maximum - minimum;
  const plotLeft = 190;
  const plotRight = 690;
  const plotTop = 44;
  const rowHeight = 42;
  const height = Math.max(250, plotTop + series.points.length * rowHeight + 56);
  const x = (value: number) =>
    plotLeft + ((value - minimum) / range) * (plotRight - plotLeft);
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const value = minimum + (range * index) / 4;
    return { value, x: x(value) };
  });
  const referenceX = x(series.reference_value);
  const chartId = `effect-plot-${series.id.replaceAll(/[^a-zA-Z0-9_-]/g, "-")}`;

  function download(format: "png" | "svg") {
    const element = document.getElementById(chartId);
    if (!(element instanceof SVGSVGElement)) return;
    downloadSvg(element, `${chartId}.${format}`, format);
  }

  return (
    <div className="research-effect-chart">
      <div className="research-chart-actions">
        <span>
          n={series.points.length} · {series.unit}
        </span>
        <div>
          <button type="button" onClick={() => download("svg")}>
            <Download size={14} />
            SVG
          </button>
          <button type="button" onClick={() => download("png")}>
            <Download size={14} />
            PNG
          </button>
        </div>
      </div>
      <svg
        id={chartId}
        viewBox={`0 0 720 ${height}`}
        role="img"
        aria-label={`${series.outcome} 效应量点图`}
      >
        <rect width="720" height={height} fill="#ffffff" />
        {ticks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={tick.x}
              x2={tick.x}
              y1={plotTop - 10}
              y2={height - 42}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <text
              x={tick.x}
              y={height - 20}
              textAnchor="middle"
              fill="#64748b"
              fontSize="12"
            >
              {formatNumber(tick.value)}
            </text>
          </g>
        ))}
        <line
          x1={referenceX}
          x2={referenceX}
          y1={plotTop - 10}
          y2={height - 42}
          stroke="#475569"
          strokeWidth="1.5"
          strokeDasharray="5 4"
        />
        <text x={referenceX + 6} y={plotTop - 18} fill="#475569" fontSize="12">
          参考值 {series.reference_value}
        </text>
        {series.points.map((point, index) => {
          const y = plotTop + index * rowHeight;
          const hasInterval = point.ci_low !== null && point.ci_high !== null;
          const tone =
            point.result_status === "negative" ||
            point.result_status === "negative_mechanism"
              ? "#64748b"
              : point.result_status === "model_inconsistent"
                ? "#b45309"
                : "#0f766e";
          return (
            <g key={point.evidence_id}>
              <text x="12" y={y + 4} fill="#334155" fontSize="13">
                {truncate(point.label, 28)}
              </text>
              {hasInterval && (
                <line
                  x1={x(point.ci_low as number)}
                  x2={x(point.ci_high as number)}
                  y1={y}
                  y2={y}
                  stroke={tone}
                  strokeWidth="2"
                />
              )}
              <circle cx={x(point.value)} cy={y} r="5" fill={tone} />
              <text x={x(point.value) + 9} y={y + 4} fill="#475569" fontSize="12">
                {formatNumber(point.value)}
              </text>
            </g>
          );
        })}
        <text x={plotLeft} y={height - 4} fill="#64748b" fontSize="12">
          点估计{series.points.some((point) => point.ci_low !== null) ? "与真实 CI" : "；未报告 CI"}
        </text>
      </svg>
      <p className="research-chart-note">
        模型：{series.model_type}；分析条件：{series.analysis_context}。
        方向、证据等级与统计状态分别展示，不把关联解释为因果。
      </p>
    </div>
  );
}

function downloadSvg(
  element: SVGSVGElement,
  filename: string,
  format: "png" | "svg"
) {
  const source = new XMLSerializer().serializeToString(element);
  const svgBlob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
  if (format === "svg") {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(svgBlob);
    link.download = filename;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
    return;
  }
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = 1440;
    canvas.height = 640;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = filename;
    link.click();
  };
  image.src = URL.createObjectURL(svgBlob);
}

function truncate(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function formatNumber(value: number) {
  return Math.abs(value) >= 10 ? value.toFixed(1) : value.toFixed(2);
}

function Metric({
  icon,
  label,
  value,
  note
}: {
  icon: ReactNode;
  label: string;
  value: number | string;
  note: string;
}) {
  return (
    <article>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function formatInterval(low = "", high = "") {
  if (!low && !high) return "—";
  return `${low || "NA"}–${high || "NA"}`;
}

export default ResearchPage;
