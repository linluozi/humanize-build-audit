const { chromium } = require("playwright");

(async () => {
  const url = process.argv[2];
  const out = process.argv[3];
  const browser = await chromium.launch({ channel: "msedge" });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
  const failures = [];
  page.on("requestfailed", r => failures.push(r.url()));
  page.on("response", r => {
    if (r.status() >= 400) failures.push(`${r.status()} ${r.url()}`);
  });
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: out, fullPage: true });
  const imgs = await page.evaluate(() =>
    Array.from(document.images).map(i => ({
      src: i.getAttribute("src"), w: i.naturalWidth, h: i.naturalHeight,
    })));
  console.log("images:", JSON.stringify(imgs));
  console.log("failures:", JSON.stringify(failures));
  const broken = imgs.filter(i => i.w === 0).length;
  console.log(broken === 0 ? "ALL IMAGES LOADED" : `${broken} BROKEN IMAGES`);
  await browser.close();
})();
