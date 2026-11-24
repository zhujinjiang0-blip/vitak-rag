import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.VITAK_WEB_URL || "http://127.0.0.1:4174";
const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
const requests = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("request", (request) => requests.push(request.url()));

await page.goto(`${baseUrl}/#/overview`, { waitUntil: "networkidle" });
await page.getByRole("heading", {
  name: "维生素 K 知识图谱检索与证据追溯"
}).waitFor();
await page.getByText("公网演示 · 外部证据版").waitFor();
await page.getByText("5,335", { exact: true }).first().waitFor();
if (await page.getByRole("link", { name: /内部研究|数据治理|数据入口/ }).count()) {
  throw new Error("公网概览仍显示受控入口");
}

await page.goto(`${baseUrl}/#/graph`, { waitUntil: "networkidle" });
await page.locator(".graph-3d-canvas canvas").waitFor({ timeout: 20_000 });
const graphCounts = await page.locator(".graph-stats strong").allInnerTexts();
if (!graphCounts.length || graphCounts.every((value) => Number(value) <= 0)) {
  throw new Error("公网知识图谱为空");
}

await page.goto(`${baseUrl}/#/evidence`, { waitUntil: "networkidle" });
await page.getByPlaceholder("输入关键词、实体或研究主题...").fill("华法林");
await page.getByRole("button", { name: "检索" }).click();
await page.locator(".evidence-result-card").first().waitFor({ timeout: 15_000 });

await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.getByPlaceholder("输入关于维生素K的问题...").fill(
  "维生素K有哪些食物来源？"
);
await page.getByRole("button", { name: "发送问题" }).click();
await page.locator(".citation-card").first().waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () => !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);

const forbiddenRequests = requests.filter((url) =>
  /\/(?:internal\/v1|api\/v1\/research|api\/v1\/auth)/.test(url)
);
if (forbiddenRequests.length) {
  throw new Error(`公网页面请求了受控接口：${forbiddenRequests.join(", ")}`);
}
if (consoleErrors.length) {
  throw new Error(`公网页面出现控制台错误：${consoleErrors.join(" | ")}`);
}

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${baseUrl}/#/overview`, { waitUntil: "networkidle" });
const mobileOverflow = await page.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth
);
if (mobileOverflow) throw new Error("公网移动端出现横向溢出");

console.log(JSON.stringify({
  valid: true,
  graphCounts,
  requests: requests.length,
  forbiddenRequests: 0,
  consoleErrors: 0,
  mobileOverflow
}, null, 2));
await browser.close();
