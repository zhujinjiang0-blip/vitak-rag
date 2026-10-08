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

await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.getByText("从一个具体问题开始").waitFor();
await page.screenshot({
  path: `${outputDir}/chat-desktop.png`,
  fullPage: true
});

await page.getByPlaceholder("输入关于维生素K的问题...").fill("维生素K有哪些食物来源？");
await page.getByRole("button", { name: "发送问题" }).click();
await page.getByText("鸡蛋含有维生素K。").waitFor({ timeout: 15_000 });
await page.locator(".origin-pill.public").first().waitFor({ timeout: 15_000 });
await page.screenshot({
  path: `${outputDir}/chat-answer-desktop.png`,
  fullPage: true
});

await page.goto(`${baseUrl}/#/graph`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "知识图谱" }).waitFor();
await page.locator(".react-flow").waitFor();
await page.screenshot({
  path: `${outputDir}/graph-desktop.png`,
  fullPage: true
});

await page.goto(`${baseUrl}/#/evidence`, { waitUntil: "networkidle" });
await page.getByPlaceholder("输入关键词、实体或研究主题...").fill("华法林");
await page.getByRole("button", { name: "检索" }).click();
await page.locator(".evidence-result-card").first().waitFor({ timeout: 15_000 });
await page.locator(".origin-pill.public").first().waitFor({ timeout: 15_000 });
await page.screenshot({
  path: `${outputDir}/evidence-desktop.png`,
  fullPage: true
});

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.screenshot({
  path: `${outputDir}/chat-mobile.png`,
  fullPage: true
});
const mobileOverflow = await page.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth
);

const screenshots = [
  "chat-desktop.png",
  "chat-answer-desktop.png",
  "graph-desktop.png",
  "evidence-desktop.png",
  "chat-mobile.png"
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
