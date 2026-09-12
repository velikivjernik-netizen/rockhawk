import { expect, test } from "@playwright/test";

test("admin can open the demo review table", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@rockhawk.local");
  await page.getByLabel("Password").fill("ChangeMeNow!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Matters" })).toBeVisible();
  await page.getByRole("button", { name: "Load demo matter" }).click();
  await page.getByText(/Northwind/).first().click();
  await expect(page.getByText(/MSA diligence/)).toBeVisible();
});
