import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : [
    {
      command: "..\\.venv\\Scripts\\python.exe -m uvicorn polaris.web.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      env: {
        POLARIS_WEB_DATABASE: join(tmpdir(), `polaris-web-e2e-${process.pid}.sqlite`),
        POLARIS_MAX_TOKENS: "1200",
      },
    },
    { command: "npm run dev -- --host 127.0.0.1", url: "http://127.0.0.1:5173" },
  ],
});
