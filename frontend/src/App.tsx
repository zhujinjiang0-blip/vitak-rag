import { useQuery } from "@tanstack/react-query";
import {
  BookOpenText,
  Database,
  GitFork,
  LayoutDashboard,
  MessageSquareText,
  UploadCloud
} from "lucide-react";
import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getHealth } from "./lib/api";
import { STATIC_DEMO_MODE } from "./lib/staticDemo";
import ChatPage from "./pages/ChatPage";
import EvidencePage from "./pages/EvidencePage";
import ImportPage from "./pages/ImportPage";
import OverviewPage from "./pages/OverviewPage";

const GraphPage = lazy(() => import("./pages/GraphPage"));

function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });

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
          <NavLink to="/overview">
            <LayoutDashboard size={18} />
            <span>项目概览</span>
          </NavLink>
          <NavLink to="/chat">
            <MessageSquareText size={18} />
            <span>智能问答</span>
          </NavLink>
          <NavLink to="/graph">
            <GitFork size={18} />
            <span>知识图谱</span>
          </NavLink>
          <NavLink to="/evidence">
            <BookOpenText size={18} />
            <span>证据检索</span>
          </NavLink>
          <NavLink to="/import">
            <UploadCloud size={18} />
            <span>数据入口</span>
          </NavLink>
        </nav>

        <div className="topbar-status">
          <span className={`status-dot ${health.isError ? "error" : ""}`} />
          <div>
            <strong>
              {health.isError
                ? "知识库加载失败"
                : STATIC_DEMO_MODE
                  ? "在线真实证据"
                  : "本地知识库"}
            </strong>
            <small>
              {health.data
                ? `${health.data.data_version.version} · ${health.data.data_version.entity_count} 实体`
                : "连接中"}
            </small>
          </div>
          <Database size={18} />
        </div>
      </header>

      <main className="page-shell">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route
            path="/graph"
            element={
              <Suspense fallback={<p className="route-loading">正在加载知识图谱...</p>}>
                <GraphPage />
              </Suspense>
            }
          />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
