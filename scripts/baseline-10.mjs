import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.VITAK_WEB_URL || "http://127.0.0.1:5173";
const expectedVersion =
  process.env.VITAK_EXPECT_VERSION || "real-public-2026.11-structured";
const outputJson = resolve(
  process.env.VITAK_BASELINE_JSON ||
    "data/eval/baseline-10-external-2026.11.json"
);
const outputMarkdown = resolve(
  process.env.VITAK_BASELINE_MARKDOWN ||
    "data/eval/baseline-10-external-2026.11.md"
);
const manualReviewPath = resolve(
  process.env.VITAK_BASELINE_REVIEW ||
    "data/eval/baseline-10-manual-review.json"
);

const questions = [
  {
    id: "Q01",
    category: "定义与形式",
    query: "维生素K1和K2有哪些主要区别？",
    requiredGroups: [["维生素K1"], ["维生素K2"], ["MK-4"], ["MK-7"]],
    minimumCoverage: 1
  },
  {
    id: "Q02",
    category: "亚型与代谢",
    query: "MK-4和MK-7在人体内的代谢和生物学作用有什么区别？",
    requiredGroups: [
      ["MK-4"],
      ["MK-7"],
      ["代谢"],
      ["半衰期"],
      ["生物学作用", "生物作用"]
    ],
    minimumCoverage: 0.8
  },
  {
    id: "Q03",
    category: "机制",
    query: "MK-7与骨钙素羧化有什么关系？",
    requiredGroups: [["MK-7"], ["骨钙素"], ["羧化"]],
    minimumCoverage: 1
  },
  {
    id: "Q04",
    category: "药物相互作用",
    query: "维生素K与华法林之间有什么相互作用？",
    requiredGroups: [["华法林"], ["维生素K"], ["INR"], ["VKORC1"]],
    minimumCoverage: 1
  },
  {
    id: "Q05",
    category: "临床研究",
    query: "MK-7与胰岛素抵抗之间有哪些临床研究证据？",
    requiredGroups: [
      ["MK-7"],
      ["胰岛素", "HOMA-IR"],
      ["研究", "证据"],
      ["结果", "结论"]
    ],
    minimumCoverage: 1
  },
  {
    id: "Q06",
    category: "阴性证据",
    query: "有没有研究发现维生素K与代谢指标无显著关联？",
    requiredGroups: [
      ["维生素K"],
      ["无显著", "没有显著", "未观察到"],
      ["阴性", "没有关联", "无关联"]
    ],
    minimumCoverage: 1
  },
  {
    id: "Q07",
    category: "交互与协同",
    query: "MK-7与维生素D是否存在协同作用？",
    requiredGroups: [["MK-7"], ["维生素D"], ["协同", "交互", "联合"]],
    minimumCoverage: 1
  },
  {
    id: "Q08",
    category: "研究差异",
    query: "不同研究关于维生素K与血脂的结论是否一致？",
    requiredGroups: [
      ["维生素K"],
      ["血脂"],
      ["一致", "不一致", "差异"],
      ["研究"]
    ],
    minimumCoverage: 0.75
  },
  {
    id: "Q09",
    category: "因果边界",
    query: "有没有证据证明补充MK-7能够降低HOMA-IR？",
    requiredGroups: [
      ["MK-7"],
      ["HOMA-IR"],
      ["降低", "改善", "减少"],
      ["证据", "证明"],
      ["不能", "有限", "不确定"]
    ],
    minimumCoverage: 0.8
  },
  {
    id: "Q10",
    category: "检测解释",
    query: "血清MK-7浓度多少属于低、中、高？",
    requiredGroups: [
      ["MK-7"],
      ["浓度"],
      ["低"],
      ["中"],
      ["高"],
      ["分组", "阈值", "范围"]
    ],
    minimumCoverage: 0.8
  }
];

await mkdir(dirname(outputJson), { recursive: true });
await mkdir(dirname(outputMarkdown), { recursive: true });

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

for (const item of questions) {
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.evaluate(() => window.localStorage.clear());
  await page.reload({ waitUntil: "networkidle" });
  await page.getByPlaceholder("输入关于维生素K的问题...").waitFor();

  const started = performance.now();
  await page.getByPlaceholder("输入关于维生素K的问题...").fill(item.query);
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
        const answer = [...messages]
          .reverse()
          .find((message) => message.answer)?.answer;
        return Boolean(answer?.data_version?.version);
      },
      null,
      { timeout: 10_000 }
    );
  } catch (requestError) {
    error =
      requestError instanceof Error ? requestError.message : String(requestError);
  }
  const wallElapsedMs = Math.round(performance.now() - started);
  await page.waitForTimeout(250);

  const captured = await page.evaluate(() => {
    const projects = JSON.parse(
      window.localStorage.getItem("vitak-rag:projects:v2") || "[]"
    );
    const messages = projects.flatMap((project) =>
      (project.sessions || []).flatMap((session) => session.messages || [])
    );
    const answer = [...messages].reverse().find((message) => message.answer)?.answer;
    return answer
      ? {
          answer,
          renderedText:
            [...document.querySelectorAll(".assistant-message .message-text")]
              .at(-1)?.textContent || ""
        }
      : null;
  });

  const answer = captured?.answer;
  const answerText = `${answer?.answer_text || ""} ${captured?.renderedText || ""}`;
  const normalizedAnswer = answerText.toLowerCase().replaceAll(/\s+/g, "");
  const groupMatches = item.requiredGroups.map((group) => ({
    group,
    matched: group.find((term) =>
      normalizedAnswer.includes(term.toLowerCase().replaceAll(/\s+/g, ""))
    ) || null
  }));
  const matchedGroups = groupMatches.filter((match) => match.matched);
  const missingGroups = groupMatches
    .filter((match) => !match.matched)
    .map((match) => match.group);
  const citationIds = new Set(
    (answer?.citations || []).map((citation) => citation.id)
  );
  const claimCitationCoverage = answer?.claims?.length
    ? answer.claims.filter(
        (claim) =>
          claim.evidence_ids.length > 0 &&
          claim.evidence_ids.every((evidenceId) => citationIds.has(evidenceId))
      ).length / answer.claims.length
    : 1;
  const termCoverage = matchedGroups.length / groupMatches.length;
  const status = error
    ? "error"
    : termCoverage >= item.minimumCoverage && claimCitationCoverage === 1
      ? "pass"
      : termCoverage >= item.minimumCoverage / 2
        ? "partial"
        : "fail";

  results.push({
    id: item.id,
    category: item.category,
    query: item.query,
    required_groups: item.requiredGroups,
    matched_required_groups: matchedGroups.map((match) => match.matched),
    missing_required_groups: missingGroups,
    minimum_required_coverage: item.minimumCoverage,
    required_term_coverage: termCoverage,
    status,
    error,
    wall_elapsed_ms: wallElapsedMs,
    data_version: answer?.data_version?.version || "",
    intent: answer?.intent || "",
    answer_text: answer?.answer_text || "",
    sufficiency: answer?.sufficiency || "",
    safety_notice: answer?.safety_notice || null,
    claim_count: answer?.claims?.length || 0,
    claims_with_evidence: (answer?.claims || []).filter(
      (claim) => claim.evidence_ids.length > 0
    ).length,
    claim_citation_coverage: claimCitationCoverage,
    claim_types: [
      ...new Set((answer?.claims || []).map((claim) => claim.claim_type || "general"))
    ],
    boundary_claims: (answer?.claims || []).filter(
      (claim) => Boolean(claim.boundary_note)
    ).length,
    comparison_count: answer?.comparisons?.length || 0,
    comparison_statuses: [
      ...new Set(
        (answer?.comparisons || []).map((comparison) => comparison.status)
      )
    ],
    citation_count: answer?.citations?.length || 0,
    citations: (answer?.citations || []).map((citation) => ({
      id: citation.id,
      source_id: citation.source_id,
      source_title: citation.source_title,
      source_type: citation.source_type,
      data_origin: citation.data_origin,
      access_scope: citation.access_scope,
      evidence_level: citation.evidence_level,
      review_status: citation.review_status || "",
      source_locator: citation.source_locator || citation.locator || "",
      analysis_context: citation.analysis_context || "",
      effect_size: citation.effect_size || "",
      p_value: citation.p_value || "",
      q_value: citation.q_value || "",
      sample_n: citation.sample_n || "",
      model_type: citation.model_type || ""
    })),
    graph_path_count: answer?.graph_paths?.length || 0,
    graph_paths: (answer?.graph_paths || []).map((path) => ({
      nodes: path.nodes.map((node) => node.name),
      relations: path.edges.map((edge) => edge.predicate),
      evidence_ids: path.evidence_ids
    })),
    claims: answer?.claims || [],
    comparisons: answer?.comparisons || [],
    related_entities: (answer?.related_entities || []).map((node) => node.name),
    manual_review_status: "pending",
    manual_review_notes: ""
  });
}

await browser.close();

let manualReview = null;
try {
  manualReview = JSON.parse(await readFile(manualReviewPath, "utf8"));
  const reviewById = new Map(
    (manualReview.results || []).map((item) => [item.id, item])
  );
  results.forEach((result) => {
    const review = reviewById.get(result.id);
    if (!review) return;
    result.manual_review_status = review.verdict || "pending";
    result.manual_review_notes = review.notes || "";
  });
} catch {
  // A baseline can still be generated before the manual review stage.
}

if (results.some((result) => result.data_version !== expectedVersion)) {
  throw new Error(
    `数据版本不一致，期望 ${expectedVersion}，实际 ${[
      ...new Set(results.map((result) => result.data_version))
    ].join(", ")}`
  );
}

const latencies = results
  .map((result) => result.wall_elapsed_ms)
  .sort((left, right) => left - right);
const p95Index = Math.max(0, Math.ceil(latencies.length * 0.95) - 1);
const summary = {
  question_count: results.length,
  answered: results.filter((result) => result.claim_count > 0).length,
  passed: results.filter((result) => result.status === "pass").length,
  partial: results.filter((result) => result.status === "partial").length,
  failed: results.filter((result) => result.status === "fail").length,
  errors: results.filter((result) => result.status === "error").length,
  total_claims: results.reduce((sum, result) => sum + result.claim_count, 0),
  claims_with_evidence: results.reduce(
    (sum, result) => sum + result.claims_with_evidence,
    0
  ),
  claim_citation_coverage:
    results.reduce((sum, result) => sum + result.claim_citation_coverage, 0) /
    results.length,
  boundary_claims: results.reduce(
    (sum, result) => sum + result.boundary_claims,
    0
  ),
  comparison_answers: results.filter((result) => result.comparison_count > 0)
    .length,
  manually_reviewed: results.filter(
    (result) => result.manual_review_status !== "pending"
  ).length,
  manually_approved: results.filter(
    (result) => result.manual_review_status === "approved"
  ).length,
  path_answers: results.filter((result) => result.graph_path_count > 0).length,
  average_latency_ms: Math.round(
    latencies.reduce((sum, value) => sum + value, 0) / latencies.length
  ),
  p95_latency_ms: latencies[p95Index],
  console_errors: consoleErrors
};

const report = {
  baseline_id: "v2.0-t04-01-external-baseline",
  generated_at: new Date().toISOString(),
  base_url: baseUrl,
  expected_data_version: expectedVersion,
  browser: "Chromium via Playwright",
  viewport: { width: 1440, height: 1000 },
  manual_review: manualReview
    ? {
        path: manualReviewPath,
        review_level: manualReview.review_level,
        final_signoff: manualReview.final_signoff
      }
    : null,
  summary,
  results
};

await writeFile(outputJson, `${JSON.stringify(report, null, 2)}\n`, "utf8");
await writeFile(outputMarkdown, renderMarkdown(report), "utf8");

console.log(
  JSON.stringify(
    {
      json: outputJson,
      markdown: outputMarkdown,
      summary
    },
    null,
    2
  )
);

function renderMarkdown(data) {
  const lines = [
    "# VitaK-RAG V2.0 T04-01 十题基线报告",
    "",
    `- 生成时间：${data.generated_at}`,
    `- 数据版本：${data.expected_data_version}`,
    `- 问题数量：${data.summary.question_count}`,
    `- 平均耗时：${data.summary.average_latency_ms} ms`,
    `- P95 耗时：${data.summary.p95_latency_ms} ms`,
    `- Claim 引用覆盖率：${(data.summary.claim_citation_coverage * 100).toFixed(1)}%`,
    "",
    "## 汇总",
    "",
    "| 指标 | 数值 |",
    "| --- | ---: |",
    `| 自动通过 | ${data.summary.passed} |`,
    `| 部分通过 | ${data.summary.partial} |`,
    `| 未通过 | ${data.summary.failed} |`,
    `| 错误 | ${data.summary.errors} |`,
    `| 有 Claim 的回答 | ${data.summary.answered} |`,
    `| 有图谱路径的回答 | ${data.summary.path_answers} |`,
    `| 有证据差异说明的回答 | ${data.summary.comparison_answers} |`,
    `| 已完成初步复核 | ${data.summary.manually_reviewed} |`,
    `| 初步复核通过 | ${data.summary.manually_approved} |`,
    "",
    "> 自动状态用于初筛；`pass` 表示必需内容组和 Claim 引用覆盖达标，仍需人工科研复核。",
    "",
    "## 关键缺口",
    "",
    ...(data.results.some((result) => result.status !== "pass")
      ? data.results
          .filter((result) => result.status !== "pass")
          .map(
            (result) =>
              `- ${result.id} ${result.query}：${result.status}，缺少 ${
                result.missing_required_groups
                  .map((group) => group.join("/"))
                  .join("、") || "无关键词缺口，需人工复核"
              }。`
          )
      : ["- 无"]),
    "",
    "## 逐题结果",
    "",
    "| ID | 类别 | 自动状态 | Claim | 引用 | 路径 | 对比 | 耗时 |",
    "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ...data.results.map(
      (result) =>
        `| ${result.id} | ${result.category} | ${result.status} | ${result.claim_count} | ${result.citation_count} | ${result.graph_path_count} | ${result.comparison_count} | ${result.wall_elapsed_ms} ms |`
    ),
    "",
    "## 回答记录",
    ""
  ];
  data.results.forEach((result) => {
    lines.push(
      `### ${result.id} ${result.query}`,
      "",
      `- 意图：${result.intent || "未识别"}`,
      `- 证据充分度：${result.sufficiency || "无"}`,
      `- Claim 类型：${result.claim_types.join("、") || "无"}`,
      `- 科学边界 Claim：${result.boundary_claims}`,
      `- 引用：${result.citation_count}`,
      `- 图谱路径：${result.graph_path_count}`,
      `- 人工复核：${result.manual_review_status}`,
      "",
      result.answer_text || result.error || "未获得回答",
      "",
      "证据：",
      ...(result.citations.length
        ? result.citations.map(
            (citation) =>
              `- ${citation.source_id} · ${citation.data_origin}/${citation.access_scope} · ${citation.evidence_level} · ${citation.source_locator}`
          )
        : ["- 无"]),
      ""
    );
  });
  return `${lines.join("\n")}\n`;
}
