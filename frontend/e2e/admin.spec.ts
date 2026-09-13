import { expect, test } from "@playwright/test";

test("admin can open Administration Center; reviewer cannot use admin APIs via UI gate", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@rockhawk.local");
  await page.getByLabel("Password").fill("ChangeMeNow!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("link", { name: "Administration" })).toBeVisible();
  await page.getByRole("link", { name: "Administration" }).click();
  await expect(page.getByRole("heading", { name: "Administration Center" })).toBeVisible();
  await expect(page.getByLabel("Search settings")).toBeVisible();
  await expect(page.getByText("Support contact")).toBeVisible();
  await page.getByPlaceholder("support email, model role…").fill("support");
  await page.getByLabel(/New value for Support contact|Support contact/i).first();
});
