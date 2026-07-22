import {test, expect} from "@playwright/test";
import {clearMailpit} from "./helpers/mailpit";

test.beforeEach(async () => {
  await clearMailpit();
});

test("an invalid or expired verification link offers a resend path", async ({page}) => {
  await page.goto("/verify-email?token=not-a-real-token");
  await expect(page.getByText("That link didn't work")).toBeVisible();

  await page.getByLabel("Email").fill(`expired-${Date.now()}@example.com`);
  await page.getByRole("button", {name: "Resend verification email"}).click();

  // Anti-enumeration: this is the identical response whether or not the
  // account exists, so this only proves the resend UI flow works, not that a
  // real new email necessarily arrives for this specific address.
  await expect(page.getByText(/we've sent a new link/i)).toBeVisible();
});
