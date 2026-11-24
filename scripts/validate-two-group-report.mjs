import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const reportPath = resolve(
  process.env.VITAK_TWO_GROUP_REPORT ||
    "data/eval/report-two-group-2026-11-25.json"
);
const report = JSON.parse(await readFile(reportPath, "utf8"));
const manifestPath = resolve(
  process.env.VITAK_TWO_GROUP_MANIFEST ||
    reportPath.replace(/\.json$/, ".manifest.json")
);
const baselinePath = process.env.VITAK_TWO_GROUP_BASELINE
  ? resolve(process.env.VITAK_TWO_GROUP_BASELINE)
  : "";
const errors = [];
const groups = ["plain_rag", "kg_hybrid"];
const metricKeys = [
  "recall_at_5",
  "mrr_at_10",
  "ndcg_at_10",
  "citation_accuracy",
  "path_hit_rate",
  "retrieval_evaluable_count",
  "path_evaluable_count",
  "p95_ms"
];

if (report.experiment !== "plain_rag_vs_kg_hybrid") {
  errors.push("experiment 必须为 plain_rag_vs_kg_hybrid");
}
if (report.question_count !== report.results?.length) {
  errors.push("question_count 与 results 数量不一致");
}
if (new Set(Object.keys(report.summary || {})).size !== 2) {
  errors.push("summary 只能包含两个检索组");
}
for (const group of groups) {
  if (!report.summary?.[group]) {
    errors.push(`summary 缺少 ${group}`);
    continue;
  }
  for (const key of metricKeys) {
    if (!(key in report.summary[group])) {
      errors.push(`summary.${group} 缺少 ${key}`);
    }
  }
}
const oldModes = ["vector", "graph", "hybrid"].filter(
  (mode) => mode in (report.summary || {})
);
if (oldModes.length) {
  errors.push(`报告混入旧组：${oldModes.join(", ")}`);
}
for (const result of report.results || []) {
  for (const group of groups) {
    if (!result[group]) errors.push(`${result.id} 缺少 ${group}`);
  }
  if (!Array.isArray(result.expected_path_evidence_ids)) {
    errors.push(`${result.id} 缺少 expected_path_evidence_ids`);
  }
}
if (report.summary?.plain_rag?.path_hit_rate !== null) {
  errors.push("普通 RAG 无显式路径，path_hit_rate 必须为 null");
}
if (report.summary?.plain_rag?.path_evaluable_count !== 0) {
  errors.push("普通 RAG 的 path_evaluable_count 必须为 0");
}

let manifest = null;
try {
  manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const reportBytes = await readFile(reportPath);
  const reportSha256 = createHash("sha256").update(reportBytes).digest("hex");
  if (manifest.report?.sha256 !== reportSha256) {
    errors.push("manifest 中的报告 SHA-256 与报告文件不一致");
  }
  if (!report.reproducibility?.generation_command) {
    errors.push("报告缺少生成命令");
  }
  const ordering = report.reproducibility?.stable_ordering || {};
  for (const key of [
    "question_order",
    "keyword",
    "semantic",
    "fusion",
    "kg_keyword",
    "kg_phrase"
  ]) {
    if (!ordering[key]) errors.push(`稳定排序缺少 ${key}`);
  }
} catch (error) {
  errors.push(`报告清单不可读取：${error.message}`);
}

let reproducible = null;
const differences = [];
if (baselinePath) {
  const baseline = JSON.parse(await readFile(baselinePath, "utf8"));
  const canonical = (value) => {
    const summary = Object.fromEntries(
      groups.map((group) => {
        const metrics = { ...(value.summary?.[group] || {}) };
        delete metrics.p95_ms;
        return [group, metrics];
      })
    );
    const results = (value.results || []).map((result) => {
      const normalized = {
        id: result.id,
        expect_no_evidence: result.expect_no_evidence,
        expected: result.expected,
        expected_path_evidence_ids: result.expected_path_evidence_ids
      };
      for (const group of groups) {
        const score = { ...(result[group] || {}) };
        delete score.elapsed_ms;
        normalized[group] = score;
      }
      return normalized;
    });
    return { summary, results };
  };
  const current = canonical(report);
  const previous = canonical(baseline);
  if (JSON.stringify(current) !== JSON.stringify(previous)) {
    differences.push("除时间与耗时字段外，两次运行的汇总或逐题评分不一致");
  }
  reproducible = differences.length === 0;
}

const output = {
  report: reportPath,
  manifest: manifestPath,
  experiment: report.experiment,
  data_version: report.data_version,
  question_count: report.question_count,
  summary: report.summary,
  ...(baselinePath ? { baseline: baselinePath, reproducible, differences } : {}),
  valid: errors.length === 0,
  errors
};
console.log(JSON.stringify(output, null, 2));
if (errors.length) process.exitCode = 1;
