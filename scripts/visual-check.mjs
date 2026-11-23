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

await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "维生素 K 知识图谱检索与证据追溯" }).waitFor();
await page.getByText("预答辩演示口径").waitFor();
await page.screenshot({
  path: `${outputDir}/overview-desktop.png`,
  fullPage: true
});

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

await page.getByPlaceholder("输入关于维生素K的问题...").fill(
  "羽衣甘蓝含有哪种维生素K？"
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
await page.getByText("EXTERNAL_STRUCTURED_TRIPLE", { exact: false }).first().waitFor({
  timeout: 15_000
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
  await page.getByPlaceholder("输入关于维生素K的问题...").fill(
    "内部队列中VK1和HOMA-IR有什么关系？"
  );
  await page.getByRole("button", { name: "发送问题" }).click();
  await page.getByText("从本项目内部队列", { exact: false }).waitFor({ timeout: 15_000 });
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
await page.locator('[data-graph-scope="all"]').waitFor({ timeout: 20_000 });
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
if (overviewCounts.scope !== "all" || overviewCounts.nodes < 1500 || overviewCounts.edges < 5000) {
  throw new Error(`图谱默认未展示全量数据：${JSON.stringify(overviewCounts)}`);
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
await page.getByPlaceholder("搜索实体，例如：华法林、纳豆、INR").fill("华法林");
await page.getByRole("button", { name: "搜索" }).click();
await page.locator(".entity-result").first().waitFor({ timeout: 15_000 });
await page.locator(".entity-result").first().click();
await page.locator('[data-graph-scope="focus"]').waitFor({ timeout: 15_000 });
await page.locator(".graph-show-all").click();
await page.locator('[data-graph-scope="all"]').waitFor({ timeout: 15_000 });
await page.getByRole("button", { name: "二维图谱" }).click();
await page.locator(".react-flow").waitFor();
await page.waitForFunction(
  () => document.querySelectorAll(".react-flow__node").length > 1500,
  null,
  { timeout: 20_000 }
);
const reactFlowCounts = await page.evaluate(() => ({
  nodes: document.querySelectorAll(".react-flow__node").length,
  edges: document.querySelectorAll(".react-flow__edge").length
}));
if (reactFlowCounts.nodes < 1500 || reactFlowCounts.edges < 5000) {
  throw new Error(`二维全图数量不完整：${JSON.stringify(reactFlowCounts)}`);
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
await page.evaluate(() => {
  const timestamp = Date.now();
  const messages = Array.from({ length: 28 }, (_, index) => ({
    id: `scroll-message-${index}`,
    role: index % 2 === 0 ? "user" : "assistant",
    text:
      index % 2 === 0
        ? `连续提问测试 ${index / 2 + 1}：维生素K与这个健康问题有什么关系？`
        : `这是第 ${Math.ceil(index / 2)} 个回答。内容用于验证只有中间问答区域产生滚动条，页面主体和输入框保持固定。`
  }));
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
});
await page.reload({ waitUntil: "networkidle" });
await page.locator(".chat-scroll").waitFor({ state: "visible" });
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

const screenshots = [
  "overview-desktop.png",
  "chat-desktop.png",
  "chat-capabilities-desktop.png",
  "chat-thinking-desktop.png",
  "chat-answer-desktop.png",
  "chat-structured-evidence-desktop.png",
  "chat-safety-desktop.png",
  ...(checkInternal ? ["chat-internal-desktop.png"] : []),
  "graph-3d-desktop.png",
  "graph-2d-desktop.png",
  "evidence-json-desktop.png",
  "evidence-desktop.png",
  "import-desktop.png",
  "chat-mobile.png",
  "graph-3d-mobile.png",
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
