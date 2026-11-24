import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.VITAK_WEB_URL || "http://127.0.0.1:5173";
const goldPath = resolve(
  process.env.VITAK_GOLD_SET || "data/eval/gold-questions-v2.jsonl"
);
const evidencePath = resolve(
  process.env.VITAK_EVIDENCE_DATA || "frontend/public/real-evidence.json"
);
const outputPath = resolve(
  process.env.VITAK_GOLD_RUN || "data/eval/gold-20-run.json"
);

const [goldText, evidenceData] = await Promise.all([
  readFile(goldPath, "utf8"),
  readFile(evidencePath, "utf8").then(JSON.parse)
]);
const questions = goldText
  .split(/\r?\n/)
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line));
const evidenceById = new Map(
  evidenceData.evidence.map((item) => [item.id, item])
);
const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));

const results = [];
for (const question of questions) {
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.evaluate(() => window.localStorage.clear());
  await page.reload({ waitUntil: "networkidle" });
  await page.getByPlaceholder("输入关于维生素K的问题...").waitFor();
  const started = performance.now();
  await page.getByPlaceholder("输入关于维生素K的问题...").fill(question.query);
  await page.getByRole("button", { name: "发送问题" }).click();
  let error = "";
  try {
    await page.locator(".assistant-message").last().waitFor({ timeout: 20_000 });
    await page.waitForFunction(
      () => !document.querySelector('[data-streaming="true"]'),
      null,
      { timeout: 20_000 }
    );
    await page.waitForFunction(
      () => {
        const projects = JSON.parse(
          window.localStorage.getItem("vitak-rag:projects:v2") || "[]"
        );
        const messages = projects.flatMap((project) =>
          (project.sessions || []).flatMap((session) => session.messages || [])
        );
        return Boolean(
          [...messages].reverse().find((message) => message.answer)?.answer
            ?.data_version?.version
        );
      },
      null,
      { timeout: 10_000 }
    );
  } catch (requestError) {
    error =
      requestError instanceof Error ? requestError.message : String(requestError);
  }
  const elapsedMs = Math.round(performance.now() - started);
  await page.waitForTimeout(150);
  const answer = await page.evaluate(() => {
    const projects = JSON.parse(
      window.localStorage.getItem("vitak-rag:projects:v2") || "[]"
    );
    const messages = projects.flatMap((project) =>
      (project.sessions || []).flatMap((session) => session.messages || [])
    );
    return [...messages].reverse().find((message) => message.answer)?.answer;
  });
  const citationIds = new Set(
    (answer?.citations || []).map((citation) => citation.id)
  );
  const expectedEvidenceIds = question.expect_abstain
    ? []
    : question.expected_evidence_ids;
  const evidenceHits = expectedEvidenceIds.filter((id) => citationIds.has(id));
  const claimCitationCoverage = answer?.claims?.length
    ? answer.claims.filter(
        (claim) =>
          claim.evidence_ids.length > 0 &&
          claim.evidence_ids.every((id) => citationIds.has(id))
      ).length / answer.claims.length
    : 1;
  const answerText = `${answer?.answer_text || ""}`.toLowerCase().replaceAll(
    /\s+/g,
    ""
  );
  const checkpointHits = (question.answer_checkpoints || []).filter(
    (checkpoint) =>
      answerText.includes(
        String(checkpoint).toLowerCase().replaceAll(/\s+/g, "")
      )
  );
  const abstained =
    answer?.sufficiency === "none" || Boolean(answer?.safety_notice);
  const intentMatch = answer?.intent === question.expected_intent;
  const pass = question.expect_abstain
    ? abstained
    : evidenceHits.length > 0 && claimCitationCoverage === 1;
  results.push({
    id: question.id,
    category: question.category,
    query: question.query,
    expected_intent: question.expected_intent,
    actual_intent: answer?.intent || "",
    intent_match: intentMatch,
    expect_abstain: question.expect_abstain,
    abstained,
    safety_case: question.safety_case,
    safety_triggered: Boolean(answer?.safety_notice),
    expected_evidence_ids: expectedEvidenceIds,
    actual_evidence_ids: [...citationIds],
    evidence_hits: evidenceHits,
    evidence_match: question.expect_abstain ? abstained : evidenceHits.length > 0,
    claim_citation_coverage: claimCitationCoverage,
    checkpoint_coverage:
      checkpointHits.length / Math.max(1, question.answer_checkpoints.length),
    checkpoint_hits: checkpointHits,
    status: error ? "error" : pass ? "pass" : "fail",
    error,
    elapsed_ms: elapsedMs,
    answer_text: answer?.answer_text || "",
    claims: answer?.claims || [],
    citations: answer?.citations || [],
    comparisons: answer?.comparisons || []
  });
}
await browser.close();

const evidenceQuestions = results.filter((result) => !result.expect_abstain);
const abstainQuestions = results.filter((result) => result.expect_abstain);
const summary = {
  question_count: results.length,
  passed: results.filter((result) => result.status === "pass").length,
  failed: results.filter((result) => result.status === "fail").length,
  errors: results.filter((result) => result.status === "error").length,
  evidence_recall_any:
    evidenceQuestions.filter((result) => result.evidence_match).length /
    evidenceQuestions.length,
  intent_accuracy:
    results.filter((result) => result.intent_match).length / results.length,
  abstain_accuracy:
    abstainQuestions.filter((result) => result.abstained).length /
    Math.max(1, abstainQuestions.length),
  claim_citation_coverage:
    results.reduce((sum, result) => sum + result.claim_citation_coverage, 0) /
    results.length,
  checkpoint_coverage:
    results.reduce((sum, result) => sum + result.checkpoint_coverage, 0) /
    results.length,
  safety_triggered:
    results.filter((result) => result.safety_case && result.safety_triggered)
      .length,
  average_latency_ms: Math.round(
    results.reduce((sum, result) => sum + result.elapsed_ms, 0) /
      results.length
  ),
  console_errors: consoleErrors
};

const report = {
  run_id: "v2.0-t04-02-gold-20",
  generated_at: new Date().toISOString(),
  data_version: evidenceData.version.version,
  gold_set: goldPath,
  summary,
  results
};
await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ output: outputPath, summary }, null, 2));
