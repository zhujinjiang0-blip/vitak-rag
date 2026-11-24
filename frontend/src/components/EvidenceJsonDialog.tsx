import { Check, Copy, Download, FileJson2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SearchResult } from "../lib/types";

interface EvidenceJsonDialogProps {
  item: SearchResult;
  onClose: () => void;
}

function evidencePayload(item: SearchResult) {
  return {
    schema_version: "vitak.evidence.v1",
    evidence_id: item.chunk_id,
    relation: {
      predicate: item.predicate || null,
      entity_ids: item.entity_ids
    },
    source: {
      source_id: item.source_id,
      source_record_id: item.source_record_id,
      source_type: item.source_type,
      source_classification: item.source_classification,
      data_owner: item.data_owner,
      publisher: typeof item.evidence_json.publisher === "string"
        ? item.evidence_json.publisher
        : "",
      title: item.title,
      url: item.url || null,
      published_at: typeof item.evidence_json.published_at === "string"
        ? item.evidence_json.published_at
        : ""
    },
    governance: {
      data_origin: item.data_origin,
      access_scope: item.access_scope,
      review_status: item.review_status,
      input_status: item.input_status,
      fusion_status: item.fusion_status,
      evidence_status: item.evidence_status,
      graph_display_role: item.graph_display_role,
      answer_eligible: item.answer_eligible
    },
    provenance: {
      source_version: item.source_version,
      source_locator: item.source_locator,
      document_id: item.document_id,
      chunk_id: item.chunk_id
    },
    retrieval: {
      score: item.score,
      snippet: item.snippet
    },
    raw_record: item.evidence_json
  };
}

function EvidenceJsonDialog({ item, onClose }: EvidenceJsonDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const payload = evidencePayload(item);
  const jsonText = JSON.stringify(payload, null, 2);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(jsonText);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setCopyState("error");
    }
  }

  function downloadJson() {
    const safeId = item.chunk_id.replace(/[^a-z0-9_-]+/gi, "-");
    const blob = new Blob([jsonText], {
      type: "application/json;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `vitak-evidence-${safeId}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return (
    <div
      className="evidence-json-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={dialogRef}
        className="evidence-json-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-json-title"
        tabIndex={-1}
      >
        <div className="evidence-json-shell">
          <header className="evidence-json-header">
            <div>
              <span className="eyebrow">结构化证据</span>
              <h2 id="evidence-json-title">
                <FileJson2 size={18} />
                {item.title}
              </h2>
            </div>
            <button
              type="button"
              className="icon-button"
              onClick={onClose}
              aria-label="关闭 JSON 详情"
            >
              <X size={17} />
            </button>
          </header>
          <div className="evidence-json-meta">
            <span className={`origin-pill ${item.data_origin}`}>
              {originLabel(item.data_origin)}
            </span>
            <span
              className={`eligibility-pill ${item.answer_eligible ? "eligible" : "research-only"}`}
            >
              {item.answer_eligible ? "可用于正式回答" : "仅研究检索"}
            </span>
            <code>{item.chunk_id}</code>
          </div>
          <pre className="evidence-json-code" data-testid="evidence-json">
            {jsonText}
          </pre>
          <footer className="evidence-json-actions">
            <button type="button" className="result-action" onClick={copyJson}>
              {copyState === "copied" ? <Check size={15} /> : <Copy size={15} />}
              {copyState === "copied"
                ? "已复制"
                : copyState === "error"
                  ? "复制失败"
                  : "复制 JSON"}
            </button>
            <button type="button" className="result-action primary" onClick={downloadJson}>
              <Download size={15} />
              下载 JSON
            </button>
          </footer>
        </div>
      </section>
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

export default EvidenceJsonDialog;
