import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const baseUrl = process.env.VITAK_API_URL || "http://127.0.0.1:8000";
const username = process.env.VITAK_RESEARCH_USER;
const password = process.env.VITAK_RESEARCH_PASSWORD;
const questionsPath = resolve(
  process.env.VITAK_RESEARCH_QUESTIONS ||
    "data/eval/research-questions-v1.jsonl"
);
const outputPath = resolve(
  process.env.VITAK_RESEARCH_OUTPUT ||
    "data/eval/research-run-2026.11.json"
);

if (!username || !password) {
  throw new Error(
    "VITAK_RESEARCH_USER and VITAK_RESEARCH_PASSWORD are required"
  );
}

const loginResponse = await fetch(`${baseUrl}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password })
});
if (!loginResponse.ok) {
  throw new Error(`login failed: ${loginResponse.status} ${await loginResponse.text()}`);
}
const cookies = loginResponse.headers.getSetCookie?.() ?? [];
const cookie = cookies.map((value) => value.split(";", 1)[0]).join("; ");

const questions = (await readFile(questionsPath, "utf8"))
  .split("\n")
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line));
const results = [];

for (const question of questions) {
  const started = performance.now();
  const response = await fetch(`${baseUrl}/api/v1/qa/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Cookie: cookie
    },
    body: JSON.stringify({
      query: question.query,
      mode: "research"
    })
  });
  const elapsed = Math.round(performance.now() - started);
  if (!response.ok) {
    results.push({
      id: question.id,
      status: "error",
      error: `${response.status} ${await response.text()}`,
      elapsed_ms: elapsed
    });
    continue;
  }
  const answer = await response.json();
  const citationIds = new Set(answer.citations.map((item) => item.id));
  const claimCoverage = answer.claims.every((claim) =>
    claim.evidence_ids.every((evidenceId) => citationIds.has(evidenceId))
  );
  const internalOnly = answer.citations.every(
    (citation) =>
      citation.data_origin === "internal" &&
      citation.access_scope === "private"
  );
  const familyHit =
    !question.expected_family ||
    answer.citations.some((citation) =>
      question.expected_family.includes(citation.test_family)
    );
  const statusHit =
    !question.expected_status ||
    answer.citations.some((citation) =>
      question.expected_status.includes(citation.evidence_status)
    );
  const answerText = answer.answer_text.toLowerCase();
  const termHits = (question.expected_terms || []).filter((term) =>
    answerText.includes(term.toLowerCase())
  );
  const termHit = termHits.length === (question.expected_terms || []).length;
  const passed =
    answer.claims.length > 0 &&
    answer.citations.length > 0 &&
    claimCoverage &&
    internalOnly &&
    familyHit &&
    statusHit &&
    termHit;
  results.push({
    id: question.id,
    category: question.category,
    query: question.query,
    status: passed ? "pass" : "fail",
    intent: answer.intent,
    sufficiency: answer.sufficiency,
    evidence_ids: answer.citations.map((citation) => citation.id),
    test_families: answer.citations.map((citation) => citation.test_family),
    evidence_statuses: answer.citations.map(
      (citation) => citation.evidence_status
    ),
    claim_citation_coverage: claimCoverage,
    internal_private_only: internalOnly,
    family_hit: familyHit,
    status_hit: statusHit,
    term_hits: termHits,
    elapsed_ms: elapsed,
    answer_text: answer.answer_text
  });
}

const summary = {
  question_count: results.length,
  passed: results.filter((item) => item.status === "pass").length,
  failed: results.filter((item) => item.status === "fail").length,
  errors: results.filter((item) => item.status === "error").length,
  average_latency_ms: Math.round(
    results.reduce((total, item) => total + item.elapsed_ms, 0) /
      Math.max(results.length, 1)
  )
};
const report = {
  run_id: `research-v1-${new Date().toISOString().slice(0, 10)}`,
  generated_at: new Date().toISOString(),
  api_url: baseUrl,
  summary,
  results
};
await writeFile(outputPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ output: outputPath, summary }, null, 2));
if (summary.passed !== summary.question_count) process.exitCode = 1;
