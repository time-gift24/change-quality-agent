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
await page.waitForTimeout(500);

const heroVisible = await page.getByText("你好,我们开始吧").isVisible();
const newConvoVisible = await page.getByLabel("发起新对话").isVisible();
const sopValue = await page.getByLabel("SOP ID").inputValue();
const envOptions = await page
  .getByLabel("环境")
  .locator("option")
  .allTextContents();
const confirmButton = await page
  .getByLabel("确认并发起运行")
  .isVisible();
const historyButtons = await page
  .locator('[aria-label="历史对话"] button[aria-pressed]')
  .count();

console.log(JSON.stringify({
  heroVisible,
  newConvoVisible,
  sopValue,
  envOptions,
  confirmButton,
  historyButtons,
  pageErrors: errors,
  consoleErrors,
}, null, 2));

await page
  .locator('[aria-label="历史对话"] button[aria-pressed]')
  .first()
  .click();
await page.waitForTimeout(700);

const observerVisible = await page.getByLabel("Run observer").isVisible();
const humanBubbleText = await page
  .locator('[aria-label="Run observer"] >> text=/请对 SOP/')
  .first()
  .innerText();

console.log(JSON.stringify({ afterHistoryClick: { observerVisible, humanBubbleText } }, null, 2));

await page.getByLabel("发起新对话").click();
await page.waitForTimeout(400);
const heroAfterReset = await page.getByText("你好,我们开始吧").isVisible();
console.log(JSON.stringify({ heroAfterReset }, null, 2));

await browser.close();
