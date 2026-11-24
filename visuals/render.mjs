import { chromium } from "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import { fileURLToPath } from "node:url";

const source = new URL("./study-design.html", import.meta.url).href;
const output = fileURLToPath(new URL("./study-design-4k.png", import.meta.url));

const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  args: ["--no-sandbox"],
});

const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 2,
});

await page.goto(source, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

const layout = await page.evaluate(() => {
  const rect = (selector) => {
    const element = document.querySelector(selector);
    const box = element.getBoundingClientRect();
    return {
      top: Math.round(box.top),
      right: Math.round(box.right),
      bottom: Math.round(box.bottom),
      left: Math.round(box.left),
      width: Math.round(box.width),
      height: Math.round(box.height),
    };
  };

  const clipped = [...document.querySelectorAll("body *")].flatMap((element) => {
    const style = getComputedStyle(element);
    const text = element.textContent.trim();
    if (!text || element.children.length || style.overflow === "hidden") return [];
    const vertical = element.scrollHeight > element.clientHeight + 1;
    const horizontal = element.scrollWidth > element.clientWidth + 1;
    return vertical || horizontal
      ? [{ tag: element.tagName, class: element.className, text: text.slice(0, 60) }]
      : [];
  });

  return {
    viewport: { width: innerWidth, height: innerHeight },
    document: {
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    },
    masthead: rect(".masthead"),
    metrics: rect(".metrics"),
    workspace: rect(".workspace"),
    footer: rect(".bottom-rule"),
    cohortNumber: {
      ...rect(".cohort-number strong"),
      clientWidth: document.querySelector(".cohort-number strong").clientWidth,
      scrollWidth: document.querySelector(".cohort-number strong").scrollWidth,
      clientHeight: document.querySelector(".cohort-number strong").clientHeight,
      scrollHeight: document.querySelector(".cohort-number strong").scrollHeight,
    },
    clipped,
  };
});

await page.screenshot({ path: output, fullPage: true });
await browser.close();

console.log(JSON.stringify({ output, layout }, null, 2));
