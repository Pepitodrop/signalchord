import {test, expect} from "@playwright/test";
import {clearMailpit, waitForVerificationLink, waitForMessageCount} from "./helpers/mailpit";
import {seedAlert} from "./helpers/alerts";

const BETA_ACCESS_CODE = process.env.BETA_ACCESS_CODE ?? "signalchord-local-beta-code";

test.beforeEach(async () => {
  await clearMailpit();
});

test("alert feed shows honest framing, and an opted-in preference receives exactly one email per qualifying alert", async ({page}) => {
  const email = `alert-feed-${Date.now()}@example.com`;
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
  const organizationCreated = page.waitForResponse(response =>
    response.url().includes("/api/v1/organizations") && response.request().method() === "POST");
  await page.getByLabel("Workspace name").fill("Alert Feed Research");
  await page.getByRole("button", {name: "Create workspace"}).click();
  const organizationBody = (await (await organizationCreated).json()) as {id: string};
  const tenantId = organizationBody.id;

  await expect(page.getByText("Add your first watchlist.")).toBeVisible();
  await page.getByLabel("Watchlist name").fill("Explainability check");
  await page.getByLabel("What are you watching?").selectOption("entity");
  await page.getByLabel("Stable entity or topic ID").fill("company:acme");
  await page.getByRole("button", {name: "Create watchlist"}).click();
  await expect(page.getByText("Watchlist created.")).toBeVisible();
  await page.getByRole("button", {name: "Continue to dashboard"}).click();

  // Seed a real alert (no watchlist linkage exists in the pipeline today — see
  // TODOS.md — so this is an org-scoped alert, not filtered to the watchlist
  // just created).
  await seedAlert(tenantId, {stableId: "e2e-alert-before-optin", title: "Signal before opt-in"});

  await page.getByRole("button", {name: "Alerts"}).click();
  await page.getByRole("button", {name: /Signal before opt-in/}).click();

  // Honest framing: real prioritization score/severity, policy fallback (no
  // watchlist->policy link exists), evidence shown as a disclosed limitation,
  // never a confidence percentage.
  await expect(page.getByText("Prioritization score 75")).toBeVisible();
  await expect(page.getByText("Not linked to a specific policy.")).toBeVisible();
  await expect(page.getByText("2 evidence records referenced.")).toBeVisible();
  await expect(page.getByText("Raw evidence references (IDs only — content lookup not yet available)")).toBeVisible();
  await expect(page.getByText(/confidence/i)).toHaveCount(0);

  // No email should have gone out yet — the preference defaults to off.
  await waitForMessageCount(email, "New SignalChord alert", 0);

  // Opt in (sidebar footer instance at desktop viewport; .first() resolves
  // the ambiguity with the hidden mobile-header duplicate).
  await page.getByRole("button", {name: "Email alerts: Off"}).first().click();
  await expect(page.getByRole("button", {name: "Email alerts: On"}).first()).toBeVisible();

  // A new qualifying alert after opting in triggers exactly one email.
  await seedAlert(tenantId, {stableId: "e2e-alert-after-optin", title: "Signal after opt-in"});
  await waitForMessageCount(email, "New SignalChord alert: Signal after opt-in", 1);

  // A suppressed alert never triggers a notification, even opted in.
  await seedAlert(tenantId, {stableId: "e2e-alert-suppressed", title: "Suppressed signal", suppressed: true});
  await waitForMessageCount(email, "New SignalChord alert: Suppressed signal", 0);
});
