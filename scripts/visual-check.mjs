import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);
const sharp = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp"
);

const outputDir = "/private/tmp/vitak-rag-visual";
const baseUrl = process.env.VITAK_WEB_URL || "http://127.0.0.1:5173";
const expectedVersion =
  process.env.VITAK_EXPECT_VERSION || "real-public-2026.11-structured";
const checkInternal = process.env.VITAK_CHECK_INTERNAL === "true";
const researchUser = process.env.VITAK_RESEARCH_USER || "admin";
const researchPassword =
  process.env.VITAK_RESEARCH_PASSWORD || "VitakResearch2026!";
await mkdir(outputDir, { recursive: true });

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

await page.goto(`${baseUrl}/#/overview`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "维生素 K 知识图谱检索与证据追溯" }).waitFor();
await page.getByText("预答辩演示口径").waitFor();
const overviewWidth = await page.evaluate(() => ({
  viewport: window.innerWidth,
  page: document.querySelector(".overview-page")?.getBoundingClientRect().width,
  hero: document.querySelector(".overview-hero")?.getBoundingClientRect().width
}));
if (
  Math.abs(Number(overviewWidth.page) - overviewWidth.viewport) > 1 ||
  Number(overviewWidth.hero) < overviewWidth.viewport - 60
) {
  throw new Error(`项目概览未平铺：${JSON.stringify(overviewWidth)}`);
}
await page.screenshot({
  path: `${outputDir}/overview-desktop.png`,
  fullPage: true
});

if (checkInternal) {
  await page.goto(`${baseUrl}/#/login`, { waitUntil: "networkidle" });
  await page.getByLabel("用户名").fill(researchUser);
  await page.getByLabel("密码").fill(researchPassword);
  await page.getByRole("button", { name: "登录" }).click();
  await page.getByRole("link", { name: "内部研究" }).waitFor({
    timeout: 15_000
  });
  await page.goto(`${baseUrl}/#/research`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "内部研究证据" }).waitFor();
  await page.getByText("248", { exact: true }).first().waitFor();
  await page.getByText("48", { exact: true }).first().waitFor();
  await page.getByText("160", { exact: true }).first().waitFor();
  await page.getByText("9", { exact: true }).first().waitFor();
  await page.getByPlaceholder(/检索实体、结局或分析场景/).fill("HOMA-IR");
  await page.locator(".research-search").getByRole("button", { name: "检索" }).click();
  await page.locator(".research-result-card").first().waitFor({
    timeout: 15_000
  });
  await page.locator(".private-pill").first().waitFor();
  await page.screenshot({
    path: `${outputDir}/research-overview-desktop.png`,
    fullPage: true
  });
  await page.goto(`${baseUrl}/#/governance`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "数据版本与质量审计" }).waitFor();
  await page.getByText("质量与权限门槛").waitFor();
  await page.locator(".governance-summary").waitFor();
  await page.screenshot({
    path: `${outputDir}/governance-desktop.png`,
    fullPage: true
  });
}

await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.getByText("从一个具体问题开始").waitFor();
await page.screenshot({
  path: `${outputDir}/chat-desktop.png`,
  fullPage: true
});

await page.getByPlaceholder("输入关于维生素K的问题...").fill("你能回答什么问题？");
await page.getByRole("button", { name: "发送问题" }).click();
await page
  .locator(".message-text", { hasText: "我可以回答围绕维生素K的九类问题" })
  .last()
  .waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () =>
    !document.querySelector(".thinking-panel") &&
    !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
await page.screenshot({
  path: `${outputDir}/chat-capabilities-desktop.png`,
  fullPage: true
});
if ((await page.locator(".graph-path-button").count()) !== 0) {
  throw new Error("能力说明不应显示图谱路径入口");
}

await page.getByPlaceholder("输入关于维生素K的问题...").fill("维生素K有哪些食物来源？");
await page.getByRole("button", { name: "发送问题" }).click();
await page.locator(".assistant-message").last().waitFor({ timeout: 15_000 });
await page.locator(".thinking-panel").waitFor({ timeout: 15_000 });
await page.screenshot({
  path: `${outputDir}/chat-thinking-desktop.png`,
  fullPage: true
});
await page.waitForFunction(
  () =>
    !document.querySelector(".thinking-panel") &&
    Boolean(document.querySelector(".assistant-message .message-text")?.textContent),
  null,
  { timeout: 15_000 }
);
await page.waitForFunction(
  () => !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
await page.locator(".citation-card").first().waitFor({ timeout: 15_000 });
await page.locator(".origin-pill.external").first().waitFor({ timeout: 15_000 });
await page.locator(".origin-legend.compact").waitFor();
await page.screenshot({
  path: `${outputDir}/chat-answer-desktop.png`,
  fullPage: true
});
await page.locator(".claim-evidence-panel").waitFor({ state: "visible" });
const claimCount = await page.locator(".claim-evidence-item").count();
if (claimCount < 1) throw new Error("回答未展示结论级证据");
const typedClaimCount = await page.locator(".claim-type-badge").count();
if (typedClaimCount !== claimCount) {
  throw new Error("结论级证据缺少科学边界类型");
}
await page.locator(".claim-citation-list button").first().click();
await page.locator(".citation-card.highlighted").first().waitFor({
  timeout: 10_000
});
await page.screenshot({
  path: `${outputDir}/chat-claim-evidence-desktop.png`,
  fullPage: true
});
const graphPathButton = page.getByRole("button", { name: "在图谱中查看" });
let answerHandoffRaw = null;
if (await graphPathButton.count()) {
await graphPathButton.click();
await page.locator('[data-graph-scope="answer"]').waitFor({ timeout: 15_000 });
await page.locator(".graph-answer-context").waitFor({ timeout: 15_000 });
answerHandoffRaw = await page.evaluate(() =>
  sessionStorage.getItem("vitak-rag:graph-path-handoff:v1")
);
if (!answerHandoffRaw) throw new Error("问答图谱路径未写入 sessionStorage");
const answerGraphState = await page.evaluate(() => {
  const values = [...document.querySelectorAll(".graph-stats strong")].map((node) =>
    Number(node.textContent?.replace(/[^\d]/g, "") || 0)
  );
  return {
    scope: document.querySelector(".graph-canvas")?.getAttribute("data-graph-scope"),
    nodes: values[0],
    edges: values[1],
    context: document.querySelector(".graph-answer-context")?.textContent
  };
});
if (
  answerGraphState.scope !== "answer" ||
  answerGraphState.nodes < 2 ||
  answerGraphState.edges < 1 ||
  !answerGraphState.context?.includes("维生素K有哪些食物来源")
) {
  throw new Error(`问答路径展示不完整：${JSON.stringify(answerGraphState)}`);
}
await page.screenshot({
  path: `${outputDir}/graph-answer-path-desktop.png`,
  fullPage: true
});
await page.getByRole("button", { name: "二维图谱" }).click();
await page.locator(".react-flow").waitFor({ state: "visible", timeout: 15_000 });
await page.waitForFunction(
  ({ expectedNodes, expectedEdges }) =>
    document.querySelectorAll(".react-flow__node").length === expectedNodes &&
    document.querySelectorAll(".react-flow__edge").length === expectedEdges,
  {
    expectedNodes: answerGraphState.nodes,
    expectedEdges: answerGraphState.edges
  },
  { timeout: 15_000 }
);
const answerPathFlowCounts = await page.evaluate(() => ({
  nodes: document.querySelectorAll(".react-flow__node").length,
  edges: document.querySelectorAll(".react-flow__edge").length,
  labels: document.querySelectorAll(".react-flow__edge-text").length
}));
if (
  answerPathFlowCounts.nodes !== answerGraphState.nodes ||
  answerPathFlowCounts.edges !== answerGraphState.edges ||
  answerPathFlowCounts.labels !== answerGraphState.edges
) {
  throw new Error(`二维问答路径数量不一致：${JSON.stringify(answerPathFlowCounts)}`);
}
await page.screenshot({
  path: `${outputDir}/graph-answer-path-2d-desktop.png`,
  fullPage: true
});

await page.evaluate(() => {
  const raw = sessionStorage.getItem("vitak-rag:graph-path-handoff:v1");
  if (!raw) return;
  const handoff = JSON.parse(raw);
  handoff.dataVersion = "stale-answer-version";
  sessionStorage.setItem("vitak-rag:graph-path-handoff:v1", JSON.stringify(handoff));
});
await page.reload({ waitUntil: "networkidle" });
await page.locator('[data-graph-scope="answer"]').waitFor({ timeout: 15_000 });
await page.locator(".graph-answer-context em", {
  hasText: "回答数据版本与当前图谱版本不同"
}).waitFor({ timeout: 15_000 });
await page
  .locator(".graph-answer-context")
  .getByRole("button", { name: "退出回答路径并显示局部图谱" })
  .click();
await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 20_000 });
const handoffAfterExit = await page.evaluate(() =>
  sessionStorage.getItem("vitak-rag:graph-path-handoff:v1")
);
if (handoffAfterExit) throw new Error("退出回答路径后未清理 sessionStorage");
if (checkInternal) {
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.getByPlaceholder("输入关于维生素K的问题...").waitFor({
    state: "visible"
  });
  await page.getByRole("button", { name: /内外对照/ }).click();
  await page.getByPlaceholder("输入关于维生素K的问题...").fill(
    "MK-7与HOMA-IR有什么关系？"
  );
  await page.getByRole("button", { name: "发送问题" }).click();
  await page.locator(".evidence-comparison-panel").waitFor({
    state: "visible",
    timeout: 15_000
  });
  await page.waitForFunction(
    () => !document.querySelector('[data-streaming="true"]'),
    null,
    { timeout: 15_000 }
  );
  const comparisonPanel = page.locator(".evidence-comparison-panel");
  await comparisonPanel
    .getByText("显著性差异", { exact: true })
    .last()
    .waitFor({ timeout: 10_000 });
  await comparisonPanel
    .getByText("机制证据与临床", { exact: false })
    .last()
    .waitFor({ timeout: 10_000 });
  await page.screenshot({
    path: `${outputDir}/chat-evidence-comparison-desktop.png`,
    fullPage: true
  });
  await page.getByRole("button", { name: /领域知识/ }).click();
}
}

await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.getByPlaceholder("输入关于维生素K的问题...").fill(
  "羽衣甘蓝是什么？"
);
await page.getByRole("button", { name: "发送问题" }).click();
await page.locator(".assistant-message").last().waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () =>
    !document.querySelector(".thinking-panel") &&
    !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
await page.getByText("external_structured_triple", { exact: false }).first().waitFor({
  timeout: 30_000
});
await page.screenshot({
  path: `${outputDir}/chat-structured-evidence-desktop.png`,
  fullPage: true
});

await page.getByPlaceholder("输入关于维生素K的问题...").fill(
  "服用华法林时应该吃多少维生素K？"
);
await page.getByRole("button", { name: "发送问题" }).click();
await page.locator(".safety-panel").waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () =>
    !document.querySelector(".thinking-panel") &&
    Boolean(document.querySelector(".assistant-message .message-text")?.textContent),
  null,
  { timeout: 15_000 }
);
await page.waitForFunction(
  () => !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
await page.getByText("涉及处方、停药或剂量调整的问题必须由医生或药师评估。", {
  exact: false
}).last().waitFor();
await page.locator(".message-meta").last().getByText(expectedVersion).waitFor();
await page.screenshot({
  path: `${outputDir}/chat-safety-desktop.png`,
  fullPage: true
});

if (checkInternal) {
  await page.getByRole("button", { name: /内部研究/ }).click();
  await page.getByPlaceholder("询问内部队列的实体、分析族或统计结果...").fill(
    "内部队列中VK1和HOMA-IR有什么关系？"
  );
  await page.getByRole("button", { name: "发送问题" }).click();
  await page
    .locator(".message-text", { hasText: "从本项目内部队列" })
    .last()
    .waitFor({ timeout: 15_000 });
  await page.waitForFunction(
    () => !document.querySelector('[data-streaming="true"]'),
    null,
    { timeout: 15_000 }
  );
  await page.locator(".origin-pill.internal").first().waitFor({ timeout: 15_000 });
  await page.getByText("基线横断面", { exact: false }).first().waitFor({ timeout: 15_000 });
  await page.screenshot({
    path: `${outputDir}/chat-internal-desktop.png`,
    fullPage: true
  });
}

await page.goto(`${baseUrl}/#/graph`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "知识图谱" }).waitFor();
await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 20_000 });
await page.locator(".graph-3d-canvas canvas").waitFor();
const overviewCounts = await page.evaluate(() => {
  const values = [...document.querySelectorAll(".graph-stats strong")].map((node) =>
    Number(node.textContent?.replace(/[^\d]/g, "") || 0)
  );
  return {
    nodes: values[0],
    edges: values[1],
    scope: document.querySelector(".graph-canvas")?.getAttribute("data-graph-scope")
  };
});
if (overviewCounts.scope !== "focus" || overviewCounts.nodes < 1 || overviewCounts.edges < 1) {
  throw new Error(`图谱未默认展示局部网络：${JSON.stringify(overviewCounts)}`);
}
await page.screenshot({
  path: `${outputDir}/graph-3d-desktop.png`,
  fullPage: true
});
const threeDownloadPromise = page.waitForEvent("download");
await page.getByRole("button", { name: "下载当前图谱 PNG" }).click();
const threeDownload = await threeDownloadPromise;
const threeDownloadPath = await threeDownload.path();
if (!threeDownloadPath) throw new Error("三维图谱 PNG 下载失败");
const threeDownloadImage = await sharp(threeDownloadPath).metadata();
const threeDownloadStats = await sharp(threeDownloadPath).stats();
if (
  threeDownloadImage.format !== "png" ||
  !threeDownloadImage.width ||
  !threeDownloadStats.channels.some((channel) => channel.stdev > 8)
) {
  throw new Error("三维图谱下载文件不是有效 PNG");
}
await page.getByPlaceholder("搜索实体，例如：华法林、纳豆、INR").fill("Warfarin");
await page.getByRole("button", { name: "搜索" }).click();
await page.locator(".entity-result").first().waitFor({ timeout: 15_000 });
await page.locator(".entity-result").first().click();
await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 15_000 });
await page.getByRole("button", { name: "二维图谱" }).click();
await page.locator(".react-flow").waitFor();
await page.waitForFunction(
  () => document.querySelectorAll(".react-flow__node").length > 0,
  null,
  { timeout: 20_000 }
);
const reactFlowCounts = await page.evaluate(() => ({
  nodes: document.querySelectorAll(".react-flow__node").length,
  edges: document.querySelectorAll(".react-flow__edge").length
}));
if (reactFlowCounts.nodes < 1 || reactFlowCounts.edges < 1) {
  throw new Error(`二维局部图数量不完整：${JSON.stringify(reactFlowCounts)}`);
}
await page.screenshot({
  path: `${outputDir}/graph-2d-desktop.png`,
  fullPage: true
});
const twoDownloadPromise = page.waitForEvent("download");
await page.getByRole("button", { name: "下载当前图谱 PNG" }).click();
const twoDownload = await twoDownloadPromise;
const twoDownloadPath = await twoDownload.path();
if (!twoDownloadPath) throw new Error("二维图谱 PNG 下载失败");
const twoDownloadImage = await sharp(twoDownloadPath).metadata();
const twoDownloadStats = await sharp(twoDownloadPath).stats();
if (
  twoDownloadImage.format !== "png" ||
  !twoDownloadImage.width ||
  !twoDownloadStats.channels.some((channel) => channel.stdev > 8)
) {
  throw new Error("二维图谱下载文件不是有效 PNG");
}

await page.goto(`${baseUrl}/#/evidence`, { waitUntil: "networkidle" });
await page.getByPlaceholder("输入关键词、实体或研究主题...").fill("华法林");
await page.getByRole("button", { name: "检索" }).click();
await page.locator(".evidence-result-card").first().waitFor({ timeout: 15_000 });
await page.locator(".origin-pill.external").first().waitFor({ timeout: 15_000 });
await page.locator(".eligibility-pill").first().waitFor({ timeout: 15_000 });
await page.locator(".origin-filter").waitFor();
const evidenceWidth = await page.evaluate(() => ({
  viewport: window.innerWidth,
  page: document.querySelector(".evidence-page")?.getBoundingClientRect().width,
  search: document.querySelector(".evidence-search")?.getBoundingClientRect().width
}));
if (
  Math.abs(Number(evidenceWidth.page) - evidenceWidth.viewport) > 1 ||
  Number(evidenceWidth.search) < evidenceWidth.viewport - 70
) {
  throw new Error(`证据检索未平铺：${JSON.stringify(evidenceWidth)}`);
}
await page.getByRole("button", { name: "查看 JSON" }).first().click();
const jsonDialog = page.getByRole("dialog");
await jsonDialog.waitFor({ state: "visible", timeout: 15_000 });
const jsonText = await page.getByTestId("evidence-json").innerText();
if (!jsonText.includes('"schema_version": "vitak.evidence.v1"')) {
  throw new Error("证据 JSON 缺少 schema_version");
}
if (!jsonText.includes('"raw_record"')) {
  throw new Error("证据 JSON 缺少原始记录");
}
const downloadPromise = page.waitForEvent("download");
await page.getByRole("button", { name: "下载 JSON" }).click();
await downloadPromise;
await page.screenshot({
  path: `${outputDir}/evidence-json-desktop.png`,
  fullPage: false
});
await page.getByRole("button", { name: "关闭 JSON 详情" }).click();
await page.screenshot({
  path: `${outputDir}/evidence-desktop.png`,
  fullPage: true
});

await page.goto(`${baseUrl}/#/import`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: /知识库导入|42 列证据表导入/ }).waitFor();
const importWidth = await page.evaluate(() => ({
  viewport: window.innerWidth,
  page: document.querySelector(".import-page")?.getBoundingClientRect().width
}));
if (Math.abs(Number(importWidth.page) - importWidth.viewport) > 1) {
  throw new Error(`数据入口未平铺：${JSON.stringify(importWidth)}`);
}
await page.screenshot({
  path: `${outputDir}/import-desktop.png`,
  fullPage: true
});

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.screenshot({
  path: `${outputDir}/chat-mobile.png`,
  fullPage: true
});
await page.goto(`${baseUrl}/#/graph`, { waitUntil: "networkidle" });
await page.locator(".graph-3d-canvas canvas").waitFor();
await page.screenshot({
  path: `${outputDir}/graph-3d-mobile.png`,
  fullPage: true
});
if (checkInternal) {
  await page.getByRole("button", { name: "内部局部" }).click();
  await page.getByPlaceholder("搜索实体，例如：华法林、纳豆、INR").fill("HOMA-IR");
  await page.getByRole("button", { name: "搜索" }).click();
  await page.locator(".entity-result").first().waitFor({ timeout: 15_000 });
  await page.locator(".entity-result").first().click();
  await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 15_000 });
  await page.screenshot({
    path: `${outputDir}/graph-research-mobile.png`,
    fullPage: true
  });
}
if (answerHandoffRaw) {
  await page.evaluate(
    (raw) => sessionStorage.setItem("vitak-rag:graph-path-handoff:v1", raw),
    answerHandoffRaw
  );
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.goto(`${baseUrl}/#/graph?source=answer`, { waitUntil: "networkidle" });
  await page.locator('[data-graph-scope="answer"]').waitFor({ timeout: 15_000 });
  await page.locator(".graph-answer-context").waitFor({ timeout: 15_000 });
  const mobileAnswerPathOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth
  );
  if (mobileAnswerPathOverflow) throw new Error("移动端问答图谱路径出现横向溢出");
  await page.screenshot({
    path: `${outputDir}/graph-answer-path-mobile.png`,
    fullPage: true
  });
  await page.evaluate(
    (raw) => sessionStorage.setItem("vitak-rag:graph-path-handoff:v1", raw),
    answerHandoffRaw
  );
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.goto(`${baseUrl}/#/graph`, { waitUntil: "networkidle" });
  await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 20_000 });
  const staleHandoffAfterNormalNavigation = await page.evaluate(() =>
    sessionStorage.getItem("vitak-rag:graph-path-handoff:v1")
  );
  if (staleHandoffAfterNormalNavigation) {
    throw new Error("普通进入图谱页时未清理旧的回答路径");
  }
}
await page.goto(`${baseUrl}/#/evidence`, { waitUntil: "networkidle" });
await page
  .getByPlaceholder("输入关键词、实体或研究主题...")
  .fill("华法林");
await page.getByRole("button", { name: "检索" }).click();
await page.locator(".evidence-result-card").first().waitFor({ timeout: 15_000 });
await page.getByRole("button", { name: "查看 JSON" }).first().click();
await page.getByRole("dialog").waitFor({ state: "visible", timeout: 15_000 });
await page.screenshot({
  path: `${outputDir}/evidence-json-mobile.png`,
  fullPage: false
});
const mobileOverflow = await page.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth
);

await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.evaluate(async (appBaseUrl) => {
  const timestamp = Date.now();
  const messages = Array.from({ length: 28 }, (_, index) => ({
    id: `scroll-message-${index}`,
    role: index % 2 === 0 ? "user" : "assistant",
    text:
      index % 2 === 0
        ? `连续提问测试 ${index / 2 + 1}：维生素K与这个健康问题有什么关系？`
        : `这是第 ${Math.ceil(index / 2)} 个回答。内容用于验证只有中间问答区域产生滚动条，页面主体和输入框保持固定。`
  }));
  const data = await fetch(`${appBaseUrl}/real-evidence.json`).then((response) =>
    response.json()
  );
  const relatedEntity =
    data.nodes.find((node) => node.name === "APOE") ?? data.nodes[0];
  messages.push({
    id: "related-entity-answer",
    role: "assistant",
    text: "当前知识库没有足够的多跳关系，请在知识图谱中查看识别到的相关实体。",
    answer: {
      session_id: "scroll-session",
      query: "APOE是什么？",
      normalized_query: "apoe是什么",
      intent: "definition",
      answer_text: "当前知识库没有足够的多跳关系。",
      claims: [],
      citations: [],
      graph_paths: [],
      sufficiency: "none",
      safety_notice: null,
      related_entities: [relatedEntity],
      data_version: data.version,
      elapsed_ms: 0,
      mode: "domain",
      generation: {
        status: "generated",
        configured: true,
        used: true,
        provider: "visual-test",
        model: "evidence-editor",
        semantic_parse_used: true,
        accepted_claim_count: 1,
        rejected_claim_count: 0,
        fallback_reason: "",
        verification: "passed",
        latency_ms: 420
      }
    }
  });
  const project = {
    id: "scroll-project",
    title: "连续问答滚动测试",
    createdAt: timestamp,
    updatedAt: timestamp,
    sessions: [
      {
        id: "scroll-session",
        title: "连续提问与历史消息",
        createdAt: timestamp,
        updatedAt: timestamp,
        messages
      }
    ]
  };
  localStorage.setItem("vitak-rag:projects:v2", JSON.stringify([project]));
  localStorage.setItem("vitak-rag:active-project:v2", project.id);
  localStorage.setItem("vitak-rag:active-conversation:v2", project.sessions[0].id);
}, baseUrl);
await page.reload({ waitUntil: "networkidle" });
await page.locator(".chat-scroll").waitFor({ state: "visible" });
await page.locator(".generation-panel.status-generated").waitFor({
  state: "visible"
});
await page.locator(".generation-pill.status-generated").waitFor({
  state: "visible"
});
const chatScrollMetrics = await page.evaluate(() => {
  const element = document.querySelector(".chat-scroll");
  if (!(element instanceof HTMLElement)) return null;
  const composer = document.querySelector(".composer")?.getBoundingClientRect();
  return {
    pageHeight: document.documentElement.scrollHeight,
    viewportHeight: window.innerHeight,
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    scrollTop: element.scrollTop,
    composerBottom: composer?.bottom ?? null
  };
});
if (!chatScrollMetrics) throw new Error("未找到中间问答滚动区域");
if (chatScrollMetrics.pageHeight > chatScrollMetrics.viewportHeight + 2) {
  throw new Error("连续问答导致整页高度增长");
}
if (chatScrollMetrics.scrollHeight <= chatScrollMetrics.clientHeight) {
  throw new Error("中间问答区域没有产生独立滚动条");
}
if (
  chatScrollMetrics.scrollHeight -
    chatScrollMetrics.scrollTop -
    chatScrollMetrics.clientHeight >
  4
) {
  throw new Error("历史会话加载后未自动定位到最新消息");
}
await page.screenshot({
  path: `${outputDir}/chat-long-scroll-desktop.png`,
  fullPage: false
});
await page.getByRole("button", { name: "查看相关实体" }).click();
await page.locator('[data-graph-scope="answer"]').waitFor({ timeout: 15_000 });
const relatedEntityGraph = await page.evaluate(() => {
  const values = [...document.querySelectorAll(".graph-stats strong")].map((node) =>
    Number(node.textContent?.replace(/[^\d]/g, "") || 0)
  );
  return {
    nodes: values[0],
    edges: values[1],
    context: document.querySelector(".graph-answer-context")?.textContent
  };
});
if (
  relatedEntityGraph.nodes !== 1 ||
  relatedEntityGraph.edges !== 0 ||
  !relatedEntityGraph.context?.includes("APOE是什么")
) {
  throw new Error(`相关实体降级图谱不正确：${JSON.stringify(relatedEntityGraph)}`);
}
await page.screenshot({
  path: `${outputDir}/graph-related-entities-desktop.png`,
  fullPage: false
});

const screenshots = [
  "overview-desktop.png",
  ...(checkInternal
    ? ["research-overview-desktop.png", "governance-desktop.png"]
    : []),
  "chat-desktop.png",
  "chat-capabilities-desktop.png",
  "chat-thinking-desktop.png",
  "chat-answer-desktop.png",
  "chat-claim-evidence-desktop.png",
  "chat-structured-evidence-desktop.png",
  "chat-safety-desktop.png",
  ...(checkInternal
    ? ["chat-evidence-comparison-desktop.png", "chat-internal-desktop.png"]
    : []),
  "graph-3d-desktop.png",
  "graph-2d-desktop.png",
  ...(answerHandoffRaw
    ? ["graph-answer-path-desktop.png", "graph-answer-path-2d-desktop.png"]
    : []),
  "graph-related-entities-desktop.png",
  "evidence-json-desktop.png",
  "evidence-desktop.png",
  "import-desktop.png",
  "chat-mobile.png",
  "graph-3d-mobile.png",
  ...(checkInternal ? ["graph-research-mobile.png"] : []),
  ...(answerHandoffRaw ? ["graph-answer-path-mobile.png"] : []),
  "evidence-json-mobile.png",
  "chat-long-scroll-desktop.png"
];
const imageChecks = {};
for (const filename of screenshots) {
  const path = `${outputDir}/${filename}`;
  const metadata = await sharp(path).metadata();
  const stats = await sharp(path).stats();
  imageChecks[filename] = {
    width: metadata.width,
    height: metadata.height,
    nonBlank: stats.channels.some((channel) => channel.stdev > 10)
  };
}

const unexpectedConsoleErrors = consoleErrors.filter(
  (message) => !message.includes("status of 401 (Unauthorized)")
);
if (unexpectedConsoleErrors.length > 0) {
  throw new Error(`浏览器控制台错误：${unexpectedConsoleErrors.join(" | ")}`);
}

console.log(
  JSON.stringify(
    {
      screenshots: outputDir,
      mobileOverflow,
      consoleErrors,
      imageChecks
    },
    null,
    2
  )
);

await browser.close();
