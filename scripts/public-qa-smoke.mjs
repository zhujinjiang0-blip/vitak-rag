import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.VITAK_WEB_URL || "https://zhujinjiang0-blip.github.io/vitak-rag";
const questions = [
  "维生素K有哪些食物来源？",
  "华法林和维生素K有什么关系？",
  "维生素K1和K2有什么区别？",
  "骨钙素与维生素K2有什么关系？",
  "MK-7有哪些随机对照研究证据？",
  "PIVKA-II可以反映什么？",
  "今天天气怎么样？",
  "服用华法林时应该吃多少维生素K？"
];

const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const results = [];

for (const question of questions) {
  await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
  await page.getByPlaceholder("输入关于维生素K的问题...").fill(question);
  await page.getByRole("button", { name: "发送问题" }).click();
  await page.locator(".assistant-message").last().waitFor({ timeout: 15_000 });
  await page.locator(".loading-line").waitFor({ state: "detached", timeout: 15_000 }).catch(() => {});
  const text = await page.locator(".assistant-message .message-text").last().innerText();
  const meta = await page.locator(".message-meta").last().innerText().catch(() => "");
  results.push({
    question,
    text: text.slice(0, 320).replaceAll("\n", " / "),
    meta: meta.replaceAll("\n", " / "),
    hasCitation: (await page.locator(".citation-card").count()) > 0,
    hasSafety: (await page.locator(".safety-panel").count()) > 0
  });
}

console.log(JSON.stringify(results, null, 2));
await browser.close();
