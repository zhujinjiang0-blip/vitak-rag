import { FormEvent, useState } from "react";
import { KeyRound, LockKeyhole, LogIn, ShieldCheck } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { STATIC_DEMO_MODE } from "../lib/staticDemo";

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading, signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (STATIC_DEMO_MODE) return <Navigate to="/overview" replace />;
  if (!loading && user) {
    return <Navigate to={location.state?.from ?? "/overview"} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await signIn(username.trim(), password);
      navigate(location.state?.from ?? "/research", { replace: true });
    } catch {
      setError("用户名或密码错误，或账号已停用。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-intro">
        <span className="eyebrow">受控研究环境</span>
        <h1>内部证据只在授权会话中打开</h1>
        <p>
          领域知识模式保持公开；内部 248 条队列证据、研究筛选和内外对照
          需要研究员账号访问。
        </p>
        <div className="login-boundaries">
          <div>
            <LockKeyhole size={18} />
            <span>HttpOnly 会话</span>
          </div>
          <div>
            <ShieldCheck size={18} />
            <span>服务端权限过滤</span>
          </div>
          <div>
            <KeyRound size={18} />
            <span>账号可撤销</span>
          </div>
        </div>
      </section>

      <form className="login-form" onSubmit={submit}>
        <div className="login-form-heading">
          <span className="eyebrow">研究员登录</span>
          <h2>进入研究模式</h2>
        </div>
        <label>
          <span>用户名</span>
          <input
            autoFocus
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label>
          <span>密码</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <div className="login-error">{error}</div>}
        <button
          type="submit"
          className="primary-action"
          disabled={!username.trim() || !password || submitting}
        >
          <LogIn size={17} />
          {submitting ? "正在验证" : "登录"}
        </button>
        <p className="login-help">
          首次使用请在本地执行
          <code>vitak auth-init-admin &lt;用户名&gt; &lt;密码&gt;</code>
          创建管理员账号。
        </p>
      </form>
    </div>
  );
}

export default LoginPage;
