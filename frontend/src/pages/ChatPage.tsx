import { FormEvent, useRef, useState } from "react";
import {
  ArrowUp,
  BookOpen,
  ExternalLink,
  GitBranch,
  Info,
  LoaderCircle,
  ShieldAlert,
  Sparkles
} from "lucide-react";
import { askQuestion } from "../lib/api";
import type { Answer } from "../lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  answer?: Answer;
}

const SUGGESTIONS = [
  "维生素K有哪些食物来源？",
  "华法林和维生素K有什么关系？",
  "维生素K缺乏会影响什么？",
  "INR可以用来评估什么？",
  "新生儿为什么需要维生素K预防？",
  "维生素K1和K2有什么区别？"
];

function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeAnswer, setActiveAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const messageSequence = useRef(0);

  async function submit(query: string) {
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    const userMessage: Message = {
      id: `message-${messageSequence.current++}`,
      role: "user",
      text: trimmed
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setLoading(true);
    setStatus("正在连接本地知识库");

    try {
      await askQuestion(trimmed, sessionId, {
        status: setStatus,
        onAnswer: (answer) => {
          setSessionId(answer.session_id);
          setActiveAnswer(answer);
          setMessages((current) => [
            ...current,
            {
              id: `message-${messageSequence.current++}`,
              role: "assistant",
              text: answer.answer_text,
              answer
            }
          ]);
        }
      });
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `message-${messageSequence.current++}`,
          role: "assistant",
          text:
            error instanceof Error
              ? `无法完成检索：${error.message}`
              : "无法完成检索，请确认后端服务已经启动。"
        }
      ]);
    } finally {
      setLoading(false);
      setStatus("");
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(input);
  }

  return (
    <div className="chat-layout">
      <section className="chat-workspace">
        <div className="page-heading chat-heading">
          <div>
            <span className="eyebrow">知识图谱检索</span>
            <h1>维K智问</h1>
            <p>回答由已审核图谱关系和来源片段组装，不调用生成式模型。</p>
          </div>
          <div className="knowledge-badge">
            <Sparkles size={17} />
            证据驱动
          </div>
        </div>

        <div className="chat-scroll" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-chat">
              <div className="empty-mark">K</div>
              <h2>从一个具体问题开始</h2>
              <p>
                系统会先定位实体，再查询图谱路径和原始证据。知识库无法支持的问题会明确拒答。
              </p>
              <div className="suggestion-grid">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="suggestion-button"
                    onClick={() => void submit(suggestion)}
                  >
                    <span>{suggestion}</span>
                    <ArrowUp size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`message ${message.role === "user" ? "user-message" : "assistant-message"}`}
                >
                  <div className="message-avatar">
                    {message.role === "user" ? "你" : "K"}
                  </div>
                  <div className="message-content">
                    <div className="message-text">{message.text}</div>
                    {message.answer && (
                      <div className="message-meta">
                        <span>{intentLabel(message.answer.intent)}</span>
                        <span>{sufficiencyLabel(message.answer.sufficiency)}</span>
                        <span>{message.answer.elapsed_ms} ms</span>
                        <span>{message.answer.citations.length} 条证据</span>
                      </div>
                    )}
                  </div>
                </article>
              ))}
              {loading && (
                <article className="message assistant-message">
                  <div className="message-avatar">K</div>
                  <div className="loading-line">
                    <LoaderCircle size={18} className="spin" />
                    <span>{status || "正在查询图谱"}</span>
                  </div>
                </article>
              )}
            </div>
          )}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit(input);
              }
            }}
            placeholder="输入关于维生素K的问题..."
            rows={2}
            disabled={loading}
          />
          <button type="submit" disabled={!input.trim() || loading} aria-label="发送问题">
            <ArrowUp size={19} />
          </button>
        </form>
        <p className="medical-disclaimer">
          <ShieldAlert size={15} />
          内容用于科普和知识检索，不能替代医生诊断、处方或个体化用药建议。
        </p>
      </section>

      <aside className="evidence-rail">
        <div className="rail-heading">
          <div>
            <span className="eyebrow">回答依据</span>
            <h2>证据与路径</h2>
          </div>
          <Info size={19} />
        </div>

        {!activeAnswer ? (
          <div className="rail-empty">
            <BookOpen size={32} />
            <p>完成一次问答后，这里会展示证据来源和图谱关联路径。</p>
          </div>
        ) : (
          <div className="rail-content">
            {activeAnswer.safety_notice && (
              <div className="safety-panel">
                <ShieldAlert size={18} />
                <p>{activeAnswer.safety_notice}</p>
              </div>
            )}

            <div className="rail-section">
              <h3>图谱路径</h3>
              {activeAnswer.graph_paths.length === 0 ? (
                <p className="muted">本次回答由单跳关系或证据片段直接组装。</p>
              ) : (
                activeAnswer.graph_paths.map((path, index) => (
                  <div className="path-block" key={`path-${index}`}>
                    <GitBranch size={16} />
                    <div>
                      {path.nodes.map((node, nodeIndex) => (
                        <span className="path-step" key={node.id}>
                          <strong>{node.name}</strong>
                          {nodeIndex < path.edges.length && (
                            <small>{path.edges[nodeIndex]?.predicate}</small>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="rail-section">
              <h3>来源证据</h3>
              <div className="citation-list">
                {activeAnswer.citations.map((citation) => (
                  <article className="citation-card" key={citation.id}>
                    <div className="citation-topline">
                      <span className="source-type">
                        {citation.source_classification || citation.source_type}
                      </span>
                      <span className={`origin-pill ${citation.data_origin}`}>
                        {originLabel(citation.data_origin)}
                      </span>
                      {citation.is_demo && <span className="demo-pill">演示</span>}
                    </div>
                    <h4>{citation.source_title}</h4>
                    <p>{citation.snippet}</p>
                    <div className="citation-footer">
                      <span>{citation.data_owner || citation.locator || citation.source_id}</span>
                      {citation.url && (
                        <a href={citation.url} target="_blank" rel="noreferrer">
                          查看来源 <ExternalLink size={13} />
                        </a>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function intentLabel(intent: string) {
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
    general: "图谱检索"
  };
  return labels[intent] ?? intent;
}

function sufficiencyLabel(value: Answer["sufficiency"]) {
  return {
    sufficient: "证据充分",
    partial: "部分证据",
    none: "无充分证据"
  }[value];
}

function originLabel(origin: string) {
  return {
    internal: "内部数据",
    external: "外部数据",
    public: "公开数据",
    synthetic: "合成数据"
  }[origin] ?? origin;
}

export default ChatPage;
