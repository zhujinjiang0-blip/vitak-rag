import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  ExternalLink,
  FolderKanban,
  FolderPlus,
  GitBranch,
  Info,
  LoaderCircle,
  MessageSquareText,
  Network,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
  X
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { answerTriage, askQuestion, startTriage } from "@api";
import { useAuth } from "@auth";
import { PUBLIC_BUILD } from "../lib/buildMode";
import {
  CLAIM_TYPE_LABELS,
  COMPARISON_STATUS_LABELS,
  claimScienceProfile
} from "../lib/claimBoundary";
import {
  createGraphPathHandoff,
  saveGraphPathHandoff
} from "../lib/graphPathHandoff";
import { STATIC_DEMO_MODE } from "../lib/staticDemo";
import type { Answer, QAMode, TriageSession } from "../lib/types";
import DataSourceLegend from "../components/DataSourceLegend";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  answer?: Answer;
  trace?: string[];
  streaming?: boolean;
}

interface ConversationSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

interface ConversationProject {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  sessions: ConversationSession[];
}

interface ConversationState {
  projects: ConversationProject[];
  activeProjectId: string;
  activeSessionId: string | null;
}

const PROJECTS_STORAGE_KEY = "vitak-rag:projects:v2";
const ACTIVE_PROJECT_STORAGE_KEY = "vitak-rag:active-project:v2";
const ACTIVE_SESSION_STORAGE_KEY = "vitak-rag:active-conversation:v2";
const LEGACY_SESSIONS_STORAGE_KEY = "vitak-rag:conversations:v1";
const LEGACY_ACTIVE_SESSION_STORAGE_KEY = "vitak-rag:active-conversation:v1";
const MAX_STORED_PROJECTS = 10;
const MAX_STORED_SESSIONS = 20;
const MAX_STORED_MESSAGES = 60;

function makeMessageId() {
  return `message-${crypto.randomUUID()}`;
}

function makeSessionId() {
  return `web-${crypto.randomUUID()}`;
}

function makeProjectId() {
  return `project-${crypto.randomUUID()}`;
}

function sessionTitle(query: string) {
  const compact = query.replace(/\s+/g, " ").trim();
  return compact.length > 28 ? `${compact.slice(0, 28)}…` : compact;
}

function makeSession(timestamp = Date.now()): ConversationSession {
  return {
    id: makeSessionId(),
    title: "新会话",
    createdAt: timestamp,
    updatedAt: timestamp,
    messages: []
  };
}

function makeProject(title: string, timestamp = Date.now()): ConversationProject {
  return {
    id: makeProjectId(),
    title,
    createdAt: timestamp,
    updatedAt: timestamp,
    sessions: [makeSession(timestamp)]
  };
}

function loadConversationState(): ConversationState {
  try {
    const storedProjects = JSON.parse(
      window.localStorage.getItem(PROJECTS_STORAGE_KEY) ?? "[]"
    ) as ConversationProject[];
    const projects = storedProjects
      .filter(
        (project) =>
          project &&
          typeof project.id === "string" &&
          typeof project.title === "string" &&
          Array.isArray(project.sessions)
      )
      .slice(0, MAX_STORED_PROJECTS)
      .map((project) => ({
        ...project,
        sessions: project.sessions
          .filter(
            (session) =>
              session &&
              typeof session.id === "string" &&
              Array.isArray(session.messages)
          )
          .slice(0, MAX_STORED_SESSIONS)
      }));
    if (projects.length) {
      const storedProject = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
      const activeProject =
        projects.find((project) => project.id === storedProject) ?? projects[0];
      const storedSession = window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
      const activeSessionId = activeProject.sessions.some(
        (session) => session.id === storedSession
      )
        ? storedSession
        : activeProject.sessions[0]?.id ?? null;
      return {
        projects,
        activeProjectId: activeProject.id,
        activeSessionId
      };
    }

    const legacySessions = JSON.parse(
      window.localStorage.getItem(LEGACY_SESSIONS_STORAGE_KEY) ?? "[]"
    ) as ConversationSession[];
    const validLegacySessions = legacySessions
      .filter(
        (session) =>
          session &&
          typeof session.id === "string" &&
          Array.isArray(session.messages)
      )
      .slice(0, MAX_STORED_SESSIONS);
    const timestamp = Date.now();
    const project: ConversationProject = {
      id: makeProjectId(),
      title: "我的维K项目",
      createdAt: timestamp,
      updatedAt: timestamp,
      sessions:
        validLegacySessions.length > 0
          ? validLegacySessions
          : [makeSession(timestamp)]
    };
    const legacyActive = window.localStorage.getItem(
      LEGACY_ACTIVE_SESSION_STORAGE_KEY
    );
    return {
      projects: [project],
      activeProjectId: project.id,
      activeSessionId: project.sessions.some(
        (session) => session.id === legacyActive
      )
        ? legacyActive
        : project.sessions[0]?.id ?? null
    };
  } catch {
    const project = makeProject("我的维K项目");
    return {
      projects: [project],
      activeProjectId: project.id,
      activeSessionId: project.sessions[0]?.id ?? null
    };
  }
}

function previewMessage(session: ConversationSession) {
  const latest = [...session.messages]
    .reverse()
    .find((message) => message.text.trim());
  return latest?.text.replace(/\s+/g, " ").slice(0, 54) ?? "暂无问答内容";
}

function relativeSessionTime(timestamp: number) {
  const elapsedMinutes = Math.max(
    0,
    Math.floor((Date.now() - timestamp) / 60_000)
  );
  if (elapsedMinutes < 1) return "刚刚";
  if (elapsedMinutes < 60) return `${elapsedMinutes} 分钟前`;
  if (elapsedMinutes < 24 * 60) return `${Math.floor(elapsedMinutes / 60)} 小时前`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit"
  }).format(timestamp);
}

const PUBLIC_SUGGESTIONS = [
  "维生素K有哪些食物来源？",
  "华法林和维生素K有什么关系？",
  "维生素K1和K2有什么区别？",
  "骨钙素与维生素K2有什么关系？",
  "MK-7有哪些随机对照研究证据？",
  "PIVKA-II可以反映什么？"
];

function ChatPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const [conversation, setConversation] =
    useState<ConversationState>(loadConversationState);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [triage, setTriage] = useState<TriageSession | null>(null);
  const [triageSelection, setTriageSelection] = useState<string[]>([]);
  const [triageLoading, setTriageLoading] = useState(false);
  const [triageError, setTriageError] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingProjectName, setEditingProjectName] = useState("");
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingSessionTitle, setEditingSessionTitle] = useState("");
  const [sessionSearch, setSessionSearch] = useState("");
  const [highlightedCitationId, setHighlightedCitationId] = useState<string | null>(
    null
  );
  const qaMode: QAMode = "domain";
  const thinkingStepsRef = useRef<string[]>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const activeProject =
    conversation.projects.find(
      (project) => project.id === conversation.activeProjectId
    ) ?? conversation.projects[0];
  const projectSessions = activeProject?.sessions ?? [];
  const activeSession =
    projectSessions.find(
      (session) => session.id === conversation.activeSessionId
    ) ?? null;
  const messages = activeSession?.messages ?? [];
  const activeAnswer = useMemo(
    () =>
      [...messages].reverse().find((message) => message.answer)?.answer ?? null,
    [messages]
  );
  const latestAnswerMessageId = useMemo(
    () => [...messages].reverse().find((message) => message.answer)?.id ?? null,
    [messages]
  );
  const orderedSessions = useMemo(
    () => [...projectSessions].sort((left, right) => right.updatedAt - left.updatedAt),
    [projectSessions]
  );
  const visibleSessions = useMemo(() => {
    const needle = sessionSearch.trim().toLowerCase();
    if (!needle) return orderedSessions;
    return orderedSessions.filter((session) =>
      `${session.title} ${previewMessage(session)}`.toLowerCase().includes(needle)
    );
  }, [orderedSessions, sessionSearch]);
  const orderedProjects = useMemo(
    () => [...conversation.projects].sort((left, right) => right.updatedAt - left.updatedAt),
    [conversation.projects]
  );

  useEffect(() => {
    const compactProjects = [...conversation.projects]
      .sort((left, right) => right.updatedAt - left.updatedAt)
      .slice(0, MAX_STORED_PROJECTS)
      .map((project) => ({
        ...project,
        sessions: [...project.sessions]
          .sort((left, right) => right.updatedAt - left.updatedAt)
          .slice(0, MAX_STORED_SESSIONS)
          .map((session) => ({
            ...session,
            messages: session.messages.slice(-MAX_STORED_MESSAGES).map(
              ({ streaming: _streaming, ...message }) => message
            )
          }))
      }));
    try {
      window.localStorage.setItem(
        PROJECTS_STORAGE_KEY,
        JSON.stringify(compactProjects)
      );
      window.localStorage.removeItem(LEGACY_SESSIONS_STORAGE_KEY);
      window.localStorage.removeItem(LEGACY_ACTIVE_SESSION_STORAGE_KEY);
    } catch {
      // Keep the current in-memory projects if browser storage is unavailable.
    }
  }, [conversation.projects]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        ACTIVE_PROJECT_STORAGE_KEY,
        conversation.activeProjectId
      );
      if (conversation.activeSessionId) {
        window.localStorage.setItem(
          ACTIVE_SESSION_STORAGE_KEY,
          conversation.activeSessionId
        );
      } else {
        window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      }
    } catch {
      // Browser storage is optional for the current page session.
    }
  }, [conversation.activeProjectId, conversation.activeSessionId]);

  useEffect(() => {
    stickToBottomRef.current = true;
    const frame = window.requestAnimationFrame(() => {
      const element = chatScrollRef.current;
      if (element) element.scrollTop = element.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [conversation.activeSessionId]);

  useEffect(() => {
    setHighlightedCitationId(null);
    setTriage(null);
    setTriageSelection([]);
    setTriageError("");
  }, [conversation.activeSessionId]);

  useEffect(() => {
    setTriageSelection([]);
    setTriageError("");
  }, [triage?.question?.id]);

  useEffect(() => {
    const element = chatScrollRef.current;
    if (!element) return;
    if (messages.at(-1)?.role === "user") {
      stickToBottomRef.current = true;
    }
    if (!stickToBottomRef.current) return;
    const frame = window.requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [loading, messages, status, thinkingSteps.length]);

  function resetComposer() {
    setInput("");
    setStatus("");
    setThinkingSteps([]);
    setEditingSessionId(null);
    setEditingSessionTitle("");
    thinkingStepsRef.current = [];
  }

  async function beginTriage() {
    if (triageLoading) return;
    setTriageLoading(true);
    setTriageError("");
    try {
      const session = await startTriage();
      setTriage(session);
      setTriageSelection([]);
    } catch (error) {
      setTriageError(
        error instanceof Error ? error.message : "无法启动风险自查"
      );
    } finally {
      setTriageLoading(false);
    }
  }

  function toggleTriageOption(value: string) {
    const question = triage?.question;
    if (!question || triageLoading) return;
    if (!question.multiple) {
      setTriageSelection([value]);
      return;
    }
    if (value === "none") {
      setTriageSelection(["none"]);
      return;
    }
    setTriageSelection((current) => {
      const withoutNone = current.filter((item) => item !== "none");
      return withoutNone.includes(value)
        ? withoutNone.filter((item) => item !== value)
        : [...withoutNone, value];
    });
  }

  async function advanceTriage(action: "next" | "back" = "next") {
    if (!triage?.question || triageLoading) return;
    if (action === "next" && triageSelection.length === 0) return;
    setTriageLoading(true);
    setTriageError("");
    try {
      const updated = await answerTriage(
        triage.session_id,
        triage.question.id,
        triageSelection,
        action
      );
      setTriage(updated);
      if (updated.question) setTriageSelection([]);
    } catch (error) {
      setTriageError(
        error instanceof Error ? error.message : "无法提交本次选择"
      );
    } finally {
      setTriageLoading(false);
    }
  }

  function closeTriage() {
    if (triageLoading) return;
    setTriage(null);
    setTriageSelection([]);
    setTriageError("");
  }

  function createSession() {
    if (!activeProject) {
      const project = makeProject("我的维K项目");
      setConversation({
        projects: [project],
        activeProjectId: project.id,
        activeSessionId: project.sessions[0]?.id ?? null
      });
      resetComposer();
      return project.sessions[0]?.id ?? null;
    }
    const timestamp = Date.now();
    const session = makeSession(timestamp);
    setConversation((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === current.activeProjectId
          ? {
              ...project,
              updatedAt: timestamp,
              sessions: [session, ...project.sessions]
            }
          : project
      ),
      activeSessionId: session.id
    }));
    resetComposer();
    return session.id;
  }

  function createProject(title: string) {
    const timestamp = Date.now();
    const project = makeProject(title.trim() || "新项目", timestamp);
    setConversation((current) => ({
      projects: [project, ...current.projects],
      activeProjectId: project.id,
      activeSessionId: project.sessions[0]?.id ?? null
    }));
    setIsCreatingProject(false);
    setProjectName("");
    setEditingProjectId(null);
    setEditingSessionId(null);
    setSessionSearch("");
    resetComposer();
  }

  function submitProject(event: FormEvent) {
    event.preventDefault();
    if (!projectName.trim()) return;
    createProject(projectName);
  }

  function selectProject(projectId: string) {
    if (loading) return;
    setConversation((current) => {
      const project = current.projects.find((item) => item.id === projectId);
      const activeSessionId =
        [...(project?.sessions ?? [])].sort(
          (left, right) => right.updatedAt - left.updatedAt
        )[0]?.id ?? null;
      return { ...current, activeProjectId: projectId, activeSessionId };
    });
    setEditingProjectId(null);
    setEditingSessionId(null);
    setSessionSearch("");
    resetComposer();
  }

  function deleteProject(projectId: string) {
    if (loading) return;
    const project = conversation.projects.find((item) => item.id === projectId);
    if (
      !window.confirm(
        `确定删除项目“${project?.title ?? ""}”及其全部会话吗？`
      )
    ) {
      return;
    }
    setConversation((current) => {
      const remaining = current.projects.filter((project) => project.id !== projectId);
      if (remaining.length === 0) {
        const project = makeProject("我的维K项目");
        return {
          projects: [project],
          activeProjectId: project.id,
          activeSessionId: project.sessions[0]?.id ?? null
        };
      }
      const nextProject = current.activeProjectId === projectId
        ? [...remaining].sort((left, right) => right.updatedAt - left.updatedAt)[0]
        : remaining.find((project) => project.id === current.activeProjectId) ??
          remaining[0];
      const activeSessionId =
        nextProject.id === current.activeProjectId
          ? current.activeSessionId
          : [...nextProject.sessions].sort(
              (left, right) => right.updatedAt - left.updatedAt
            )[0]?.id ?? null;
      return {
        projects: remaining,
        activeProjectId: nextProject.id,
        activeSessionId
      };
    });
    resetComposer();
  }

  function selectSession(sessionId: string) {
    if (loading) return;
    setConversation((current) => ({ ...current, activeSessionId: sessionId }));
    resetComposer();
  }

  function deleteSession(sessionId: string) {
    if (loading) return;
    const session = projectSessions.find((item) => item.id === sessionId);
    if (!window.confirm(`确定删除会话“${session?.title ?? ""}”吗？`)) {
      return;
    }
    setConversation((current) => {
      const activeProject = current.projects.find(
        (project) => project.id === current.activeProjectId
      );
      const sessions =
        activeProject?.sessions.filter((session) => session.id !== sessionId) ?? [];
      const activeSessionId =
        current.activeSessionId === sessionId
          ? [...sessions].sort(
              (left, right) => right.updatedAt - left.updatedAt
            )[0]?.id ?? null
          : current.activeSessionId;
      return {
        ...current,
        projects: current.projects.map((project) => {
          if (project.id !== current.activeProjectId) return project;
          return { ...project, sessions };
        }),
        activeSessionId
      };
    });
  }

  function startProjectRename(project: ConversationProject) {
    setEditingProjectId(project.id);
    setEditingProjectName(project.title);
  }

  function submitProjectRename(event: FormEvent) {
    event.preventDefault();
    const title = editingProjectName.trim();
    if (!title || !editingProjectId) return;
    setConversation((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === editingProjectId
          ? { ...project, title, updatedAt: Date.now() }
          : project
      )
    }));
    setEditingProjectId(null);
    setEditingProjectName("");
  }

  function startSessionRename(session: ConversationSession) {
    setEditingSessionId(session.id);
    setEditingSessionTitle(session.title);
  }

  function submitSessionRename(event: FormEvent) {
    event.preventDefault();
    const title = editingSessionTitle.trim();
    if (!title || !editingSessionId) return;
    setConversation((current) => ({
      ...current,
      projects: current.projects.map((project) => {
        if (project.id !== current.activeProjectId) return project;
        return {
          ...project,
          updatedAt: Date.now(),
          sessions: project.sessions.map((session) =>
            session.id === editingSessionId
              ? { ...session, title, updatedAt: Date.now() }
              : session
          )
        };
      })
    }));
    setEditingSessionId(null);
    setEditingSessionTitle("");
  }

  function updateMessages(
    sessionId: string,
    updater: (messages: Message[]) => Message[],
    titleSource?: string
  ) {
    setConversation((current) => ({
      ...current,
      projects: current.projects.map((project) => {
        if (!project.sessions.some((session) => session.id === sessionId)) {
          return project;
        }
        const timestamp = Date.now();
        return {
          ...project,
          updatedAt: timestamp,
          sessions: project.sessions.map((session) => {
            if (session.id !== sessionId) return session;
            return {
              ...session,
              title:
                session.messages.length === 0 && titleSource
                  ? sessionTitle(titleSource)
                  : session.title,
              updatedAt: timestamp,
              messages: updater(session.messages)
            };
          })
        };
      })
    }));
  }

  function appendThinkingStep(message: string) {
    if (!message || message === "正在检索知识图谱与证据") return;
    if (thinkingStepsRef.current.includes(message)) return;
    thinkingStepsRef.current = [...thinkingStepsRef.current, message];
    setThinkingSteps(thinkingStepsRef.current);
  }

  async function revealAnswer(sessionId: string, messageId: string, text: string) {
    const chunks = text.match(/[^。！？\n]+[。！？]?|\n+/g) ?? [text];
    let rendered = "";
    for (const chunk of chunks) {
      rendered += chunk;
      updateMessages(sessionId, (current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, text: rendered.trimStart() } : message
        )
      );
      if (chunk.trim()) {
        await new Promise((resolve) => window.setTimeout(resolve, 75));
      }
    }
    updateMessages(sessionId, (current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, streaming: false } : message
      )
    );
  }

  async function submit(query: string) {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    const targetSessionId = activeSession?.id ?? createSession();
    if (!targetSessionId) return;

    stickToBottomRef.current = true;
    const userMessage: Message = {
      id: makeMessageId(),
      role: "user",
      text: trimmed
    };
    updateMessages(targetSessionId, (current) => [...current, userMessage], trimmed);
    setInput("");
    setLoading(true);
    setStatus("正在准备检索");
    setThinkingSteps([]);
    thinkingStepsRef.current = [];

    try {
      await askQuestion(trimmed, targetSessionId, qaMode, {
        status: (message) => {
          setStatus(message);
          appendThinkingStep(message);
        },
        onAnswer: async (answer) => {
          const messageId = makeMessageId();
          const trace = [...thinkingStepsRef.current, "已完成来源核对并生成回答"];
          updateMessages(targetSessionId, (current) => [
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
          await revealAnswer(targetSessionId, messageId, answer.answer_text);
        }
      });
    } catch (error) {
      updateMessages(targetSessionId, (current) => [
        ...current,
        {
          id: makeMessageId(),
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

  function focusCitation(evidenceId: string) {
    setHighlightedCitationId(evidenceId);
    window.requestAnimationFrame(() => {
      document
        .getElementById(`citation-${evidenceId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    window.setTimeout(() => setHighlightedCitationId(null), 2200);
  }

  function openAnswerGraph(answer: Answer) {
    const handoff = createGraphPathHandoff(answer);
    if (!handoff) return;
    saveGraphPathHandoff(handoff);
    navigate("/graph?source=answer");
  }

  return (
    <div className="chat-layout">
      <aside className="conversation-sidebar">
        <div className="conversation-heading">
          <div>
            <span className="eyebrow">项目</span>
            <h2>项目空间</h2>
          </div>
          <MessageSquareText size={19} />
        </div>

        {isCreatingProject ? (
          <form className="project-create-form" onSubmit={submitProject}>
            <input
              autoFocus
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="输入项目名称"
              maxLength={40}
            />
            <button type="submit" disabled={!projectName.trim()} aria-label="创建项目">
              <CheckCircle2 size={15} />
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreatingProject(false);
                setProjectName("");
              }}
              aria-label="取消创建项目"
            >
              <X size={15} />
            </button>
          </form>
        ) : (
          <button
            type="button"
            className="new-project-button"
            onClick={() => setIsCreatingProject(true)}
            disabled={loading}
          >
            <FolderPlus size={16} />
            新建项目
          </button>
        )}

        <div className="project-list">
          {orderedProjects.map((project) => (
            <div
              className={`project-item ${
                project.id === conversation.activeProjectId ? "active" : ""
              }`}
              key={project.id}
            >
              {editingProjectId === project.id ? (
                <form className="inline-name-form" onSubmit={submitProjectRename}>
                  <input
                    autoFocus
                    value={editingProjectName}
                    onChange={(event) => setEditingProjectName(event.target.value)}
                    maxLength={40}
                    aria-label="项目名称"
                  />
                  <button
                    type="submit"
                    disabled={!editingProjectName.trim()}
                    aria-label="保存项目名称"
                  >
                    <CheckCircle2 size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingProjectId(null)}
                    aria-label="取消重命名项目"
                  >
                    <X size={14} />
                  </button>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    className="project-open"
                    onClick={() => selectProject(project.id)}
                    disabled={loading}
                  >
                    <FolderKanban size={16} />
                    <span>
                      <strong>{project.title}</strong>
                      <small>{project.sessions.length} 个会话</small>
                    </span>
                  </button>
                  <button
                    type="button"
                    className="project-edit"
                    onClick={() => startProjectRename(project)}
                    disabled={loading}
                    aria-label={`重命名项目：${project.title}`}
                    title="重命名项目"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    type="button"
                    className="project-delete"
                    onClick={() => deleteProject(project.id)}
                    disabled={loading}
                    aria-label={`删除项目：${project.title}`}
                    title="删除项目"
                  >
                    <Trash2 size={13} />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>

        <div className="session-section-heading">
          <div>
            <strong>项目会话</strong>
            <small>{activeProject?.title ?? "未选择项目"}</small>
          </div>
          <button
            type="button"
            className="new-session-button"
            onClick={createSession}
            disabled={loading}
            aria-label="新建会话"
            title="新建会话"
          >
            <Plus size={15} />
          </button>
        </div>
        <label className="session-search">
          <Search size={13} />
          <input
            value={sessionSearch}
            onChange={(event) => setSessionSearch(event.target.value)}
            placeholder="搜索当前项目会话"
            aria-label="搜索当前项目会话"
          />
        </label>
        <div className="session-list">
          {visibleSessions.length === 0 ? (
            <p className="session-empty">
              {sessionSearch.trim() ? "没有匹配的会话" : "暂无历史会话"}
            </p>
          ) : (
            visibleSessions.map((session) => (
              <div
                className={`session-item ${
                  session.id === conversation.activeSessionId ? "active" : ""
                }`}
                key={session.id}
              >
                {editingSessionId === session.id ? (
                  <form className="inline-name-form" onSubmit={submitSessionRename}>
                    <input
                      autoFocus
                      value={editingSessionTitle}
                      onChange={(event) => setEditingSessionTitle(event.target.value)}
                      maxLength={48}
                      aria-label="会话名称"
                    />
                    <button
                      type="submit"
                      disabled={!editingSessionTitle.trim()}
                      aria-label="保存会话名称"
                    >
                      <CheckCircle2 size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingSessionId(null)}
                      aria-label="取消重命名会话"
                    >
                      <X size={14} />
                    </button>
                  </form>
                ) : (
                  <>
                    <button
                      type="button"
                      className="session-open"
                      onClick={() => selectSession(session.id)}
                      disabled={loading}
                    >
                      <span className="session-copy">
                        <strong>{session.title}</strong>
                        <small>{previewMessage(session)}</small>
                        <time>{relativeSessionTime(session.updatedAt)}</time>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="session-edit"
                      onClick={() => startSessionRename(session)}
                      disabled={loading}
                      aria-label={`重命名会话：${session.title}`}
                      title="重命名会话"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      type="button"
                      className="session-delete"
                      onClick={() => deleteSession(session.id)}
                      disabled={loading}
                      aria-label={`删除会话：${session.title}`}
                      title="删除会话"
                    >
                      <Trash2 size={14} />
                    </button>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </aside>
      <section className="chat-workspace">
        <div className="page-heading chat-heading">
          <div>
            <span className="eyebrow">知识图谱检索</span>
            <h1>维K智问</h1>
            <p>
              仅使用外部公开证据；模型输出必须通过证据校验，失败时自动回退。
            </p>
          </div>
          <div className="knowledge-badge">
            <Sparkles size={17} />
            证据驱动
          </div>
        </div>

        <div
          ref={chatScrollRef}
          className="chat-scroll"
          aria-live="polite"
          aria-label="当前会话问答内容"
          tabIndex={0}
          onScroll={(event) => {
            const element = event.currentTarget;
            stickToBottomRef.current =
              element.scrollHeight - element.scrollTop - element.clientHeight < 72;
          }}
        >
          {messages.length === 0 ? (
            <div className="empty-chat">
              <div className="empty-mark">K</div>
              <h2>从一个具体问题开始</h2>
              <p>
                系统会先定位实体，再查询图谱路径和原始证据。知识库无法支持的问题会明确拒答。
              </p>
              <div className="suggestion-grid">
                {PUBLIC_SUGGESTIONS.map((suggestion) => (
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
              <button
                type="button"
                className="triage-start-button"
                onClick={() => void beginTriage()}
                disabled={triageLoading}
              >
                <ClipboardCheck size={17} />
                <span>
                  <strong>{triageLoading ? "正在准备" : "开始维生素K风险自查"}</strong>
                  <small>7 步结构化问答，不进行疾病诊断</small>
                </span>
                <ChevronRight size={17} />
              </button>
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
                        {!PUBLIC_BUILD && (
                          <span>{modeLabel(message.answer.mode ?? "domain")}</span>
                        )}
                        {message.answer.intent !== "capabilities" && (
                          <>
                            <span>{sufficiencyLabel(message.answer.sufficiency)}</span>
                            <span>{message.answer.data_version.version}</span>
                            <span>{message.answer.elapsed_ms} ms</span>
                            <span>{message.answer.citations.length} 条证据</span>
                          </>
                        )}
                        {message.answer.intent === "capabilities" && (
                          <span>功能范围说明</span>
                        )}
                        {message.answer.generation?.configured && (
                          <span
                            className={`generation-pill status-${message.answer.generation.status}`}
                            title={message.answer.generation.fallback_reason}
                          >
                            {generationLabel(message.answer.generation.status)}
                          </span>
                        )}
                      </div>
                    )}
                    {message.answer &&
                      message.id === latestAnswerMessageId &&
                      message.answer.claims.length > 0 && (
                        <details className="claim-evidence-panel" open>
                          <summary>
                            <span>结论级证据</span>
                            <small>{message.answer.claims.length} 条结论</small>
                          </summary>
                          <div className="claim-evidence-list">
                            {message.answer.claims.map((claim, index) => {
                              const profile = claimScienceProfile(claim);
                              return (
                                <article
                                  className={`claim-evidence-item claim-type-${profile.claimType}`}
                                  key={claim.id}
                                >
                                  <div className="claim-evidence-main">
                                    <span className="claim-index">{index + 1}</span>
                                    <p>{claim.text}</p>
                                  </div>
                                  <div className="claim-evidence-footer">
                                    <span className="claim-type-badge">
                                      {CLAIM_TYPE_LABELS[profile.claimType]}
                                    </span>
                                    <div className="claim-citation-list">
                                      {claim.evidence_ids.map((evidenceId) => {
                                        const citation = message.answer?.citations.find(
                                          (item) => item.id === evidenceId
                                        );
                                        return (
                                          <button
                                            type="button"
                                            key={evidenceId}
                                            className={
                                              highlightedCitationId === evidenceId
                                                ? "active"
                                                : ""
                                            }
                                            onClick={() => focusCitation(evidenceId)}
                                            title={citation?.source_title ?? evidenceId}
                                          >
                                            {citation?.source_id ?? "查看证据"}
                                          </button>
                                        );
                                      })}
                                    </div>
                                  </div>
                                  {profile.boundaryNote && (
                                    <p className="claim-boundary-note">
                                      {profile.boundaryNote}
                                    </p>
                                  )}
                                </article>
                              );
                            })}
                          </div>
                        </details>
                      )}
                    {message.answer &&
                      message.id === latestAnswerMessageId &&
                      (message.answer.comparisons?.length ?? 0) > 0 && (
                        <section className="evidence-comparison-panel">
                          <div className="evidence-comparison-heading">
                            <span>证据差异与适用条件</span>
                            <small>
                              {message.answer.comparisons?.length} 项
                            </small>
                          </div>
                          <div className="evidence-comparison-list">
                            {message.answer.comparisons?.map((comparison) => (
                              <article
                                className={`evidence-comparison-item status-${comparison.status}`}
                                key={comparison.id}
                              >
                                <span className="comparison-type">
                                  {COMPARISON_STATUS_LABELS[comparison.status] ??
                                    comparison.status}
                                </span>
                                <p>{comparison.summary}</p>
                                <div className="comparison-evidence-list">
                                  {comparison.evidence_ids.map((evidenceId) => {
                                    const citation =
                                      message.answer?.citations.find(
                                        (item) => item.id === evidenceId
                                      );
                                    return (
                                      <button
                                        type="button"
                                        key={evidenceId}
                                        onClick={() => focusCitation(evidenceId)}
                                      >
                                        {citation?.source_id ?? "查看证据"}
                                      </button>
                                    );
                                  })}
                                </div>
                              </article>
                            ))}
                          </div>
                        </section>
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
          {triage && (
            <TriagePanel
              session={triage}
              selection={triageSelection}
              loading={triageLoading}
              error={triageError}
              onToggle={toggleTriageOption}
              onNext={() => void advanceTriage("next")}
              onBack={() => void advanceTriage("back")}
              onRestart={() => void beginTriage()}
              onClose={closeTriage}
            />
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
        ) : activeAnswer.intent === "capabilities" ? (
          <div className="rail-empty">
            <Info size={32} />
            <p>这是系统的能力范围说明，不需要引用医学证据或图谱路径。</p>
          </div>
        ) : (
          <div className="rail-content">
            {activeAnswer.safety_notice && (
              <div className="safety-panel">
                <ShieldAlert size={18} />
                <p>{activeAnswer.safety_notice}</p>
              </div>
            )}

            {activeAnswer.generation?.configured && (
              <div className={`generation-panel status-${activeAnswer.generation.status}`}>
                <Sparkles size={16} />
                <div>
                  <strong>{generationLabel(activeAnswer.generation.status)}</strong>
                  <p>
                    {activeAnswer.generation.used
                      ? `${activeAnswer.generation.provider} / ${activeAnswer.generation.model}，`
                        + `${activeAnswer.generation.accepted_claim_count} 条 Claim 已通过证据核验。`
                      : activeAnswer.generation.fallback_reason
                        || "本次使用确定性证据回答。"}
                  </p>
                </div>
              </div>
            )}

            <div className="rail-section">
              <div className="rail-section-heading">
                <h3>图谱路径</h3>
                {(activeAnswer.graph_paths.length > 0 ||
                  activeAnswer.related_entities.length > 0) && (
                  <button
                    type="button"
                    className="graph-path-button"
                    onClick={() => openAnswerGraph(activeAnswer)}
                  >
                    <Network size={13} />
                    {activeAnswer.graph_paths.length > 0
                      ? "在图谱中查看"
                      : "查看相关实体"}
                  </button>
                )}
              </div>
              {activeAnswer.graph_paths.length === 0 ? (
                <p className="muted">
                  {activeAnswer.related_entities.length > 0
                    ? "本次回答没有多跳关系，可在图谱中查看识别到的相关实体。"
                    : "本次回答由证据片段直接组装，没有可展示的图谱路径。"}
                </p>
              ) : (
                activeAnswer.graph_paths.map((path, index) => (
                  <div className="path-block" key={`path-${index}`}>
                    <GitBranch size={16} />
                    <div>
                      {path.nodes.map((node, nodeIndex) => (
                        <span
                          className="path-step"
                          key={`${index}-${nodeIndex}-${node.id}`}
                        >
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
                  <article
                    className={`citation-card ${
                      highlightedCitationId === citation.id ? "highlighted" : ""
                    }`}
                    id={`citation-${citation.id}`}
                    key={citation.id}
                  >
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
                      {citation.test_family && (
                        <span className="review-pill">{citation.test_family}</span>
                      )}
                      {!PUBLIC_BUILD && citation.core_48 && (
                        <span className="core-pill">核心</span>
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
                        {citation.q_value && <span>Q={citation.q_value}</span>}
                        {citation.conflict_id && <span>冲突 {citation.conflict_id}</span>}
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

function TriagePanel({
  session,
  selection,
  loading,
  error,
  onToggle,
  onNext,
  onBack,
  onRestart,
  onClose
}: {
  session: TriageSession;
  selection: string[];
  loading: boolean;
  error: string;
  onToggle: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
  onRestart: () => void;
  onClose: () => void;
}) {
  const question = session.question;
  const outcome = session.outcome;
  return (
    <section className="triage-panel" aria-live="polite">
      <div className="triage-header">
        <div>
          <span className="eyebrow">结构化风险自查</span>
          <h2>维生素K补充风险自查</h2>
        </div>
        <button type="button" onClick={onClose} aria-label="关闭风险自查">
          <X size={16} />
        </button>
      </div>
      <div className="triage-progress">
        <span>
          {outcome
            ? "自查完成"
            : `第 ${session.progress.current} / ${session.progress.total} 步`}
        </span>
        <div aria-hidden="true">
          <i
            style={{
              width: `${Math.min(
                100,
                (session.progress.current / session.progress.total) * 100
              )}%`
            }}
          />
        </div>
      </div>

      {question ? (
        <>
          <h3>{question.prompt}</h3>
          {question.help_text && <p className="triage-help">{question.help_text}</p>}
          <div className="triage-options">
            {question.options.map((option) => (
              <button
                type="button"
                key={option.value}
                className={selection.includes(option.value) ? "selected" : ""}
                aria-pressed={selection.includes(option.value)}
                onClick={() => onToggle(option.value)}
                disabled={loading}
              >
                <span className="triage-check">
                  {selection.includes(option.value) && <CheckCircle2 size={14} />}
                </span>
                <span>
                  <strong>{option.label}</strong>
                  {option.description && <small>{option.description}</small>}
                </span>
              </button>
            ))}
          </div>
          <div className="triage-actions">
            <button
              type="button"
              className="secondary"
              onClick={onBack}
              disabled={loading || session.progress.current <= 1}
            >
              <ChevronLeft size={15} />
              上一步
            </button>
            <button
              type="button"
              onClick={onNext}
              disabled={loading || selection.length === 0}
            >
              {loading ? <LoaderCircle size={15} className="spin" /> : null}
              {session.progress.current === session.progress.total
                ? "查看自查结果"
                : "下一步"}
              <ChevronRight size={15} />
            </button>
          </div>
        </>
      ) : (
        outcome && (
          <div className={`triage-outcome level-${outcome.level}`}>
            <div className="triage-outcome-heading">
              <ShieldAlert size={20} />
              <div>
                <span>
                  {
                    {
                      emergency: "需要优先处理",
                      professional_review: "建议专业评估",
                      insufficient_information: "信息不足"
                    }[outcome.level]
                  }
                </span>
                <h3>{outcome.title}</h3>
              </div>
            </div>
            <p>{outcome.summary}</p>
            <ul>
              {outcome.recommendations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="triage-cannot-conclude">{outcome.cannot_conclude}</div>
            {outcome.citations.length > 0 && (
              <details className="triage-evidence">
                <summary>查看相关公开证据</summary>
                {outcome.citations.map((citation) => (
                  <article key={citation.id}>
                    <strong>{citation.source_title}</strong>
                    <p>{citation.snippet}</p>
                    <small>{citation.source_locator || citation.locator}</small>
                    {citation.url && (
                      <a href={citation.url} target="_blank" rel="noreferrer">
                        查看来源 <ExternalLink size={13} />
                      </a>
                    )}
                  </article>
                ))}
              </details>
            )}
            <div className="triage-actions">
              <button type="button" className="secondary" onClick={onRestart}>
                <RotateCcw size={15} />
                重新自查
              </button>
              <button type="button" onClick={onClose}>
                返回问答
              </button>
            </div>
          </div>
        )
      )}
      {error && <div className="triage-error">{error}</div>}
    </section>
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
    negative_evidence: "阴性证据",
    comparison: "关系比较",
    definition: "知识介绍",
    emergency: "紧急安全",
    medication: "用药安全",
    diagnosis: "诊断边界",
    no_evidence: "无证据拒答",
    general: "图谱检索",
    capabilities: "能力说明"
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

function modeLabel(value: QAMode) {
  return {
    domain: "领域模式",
    research: "研究模式",
    comparison: "对照模式"
  }[value];
}

function generationLabel(status: string) {
  return {
    generated: "大模型证据改写",
    fallback: "已回退确定性回答",
    not_attempted: "确定性证据回答",
    disabled: "未启用运行时模型"
  }[status] ?? status;
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
