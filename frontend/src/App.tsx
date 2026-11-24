import { useQuery } from "@tanstack/react-query";
import {
  BookOpenText,
  Database,
  GitFork,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageSquareText,
  Microscope,
  ShieldCheck,
  UploadCloud
} from "lucide-react";
import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getHealth } from "./lib/api";
import { useAuth } from "./lib/auth";
import { STATIC_DEMO_MODE } from "./lib/staticDemo";
import ChatPage from "./pages/ChatPage";
import EvidencePage from "./pages/EvidencePage";
import GovernancePage from "./pages/GovernancePage";
import ImportPage from "./pages/ImportPage";
import OverviewPage from "./pages/OverviewPage";
import LoginPage from "./pages/LoginPage";
import ResearchPage from "./pages/ResearchPage";

const GraphPage = lazy(() => import("./pages/GraphPage"));

function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const { user, signOut, loading } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">K</div>
          <div>
            <div className="brand-name">维K智问</div>
            <div className="brand-subtitle">VitaK-RAG</div>
          </div>
        </div>

        <nav className="main-nav" aria-label="主导航">
          <NavLink to="/chat">
            <MessageSquareText size={18} />
            <span>智能问答</span>
          </NavLink>
          <NavLink to="/overview">
            <LayoutDashboard size={18} />
            <span>项目概览</span>
          </NavLink>
          <NavLink to="/graph">
            <GitFork size={18} />
            <span>知识图谱</span>
          </NavLink>
          <NavLink to="/evidence">
            <BookOpenText size={18} />
            <span>证据检索</span>
          </NavLink>
          {user && (
            <NavLink to="/research">
              <Microscope size={18} />
              <span>内部研究</span>
            </NavLink>
          )}
          {user?.role === "admin" && (
            <>
              <NavLink to="/governance">
                <ShieldCheck size={18} />
                <span>数据治理</span>
              </NavLink>
              <NavLink to="/import">
                <UploadCloud size={18} />
                <span>数据入口</span>
              </NavLink>
            </>
          )}
        </nav>

        <div className="topbar-status">
          <span className={`status-dot ${health.isError ? "error" : ""}`} />
          <div>
            <strong>
              {health.isError
                ? "知识库加载失败"
                : STATIC_DEMO_MODE
                  ? "在线真实证据"
                  : health.data?.runtime_llm
                    ? "证据约束生成"
                    : "确定性知识库"}
            </strong>
            <small>
              {health.data
                ? `${health.data.data_version.version} · ${
                    health.data.runtime_llm
                      ? `${health.data.llm_provider}/${health.data.llm_model}`
                      : "运行时模型未启用"
                  }`
                : "连接中"}
            </small>
          </div>
          <Database size={18} />
          {!STATIC_DEMO_MODE && (
            loading ? (
              <span className="account-loading">会话校验中</span>
            ) : user ? (
              <button
                type="button"
                className="account-button"
                onClick={() => void signOut()}
                title="退出研究会话"
              >
                <LogOut size={15} />
                <span>{user.display_name}</span>
              </button>
            ) : (
              <NavLink className="account-button" to="/login">
                <LogIn size={15} />
                <span>登录</span>
              </NavLink>
            )
          )}
        </div>
      </header>

      <main className="page-shell">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/graph"
            element={
              <Suspense fallback={<p className="route-loading">正在加载知识图谱...</p>}>
                <GraphPage />
              </Suspense>
            }
          />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route
            path="/research"
            element={user ? <ResearchPage /> : <Navigate to="/login" replace />}
          />
          <Route
            path="/governance"
            element={
              user?.role === "admin" ? <GovernancePage /> : <Navigate to="/login" replace />
            }
          />
          <Route path="/import" element={<ImportPage />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
