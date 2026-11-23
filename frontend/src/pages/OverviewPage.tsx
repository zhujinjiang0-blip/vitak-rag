import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  ArrowRight,
  BookMarked,
  Database,
  GitFork,
  Info,
  LockKeyhole,
  Network,
  ShieldCheck
} from "lucide-react";
import { Link } from "react-router-dom";
import DataSourceLegend from "../components/DataSourceLegend";

interface OverviewData {
  audit_date: string;
  total_records: number;
  graph_edges: number;
  merged_duplicate_records: number;
  answer_eligible_records: number;
  review_only_records: number;
  unique_entities: number;
  literal_nodes: number;
  sources: number;
  public_evidence_pack?: {
    version: string;
    eligible_literature_records: number;
    eligible_structured_records?: number;
    research_only_literature_records: number;
    internal_records: number;
    nodes: number;
    edges: number;
  };
  datasets: Array<{
    id: string;
    name: string;
    records: number;
    origin: string;
    description: string;
  }>;
  review_statuses: Record<string, number>;
  mvp_pages: string[];
  limits: string[];
}

function OverviewPage() {
  const overview = useQuery({
    queryKey: ["project-overview"],
    queryFn: async () => {
      const response = await fetch(`${import.meta.env.BASE_URL}project-overview.json`);
      if (!response.ok) throw new Error("项目概览数据加载失败");
      return response.json() as Promise<OverviewData>;
    }
  });
  const data = overview.data;

  return (
    <div className="overview-page">
      <section className="overview-hero">
        <div>
          <span className="eyebrow">预答辩 MVP · 研究人员工作台</span>
          <h1>维生素 K 知识图谱检索与证据追溯</h1>
          <p>
            整合外部文献、外部结构化数据和内部 395 人队列证据，
            从图谱关系定位到原文与统计证据。
          </p>
          <div className="overview-actions">
            <Link className="primary-link" to="/chat">
              开始问答 <ArrowRight size={17} />
            </Link>
            <Link className="secondary-link" to="/evidence">
              浏览证据
            </Link>
          </div>
        </div>
        <div className="overview-facts">
          <span>真实数据审计</span>
          <strong>{formatNumber(data?.total_records ?? 73396)}</strong>
          <small>条证据记录 · {data?.audit_date ?? "2026-11-19"}</small>
        </div>
      </section>

      <div className="overview-runtime-note">
        <Info size={18} />
        <p>
          <strong>预答辩演示口径：</strong>
          在线问答读取 1,012 条已审核外部文献关系、
          {formatNumber(data?.public_evidence_pack?.eligible_structured_records ?? 3123)}
          条公开结构化关系和 1,200 条仅研究检索记录；
          内部 248 条队列证据只保留在本地私有快照，不上传原始 CSV、内部证据或全量图谱。
        </p>
      </div>

      <DataSourceLegend />

      <section className="overview-metrics" aria-label="数据规模">
        <MetricCard
          icon={<Database size={20} />}
          label="总三元组"
          value={formatNumber(data?.total_records ?? 73396)}
          note="外部 73,148 条 · 内部 248 条"
        />
        <MetricCard
          icon={<Network size={20} />}
          label="真实关系边"
          value={formatNumber(data?.graph_edges ?? 73279)}
          note={`${formatNumber(data?.unique_entities ?? 36638)} 个图谱实体`}
        />
        <MetricCard
          icon={<ShieldCheck size={20} />}
          label="正式回答可用"
          value={formatNumber(data?.answer_eligible_records ?? 54249)}
          note={`${formatNumber(data?.merged_duplicate_records ?? 117)} 条重复证据 · ${formatNumber(data?.review_only_records ?? 19147)} 条仅研究检索`}
        />
        <MetricCard
          icon={<BookMarked size={20} />}
          label="来源记录"
          value={formatNumber(data?.sources ?? 566)}
          note={`${formatNumber(data?.literal_nodes ?? 25527)} 个字面值节点`}
        />
      </section>

      <section className="overview-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">数据构成</span>
            <h2>三类真实数据源</h2>
          </div>
        </div>
        <div className="dataset-grid">
          {(data?.datasets ?? []).map((dataset) => (
            <article className="dataset-card" key={dataset.id}>
              <span className={`origin-pill ${dataset.origin}`}>
                {dataset.origin === "internal" ? "内部数据" : "外部数据"}
              </span>
              <strong>{formatNumber(dataset.records)}</strong>
              <h3>{dataset.name}</h3>
              <p>{dataset.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="overview-columns">
        <div className="overview-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">预答辩演示路径</span>
              <h2>四个核心页面</h2>
            </div>
          </div>
          <ol className="demo-path">
            <li><span>01</span><div><strong>项目概览</strong><p>说明数据来源和规模。</p></div></li>
            <li><span>02</span><div><strong>知识图谱</strong><p>展示实体和多跳关系。</p></div></li>
            <li><span>03</span><div><strong>智能问答</strong><p>展示答案、证据和推理路径。</p></div></li>
            <li><span>04</span><div><strong>证据检索</strong><p>筛选内部和外部证据。</p></div></li>
          </ol>
        </div>

        <div className="overview-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">系统边界</span>
              <h2>当前 MVP 约定</h2>
            </div>
          </div>
          <ul className="limit-list">
            {(data?.limits ?? []).map((limit) => (
              <li key={limit}><LockKeyhole size={15} /><span>{limit}</span></li>
            ))}
          </ul>
          <Link className="text-link" to="/import">
            查看本地 CSV 数据入口 <GitFork size={15} />
          </Link>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  note
}: {
  icon: ReactNode;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export default OverviewPage;
