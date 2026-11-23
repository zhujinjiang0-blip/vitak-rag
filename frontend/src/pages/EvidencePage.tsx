import { FormEvent, useState } from "react";
import {
  BookOpenText,
  ExternalLink,
  FileJson2,
  FileSearch,
  Search
} from "lucide-react";
import DataSourceLegend from "../components/DataSourceLegend";
import EvidenceJsonDialog from "../components/EvidenceJsonDialog";
import { searchEvidence } from "../lib/api";
import type { SearchResult } from "../lib/types";

function EvidencePage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [items, setItems] = useState<SearchResult[]>([]);
  const [originFilter, setOriginFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [jsonItem, setJsonItem] = useState<SearchResult | null>(null);

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError("");
    setSubmitted(trimmed);
    try {
      const result = await searchEvidence(trimmed);
      setItems(result.items);
    } catch (requestError) {
      setItems([]);
      setError(requestError instanceof Error ? requestError.message : "检索失败");
    } finally {
      setLoading(false);
    }
  }

  const visibleItems =
    originFilter === "all"
      ? items
      : items.filter((item) => item.data_origin === originFilter);

  return (
    <div className="evidence-page">
      <section className="page-heading evidence-heading">
        <div>
          <span className="eyebrow">来源片段检索</span>
          <h1>证据检索</h1>
          <p>检索真实外部文献证据，并区分可用于正式回答与仅用于研究审核的记录。</p>
        </div>
        <BookOpenText size={34} />
      </section>

      <DataSourceLegend />

      <form className="evidence-search" onSubmit={runSearch}>
        <FileSearch size={21} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="输入关键词、实体或研究主题..."
        />
        <button type="submit" disabled={!query.trim() || loading}>
          <Search size={17} />
          {loading ? "检索中" : "检索"}
        </button>
      </form>

      <div className="evidence-summary">
        <span>{submitted ? `“${submitted}”` : "等待检索"}</span>
        <div className="origin-filter">
          {[
            ["all", "全部"],
            ["internal", "内部"],
            ["external", "外部"],
            ["public", "公开"]
          ].map(([value, label]) => (
            <button
              type="button"
              key={value}
              className={originFilter === value ? "active" : ""}
              onClick={() => setOriginFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <strong>{visibleItems.length} 条结果</strong>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {visibleItems.length === 0 && !loading && !error ? (
        <div className="evidence-empty">
          <BookOpenText size={42} />
          <h2>从知识库中查找来源</h2>
          <p>尝试搜索“华法林”“骨钙素”“绿叶蔬菜”“MK-7”或“PIVKA-II”。</p>
        </div>
      ) : (
        <div className="evidence-results">
          {visibleItems.map((item) => (
            <article className="evidence-result-card" key={item.chunk_id}>
              <div className="result-topline">
                <span>{item.source_id}</span>
                <span className={`origin-pill ${item.data_origin}`}>
                  {originLabel(item.data_origin)}
                </span>
                <span
                  className={`eligibility-pill ${item.answer_eligible ? "eligible" : "research-only"}`}
                >
                  {item.answer_eligible ? "可用于正式回答" : "仅研究检索"}
                </span>
                {item.is_demo && <span className="demo-pill">演示数据</span>}
                <span className="result-score">匹配度 {Math.round(item.score * 100)}%</span>
              </div>
              <h2>{item.title}</h2>
              <p>{item.snippet}</p>
              {item.entity_ids.length > 0 && (
                <div className="entity-tags">
                  {item.entity_ids.map((entityId) => (
                    <span key={entityId}>{entityId}</span>
                  ))}
                </div>
              )}
              <div className="result-footer">
                <span className="result-source-meta">
                  {item.review_status} · {item.source_version || item.data_owner || item.chunk_id}
                </span>
                <div className="result-actions">
                  {item.url && (
                    <a
                      className="result-action"
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      查看原文
                      <ExternalLink size={14} />
                    </a>
                  )}
                  <button
                    type="button"
                    className="result-action"
                    onClick={() => setJsonItem(item)}
                  >
                    <FileJson2 size={14} />
                    查看 JSON
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {jsonItem && (
        <EvidenceJsonDialog
          key={jsonItem.chunk_id}
          item={jsonItem}
          onClose={() => setJsonItem(null)}
        />
      )}
    </div>
  );
}

function originLabel(origin: string) {
  return {
    internal: "内部数据",
    external: "外部数据",
    public: "公开数据",
    synthetic: "合成数据"
  }[origin] ?? origin;
}

export default EvidencePage;
