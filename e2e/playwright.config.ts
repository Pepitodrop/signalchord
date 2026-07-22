import {defineConfig} from "@playwright/test";

// Runs against the docker-compose --profile slice stack (web on :5173,
// control-plane on :3000, Mailpit on :8025/:1025). Not runnable in a
// sandbox without Docker/Ruby — see this repo's PR description for how
// this suite was verified (written and typechecked, not locally executed
// end-to-end).
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 0,
  fullyParallel: false,
  use: {
    baseURL: process.env.PUBLIC_WEB_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
  },
});
