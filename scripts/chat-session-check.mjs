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

await page.getByRole("button", { name: "新建项目" }).click();
await page.getByPlaceholder("输入项目名称").fill("内部数据分析");
await page.getByRole("button", { name: "创建项目", exact: true }).click();
const projectCount = await page.locator(".project-item").count();
if (projectCount !== 2) {
  throw new Error(`新建项目后数量异常：${projectCount}`);
}
await page
  .getByRole("button", { name: "重命名项目：内部数据分析" })
  .click();
await page.getByLabel("项目名称", { exact: true }).fill("内部数据研究");
await page.getByRole("button", { name: "保存项目名称" }).click();
await page
  .locator(".project-item.active")
  .filter({ hasText: "内部数据研究" })
  .waitFor();

await page.getByPlaceholder("输入关于维生素K的问题...").fill("华法林和维生素K有什么关系？");
await page.getByRole("button", { name: "发送问题" }).click();
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "华法林通过抑制 VKORC1" })
  .waitFor({ timeout: 15_000 });
await page.waitForFunction(
  () => !document.querySelector('[data-streaming="true"]'),
  null,
  { timeout: 15_000 }
);
await page
  .getByRole("button", { name: /重命名会话：华法林和维生素K有什么关系/ })
  .click();
await page.getByLabel("会话名称", { exact: true }).fill("华法林相互作用");
await page.getByRole("button", { name: "保存会话名称" }).click();
await page.getByText("华法林相互作用", { exact: true }).waitFor();

await page
  .locator(".project-open")
  .filter({ hasText: "我的维K项目" })
  .click();
await page
  .locator(".session-open")
  .filter({ hasText: "维生素K有哪些食物来源" })
  .click();
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "维生素K的食物来源" })
  .waitFor();
await page.getByLabel("搜索当前项目会话").fill("食物");
const filteredSessions = await page.locator(".session-item").count();
if (filteredSessions !== 1) {
  throw new Error(`项目内会话搜索异常：${filteredSessions}`);
}
await page.getByLabel("搜索当前项目会话").fill("");

await page
  .locator(".project-open")
  .filter({ hasText: "内部数据研究" })
  .click();
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "华法林通过抑制 VKORC1" })
  .waitFor();
await page.reload({ waitUntil: "networkidle" });
const activeProject = await page.locator(".project-item.active").innerText();
if (!activeProject.includes("内部数据研究")) {
  throw new Error(`刷新后未恢复项目：${activeProject}`);
}
await page
  .locator(".assistant-message .message-text")
  .filter({ hasText: "华法林通过抑制 VKORC1" })
  .waitFor({ timeout: 15_000 });

console.log(
  JSON.stringify(
    {
      sessionCount,
      projectCount,
      restoredAfterReload: true,
      restoredProject: "内部数据研究",
      url: `${baseUrl}/#/chat`
    },
    null,
    2
  )
);
await browser.close();
