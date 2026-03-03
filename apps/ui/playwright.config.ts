import type { PlaywrightTestConfig } from "@playwright/test";

const config: PlaywrightTestConfig = {
  testDir: "./tests",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    headless: true,
  },
  webServer: {
    command: "next dev -p 3100 -H 127.0.0.1",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    timeout: 120_000,
  },
};

export default config;
