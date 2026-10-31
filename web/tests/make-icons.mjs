// Renders public/icons/*.png from icon.svg. Run once: node tests/make-icons.mjs
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
const svg = readFileSync("public/icons/icon.svg", "utf8");
const b = await chromium.launch({ channel: "chrome", headless: true });
for (const [name, size, pad] of [["icon-192", 192, 0], ["icon-512", 512, 0], ["maskable-512", 512, 56]]) {
  const p = await b.newPage({ viewport: { width: size, height: size } });
  await p.setContent(`<body style="margin:0;background:#3B2415"><div style="padding:${pad}px;width:${size}px;height:${size}px;box-sizing:border-box">${svg}</div></body>`);
  await p.screenshot({ path: `public/icons/${name}.png` });
  await p.close();
}
await b.close();
