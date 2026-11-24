import { chromium } from "/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import { fileURLToPath } from "node:url";

const source = new URL("./project-overview.html", import.meta.url).href;
const output4k = fileURLToPath(new URL("./project-overview-4k.png", import.meta.url));
const outputPreview = fileURLToPath(new URL("./project-overview-preview.png", import.meta.url));

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
    if (!element) return null;
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
    if (!text || element.children.length) return [];
    const clipsHorizontally = ["hidden", "clip"].includes(style.overflowX);
    const clipsVertically = ["hidden", "clip"].includes(style.overflowY);
    if (!clipsHorizontally && !clipsVertically) return [];
    const vertical = element.scrollHeight > element.clientHeight + 4;
    const horizontal = element.scrollWidth > element.clientWidth + 4;
    return (clipsHorizontally && horizontal) || (clipsVertically && vertical)
      ? [{ tag: element.tagName, class: String(element.className), text: text.slice(0, 80) }]
      : [];
  });

  const requiredText = [
    "395",
    "SAA",
    "197",
    "SADA",
    "198",
    "基线",
    "干预后",
    "空腹 0 h",
    "餐后 1 h",
    "餐后 3 h",
    "VK1",
    "MK-4",
    "MK-7",
    "VD2-25OH",
    "VD3-25OH",
    "GLU",
    "Insulin",
    "TG",
    "TCH",
    "HDL-C",
    "LDL-C",
    "UA",
    "ALT",
    "GGT",
    "hsCRP",
    "FFA",
  ];
  const bodyText = document.body.innerText;
  const posterRect = document.querySelector(".poster").getBoundingClientRect();
  const textRects = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const value = node.textContent.trim();
    if (!value) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    [...range.getClientRects()].forEach((box, index) => {
      if (box.width < 2 || box.height < 2) return;
      textRects.push({
        text: value.slice(0, 60),
        index,
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
      });
    });
  }
  const textOverlaps = [];
  for (let i = 0; i < textRects.length; i += 1) {
    for (let j = i + 1; j < textRects.length; j += 1) {
      const a = textRects[i];
      const b = textRects[j];
      if (a.text === b.text) continue;
      const width = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const height = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (width > 2 && height > 2) {
        textOverlaps.push({ a: a.text, b: b.text, width: Math.round(width), height: Math.round(height) });
      }
    }
  }
  const textOutsidePoster = textRects.filter((box) => (
    box.left < posterRect.left - 1 ||
    box.right > posterRect.right + 1 ||
    box.top < posterRect.top - 1 ||
    box.bottom > posterRect.bottom + 1
  )).map((box) => box.text);

  return {
    viewport: { width: innerWidth, height: innerHeight },
    document: {
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    },
    regions: {
      hero: rect(".hero"),
      cohort: rect(".cohort-band"),
      process: rect(".process-band"),
      analytes: rect(".analytes-band"),
      footer: rect(".footer"),
    },
    clipped,
    missingText: requiredText.filter((text) => !bodyText.includes(text)),
    textOverlaps,
    textOutsidePoster,
    visibleElements: [...document.querySelectorAll("body *")].filter((element) => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    }).length,
  };
});

if (layout.document.width !== 1920 || layout.document.height !== 1080) {
  throw new Error(`Unexpected canvas size: ${layout.document.width}x${layout.document.height}`);
}
if (layout.clipped.length > 0) {
  throw new Error(`Potential clipped text: ${JSON.stringify(layout.clipped)}`);
}
if (layout.missingText.length > 0) {
  throw new Error(`Missing required text: ${layout.missingText.join(", ")}`);
}
if (layout.textOverlaps.length > 0) {
  throw new Error(`Overlapping text detected: ${JSON.stringify(layout.textOverlaps)}`);
}
if (layout.textOutsidePoster.length > 0) {
  throw new Error(`Text outside poster: ${layout.textOutsidePoster.join(", ")}`);
}

await page.screenshot({ path: output4k, fullPage: true });
await page.setViewportSize({ width: 1920, height: 1080 });
await page.screenshot({ path: outputPreview, fullPage: true, scale: "css" });
await browser.close();

console.log(JSON.stringify({ output4k, outputPreview, layout }, null, 2));
