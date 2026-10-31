// Layout checks with a mocked API. Fixtures live only in tests/ and are never shipped.
import { test, expect, type Page, type Route } from "@playwright/test";
import { deflateSync } from "node:zlib";
import { evidence } from "./fixtures/evidence";

const SHOTS = process.env.SHOTS ?? "/tmp";

function crc32(buf: Buffer) {
  let c, crc = ~0;
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return ~crc >>> 0;
}
function chunk(type: string, data: Buffer) {
  const t = Buffer.from(type);
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])));
  return Buffer.concat([len, t, data, crc]);
}
function testPng(block: number, r: number, g: number, b: number) {
  const size = 200;
  const raw = Buffer.alloc((size * 3 + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (size * 3 + 1)] = 0;
    for (let x = 0; x < size; x++) {
      const v = ((Math.floor(x / block) * 37 + Math.floor(y / block) * 61) % 97) / 97;
      const o = y * (size * 3 + 1) + 1 + x * 3;
      raw[o] = r * v + 60; raw[o + 1] = g * v + 40; raw[o + 2] = b * v + 30;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

async function mock(page: Page, ev: ReturnType<typeof evidence>) {
  await page.route("**/api/**", (route: Route) => {
    const url = new URL(route.request().url());
    const p = url.pathname;
    if (p === "/api/health") return route.fulfill({ json: { status: "ok", gemini: false, version: "test" } });
    if (p.startsWith("/api/artifacts/")) {
      const m = p.match(/fade_(\d+)/);
      const block = m ? Math.max(2, Math.round(Number(m[1]) / 15)) : p.includes("post") ? 6 : 10;
      return route.fulfill({ contentType: "image/png", body: testPng(block, 170, 120, 90) });
    }
    if (p.match(/^\/api\/cases\/[^/]+$/)) {
      return route.fulfill({ json: {
        case: { id: "testcase0001", lat: 29.53, lon: 75.03, event_date: "2026-10-25", plot: { geometry: ev.plot.geometry, area_ha: 4.31, centroid: ev.plot.centroid, crs: "x", warnings: [] }, active_run_id: null, latest_run: { id: "testrun0001", status: "done" } },
        evidence: ev,
        actions: [{ id: "a1", type: "intimation_draft", status: "open", payload: { available: true, text_hi: "विषय: फ़सल नुकसान की सूचना\nफ़सल: धान\nनाम / मोबाइल: [कृपया भरें]", text_en: "Subject: Intimation of crop loss\nCrop: paddy\nName / mobile: [please fill in]", channels: ["Crop Insurance App", "Krishi Rakshak Portal & Helpline 14447"], time_assumed: true } }],
      } });
    }
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
}

const VIEWPORTS = [{ name: "m", width: 360, height: 780 }, { name: "d", width: 1440, height: 900 }];

for (const vp of VIEWPORTS) {
  test.describe(vp.name, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test("verdict strong", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await mock(page, evidence());
      await page.goto("/case/testcase0001");
      await expect(page.locator(".verdict-headline")).toBeVisible();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${SHOTS}/verdict-top-${vp.name}.png` });
      await page.locator(".tenfield").scrollIntoViewIfNeeded();
      await page.waitForTimeout(3500);
      await page.locator(".signature").nth(2).screenshot({ path: `${SHOTS}/draw-mid-${vp.name}.png` });
      // Natural end of the sequence, not the skip button: the bars must reach their full height.
      await page.waitForTimeout(16000);
      const heights = await page.locator(".drw-hist .bar").evaluateAll((els) => els.map((e) => Number(e.getAttribute("height"))));
      expect(Math.max(...heights)).toBeGreaterThan(50);
      await page.locator(".signature").nth(2).screenshot({ path: `${SHOTS}/draw-final-${vp.name}.png` });
      await page.locator(".vanish").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1500);
      await page.locator(".signature").nth(1).screenshot({ path: `${SHOTS}/vanish-${vp.name}.png` });
      await page.locator(".signature").first().screenshot({ path: `${SHOTS}/foot-${vp.name}.png` });
      await page.locator("#ex-b").scrollIntoViewIfNeeded();
      await page.locator(".exhibits").screenshot({ path: `${SHOTS}/exhibits-${vp.name}.png` });
      expect(errors).toEqual([]);
    });

    test("verdict no damage, all null", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await mock(page, evidence({
        neighbours: null, history: null, sar: null, weather: null, timeline: [], chips: [], cross_examination: [], scale_fade: null, village: null, claim_path: null,
        testimony_hi: null, testimony_en: null, deadlines: [], explanation_hi: null, explanation_en: null, replay: null, evidence_hash: null, provenance: [], policy: [],
        optical: { scenes_considered: [] },
        verdict: { level: "insufficient", headline_hi: "अभी कोई साफ़ तस्वीर नहीं मिली।", headline_en: "No clear image yet.", reasons: ["no accepted optical post scene and no usable radar pair"], caveats: ["Weather data could not be retrieved for this run."], falsifiers_checked: [], rubric_version: "v2" },
      }));
      await page.goto("/case/testcase0001");
      await expect(page.locator(".verdict-headline")).toBeVisible();
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${SHOTS}/nulls-${vp.name}.png`, fullPage: true });
      expect(errors).toEqual([]);
    });

    test("action countdown and path", async ({ page }) => {
      await mock(page, evidence());
      await page.goto("/case/testcase0001/action");
      await expect(page.locator(".claim-path")).toBeVisible();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SHOTS}/action-${vp.name}.png`, fullPage: true });
    });

    test("action no countdown", async ({ page }) => {
      await mock(page, evidence({ claim_path: { route: "area_yield_basic", insured: "unknown", crop_stage: "standing", intimation: "not_essential", countdown_applies: false, reasons: ["Cyclone is not a localized peril for standing crop."], next_steps: ["Confirm your insurance with your bank or 14447."], evidence_use: "Context for an officer. No individual intimation is required on this route.", unknowns: ["Whether you are insured this season."], clause_ids: ["5.5"] } }));
      await page.goto("/case/testcase0001/action");
      await expect(page.locator(".clock")).toHaveCount(0);
      await page.screenshot({ path: `${SHOTS}/action-nocountdown-${vp.name}.png` });
    });

    test("start", async ({ page }) => {
      await page.route("**/api/health", (r) => r.fulfill({ json: { status: "ok", gemini: true, version: "t" } }));
      await page.goto("/");
      await expect(page.locator(".mic")).toBeVisible();
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${SHOTS}/start-${vp.name}.png`, fullPage: true });
    });
  });
}

const sse = (events: object[]) => events.map((e, i) => `id: ${i + 1}\ndata: ${JSON.stringify(e)}\n\n`).join("");
const NOW = Date.now();
const ev = (seq: number, type: string, node: string, hi: string, en: string, detail: object = {}) => ({
  seq, run_id: "r1", ts: new Date(NOW + seq * 7000).toISOString(), type, node, title_hi: hi, title_en: en, detail,
});
const TRACE = [
  ev(1, "step_started", "parse", "बयान पढ़ा जा रहा है", "Reading the statement"),
  ev(2, "tool_called", "search_optical", "Sentinel-2 से तस्वीरें खोज रहे हैं", "Searching Sentinel-2", { tool: "search_optical" }),
  ev(3, "tool_result", "search_optical", "3 तस्वीरें मिलीं", "Found 3 scenes", { n_scenes: 3, metadata_cloud_pct: 1.2 }),
  ev(4, "scene_rejected", "search_optical", "28 अक्टूबर की तस्वीर हटा दी गई: यह जाँच में ख़राब निकली", "Rejected the 28 Oct image: infrared band invalid", { scene_id: "S2B_MSIL2A_20261028T053719_TEST", date: "2026-10-28", reasons: ["infrared band invalid over the context window"], metadata_cloud_pct: 0, context_ndvi_median: 0.02 }),
  ev(5, "sensor_switch", "sensor_switch", "प्रकाशीय तस्वीर काम की नहीं, अब रडार से", "Optical unusable, switching to radar", { frm: "sentinel-2", to: "sentinel-1", n_rejected: 1, rejected: [{ id: "x", date: "2026-10-28", reasons: ["infrared band invalid"] }] }),
  ev(6, "objection", "cross_examine", "यह नुकसान नहीं, कटाई है। फ़सल कट गई तो हरियाली तो घटेगी ही।", "This isn't damage, it's harvest.", { id: "harvest", test: "Bare fraction after the event > 0.5 and uniform pattern.", measured: { post_bare_fraction: 0.08, within_plot_pattern: "patchy", excess_vs_history: null }, outcome: "rebutted", finding_hi: "कटाई जैसा नहीं दिखता: 8% ही खाली मिट्टी है।", finding_en: "This does not look like harvest: only 8% is bare." }),
  ev(7, "objection", "cross_examine", "तारीख़ पक्की है?", "Are you sure of the date?", { id: "wrong_date", test: "Weather peak against the reported date.", measured: { max_daily_mm: 18.4 }, outcome: "conceded", finding_hi: "तारीख़ पर यह आपत्ति मान ली गई।", finding_en: "This objection on the date is conceded." }),
  ev(8, "verdict", "verdict", "नुकसान से मेल खाता सबूत मिला", "Evidence consistent with damage", { level: "moderate" }),
];

for (const vp of VIEWPORTS) {
  test.describe(`${vp.name} stream`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test("trace resumes with after=seq and survives a refresh", async ({ page }) => {
      const afters: string[] = [];
      let n = 0;
      await page.route("**/api/**", (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
        if (url.pathname.startsWith("/api/runs/")) {
          afters.push(url.searchParams.get("after") ?? "");
          n += 1;
          const after = Number(url.searchParams.get("after") ?? 0);
          // The first connection drops part way, as a phone connection does.
          const batch = n === 1 ? TRACE.slice(0, 5) : TRACE.filter((e) => e.seq > after);
          const end = n === 1 ? batch : [...batch, ev(9, "done", "runner", "जाँच समाप्त", "Investigation ended", { status: "complete" })];
          return route.fulfill({ status: 200, contentType: "text/event-stream", body: sse(end) });
        }
        return route.fulfill({ status: 404, json: { detail: "x" } });
      });
      await page.goto("/case/c1/investigate?run=r1");
      await expect(page.getByText("निष्कर्ष पढ़ें")).toBeVisible({ timeout: 30000 });
      expect(afters[0]).toBe("0");
      expect(afters.some((a) => a === "5")).toBe(true);
      await expect(page.locator(".rejected")).toBeVisible();
      await expect(page.locator(".switch")).toBeVisible();
      await expect(page.locator(".exchange")).toHaveCount(2);
      await page.screenshot({ path: `${SHOTS}/trace-${vp.name}.png`, fullPage: true });
      // A refresh restores from the cache and does not go back to the beginning.
      await page.reload();
      await expect(page.locator(".exchange")).toHaveCount(2);
      expect(afters.filter((a) => a === "0").length).toBe(1);
    });

    test("verify: stored vs recomputed, final line", async ({ page }) => {
      const hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
      await page.route("**/api/**", (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
        if (url.pathname.startsWith("/api/verify/")) {
          const rows = [["optical.plot_delta_ndvi", -0.3, -0.3, true], ["optical.pre.ndvi_median", 0.71, 0.71, true], ["neighbours.placebo.p_value", 0.0249, 0.0249, true], ["sar.vh_change_db", -2.4, -2.4, true]] as const;
          const msgs = [{ type: "start", hash, hash_verified: true, engine_version: "t", event_date: "2026-10-25", optical_pre_id: "S2A_PRE", optical_post_id: "S2A_POST", sar_pre_id: null, sar_post_id: null, history_scene_ids: [], seed: 1, n_numbers: rows.length, tolerance: 0.0005 }, ...rows.map(([field, stored, recomputed, match]) => ({ type: "number", field, stored, recomputed, match })), { type: "result", status: "verified", ok: true, matched: 4, total: 4, mismatched: [], message_en: "4 of 4", message_hi: "4 में से 4" }];
          return route.fulfill({ status: 200, contentType: "text/event-stream", body: sse(msgs) });
        }
        return route.fulfill({ status: 404, json: { detail: "x" } });
      });
      await page.goto(`/verify/${hash}`);
      await expect(page.locator(".verify-line")).toBeVisible({ timeout: 15000 });
      await page.screenshot({ path: `${SHOTS}/verify-${vp.name}.png`, fullPage: true });
    });

    test("API down: honest message, no white screen", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.route("**/api/**", (route) => route.abort());
      await page.goto("/case/c1");
      await expect(page.getByRole("alert")).toBeVisible();
      await page.screenshot({ path: `${SHOTS}/apidown-${vp.name}.png` });
      await page.goto("/verify/zzzz");
      await expect(page.getByText(/हैश सही ढंग/)).toBeVisible();
      await page.goto("/radar");
      await expect(page.getByRole("alert")).toBeVisible();
      expect(errors).toEqual([]);
    });
  });
}

test.describe("languages and shared links", () => {
  test.use({ viewport: { width: 360, height: 780 } });
  for (const lang of ["te", "en"] as const) {
    test(`verdict in ${lang}`, async ({ page }) => {
      await mock(page, evidence());
      await page.goto(`/case/testcase0001?lang=${lang}`);
      await expect(page.locator(".verdict-headline")).toBeVisible();
      await page.waitForTimeout(600);
      await page.screenshot({ path: `${SHOTS}/lang-${lang}.png` });
      await page.goto(`/?lang=${lang}`);
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${SHOTS}/lang-start-${lang}.png` });
    });
  }

  test("illustration_only is said aloud, and no copy says lottery", async ({ page }) => {
    const e = evidence();
    (e.village as { lottery: { rule_applicability: string } }).lottery.rule_applicability = "illustration_only";
    await mock(page, e);
    await page.goto("/case/testcase0001?lang=en");
    await expect(page.getByText("what the rule would do if it applied here")).toBeVisible();
    const text = await page.locator("body").innerText();
    expect(text.toLowerCase()).not.toContain("lottery");
    expect(text).not.toMatch(/₹|rupee/i);
  });

  test("a neighbour's link opens the map near the area and creates nothing", async ({ page }) => {
    const posts: string[] = [];
    await page.route("**/api/**", (r) => {
      if (r.request().method() !== "GET") posts.push(r.request().url());
      return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
    });
    await page.goto("/?near=28.77,76.18");
    await expect(page.locator(".pinmap")).toBeVisible();
    await page.getByRole("button", { name: /ओले, भिवानी/ }).click();
    expect(posts).toEqual([]);
  });
});

test.describe("plot at desktop", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  test("drawing, undo, finish, handles", async ({ page }) => {
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/health") return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
      return r.fulfill({ json: { case: { id: "c", lat: 16.75, lon: 81.8, active_run_id: null }, evidence: null, actions: [] } });
    });
    await page.goto("/case/c/plot");
    await page.waitForTimeout(3500);
    const box = (await page.locator(".plot-canvas").boundingBox())!;
    const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
    const undo = page.getByRole("button", { name: /पिछला हटाएँ/ });
    for (const [dx, dy] of [[-160, -120], [160, -120], [240, 60], [160, 120], [-160, 120]]) {
      await page.mouse.move(cx + dx, cy + dy);
      await page.mouse.click(cx + dx, cy + dy);
      await page.waitForTimeout(250);
    }
    await undo.click();
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${SHOTS}/plot-drawing-d.png` });
    await page.getByRole("button", { name: /पूरा करें/ }).click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${SHOTS}/plot-edit-d.png` });
    await expect(page.getByRole("button", { name: /यही मेरा खेत/ })).toBeEnabled();
  });
});

test.describe("judges trying to break it", () => {
  test.use({ viewport: { width: 360, height: 780 } });

  test("mic and GPS denied leave a working path", async ({ page }) => {
    await page.route("**/api/health", (r) => r.fulfill({ json: { status: "ok", gemini: true, version: "t" } }));
    await page.addInitScript(() => {
      navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError"));
      navigator.geolocation.getCurrentPosition = (_ok, err) => err?.({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "denied" } as GeolocationPositionError);
    });
    await page.goto("/");
    await page.locator(".mic").click();
    await expect(page.getByText(/माइक की अनुमति नहीं मिली/)).toBeVisible();
    await page.getByRole("button", { name: /मेरी जगह/ }).click();
    await expect(page.getByText(/जगह की अनुमति नहीं मिली/)).toBeVisible();
    await expect(page.locator(".pinmap")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/denied-m.png`, fullPage: true });
  });

  test("crossing polygon is refused, server refusal is shown in the reader's language", async ({ page }) => {
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/health") return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
      if (r.request().method() === "PUT") return r.fulfill({ status: 422, json: { detail: { code: "too_big", message_hi: "यह सीमा एक खेत से बहुत बड़ी है।", message_en: "This boundary is far larger than a field." } } });
      return r.fulfill({ json: { case: { id: "c", lat: 16.75, lon: 81.8, active_run_id: null }, evidence: null, actions: [] } });
    });
    await page.goto("/case/c/plot");
    await page.waitForTimeout(3000);
    const box = (await page.locator(".plot-canvas").boundingBox())!;
    const cx = box.x + box.width / 2, cy = box.y + box.height / 2 + 20;
    for (const [dx, dy] of [[-70, -60], [70, 60], [70, -60], [-70, 60]]) {
      await page.mouse.move(cx + dx, cy + dy);
      await page.mouse.click(cx + dx, cy + dy);
      await page.waitForTimeout(250);
    }
    await page.getByRole("button", { name: /पूरा करें/ }).click();
    await expect(page.getByText(/रेखाएँ एक-दूसरे को काट रही हैं/)).toBeVisible();
    await expect(page.getByRole("button", { name: /यही मेरा खेत/ })).toBeDisabled();
    await page.getByRole("button", { name: /मिटाएँ/ }).click();
    await page.waitForTimeout(250);
    for (const [dx, dy] of [[-70, -60], [70, -60], [70, 60], [-70, 60]]) {
      await page.mouse.move(cx + dx, cy + dy);
      await page.mouse.click(cx + dx, cy + dy);
      await page.waitForTimeout(250);
    }
    await page.getByRole("button", { name: /पूरा करें/ }).click();
    await page.getByRole("button", { name: /यही मेरा खेत/ }).click();
    await expect(page.getByText("यह सीमा एक खेत से बहुत बड़ी है।")).toBeVisible();
  });

  test("no reference number means not filed", async ({ page }) => {
    let posted = 0;
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/health") return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
      if (r.request().method() === "POST") { posted += 1; return r.fulfill({ status: 500, json: { detail: "x" } }); }
      return r.fulfill({ json: { case: { id: "c", lat: 1, lon: 1 }, evidence: null, actions: [] } });
    });
    await page.goto("/case/c/action");
    await page.getByRole("button", { name: /दर्ज करें/ }).click();
    await expect(page.getByText(/संदर्भ संख्या के बिना/)).toBeVisible();
    expect(posted).toBe(0);
    await expect(page.locator(".filed")).toHaveCount(0);
  });
});
