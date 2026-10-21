const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const browser = await chromium.launch({ channel: "msedge" });
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const url = "file:///" + path.resolve(process.argv[2]).split(path.sep).join("/");
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: process.argv[3] });
  await browser.close();
})();
