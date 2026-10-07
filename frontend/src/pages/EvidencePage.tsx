import { FormEvent, useState } from "react";
import { BookOpenText, ExternalLink, FileSearch, Search } from "lucide-react";
import { searchEvidence } from "../lib/api";
import type { SearchResult } from "../lib/types";

function EvidencePage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [items, setItems] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  return (
    <div className="evidence-page">
      <section className="page-heading evidence-heading">
        <div>
          <span className="eyebrow">来源片段检索</span>
          <h1>证据检索</h1>
          <p>同时使用中文全文索引和向量召回，结果中的所有来源均来自当前版本。</p>
        </div>
        <BookOpenText size={34} />
      </section>

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
        <strong>{items.length} 条结果</strong>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {items.length === 0 && !loading && !error ? (
        <div className="evidence-empty">
          <BookOpenText size={42} />
          <h2>从知识库中查找来源</h2>
          <p>尝试搜索“华法林”“食物来源”“新生儿”或“检测指标”。</p>
        </div>
      ) : (
        <div className="evidence-results">
          {items.map((item) => (
            <article className="evidence-result-card" key={item.chunk_id}>
              <div className="result-topline">
                <span>{item.source_id}</span>
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
              <div className="result-link">
                <span>{item.chunk_id}</span>
                <ExternalLink size={14} />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

export default EvidencePage;

