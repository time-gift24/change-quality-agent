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

const headerVisible = await page.getByText("Run an SOP quality check").isVisible();
const sopInput = await page.getByLabel("SOP id", { exact: true }).inputValue();
const envOptions = await page.getByLabel("Environment").locator("option").allTextContents();

await page.waitForTimeout(500);

const historyButtons = await page
  .locator('[aria-label="Run history"] button[aria-pressed]')
  .count();

console.log(JSON.stringify({
  headerVisible,
  sopInput,
  envOptions,
  historyButtons,
  pageErrors: errors,
  consoleErrors,
}, null, 2));

if (historyButtons > 0) {
  await page
    .locator('[aria-label="Run history"] button[aria-pressed]')
    .first()
    .click();
  await page.waitForTimeout(800);
  const observerVisible = await page.getByLabel("Run observer").isVisible();
  const eventsLabelVisible = await page.getByLabel("Run events").isVisible();
  console.log(JSON.stringify({ afterClick: { observerVisible, eventsLabelVisible } }, null, 2));
}

await browser.close();
