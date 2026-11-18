import { ChangeEvent, FormEvent, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  DatabaseZap,
  FileSpreadsheet,
  LockKeyhole,
  Upload
} from "lucide-react";
import DataSourceLegend from "../components/DataSourceLegend";
import { uploadExternalTriples, uploadInternalCsv } from "../lib/api";
import { STATIC_DEMO_MODE } from "../lib/staticDemo";

function ImportPage() {
  const [mode, setMode] = useState<"external" | "internal">("external");
  const [file, setFile] = useState<File | null>(null);
  const [activate, setActivate] = useState(false);
  const [token, setToken] = useState("change-me-in-local-development");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setMessage("");
    setError("");
  }

  function switchMode(nextMode: "external" | "internal") {
    setMode(nextMode);
    setMessage("");
    setError("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || loading) return;
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const result =
        mode === "external"
          ? await uploadExternalTriples(file, activate, token)
          : await uploadInternalCsv(file, activate, token);
      setMessage(
        `导入完成：快照 ${result.version ?? result.snapshot_version}，` +
          `${result.rows ?? result.chunks ?? 0} 条数据，` +
          `${result.graph_edges ?? result.edges_added ?? result.candidates ?? 0} 条图谱关系或候选关系，` +
          `${result.nodes ?? 0} 个实体。`
      );
      setFile(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "导入失败");
    } finally {
      setLoading(false);
    }
  }

  if (STATIC_DEMO_MODE) {
    return (
      <div className="import-page">
        <section className="page-heading">
          <div>
            <span className="eyebrow">数据入口</span>
            <h1>知识库导入</h1>
            <p>上传功能需要本地 FastAPI 后端，在线 GitHub Pages 版本为只读演示。</p>
          </div>
          <DatabaseZap size={34} />
        </section>
        <div className="import-static-notice">
          <LockKeyhole size={28} />
          <h2>在线演示不接收文件</h2>
          <p>
            请在项目目录运行 <code>make api</code> 和 <code>make web</code>，
            然后访问本机 <code>http://127.0.0.1:5173/#/import</code> 上传 CSV。
          </p>
        </div>
        <DataSourceLegend />
      </div>
    );
  }

  return (
    <div className="import-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">数据入口</span>
          <h1>42 列证据表导入</h1>
          <p>按每行的 source_type 自动标记内外部来源，并写入版本化证据快照。</p>
        </div>
        <DatabaseZap size={34} />
      </section>

      <DataSourceLegend />

      <form className="import-form" onSubmit={submit}>
        <div className="import-mode" role="group" aria-label="数据来源">
          <button
            type="button"
            className={mode === "external" ? "active" : ""}
            onClick={() => switchMode("external")}
          >
            <span className="origin-pill external">外部数据</span>
            <small>literature / structured · 42 列</small>
          </button>
          <button
            type="button"
            className={mode === "internal" ? "active" : ""}
            onClick={() => switchMode("internal")}
          >
            <span className="origin-pill internal">内部数据</span>
            <small>internal · private · 42 列</small>
          </button>
        </div>

        <label className="file-drop">
          <FileSpreadsheet size={30} />
          <strong>{file ? file.name : "选择 CSV 文件"}</strong>
          <span>支持 UTF-8 编码的 42 列统一三元组表，原始文件仅用于本次本地导入。</span>
          <input type="file" accept=".csv,text/csv" onChange={selectFile} />
        </label>

        <div className="import-classification-note">
          <LockKeyhole size={17} />
          <p>
            <strong>来源自动标注：</strong>
            `internal` 映射为内部/私有；`literature` 与 `structured` 映射为外部/公开。
            三张表可分别导入，也可在本地使用 `import-evidence-tables` 一次批量导入。
          </p>
        </div>

        <div className="import-fields">
          <label>
            <span>内部接口令牌</span>
            <input
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
        </div>

        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={activate}
            onChange={(event) => setActivate(event.target.checked)}
          />
          <span>导入完成后立即激活新快照</span>
        </label>

        <button className="primary-action" type="submit" disabled={!file || loading}>
          <Upload size={18} />
          {loading ? "正在导入" : "开始导入"}
        </button>
      </form>

      {message && (
        <div className="import-result success">
          <CheckCircle2 size={20} />
          <span>{message}</span>
        </div>
      )}
      {error && (
        <div className="import-result error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}

export default ImportPage;
