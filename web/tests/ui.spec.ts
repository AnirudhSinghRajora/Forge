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
        rubric: { version: "v3", p_field: 0.025, strong_delta: -0.15, moderate_delta: -0.1 },
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
    await page.getByRole("button", { name: /भिवानी: आम खेत/ }).click();
    await expect(page.locator(".selected-note")).toBeVisible();
    expect(posts).toEqual([]);
  });

  test("a shortcut moves the map, says what was reported, and sets no date", async ({ page }) => {
    const created = { case_id: "c1", needs: ["event_date"], questions: {}, parsed: { event_date: null, crop: null, event_type: "unknown", transcript: "x", confidence: 0.1 } };
    let form = "";
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/cases" && r.request().method() === "POST") {
        form = r.request().postData() ?? "";
        return r.fulfill({ json: created });
      }
      if (u.pathname === "/api/cases/c1") return r.fulfill({ json: { case: { id: "c1" }, evidence: null, actions: [] } });
      return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
    });
    await page.goto("/?near=28.77,76.18&lang=en");
    await page.getByRole("button", { name: /Bhiwani: typical plot/ }).click();
    const note = page.locator(".place-note");
    await expect(note).toContainText("Hail reported: 2-3 March 2024");
    await expect(note.getByRole("link")).toHaveAttribute("href", /tribuneindia\.com/);
    await expect(note).toContainText("only moves the map");
    expect(form).toBe("");
  });

  test("a date before Sentinel-2 is refused in the reader's language", async ({ page }) => {
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/cases/c1") return r.fulfill({ json: { case: { id: "c1", event_date: "2014-01-01", needs: [], questions: {}, parsed: { date_note: "too_old_refused:2001-01-01" } }, evidence: null, actions: [] } });
      return r.fulfill({ json: { status: "ok", gemini: true, version: "t" } });
    });
    await page.goto("/case/c1/confirm?lang=en");
    await expect(page.getByRole("alert")).toContainText("before 23 June 2015");
    await expect(page.locator("input[type=date]")).toHaveAttribute("min", "2015-06-23");
    await expect(page.locator("body")).not.toContainText("too_old_refused");
    await expect(page.locator("body")).toContainText("too far back");
  });
});

test.describe("what the review changed", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  const envelope = (overrides: Record<string, unknown>, ev: Record<string, unknown> = evidence() as unknown as Record<string, unknown>) => ({
    rubric: { version: "v3", p_field: 0.025, strong_delta: -0.15, moderate_delta: -0.1 },
    case: { id: "testcase0001", lat: 29.53, lon: 75.03, event_date: "2026-10-25", plot: null, latest_run: { id: "r1", status: "interrupted" }, active_run_id: null, status: "open" },
    evidence: ev, actions: [], exhibits: {}, sealed: !!ev.evidence_hash, ...overrides,
  });
  const serve = async (page: Page, body: unknown, status = 200) => {
    await page.route("**/api/**", (r) => {
      const p = new URL(r.request().url()).pathname;
      if (p === "/api/health") return r.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
      if (p.startsWith("/api/cases/")) return r.fulfill({ status, json: body });
      if (p.startsWith("/api/artifacts/")) return r.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
      return r.fulfill({ status: 404, json: { detail: "not mocked" } });
    });
  };

  test("an unsealed record with no active run offers Run Again", async ({ page }) => {
    await serve(page, envelope({}, { ...evidence(), evidence_hash: null }));
    await page.goto("/case/testcase0001?lang=en");
    await expect(page.getByRole("button", { name: /run the inquiry again/i }).first()).toBeVisible();
    await expect(page.locator("body")).toContainText("stopped before it was sealed");
    await expect(page.locator("body")).not.toContainText("may still change");
  });

  test("a next re-check shows only when a real action is behind it", async ({ page }) => {
    const ev = { ...evidence(), deadlines: [{ type: "recheck", due_at: "2026-11-05T00:00:00Z", basis: "sentinel-2-revisit", status: "open" }] };
    await serve(page, envelope({ actions: [] }, ev));
    await page.goto("/case/testcase0001?lang=en");
    await expect(page.locator(".verdict-side")).not.toContainText("Next re-check");
    await page.unrouteAll();
    await serve(page, envelope({ actions: [{ id: "a", type: "recheck", status: "open", due_at: "2026-11-05T00:00:00Z", payload: {} }] }, ev));
    await page.reload();
    await expect(page.locator(".verdict-side")).toContainText("Next re-check");
  });

  test("an old event says no re-check will run", async ({ page }) => {
    await serve(page, envelope({ recheck_closed: true, actions: [] }));
    await page.goto("/case/testcase0001?lang=en");
    await expect(page.locator(".verdict-side")).toContainText("No re-check will run");
  });

  test("sealed numbers show labels, never the internal name; news is labelled related reports", async ({ page }) => {
    const ev = { ...evidence(), news: [{ title: "A report", url: "https://news.example/a" }],
                 replay: { ...(evidence() as unknown as { replay: object }).replay, numbers: { "village.lottery.average_median": -0.08 } } };
    await serve(page, envelope({}, ev));
    await page.goto("/case/testcase0001?lang=en");
    await page.getByText(/Sealed numbers/).click();
    const body = await page.locator("body").innerText();
    expect(body).not.toContain("lottery");
    expect(body).toContain("village.ten_field_draw.average_median");
    expect(body).toContain("Related reports");
    expect(body).toContain("do not change the result");
  });

  test("a rate limit shows the server's message in the reader's language", async ({ page }) => {
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname.endsWith("/investigate")) {
        return r.fulfill({ status: 429, headers: { "retry-after": "60" }, json: { detail: { code: "rate_limited", message_hi: "हिंदी सीमा", message_en: "english limit", message_te: "తెలుగు పరిమితి" } } });
      }
      if (u.pathname === "/api/health") return r.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
      return r.fulfill({ json: envelope({}, { ...evidence(), evidence_hash: null }) });
    });
    await page.goto("/case/testcase0001?lang=te");
    await page.locator("button", { hasText: /మళ్ళీ/ }).first().click();
    await expect(page.locator("[role=alert]").first()).toContainText("తెలుగు పరిమితి");
  });

  test("the verify page says what was recomputed, and shows a 429 once", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname.startsWith("/api/verify/")) {
        calls += 1;
        return r.fulfill({ status: 429, json: { detail: { code: "rate_limited", message_en: "english limit", message_hi: "हिंदी सीमा", message_te: "తెలుగు" } } });
      }
      return r.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    });
    await page.goto(`/verify/${"ab".repeat(32)}?lang=en`);
    await expect(page.locator(".verify-scope")).toContainText("Satellite numbers are recomputed; the verdict and weather are checked for tampering only.");
    await expect(page.getByRole("alert")).toContainText("english limit");
    await page.waitForTimeout(1500);
    expect(calls).toBe(1);
  });

  test("radar says last 72 hours, not now, and labels a thunder-only cell", async ({ page }) => {
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/radar") return r.fulfill({ json: { source: "s", cells: [{ name: "Sirsa", state: "Haryana", lat: 29.5, lon: 75, hours_left: 20, precip_mm: 1, heavy_date: "2026-10-30", signal: "thunder_code" }] } });
      return r.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    });
    await page.goto("/radar?lang=en");
    await expect(page.locator(".radar")).toContainText("last 72 hours");
    await expect(page.locator(".radar table")).toContainText("Thunder code only");
    await expect(page.locator(".radar h1")).not.toContainText("active");
  });

  test("a failed run shows no raw exception text", async ({ page }) => {
    const events = [
      { seq: 1, run_id: "r1", ts: "2026-11-01T00:00:00Z", type: "error", node: "runner", title_hi: "रुकी", title_en: "The investigation stopped unexpectedly. (ref abc)", detail: { error_ref: "abc" } },
      { seq: 2, run_id: "r1", ts: "2026-11-01T00:00:01Z", type: "done", node: "runner", title_hi: "समाप्त", title_en: "Investigation ended", detail: { status: "failed" } },
    ];
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      if (u.pathname === "/api/runs/r1/stream") return r.fulfill({ contentType: "text/event-stream", body: events.map((e) => `id: ${e.seq}\ndata: ${JSON.stringify(e)}\n\n`).join("") });
      return r.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    });
    await page.goto("/case/c1/investigate?run=r1&lang=en");
    const end = page.locator(".trace-end");
    await expect(end).toContainText("(ref abc)", { timeout: 15000 });
    await expect(end).not.toContainText("Traceback");
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

test.describe("verdict first, exhibits later", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  const shell = (over: object, env: object) => async (route: Route) => {
    const u = new URL(route.request().url());
    if (u.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    if (u.pathname.match(/^\/api\/cases\/[^/]+$/)) {
      const e = evidence(over);
      return route.fulfill({ json: { case: { id: "c", lat: 29.5, lon: 75, active_run_id: null, latest_run: { id: "r", status: "done", started_at: new Date(Date.now() - 200000).toISOString() } }, evidence: e, actions: [], sealed: true, verdict_ready: true, exhibits: {}, rubric: { version: "v3", p_field: 0.025, strong_delta: -0.15, moderate_delta: -0.1 }, ...env } });
    }
    if (u.pathname.includes("/retry")) return route.fulfill({ json: { run_id: "r2", exhibit: "village", status: "pending" } });
    if (u.pathname.startsWith("/api/artifacts/")) return route.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
    return route.fulfill({ status: 404, json: { detail: "x" } });
  };

  test("pending and failed exhibits say so, and retry is offered", async ({ page }) => {
    const retries: string[] = [];
    page.on("request", (r) => { if (r.url().includes("/retry")) retries.push(r.url()); });
    await page.route("**/api/**", shell({ scale_fade: null, village: null, chips: [] }, {
      sealed: true,
      exhibits: { scale_fade: { status: "pending" }, village: { status: "failed", reason: "not finished within 600 s" }, chips: { status: "not_applicable", reason: "no pair" }, timeline: { status: "done" } },
    }));
    await page.goto("/case/c");
    await expect(page.locator(".computing")).toHaveCount(1);
    await expect(page.locator(".activity")).toBeVisible();
    const retry = page.locator(".signature").nth(2).getByRole("button", { name: /फिर कोशिश/ });
    await expect(retry).toBeVisible();
    await retry.click();
    await expect.poll(() => retries.length).toBe(1);
    await page.screenshot({ path: `${SHOTS}/exhibits-states-d.png`, fullPage: true });
  });

  test("a provisional insufficient never reads as a finding", async ({ page }) => {
    const base = evidence();
    await page.route("**/api/**", shell(
      { evidence_hash: null, verdict: { ...base.verdict, level: "insufficient", headline_hi: "अभी पक्की बात कहने लायक सबूत नहीं हैं", headline_en: "Not enough evidence" } },
      { sealed: false, exhibits: { chips: { status: "pending" } }, case: { id: "c", lat: 29.5, lon: 75, active_run_id: "r", latest_run: { id: "r", status: "running", started_at: new Date(Date.now() - 90000).toISOString() } } },
    ));
    await page.goto("/case/c");
    await expect(page.getByRole("heading", { name: "अभी नतीजा बन रहा है" })).toBeVisible();
    await expect(page.getByText("अभी पक्की बात कहने लायक सबूत नहीं हैं")).toHaveCount(0);
    await expect(page.locator(".testimony")).toHaveCount(0);
  });

  test("a null affected-only scenario gives its reason, and all-cropland numbers stay", async ({ page }) => {
    const base = evidence();
    const v = base.village as { lottery: Record<string, unknown> };
    await page.route("**/api/**", shell({ village: { ...base.village, lottery: { ...v.lottery, affected_only_median: null, affected_only_p05: null, affected_only_p95: null, affected_only_n_candidates: 3, affected_only_reason: "Only 3 parcels dropped past the threshold." } } }, {}));
    await page.goto("/case/c?lang=en");
    await expect(page.getByText("Only 3 parcels dropped past the threshold.")).toBeVisible();
    await expect(page.locator(".scen").first().locator(".scen-nums")).toBeVisible();
    await expect(page.getByText("These two are bounds, not an estimate.", { exact: false })).toBeVisible();
    await expect(page.getByText("nobody outside the insurer can see that list", { exact: false })).toBeVisible();
    const text = (await page.locator("body").innerText()).toLowerCase();
    expect(text).not.toContain("unfair");
    expect(text).not.toContain("lottery");
  });

  test("the plain reading follows the values: holds, fades, none", async ({ page }) => {
    const base = evidence();
    const fadeWith = (vals: number[]) => ({ ...base.scale_fade, levels: [10, 100, 500, 1000, 3000].map((b, i) => ({ block_m: b, plot_cell_value: vals[i], context_min: null, chip_path: `test/fade_${b}.png` })) });
    await page.route("**/api/**", shell({ scale_fade: fadeWith([-0.1275, -0.1233, -0.1196, -0.13, -0.0811]) }, {}));
    await page.goto("/case/c?lang=en");
    await expect(page.getByText("of this field's change remains, so a coarse average still shows most of it", { exact: false })).toBeAttached();
    await page.unroute("**/api/**");
    await page.route("**/api/**", shell({ scale_fade: fadeWith([-0.4372, -0.3518, -0.2667, -0.1635, -0.0983]) }, {}));
    await page.goto("/case/c?lang=en");
    await expect(page.getByText("only 22% of this field's change remains", { exact: false })).toBeAttached();
    await page.unroute("**/api/**");
    await page.route("**/api/**", shell({ scale_fade: fadeWith([0.0087, 0.0205, 0.0199, 0.0167, 0.0088]) }, {}));
    await page.goto("/case/c?lang=en");
    await expect(page.getByText("This field shows no real fall", { exact: false })).toBeAttached();
  });
});

test.describe("staged verify", () => {
  test.use({ viewport: { width: 360, height: 780 } });
  const hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
  const sseSeq = (events: object[]) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const R = "run1";
  const numbers = { "optical.pre.ndvi_median": 0.75, "optical.post.ndvi_median": 0.39, "village.lottery.average_median": -0.08 };
  const startEv = { type: "start", seq: 1, run_id: R, hash, hash_verified: true, engine_version: "t", event_date: "2024-03-02", seed: 1, n_numbers: 3, tolerance: 0.001, numbers, started_at: new Date().toISOString(), cached: false };
  const head = [
    startEv,
    { type: "group_started", seq: 2, run_id: R, group: "field_pre", n_numbers: 1, budget_s: 180 },
    { type: "number", seq: 3, run_id: R, group: "field_pre", field: "optical.pre.ndvi_median", label: "optical.pre.ndvi_median", stored: 0.75, recomputed: 0.75, match: true },
    { type: "group_done", seq: 4, run_id: R, group: "field_pre", n_numbers: 1, elapsed_s: 8 },
    { type: "group_started", seq: 5, run_id: R, group: "field_post", n_numbers: 1, budget_s: 180 },
    { type: "number", seq: 6, run_id: R, group: "field_post", field: "optical.post.ndvi_median", label: "optical.post.ndvi_median", stored: 0.39, recomputed: 0.39, match: true },
    { type: "group_done", seq: 7, run_id: R, group: "field_post", n_numbers: 1, elapsed_s: 4 },
    { type: "stage_result", seq: 8, run_id: R, stage: "field", status: "field_verified", matched: 2, total: 2, remaining: 1, message_en: "x", message_hi: "x" },
    { type: "group_started", seq: 9, run_id: R, group: "far_twin", n_numbers: 1, budget_s: 600 },
  ];
  const health = (route: Route) => route.fulfill({ json: { status: "ok", gemini: true, version: "t" } });

  test("the field stage never reads as verified, and resumes with after", async ({ page }) => {
    const urls: string[] = [];
    let n = 0;
    await page.route("**/api/health", health);
    await page.route("**/api/verify/**", (route) => {
      urls.push(route.request().url());
      n += 1;
      if (n === 1) return route.fulfill({ status: 200, contentType: "text/event-stream", body: sseSeq(head) });
      if (n === 2) return route.fulfill({ status: 200, contentType: "text/event-stream", body: "" });
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: sseSeq([
        { type: "group_failed", seq: 10, run_id: R, group: "far_twin", n_numbers: 1, reason: "time limit reached", fields: ["village.lottery.average_median"] },
        { type: "result", seq: 11, run_id: R, status: "field_verified", ok: false, field_verified: true, checked: 2, matched: 2, total: 3, unchecked: ["village.lottery.average_median"], errors: { far_twin: "time limit" } },
      ]) });
    });
    await page.goto(`/verify/${hash}`);
    await expect(page.getByText("आपके खेत की 2 में से 2 संख्याएँ मेल खाती हैं")).toBeVisible();
    await expect(page.getByText("आस-पास की बाकी 1 संख्याओं की जाँच अभी चल रही है")).toBeVisible();
    await expect(page.getByText("आप यह पन्ना बंद कर सकते हैं।")).toBeVisible();
    await expect(page.getByText("सत्यापित")).toHaveCount(0);
    await page.screenshot({ path: `${SHOTS}/verify-stage-m.png`, fullPage: true });
    await expect(page.locator(".verify-line")).toBeVisible({ timeout: 20000 });
    expect(urls[1]).toContain("after=9");
    await expect(page.getByText("सत्यापित")).toHaveCount(0);
    await expect(page.locator(".verify-line")).toContainText("यह पूरी जाँच नहीं है");
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("lottery");
    await page.screenshot({ path: `${SHOTS}/verify-field-final-m.png`, fullPage: true });
    // A check that ended short is remembered, so coming back does not start a download.
    const before = urls.length;
    await page.reload();
    await expect(page.locator(".verify-line")).toBeVisible();
    await page.waitForTimeout(300);
    expect(urls.slice(before).every((u) => u.includes("after=") && !u.includes("rerun"))).toBe(true);
  });

  test("a stored check is labelled as one, and only the button reruns", async ({ page }) => {
    const urls: string[] = [];
    const stamp = { cached: true, checked_at: "2026-10-31T19:13:47Z", rerun: "?rerun=1" };
    await page.route("**/api/health", health);
    await page.route("**/api/verify/**", (route) => {
      urls.push(route.request().url());
      if (route.request().url().includes("rerun=1")) return route.fulfill({ status: 200, contentType: "text/event-stream", body: sseSeq(head) });
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: sseSeq([
        { ...startEv, ...stamp },
        { type: "number", seq: 3, run_id: R, field: "optical.pre.ndvi_median", label: "optical.pre.ndvi_median", stored: 0.75, recomputed: 0.75, match: true },
        { type: "result", seq: 4, run_id: R, status: "verified", ok: true, checked: 1, matched: 1, total: 1, ...stamp },
      ]) });
    });
    await page.goto(`/verify/${hash}`);
    await expect(page.locator(".stored-check")).toContainText("2026");
    await expect(page.getByText("पिछली पूरी जाँच का रिकॉर्ड")).toBeVisible();
    await expect(page.locator(".verify-line")).toBeVisible();
    expect(urls.length).toBe(1);
    expect(urls[0]).not.toContain("rerun");
    await page.getByRole("button", { name: /संग्रह से अभी दोबारा जाँचें/ }).click();
    await expect(page.getByText("आपके खेत की 2 में से 2 संख्याएँ मेल खाती हैं")).toBeVisible();
    expect(urls[1]).toContain("rerun=1");
    await expect(page.locator(".stored-check")).toHaveCount(0);
  });

  test("without a rubric threshold the two answers are not guessed", async ({ page }) => {
    await page.route("**/api/**", (route) => {
      const u = new URL(route.request().url());
      if (u.pathname === "/api/health") return health(route);
      if (u.pathname.startsWith("/api/artifacts/")) return route.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
      return route.fulfill({ json: { case: { id: "c", lat: 1, lon: 1, active_run_id: null }, evidence: evidence(), actions: [], sealed: true, exhibits: {} } });
    });
    await page.goto("/case/c?lang=en");
    await expect(page.locator(".two-q").getByText("did not arrive from the server", { exact: false })).toBeVisible();
    await expect(page.locator(".tq-a")).toHaveCount(0);
  });
});

test.describe("selection note from the server", () => {
  const note = { kind: "strongest", hi: "यह खेत एक स्कैन से चुना गया है: 200 में सबसे ज़्यादा। यह आम खेत नहीं है।", te: "స్కాన్ నుంచి ఎంచుకున్నాం.", en: "This plot was picked from a scan: the strongest of 200 random plots scanned in this area. It is not a typical field." };
  const envelope = (selection_note: object | null) => async (route: Route) => {
    const u = new URL(route.request().url());
    if (u.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    if (u.pathname.startsWith("/api/artifacts/")) return route.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
    const ev = evidence();
    return route.fulfill({ json: { case: { id: "c", lat: 29.5, lon: 75, active_run_id: null, plot: { geometry: ev.plot.geometry, area_ha: 1, centroid: ev.plot.centroid, crs: "EPSG:32643", warnings: [] } }, evidence: ev, actions: [], sealed: true, exhibits: {}, selection_note, rubric: { version: "v3", p_field: 0.025, strong_delta: -0.15, moderate_delta: -0.1 } } });
  };

  test("it comes first, and on the footprint, the answers, the Vanishing and the Draw", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.route("**/api/**", envelope(note));
    await page.goto("/case/c");
    const top = page.locator(".selected-note-top");
    await expect(top).toHaveText(note.hi);
    const noteY = (await top.boundingBox())!.y;
    const testimony = page.locator(".testimony, .tst, [class*=testimony]").first();
    await expect(testimony).toBeVisible();
    expect(noteY).toBeLessThan((await testimony.boundingBox())!.y);
    for (const id of ["foot-t", "van-t", "draw-t"]) {
      await expect(page.locator(`section:has(#${id}) .selected-note`).first()).toHaveText(note.hi);
    }
    await expect(page.locator(".foot-answers .selected-note")).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 900 });
    // Side by side, the note above the two columns covers both.
    await expect(page.locator(".foot-answers .selected-note")).toBeHidden();
    await expect(page.locator("section:has(#foot-t) > .selected-note")).toBeVisible();
  });

  test("a plot not chosen from a scan shows none", async ({ page }) => {
    await page.route("**/api/**", envelope(null));
    await page.goto("/case/c");
    await expect(page.locator(".verdict-headline")).toBeVisible();
    await expect(page.locator(".selected-note")).toHaveCount(0);
  });
});

test.describe("language in the headline area and on the Action screen", () => {
  const shell = (over: object) => async (route: Route) => {
    const u = new URL(route.request().url());
    if (u.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    if (u.pathname.startsWith("/api/artifacts/")) return route.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
    const ev = evidence(over);
    return route.fulfill({ json: { case: { id: "c", lat: 29.5, lon: 75, active_run_id: null }, evidence: ev, actions: [], sealed: true, exhibits: {} } });
  };

  test("the crop is named in Hindi, and an English clause says it is English", async ({ page }) => {
    const ev = evidence();
    await page.route("**/api/**", shell({ event: { ...ev.event, crop: "wheat" } }));
    await page.goto("/case/c");
    await expect(page.locator(".file-facts")).toContainText("गेहूँ");
    await expect(page.locator(".file-facts")).not.toContainText("wheat");
    await page.goto("/case/c/action");
    await expect(page.locator(".clause-lang").first()).toHaveText("मूल पाठ, अंग्रेज़ी में");
  });

  test("a corroboration reason has no English source name in Hindi", async ({ page }) => {
    const ev = evidence();
    await page.route("**/api/**", shell({ verdict: { ...ev.verdict, caveats: [], reasons: ["corroborated by weather, official_alert"] } }));
    await page.goto("/case/c");
    await expect(page.locator(".why-grid")).toContainText("मौसम मॉडल, सरकारी चेतावनी से पुष्टि");
    await expect(page.locator(".why-grid")).not.toContainText("weather");
  });

  test("the stored crop route has its own label in every language", async ({ page }) => {
    const ev = evidence();
    await page.route("**/api/**", shell({ claim_path: { ...ev.claim_path, route: "outside_cover", crop_stage: "harvested_stored", intimation: "unknown", countdown_applies: false } }));
    await page.goto("/case/c/action");
    await expect(page.locator(".path-route")).toHaveText("खेत से हटाई गई फ़सल: कवर से बाहर");
    await expect(page.locator(".path-route")).not.toContainText("route.");
  });
});

test.describe("a record from another engine version", () => {
  const hash = "c".repeat(64);
  const R = "run-e";
  const body = (msgs: object[]) => msgs.map((m) => `data: ${JSON.stringify(m)}\n\n`).join("");
  const start = { type: "start", seq: 1, run_id: R, hash, hash_verified: true, engine_version: "old", event_date: "2024-03-03", n_numbers: 1, numbers: { "optical.plot_delta_ndvi": -0.37 }, tolerance: 0.001, cached: false };
  const row = { type: "number", seq: 3, run_id: R, field: "optical.plot_delta_ndvi", label: "optical.plot_delta_ndvi", stored: -0.37, recomputed: -0.31, match: false };
  const health = (route: Route) => route.fulfill({ json: { status: "ok", gemini: true, version: "t" } });

  test("a difference is not called a mismatch when the engine changed", async ({ page }) => {
    await page.route("**/api/health", health);
    await page.route("**/api/verify/**", (r) => r.fulfill({ status: 200, contentType: "text/event-stream", body: body([
      start,
      { type: "note", seq: 2, run_id: R, kind: "engine_version_differs", message_en: "sealed by a different engine", message_hi: "इंजन के दूसरे संस्करण से बना" },
      row,
      { type: "result", seq: 4, run_id: R, status: "engine_changed", ok: false, checked: 1, matched: 0, total: 1, mismatched: ["optical.plot_delta_ndvi"], message_en: "This record was sealed by an earlier engine version", message_hi: "यह रिकॉर्ड इंजन के पहले के संस्करण से बना था", message_te: "ఈ రికార్డు ఇంజిన్ పాత వెర్షన్‌తో" },
    ]) }));
    await page.goto(`/verify/${hash}`);
    const line = page.locator(".verify-engine");
    await expect(line).toBeVisible({ timeout: 20000 });
    await expect(line).toContainText("इंजन बदला है");
    await expect(line).toContainText("यह रिकॉर्ड इंजन के पहले के संस्करण से बना था");
    await expect(page.locator(".verify-bad")).toHaveCount(0);
    await expect(page.locator(".v-bad")).toHaveCount(0);
    await expect(page.locator(".v-diff").first()).toHaveText("अलग");
  });

  test("the same difference under the same engine stays a mismatch", async ({ page }) => {
    await page.route("**/api/health", health);
    await page.route("**/api/verify/**", (r) => r.fulfill({ status: 200, contentType: "text/event-stream", body: body([
      start, row,
      { type: "result", seq: 4, run_id: R, status: "mismatch", ok: false, checked: 1, matched: 0, total: 1, mismatched: ["optical.plot_delta_ndvi"] },
    ]) }));
    await page.goto(`/verify/${hash}`);
    await expect(page.locator(".verify-bad")).toBeVisible({ timeout: 20000 });
    await expect(page.locator(".verify-engine")).toHaveCount(0);
    await expect(page.locator(".v-bad").first()).toBeVisible();
  });
});

test.describe("an answer near the threshold", () => {
  const withP = (far: number, ring: number, decides: boolean) => async (route: Route) => {
    const u = new URL(route.request().url());
    if (u.pathname === "/api/health") return route.fulfill({ json: { status: "ok", gemini: false, version: "t" } });
    if (u.pathname.startsWith("/api/artifacts/")) return route.fulfill({ contentType: "image/png", body: testPng(8, 170, 120, 90) });
    const base = evidence();
    const n = base.neighbours as Record<string, unknown> & { placebo: Record<string, unknown>; far_placebo?: Record<string, unknown> | null };
    const test_ = (p: number) => ({ ...n.placebo, p_value: p, plot_value: -0.3, placebo_median: -0.05, n_placebos: 200, n_at_least_as_extreme: 3, insufficient_reason: null });
    return route.fulfill({ json: { case: { id: "c", lat: 29.5, lon: 75, active_run_id: null }, sealed: true, exhibits: {}, actions: [],
      evidence: { ...base, neighbours: { ...n, placebo: test_(ring), far_placebo: test_(far) } },
      rubric: { version: "v3", p_field: 0.025, near_low: 0.01, near_high: 0.075, near_line_decides: decides } } });
  };

  test("the extreme example: far is plain yes, ring is near, and the level does not turn on it", async ({ page }) => {
    await page.route("**/api/**", withP(0.005, 0.035, false));
    await page.goto("/case/c");
    await expect(page.locator(".tq").nth(0).locator(".tq-a")).toHaveText("हाँ");
    await expect(page.locator(".tq").nth(1).locator(".tq-a")).toHaveText("नहीं, पर सीमा के पास");
    await expect(page.locator(".tq-near-note")).toHaveCount(0);
  });

  test("the typical example: far near and deciding, ring plain no", async ({ page }) => {
    await page.route("**/api/**", withP(0.054, 0.202, true));
    await page.goto("/case/c?lang=en");
    await expect(page.locator(".tq").nth(0).locator(".tq-a")).toHaveText("No, but near the line");
    await expect(page.locator(".tq").nth(1).locator(".tq-a")).toHaveText("No");
    await expect(page.locator(".tq-near-note")).toContainText("a slightly different drawing of this field could change this result");
  });

  test("yes near the line has its own wording", async ({ page }) => {
    await page.route("**/api/**", withP(0.02, 0.5, true));
    await page.goto("/case/c?lang=en");
    await expect(page.locator(".tq").nth(0).locator(".tq-a")).toContainText("Yes, but near the line");
  });
});
