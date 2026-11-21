import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.VITAK_WEB_URL || "https://zhujinjiang0-blip.github.io/vitak-rag";
const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.goto(`${baseUrl}/#/chat`, { waitUntil: "networkidle" });
await page.evaluate(() => window.localStorage.clear());
await page.reload({ waitUntil: "networkidle" });

await page.getByPlaceholder("输入关于维生素K的问题...").fill("维生素K有哪些食物来源？");
await page.getByRole("button", { name: "发送问题" }).click();
await page.locator(".session-item").first().waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () => !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
const firstSession = page
  .locator(".session-open")
  .filter({ hasText: "维生素K有哪些食物来源" })
  .first();
await firstSession.waitFor();

await page.getByRole("button", { name: "新建会话" }).click();
await page.getByText("从一个具体问题开始").waitFor();
const sessionCount = await page.locator(".session-item").count();
if (sessionCount !== 2) {
  throw new Error(`新建会话后数量异常：${sessionCount}`);
}

await firstSession.click();
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "维生素K的食物来源" })
  .waitFor();
await page.reload({ waitUntil: "networkidle" });
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "维生素K的食物来源" })
  .waitFor({ timeout: 15_000 });

console.log(
  JSON.stringify(
    {
      sessionCount,
      restoredAfterReload: true,
      url: `${baseUrl}/#/chat`
    },
    null,
    2
  )
);
await browser.close();
