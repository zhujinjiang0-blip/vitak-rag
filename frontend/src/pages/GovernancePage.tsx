import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  DatabaseZap,
  GitCompareArrows,
  History,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  XCircle
} from "lucide-react";
import { useState } from "react";
import {
  activateSnapshot,
  getActiveSnapshotAudit,
  getAuditLogs,
  getReviewItems,
  getSnapshotAudit,
  getSnapshotDiff,
  getSnapshots,
  getUnmetNeeds
} from "../lib/api";
import { useAuth } from "../lib/auth";
import type { GovernanceCheck, SnapshotAudit } from "../lib/types";

function GovernancePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedVersion, setSelectedVersion] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const active = useQuery({
    queryKey: ["governance-active"],
    queryFn: getActiveSnapshotAudit
  });
  const snapshots = useQuery({
    queryKey: ["governance-snapshots"],
    queryFn: getSnapshots
  });
  const version = selectedVersion || active.data?.version || "";
  const audit = useQuery({
    queryKey: ["governance-audit", version],
    queryFn: () => getSnapshotAudit(version),
    enabled: Boolean(version)
  });
  const diff = useQuery({
    queryKey: ["governance-diff", active.data?.version, version],
    queryFn: () => getSnapshotDiff(active.data?.version ?? "", version),
    enabled: Boolean(active.data?.version && version && active.data.version !== version)
  });
  const review = useQuery({
    queryKey: ["governance-review"],
    queryFn: getReviewItems
  });
  const unmet = useQuery({
    queryKey: ["governance-unmet"],
    queryFn: getUnmetNeeds
  });
  const logs = useQuery({
    queryKey: ["governance-logs"],
    queryFn: getAuditLogs
  });
  const activate = useMutation({
    mutationFn: activateSnapshot,
    onSuccess: async (result) => {
      setActionMessage(
        result.status === "already-active"
          ? `${result.version} 已是活动快照`
          : `已切换到快照 ${result.version}`
      );
      await queryClient.invalidateQueries();
    },
    onError: (error) => {
      setActionMessage(error instanceof Error ? error.message : "快照切换失败");
    }
  });

  if (!user || user.role !== "admin") {
    return (
      <div className="governance-page">
        <section className="page-heading">
          <div>
            <span className="eyebrow">管理员入口</span>
            <h1>需要数据治理权限</h1>
            <p>快照审计、版本差异、审核队列和未满足需求只对本地管理员开放。</p>
          </div>
          <ShieldAlert size={34} />
        </section>
      </div>
    );
  }

  const currentAudit = audit.data ?? active.data;
  return (
    <div className="governance-page">
      <section className="page-heading governance-heading">
        <div>
          <span className="eyebrow">T01 数据治理 · 管理员环境</span>
          <h1>数据版本与质量审计</h1>
          <p>
            对照输入文件、入库计数和索引结果。审核匹配、科学语义和发布决定保留人工签认，
            系统不自动改写研究结论。
          </p>
        </div>
        <div className="governance-active-badge">
          <ShieldCheck size={17} />
          活动版本 {active.data?.version ?? "加载中"}
        </div>
      </section>

      <section className="governance-toolbar">
        <label>
          <span>查看快照</span>
          <select
            value={version}
            onChange={(event) => setSelectedVersion(event.target.value)}
          >
            {snapshots.data?.items.map((item) => (
              <option key={item.version} value={item.version}>
                {item.version}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="secondary-action"
          disabled={
            !currentAudit ||
            currentAudit.active ||
            activate.isPending ||
            !version
          }
          onClick={() => {
            const confirmed = window.confirm(
              `确认将活动知识库切换到 ${version}？切换会立即影响在线问答。`
            );
            if (confirmed) activate.mutate(version);
          }}
        >
          <RotateCcw size={16} />
          切换或回滚到该版本
        </button>
        {actionMessage && <span className="governance-action-status">{actionMessage}</span>}
      </section>

      {audit.isLoading || active.isLoading ? (
        <div className="governance-loading">正在读取快照审计信息...</div>
      ) : audit.isError || active.isError ? (
        <div className="error-banner">治理数据加载失败，请确认管理员会话和服务端快照可用。</div>
      ) : currentAudit ? (
        <>
          <SnapshotSummary audit={currentAudit} />
          <section className="governance-checks">
            <div className="governance-section-heading">
              <div>
                <span className="eyebrow">自动检查</span>
                <h2>质量与权限门槛</h2>
              </div>
              <span>{currentAudit.checks.length} 项</span>
            </div>
            <div className="governance-check-list">
              {currentAudit.checks.map((check) => (
                <CheckRow check={check} key={check.key} />
              ))}
            </div>
          </section>

          <section className="governance-columns">
            <DistributionPanel
              title="来源与权限"
              groups={[
                ["来源类型", currentAudit.source_types],
                ["数据域", currentAudit.origins],
                ["访问范围", currentAudit.access_scopes]
              ]}
            />
            <DistributionPanel
              title="审核与结果状态"
              groups={[
                ["审核状态", currentAudit.review_statuses],
                ["研究结果", currentAudit.evidence_statuses]
              ]}
            />
          </section>

          <section className="governance-inputs">
            <div className="governance-section-heading">
              <div>
                <span className="eyebrow">数据清单</span>
                <h2>内部输入文件</h2>
              </div>
              <span>{currentAudit.input_files.length} 个输入</span>
            </div>
            <div className="governance-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>文件</th>
                    <th>记录数</th>
                    <th>SHA-256</th>
                  </tr>
                </thead>
                <tbody>
                  {currentAudit.input_files.map((file) => (
                    <tr key={`${file.name}-${file.sha256}`}>
                      <td>{file.name}</td>
                      <td>{file.rows}</td>
                      <td className="governance-hash">{file.sha256 || "未记录"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {active.data?.version && version !== active.data.version && (
            <section className="governance-diff">
              <div className="governance-section-heading">
                <div>
                  <span className="eyebrow">版本差异</span>
                  <h2>
                    {active.data.version} → {version}
                  </h2>
                </div>
                <GitCompareArrows size={20} />
              </div>
              {diff.isError ? (
                <p className="governance-muted">版本差异读取失败。</p>
              ) : (
                <div className="governance-diff-grid">
                  <DeltaList title="记录计数" values={diff.data?.count_deltas ?? {}} />
                  {Object.entries(diff.data?.distribution_deltas ?? {}).map(
                    ([title, values]) => (
                      <DeltaList key={title} title={statusLabel(title)} values={values} />
                    )
                  )}
                  <DeltaList
                    title="输入文件"
                    values={{
                      新增: diff.data?.added_input_files.length ?? 0,
                      移除: diff.data?.removed_input_files.length ?? 0
                    }}
                  />
                </div>
              )}
            </section>
          )}
        </>
      ) : null}

      <section className="governance-queue-grid">
        <QueuePanel
          title="异常审核队列"
          count={review.data?.items.length ?? 0}
          empty="当前没有待审核候选关系。"
        >
          {review.data?.items.slice(0, 12).map((item) => (
            <div className="governance-queue-row" key={item.id}>
              <span>{item.candidate_type}</span>
              <strong>{item.id}</strong>
              <small>{new Date(item.created_at).toLocaleString("zh-CN")}</small>
            </div>
          ))}
        </QueuePanel>
        <QueuePanel
          title="未满足科研需求"
          count={unmet.data?.total ?? 0}
          empty="当前没有自动记录的未满足需求。"
        >
          {unmet.data?.items.slice(0, 12).map((item) => (
            <div className="governance-queue-row" key={item.id}>
              <span>{reasonLabel(item.reason)}</span>
              <strong>{item.query}</strong>
              <small>
                {item.mode} · {item.data_version} ·{" "}
                {new Date(item.created_at).toLocaleString("zh-CN")}
              </small>
            </div>
          ))}
        </QueuePanel>
      </section>

      <section className="governance-logs">
        <div className="governance-section-heading">
          <div>
            <span className="eyebrow">访问审计</span>
            <h2>管理员操作记录</h2>
          </div>
          <History size={20} />
        </div>
        <div className="governance-log-list">
          {logs.data?.items.slice(0, 20).map((item) => (
            <div key={item.id}>
              <strong>{item.action}</strong>
              <span>{item.target || "全局"}</span>
              <small>{new Date(item.created_at).toLocaleString("zh-CN")}</small>
            </div>
          ))}
          {!logs.data?.items.length && (
            <p className="governance-muted">暂无管理员操作记录。</p>
          )}
        </div>
      </section>
    </div>
  );
}

function SnapshotSummary({ audit }: { audit: SnapshotAudit }) {
  const counts = [
    ["证据记录", audit.counts.evidence],
    ["图谱关系", audit.counts.edges],
    ["实体", audit.counts.nodes],
    ["来源", audit.counts.sources]
  ] as const;
  return (
    <section className="governance-summary">
      <div>
        <span className="eyebrow">当前选择</span>
        <h2>{audit.version}</h2>
        <p>
          {audit.is_demo ? "演示快照" : "真实数据快照"}
          {audit.created_at
            ? ` · ${new Date(audit.created_at).toLocaleString("zh-CN")}`
            : ""}
        </p>
      </div>
      <div className="governance-counts">
        {counts.map(([label, value]) => (
          <span key={label}>
            <small>{label}</small>
            <strong>{value?.toLocaleString() ?? "—"}</strong>
          </span>
        ))}
      </div>
      <div className="governance-summary-state">
        {audit.active ? <CheckCircle2 size={18} /> : <DatabaseZap size={18} />}
        {audit.active ? "当前活动版本" : "非活动版本"}
      </div>
    </section>
  );
}

function CheckRow({ check }: { check: GovernanceCheck }) {
  const icon =
    check.status === "pass" ? (
      <CheckCircle2 size={18} />
    ) : check.status === "fail" ? (
      <XCircle size={18} />
    ) : (
      <AlertTriangle size={18} />
    );
  return (
    <article className={`governance-check status-${check.status}`}>
      {icon}
      <div>
        <span>{check.label}</span>
        <p>{check.detail}</p>
      </div>
      <strong>{check.value}</strong>
    </article>
  );
}

function DistributionPanel({
  title,
  groups
}: {
  title: string;
  groups: Array<[string, Record<string, number>]>;
}) {
  return (
    <article className="governance-distribution-panel">
      <h3>{title}</h3>
      {groups.map(([label, values]) => (
        <div key={label}>
          <span>{label}</span>
          <div>
            {Object.entries(values).map(([key, value]) => (
              <span key={key}>
                {statusLabel(key)}
                <strong>{value}</strong>
              </span>
            ))}
          </div>
        </div>
      ))}
    </article>
  );
}

function DeltaList({
  title,
  values
}: {
  title: string;
  values: Record<string, number>;
}) {
  return (
    <article>
      <h3>{title}</h3>
      {Object.entries(values).map(([key, value]) => (
        <div key={key}>
          <span>{statusLabel(key)}</span>
          <strong className={value > 0 ? "delta-positive" : value < 0 ? "delta-negative" : ""}>
            {value > 0 ? `+${value}` : value}
          </strong>
        </div>
      ))}
      {!Object.keys(values).length && <p>无变化</p>}
    </article>
  );
}

function QueuePanel({
  title,
  count,
  empty,
  children
}: {
  title: string;
  count: number;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <section className="governance-queue-panel">
      <div className="governance-section-heading">
        <h2>{title}</h2>
        <span>{count} 条</span>
      </div>
      <div>{children}</div>
      {!count && <p className="governance-muted">{empty}</p>}
    </section>
  );
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    internal: "内部数据",
    external: "外部数据",
    public: "公开",
    private: "私有",
    controlled: "受控",
    literature: "科学文献",
    structured: "结构化知识",
    synthetic: "演示数据",
    source_types: "来源类型",
    review_statuses: "审核状态",
    evidence_statuses: "结果状态",
    origins: "数据域",
    input_statuses: "输入状态",
    fusion_statuses: "融合状态",
    answer_eligible: "可正式回答",
    answer_ineligible: "仅研究检索"
  };
  return labels[value] ?? value;
}

function reasonLabel(reason: string) {
  const labels: Record<string, string> = {
    evidence_insufficient: "证据不足",
    partial_evidence: "部分可答",
    retrieval_error: "检索问题",
    expression_gap: "表达问题",
    feature_gap: "功能问题"
  };
  return labels[reason] ?? reason;
}

export default GovernancePage;
