import { chromium } from "playwright";

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

await page.goto("http://127.0.0.1:5174/", { waitUntil: "networkidle" });
await page.waitForTimeout(700);
await page.screenshot({ path: "/tmp/cqa-empty.png", fullPage: false });

await page.locator('[aria-label="历史对话"] button[aria-pressed]').nth(3).click();
await page.waitForTimeout(900);
await page.screenshot({ path: "/tmp/cqa-conversation.png", fullPage: false });

await browser.close();
console.log("ok");
