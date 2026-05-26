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
await page.waitForTimeout(500);

const historyButtons = await page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .count();

await page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .first()
  .click();
await page.waitForTimeout(800);

const observerVisible = await page.getByLabel("Run observer").isVisible();
const observerText = await page.getByLabel("Run observer").innerText();
const humanBubble = await page
  .locator('[aria-label="Run observer"] >> text=/Run SOP `/')
  .first()
  .innerText();
const assistantTurns = await page
  .locator('[aria-label^="Assistant turn "]')
  .all();

const assistantTurnLabels = await Promise.all(
  assistantTurns.map((turn) => turn.getAttribute("aria-label")),
);

const firstAssistantText =
  assistantTurns.length > 0 ? await assistantTurns[0].innerText() : null;

console.log(JSON.stringify({
  historyButtons,
  observerVisible,
  humanBubble,
  assistantTurnLabels,
  firstAssistantText,
  observerSnippet: observerText.slice(0, 400),
  pageErrors: errors,
  consoleErrors,
}, null, 2));

await browser.close();
