import {test, expect} from "@playwright/test";
import {clearMailpit, waitForVerificationLink} from "./helpers/mailpit";

const BETA_ACCESS_CODE = process.env.BETA_ACCESS_CODE ?? "signalchord-local-beta-code";

test.beforeEach(async () => {
  await clearMailpit();
});

test("signup -> verify -> login -> create workspace -> create first watchlist -> dashboard", async ({page}) => {
  const email = `beta-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Beta access code").fill(BETA_ACCESS_CODE);
  await page.getByRole("button", {name: "Sign up"}).click();
  await expect(page.getByText("Check your email")).toBeVisible();

  const verificationLink = await waitForVerificationLink(email);
  await page.goto(verificationLink);
  await expect(page.getByText("Email verified")).toBeVisible();

  await page.getByRole("link", {name: "Continue to sign in"}).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", {name: "Sign in"}).click();

  await expect(page.getByText("Name your workspace.")).toBeVisible();
  await page.getByLabel("Workspace name").fill("Acme Research");
  await page.getByRole("button", {name: "Create workspace"}).click();

  await expect(page.getByText("Add your first watchlist.")).toBeVisible();
  await page.getByLabel("Watchlist name").fill("Competitor moves");
  await page.getByRole("button", {name: "Create watchlist"}).click();

  await expect(page.getByText("Acme Research")).toBeVisible();
  await expect(page.getByRole("button", {name: "Sign out"})).toBeVisible();
});
