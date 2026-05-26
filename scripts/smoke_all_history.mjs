import { chromium } from "playwright";

const URL = "http://127.0.0.1:5174/";

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();

const errors = [];
const consoleErrors = [];
page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});

await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(400);

const historyButtons = await page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .all();

const summaries = [];
for (let index = 0; index < historyButtons.length; index += 1) {
  await historyButtons[index].click();
  await page.waitForTimeout(700);
  const observerText = await page.getByLabel("Run observer").innerText();
  summaries.push({
    index,
    snippet: observerText.slice(0, 600),
  });
}

console.log(JSON.stringify({ count: historyButtons.length, summaries, errors, consoleErrors }, null, 2));

await browser.close();
