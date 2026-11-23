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
await page.locator(".graph-3d-canvas canvas").waitFor();
await page.screenshot({
  path: `${outputDir}/graph-3d-desktop.png`,
  fullPage: true
});
await page.getByRole("button", { name: "二维图谱" }).click();
await page.locator(".react-flow").waitFor();
await page.screenshot({
  path: `${outputDir}/graph-2d-desktop.png`,
  fullPage: true
});

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
  "evidence-json-mobile.png"
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
