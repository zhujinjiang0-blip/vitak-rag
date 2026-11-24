import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  ArrowRight,
  BookMarked,
  Database,
  Network,
  ShieldCheck
} from "lucide-react";
import { Link } from "react-router-dom";

interface PublicOverviewData {
  audit_date: string;
  total_records: number;
  graph_edges: number;
  answer_eligible_records: number;
  review_only_records: number;
  unique_entities: number;
  sources: number;
  public_evidence_pack: {
    version: string;
    eligible_literature_records: number;
    eligible_structured_records: number;
    research_only_literature_records: number;
    nodes: number;
    edges: number;
  };
  datasets: Array<{
    id: string;
    name: string;
    records: number;
    origin: "external" | "public";
    description: string;
  }>;
  limits: string[];
}

function PublicOverviewPage() {
  const overview = useQuery({
    queryKey: ["public-project-overview"],
    queryFn: async () => {
      const response = await fetch(
        `${import.meta.env.BASE_URL}project-overview.json`,
        { cache: "no-cache" }
      );
      if (!response.ok) throw new Error("项目概览数据加载失败");
      return response.json() as Promise<PublicOverviewData>;
    }
  });
  const data = overview.data;
  const pack = data?.public_evidence_pack;

  return (
    <div className="overview-page">
      <section className="overview-hero">
        <div>
          <span className="eyebrow">公网演示 · 外部证据版</span>
          <h1>维生素 K 知识图谱检索与证据追溯</h1>
          <p>
            整合已发表文献和权威公开结构化数据，从真实图谱关系定位到来源片段，
            提供可追溯的维生素 K 问答与证据检索。
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
          <span>公网外部证据</span>
          <strong>{formatNumber(pack?.nodes ?? data?.unique_entities ?? 0)}</strong>
          <small>个图谱实体 · {data?.audit_date ?? "2026-11-25"}</small>
        </div>
      </section>

      <div className="overview-runtime-note">
        <ShieldCheck size={18} />
        <p>
          <strong>公开数据范围：</strong>
          已审核外部文献 {formatNumber(pack?.eligible_literature_records ?? 0)} 条，
          公开结构化问答关系 {" "}
          {formatNumber(pack?.eligible_structured_records ?? 0)} 条，
          仅用于研究检索的外部记录 {" "}
          {formatNumber(pack?.research_only_literature_records ?? 0)} 条。
        </p>
      </div>

      <section className="overview-metrics" aria-label="公开数据规模">
        <MetricCard
          icon={<Database size={20} />}
          label="公开证据记录"
          value={formatNumber(data?.total_records ?? pack?.edges ?? 0)}
          note="真实外部文献与结构化关系"
        />
        <MetricCard
          icon={<Network size={20} />}
          label="知识图谱关系"
          value={formatNumber(data?.graph_edges ?? pack?.edges ?? 0)}
          note={`${formatNumber(data?.unique_entities ?? pack?.nodes ?? 0)} 个实体`}
        />
        <MetricCard
          icon={<ShieldCheck size={20} />}
          label="正式回答可用"
          value={formatNumber(data?.answer_eligible_records ?? 0)}
          note="通过来源边界与审核状态检查"
        />
        <MetricCard
          icon={<BookMarked size={20} />}
          label="来源记录"
          value={formatNumber(data?.sources ?? 0)}
          note={`${formatNumber(data?.review_only_records ?? 0)} 条仅用于研究检索`}
        />
      </section>

      <section className="overview-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">数据构成</span>
            <h2>公开证据来源</h2>
          </div>
          <span className="origin-pill public">{pack?.version}</span>
        </div>
        <div className="dataset-grid">
          {(data?.datasets ?? []).map((dataset) => (
            <article className="dataset-card" key={dataset.id}>
              <span className={`origin-pill ${dataset.origin}`}>外部数据</span>
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
              <span className="eyebrow">演示路径</span>
              <h2>四个公开页面</h2>
            </div>
          </div>
          <ol className="demo-path">
            <li><span>01</span><div><strong>项目概览</strong><p>说明公开数据来源和规模。</p></div></li>
            <li><span>02</span><div><strong>知识图谱</strong><p>展示实体和关系网络。</p></div></li>
            <li><span>03</span><div><strong>智能问答</strong><p>展示回答、引用和证据路径。</p></div></li>
            <li><span>04</span><div><strong>证据检索</strong><p>浏览外部来源片段。</p></div></li>
          </ol>
        </div>

        <div className="overview-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">系统边界</span>
              <h2>公网演示约定</h2>
            </div>
          </div>
          <ul className="limit-list">
            {(data?.limits ?? []).map((limit) => (
              <li key={limit}><ShieldCheck size={15} /><span>{limit}</span></li>
            ))}
          </ul>
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

export default PublicOverviewPage;
