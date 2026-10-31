// End to end against the REAL backend: real satellite data, no mocks. Run with REAL=1.
import { test, expect } from "@playwright/test";

const SHOTS = process.env.SHOTS ?? "/tmp";
test.skip(!process.env.REAL, "needs REAL=1 and the backend on :8000");
test.setTimeout(15 * 60 * 1000);
const LAT = Number(process.env.LAT ?? 16.75);
const LON = Number(process.env.LON ?? 81.8);
const STMT = process.env.STMT ?? "28 अक्टूबर को चक्रवात से धान की फ़सल गिर गई";

test("whole path", async ({ browser }) => {
  const ctx = await browser.newContext({
    viewport: { width: 360, height: 780 }, hasTouch: false,
    permissions: ["geolocation"], geolocation: { latitude: LAT, longitude: LON },
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console ${m.text().slice(0, 200)}`); });

  await page.goto("/");
  await page.locator("textarea").fill(STMT);
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: /मेरी जगह/ }).click();
  await expect(page.locator(".loc-set")).toBeVisible();
  await page.getByRole("button", { name: /आगे बढ़ें/ }).click();

  await page.waitForURL(/confirm/);
  await expect(page.locator(".confirm")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/real-confirm.png`, fullPage: true });
  const date = page.locator('input[type="date"]');
  if (!(await date.inputValue())) await date.fill(process.env.EVENT_DATE ?? "2026-10-28");
  await page.getByRole("radio", { name: new RegExp(process.env.EVENT_RX ?? "चक्रवात") }).click();
  await page.getByRole("radio", { name: /हाँ, बीमा है/ }).click();
  await page.getByRole("radio", { name: /खड़ी फ़सल/ }).click();
  await page.getByRole("button", { name: /खेत चिह्नित/ }).click();

  await page.waitForURL(/plot/);
  await expect(page.locator(".plot-hint")).toBeVisible();
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${SHOTS}/real-plot-empty.png` });
  const box = (await page.locator(".plot-canvas").boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2 + 30;
  for (const [dx, dy] of [[-60, -50], [60, -50], [60, 50], [-60, 50]]) {
    await page.mouse.click(cx + dx, cy + dy);
    await page.waitForTimeout(350);
  }
  await page.screenshot({ path: `${SHOTS}/real-plot-drawing.png` });
  await page.getByRole("button", { name: /पूरा करें/ }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${SHOTS}/real-plot-edit.png` });
  await page.getByRole("button", { name: /यही मेरा खेत/ }).click();

  await page.waitForURL(/investigate/, { timeout: 60000 });
  console.log("URL", page.url());
  await page.waitForTimeout(15000);
  await page.screenshot({ path: `${SHOTS}/real-trace-early.png` });
  // Refresh mid-run: it must resume, not restart.
  await page.reload();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SHOTS}/real-trace-after-reload.png` });

  await expect(page.locator(".trace-end")).toBeVisible({ timeout: 12 * 60 * 1000 });
  await page.screenshot({ path: `${SHOTS}/real-trace-m.png`, fullPage: true });
  const caseUrl = page.url().split("/investigate")[0];
  console.log("CASE", caseUrl);

  await page.goto(caseUrl);
  await expect(page.locator(".verdict-top")).toBeVisible();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/real-verdict-m.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SHOTS}/real-verdict-d.png`, fullPage: true });
  await page.goto(`${caseUrl}/action`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/real-action-d.png`, fullPage: true });
  // Action: file with a reference, ask a question, fetch the PDF, then verify in public.
  const id = caseUrl.split("/case/")[1];
  await page.locator('input.mono').fill("TEST-REF-NOT-REAL-" + Date.now());
  await page.getByRole("button", { name: /दर्ज करें/ }).click();
  await expect(page.locator(".filed")).toBeVisible();
  await page.locator(".ask textarea").fill("क्या कटाई के बाद का नुकसान कवर है?");
  await page.getByRole("button", { name: /^पूछिए$/ }).click();
  await expect(page.locator(".answer")).toBeVisible({ timeout: 60000 });
  await page.screenshot({ path: `${SHOTS}/real-action-filed-d.png`, fullPage: true });
  const env = await (await page.request.get(`/api/cases/${id}`)).json();
  console.log("LEVEL", env.evidence?.verdict?.level, "HASH", env.evidence?.evidence_hash, "RUN", env.case.latest_run?.status, "NUMBERS", Object.keys(env.evidence?.replay?.numbers ?? {}).length);
  const pdf = await page.request.get(`/api/cases/${id}/evidence.pdf?lang=hi`);
  console.log("PDF", pdf.status(), pdf.headers()["content-type"], (await pdf.body()).length);
  if (env.evidence?.evidence_hash) {
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto(`/verify/${env.evidence.evidence_hash}`);
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${SHOTS}/real-verify-running-m.png`, fullPage: true });
    await expect(page.locator(".verify-line")).toBeVisible({ timeout: 8 * 60 * 1000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${SHOTS}/real-verify-m.png`, fullPage: true });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: `${SHOTS}/real-verify-d.png`, fullPage: true });
  }
  console.log("ERRORS", JSON.stringify(errors.slice(0, 20), null, 1));
  await ctx.close();
});
