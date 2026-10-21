const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const target = process.argv[2];
  const out = process.argv[3];
  const browser = await chromium.launch({ channel: "msedge" });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
  await page.goto("file:///" + path.resolve(target).replace(/\\/g, "/"),
                  { waitUntil: "load" });
  await page.waitForTimeout(600);
  await page.screenshot({ path: out, fullPage: true });
  const imgs = await page.evaluate(() =>
    Array.from(document.images).map(i => ({
      src: i.getAttribute("src"),
      w: i.naturalWidth,
      h: i.naturalHeight,
    })));
  console.log(JSON.stringify(imgs, null, 1));
  await browser.close();
})();
