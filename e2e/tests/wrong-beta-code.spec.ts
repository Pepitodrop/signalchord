import {test, expect} from "@playwright/test";

test("signup is blocked with an incorrect beta access code", async ({page}) => {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(`rejected-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByLabel("Beta access code").fill("definitely-wrong-code");
  await page.getByRole("button", {name: "Sign up"}).click();

  await expect(page.getByText("Check your email")).not.toBeVisible();
  await expect(page.getByText(/sign-up failed/i)).toBeVisible();
});
