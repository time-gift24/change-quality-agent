import { chromium } from "playwright";

const URL = "http://127.0.0.1:5174/";

const errors = [];
const consoleErrors = [];

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();

page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});

await page.goto(URL, { waitUntil: "networkidle" });

await page.getByRole("button", { name: "Run" }).click();
await page.waitForTimeout(1500);

const eventsSectionVisible = await page.getByLabel("Run events").isVisible();
const eventsText = await page.getByLabel("Run events").innerText();
const nodesText = await page.getByLabel("Run nodes").innerText();
const historyCount = await page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .count();

console.log(JSON.stringify({
  eventsSectionVisible,
  eventsHasContent: !eventsText.includes("No events yet"),
  nodesText,
  historyCount,
  pageErrors: errors,
  consoleErrors,
}, null, 2));

const failedRunButton = page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .filter({ hasText: "error" })
  .first();
const failedRunCount = await failedRunButton.count();
if (failedRunCount > 0) {
  await failedRunButton.click();
  await page.waitForTimeout(800);
  const errorEventsText = await page.getByLabel("Run events").innerText();
  console.log(JSON.stringify({ errorRunEvents: errorEventsText.slice(0, 400) }, null, 2));
}

await browser.close();
