import { readdir, readFile } from "node:fs/promises";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const publicRoot = join(root, "frontend", "public");
const distRoot = join(root, "frontend", "dist");
const evidencePath = join(publicRoot, "real-evidence.json");
const overviewPath = join(publicRoot, "project-overview.json");

const forbiddenPatterns = [
  ["internal API path", /\/internal\/v1/gi],
  ["research API path", /\/api\/v1\/research/gi],
  ["authentication API path", /\/api\/v1\/auth/gi],
  ["private label", /internal\/private/gi],
  ["internal evidence class", /internal_rct_evidence/gi],
  ["internal record field", /internal_records/gi],
  ["internal source id", /INT-SRC-[A-Za-z0-9]+/g],
  ["internal edge id", /INT_[a-f0-9]{16}/gi],
  ["internal ledger status", /(?:accepted_internal_ledger|conflict_retained_internal)/gi]
];

async function walk(path) {
  const entries = await readdir(path, { withFileTypes: true });
  const output = [];
  for (const entry of entries) {
    const target = join(path, entry.name);
    if (entry.isDirectory()) output.push(...await walk(target));
    else if (entry.isFile()) output.push(target);
  }
  return output;
}

function scanText(text) {
  const matches = [];
  for (const [label, pattern] of forbiddenPatterns) {
    pattern.lastIndex = 0;
    const count = [...text.matchAll(pattern)].length;
    if (count > 0) matches.push({ label, count });
  }
  return matches;
}

function assertNoInternalKeys(value, path = "$") {
  const errors = [];
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      errors.push(...assertNoInternalKeys(item, `${path}[${index}]`))
    );
    return errors;
  }
  if (!value || typeof value !== "object") return errors;
  for (const [key, child] of Object.entries(value)) {
    if (/^internal(?:_|$)/i.test(key) || key.toLowerCase() === "internal") {
      errors.push(`${path}.${key}`);
    }
    errors.push(...assertNoInternalKeys(child, `${path}.${key}`));
  }
  return errors;
}

const errors = [];
const [evidenceRaw, overviewRaw] = await Promise.all([
  readFile(evidencePath, "utf8"),
  readFile(overviewPath, "utf8")
]);
const evidence = JSON.parse(evidenceRaw);
const overview = JSON.parse(overviewRaw);

for (const item of evidence.evidence) {
  if (!["external", "public"].includes(item.data_origin)) {
    errors.push(`公开证据包含非公开来源：${item.id} (${item.data_origin})`);
  }
  if (item.access_scope !== "public") {
    errors.push(`公开证据包含非公开访问范围：${item.id} (${item.access_scope})`);
  }
}

const internalKeys = [
  ...assertNoInternalKeys(evidence, "real-evidence"),
  ...assertNoInternalKeys(overview, "project-overview")
];
errors.push(...internalKeys.map((path) => `公开 JSON 含内部字段：${path}`));

const answerEligible = evidence.evidence.filter(
  (item) => item.answer_eligible === true
).length;
const reviewOnly = evidence.evidence.length - answerEligible;
const expectedCounts = {
  total_records: evidence.evidence.length,
  graph_edges: evidence.edges.length,
  answer_eligible_records: answerEligible,
  review_only_records: reviewOnly,
  unique_entities: evidence.nodes.length,
  sources: evidence.version.source_count
};
for (const [key, expected] of Object.entries(expectedCounts)) {
  if (overview[key] !== expected) {
    errors.push(`项目概览计数不一致：${key}=${overview[key]}，期望 ${expected}`);
  }
}
if (overview.total_records <= 0 || overview.datasets.length === 0) {
  errors.push("公开项目概览为空");
}
if (overview.datasets.some((item) => item.origin !== "external")) {
  errors.push("公开项目概览包含非外部数据集");
}

const buildFiles = await walk(distRoot).catch(() => []);
if (buildFiles.length === 0) {
  errors.push("frontend/dist 不存在或为空，请先执行静态生产构建");
}
const textExtensions = new Set([
  ".css",
  ".html",
  ".js",
  ".json",
  ".svg",
  ".txt",
  ".xml"
]);
const scannedBuildFiles = buildFiles.filter((path) =>
  textExtensions.has(extname(path).toLowerCase())
);
const matchMap = new Map();
for (const path of scannedBuildFiles) {
  const text = await readFile(path, "utf8");
  for (const match of scanText(text)) {
    const key = `${relative(root, path)}:${match.label}`;
    matchMap.set(key, (matchMap.get(key) ?? 0) + match.count);
  }
}
for (const [key, count] of matchMap) {
  errors.push(`构建产物残留 ${key} × ${count}`);
}

const result = {
  valid: errors.length === 0,
  evidence_records: evidence.evidence.length,
  public_nodes: evidence.nodes.length,
  public_edges: evidence.edges.length,
  overview_records: overview.total_records,
  scanned_build_files: scannedBuildFiles.length,
  errors
};
console.log(JSON.stringify(result, null, 2));
if (!result.valid) process.exitCode = 1;
