import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  testMatch: /.*\.spec\.ts/,
  timeout: 90_000,
  workers: 1,
  use: { baseURL: process.env.BASE_URL ?? "http://localhost:5173", channel: "chrome", headless: true, reducedMotion: "no-preference" },
});
