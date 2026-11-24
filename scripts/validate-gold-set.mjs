import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const goldPath = resolve(
  process.env.VITAK_GOLD_SET || "data/eval/gold-questions-v2.jsonl"
);
const evidencePath = resolve(
  process.env.VITAK_EVIDENCE_DATA || "frontend/public/real-evidence.json"
);
const outputPath = resolve(
  process.env.VITAK_GOLD_VALIDATION ||
    "data/eval/gold-20-validation.json"
);

const [goldText, evidence] = await Promise.all([
  readFile(goldPath, "utf8"),
  readFile(evidencePath, "utf8").then(JSON.parse)
]);
const questions = goldText
  .split(/\r?\n/)
  .filter((line) => line.trim())
  .map((line, index) => {
    try {
      return JSON.parse(line);
    } catch (error) {
      throw new Error(`JSONL 第 ${index + 1} 行无法解析：${error}`);
    }
  });
const evidenceById = new Map(evidence.evidence.map((item) => [item.id, item]));
const ids = new Set();
const queries = new Set();
const errors = [];

for (const question of questions) {
  if (!question.id || ids.has(question.id)) {
    errors.push(`问题 ID 缺失或重复：${question.id}`);
  }
  ids.add(question.id);
  if (!question.query || queries.has(question.query)) {
    errors.push(`问题缺失或重复：${question.id}`);
  }
  queries.add(question.query);
  if (!question.expected_intent) {
    errors.push(`${question.id} 缺少 expected_intent`);
  }
  if (!question.standard_answer) {
    errors.push(`${question.id} 缺少 standard_answer`);
  }
  if (!Array.isArray(question.answer_checkpoints) || !question.answer_checkpoints.length) {
    errors.push(`${question.id} 缺少 answer_checkpoints`);
  }
  if (!Array.isArray(question.expected_evidence_ids)) {
    errors.push(`${question.id} 缺少 expected_evidence_ids`);
    continue;
  }
  if (!question.expect_abstain && question.expected_evidence_ids.length === 0) {
    errors.push(`${question.id} 非拒答题没有金标准证据`);
  }
  if (question.expect_abstain && question.expected_evidence_ids.length > 0) {
    errors.push(`${question.id} 拒答题不应设置金标准证据`);
  }
  for (const evidenceId of question.expected_evidence_ids) {
    const item = evidenceById.get(evidenceId);
    if (!item) {
      errors.push(`${question.id} 引用了不存在的证据 ${evidenceId}`);
      continue;
    }
    if (item.answer_eligible !== true) {
      errors.push(`${question.id} 的金标准证据不可正式回答 ${evidenceId}`);
    }
    if (item.data_origin === "internal") {
      errors.push(`${question.id} 的公开测试集包含内部证据 ${evidenceId}`);
    }
  }
}

const report = {
  gold_set: goldPath,
  evidence_data: evidencePath,
  data_version: evidence.version.version,
  question_count: questions.length,
  evidence_backed_questions: questions.filter(
    (question) => !question.expect_abstain
  ).length,
  abstain_questions: questions.filter((question) => question.expect_abstain).length,
  safety_questions: questions.filter((question) => question.safety_case).length,
  boundary_required_questions: questions.filter(
    (question) => question.requires_boundary
  ).length,
  categories: Object.fromEntries(
    [...new Set(questions.map((question) => question.category))].map(
      (category) => [
        category,
        questions.filter((question) => question.category === category).length
      ]
    )
  ),
  valid: errors.length === 0,
  errors
};

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ output: outputPath, ...report }, null, 2));
if (!report.valid) process.exitCode = 1;
