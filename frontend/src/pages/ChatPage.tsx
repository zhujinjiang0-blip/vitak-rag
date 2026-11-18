import { FormEvent, useRef, useState } from "react";
import {
  ArrowUp,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  Info,
  LoaderCircle,
  ShieldAlert,
  Sparkles
} from "lucide-react";
import { askQuestion } from "../lib/api";
import { STATIC_DEMO_MODE } from "../lib/staticDemo";
import type { Answer } from "../lib/types";
import DataSourceLegend from "../components/DataSourceLegend";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  answer?: Answer;
  trace?: string[];
  streaming?: boolean;
}

const PUBLIC_SUGGESTIONS = [
  "维生素K有哪些食物来源？",
  "华法林和维生素K有什么关系？",
  "维生素K1和K2有什么区别？",
  "骨钙素与维生素K2有什么关系？",
  "MK-7有哪些随机对照研究证据？",
  "PIVKA-II可以反映什么？"
];

const PRIVATE_SUGGESTIONS = [
  "维生素K有哪些食物来源？",
  "华法林和维生素K有什么关系？",
  "骨钙素与维生素K2有什么关系？",
  "MK-7有哪些随机对照研究证据？",
  "内部队列中MK-7和胰岛素有什么关系？",
  "内部队列中VK1和HOMA-IR有什么关系？"
];

function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeAnswer, setActiveAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const messageSequence = useRef(0);
  const thinkingStepsRef = useRef<string[]>([]);

  function appendThinkingStep(message: string) {
    if (!message || message === "正在检索知识图谱与证据") return;
    if (thinkingStepsRef.current.includes(message)) return;
    thinkingStepsRef.current = [...thinkingStepsRef.current, message];
    setThinkingSteps(thinkingStepsRef.current);
  }

  async function revealAnswer(messageId: string, text: string) {
    const chunks = text.match(/[^。！？\n]+[。！？]?|\n+/g) ?? [text];
    let rendered = "";
    for (const chunk of chunks) {
      rendered += chunk;
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, text: rendered.trimStart() } : message
        )
      );
      if (chunk.trim()) {
        await new Promise((resolve) => window.setTimeout(resolve, 75));
      }
    }
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, streaming: false } : message
      )
    );
  }

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
    setStatus("正在准备检索");
    setThinkingSteps([]);
    thinkingStepsRef.current = [];

    try {
      await askQuestion(trimmed, sessionId, {
        status: (message) => {
          setStatus(message);
          appendThinkingStep(message);
        },
        onAnswer: async (answer) => {
          setSessionId(answer.session_id);
          setActiveAnswer(answer);
          const messageId = `message-${messageSequence.current++}`;
          const trace = [...thinkingStepsRef.current, "已完成来源核对并生成回答"];
          setMessages((current) => [
            ...current,
            {
              id: messageId,
              role: "assistant",
              text: "",
              answer,
              trace,
              streaming: true
            }
          ]);
          await revealAnswer(messageId, answer.answer_text);
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
      setThinkingSteps([]);
      thinkingStepsRef.current = [];
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
            <p>
              {STATIC_DEMO_MODE
                ? "回答由真实外部文献证据和原文片段确定性组装，不调用生成式模型。"
                : "回答可使用真实外部文献与本地内部队列证据，不调用生成式模型。"}
            </p>
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
                {(STATIC_DEMO_MODE ? PUBLIC_SUGGESTIONS : PRIVATE_SUGGESTIONS).map((suggestion) => (
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
                  data-streaming={
                    message.streaming ? "true" : undefined
                  }
                >
                  <div className="message-avatar">
                    {message.role === "user" ? "你" : "K"}
                  </div>
                  <div className="message-content">
                    <div
                      className={`message-text ${
                        message.streaming ? "streaming" : ""
                      }`}
                    >
                      {message.text}
                    </div>
                    {message.answer && (
                      <div className="message-meta">
                        <span>{intentLabel(message.answer.intent)}</span>
                        <span>{sufficiencyLabel(message.answer.sufficiency)}</span>
                        <span>{message.answer.data_version.version}</span>
                        <span>{message.answer.elapsed_ms} ms</span>
                        <span>{message.answer.citations.length} 条证据</span>
                      </div>
                    )}
                    {message.answer && message.trace && message.trace.length > 0 && (
                      <details className="reasoning-trace">
                        <summary>查看检索过程</summary>
                        <ol>
                          {message.trace.map((step) => (
                            <li key={step}>{step}</li>
                          ))}
                        </ol>
                      </details>
                    )}
                  </div>
                </article>
              ))}
              {loading && !messages.some((message) => message.streaming) && (
                <article className="message assistant-message">
                  <div className="message-avatar">K</div>
                  <div className="thinking-panel" aria-live="polite">
                    <div className="thinking-heading">
                      <LoaderCircle size={18} className="spin" />
                      <strong>{status || "正在整理答案"}</strong>
                    </div>
                    <ol>
                      {thinkingSteps.map((step, index) => (
                        <li key={step}>
                          <span className="thinking-index">
                            {index < thinkingSteps.length - 1 ? (
                              <CheckCircle2 size={14} />
                            ) : (
                              <LoaderCircle size={14} className="spin" />
                            )}
                          </span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
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
        <DataSourceLegend compact />

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
                      {citation.review_status && (
                        <span className="review-pill">{citation.review_status}</span>
                      )}
                      {citation.is_demo && <span className="demo-pill">演示</span>}
                    </div>
                    <h4>{citation.source_title}</h4>
                    <p>{citation.snippet}</p>
                    {(citation.analysis_context ||
                      citation.model_type ||
                      citation.sample_n ||
                      citation.effect_size ||
                      citation.p_value) && (
                      <div className="citation-statline">
                        {citation.analysis_context && <span>分析：{citation.analysis_context}</span>}
                        {citation.model_type && <span>模型：{citation.model_type}</span>}
                        {citation.sample_n && <span>n={citation.sample_n}</span>}
                        {citation.effect_size && <span>效应：{citation.effect_size}</span>}
                        {citation.p_value && <span>P={citation.p_value}</span>}
                      </div>
                    )}
                    <div className="citation-footer">
                      <span>
                        {citation.source_version ||
                          citation.data_owner ||
                          citation.locator ||
                          citation.source_id}
                      </span>
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
