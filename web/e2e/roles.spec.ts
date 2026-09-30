// What the page offers depends on who's viewing. The API enforces every rule on its own (see
// api/tests/test_access_matrix.py); these tests check the UI agrees: admins get the admin controls, reps
// don't see them at all, and a rep can't open someone else's referral.
import { expect, test } from "@playwright/test";

import { ADMIN, OTHER_REP, REP, referralOf, viewAs } from "./helpers";

test.describe("dashboard", () => {
  test("an admin sees every rep and can edit goals", async ({ page, context, request }) => {
    await viewAs(context, request, ADMIN);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Reps" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit goal" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit target" })).toBeVisible();
  });

  test("a rep sees only their own numbers and no goal editors", async ({ page, context, request }) => {
    await viewAs(context, request, REP);
    await page.goto("/dashboard");
    await expect(page.getByRole("group", { name: "Your clients bound" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Reps" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Edit (goal|target)$/ })).toHaveCount(0);
    // No colleague's row anywhere on the page (the dev "View as" list in the header names everyone).
    await expect(page.getByRole("main").getByText(OTHER_REP)).toHaveCount(0);
  });
});

test.describe("partner page", () => {
  test("only an admin can reassign the primary rep", async ({ page, context, request }) => {
    await viewAs(context, request, ADMIN);
    await page.goto("/partners");
    await page.getByRole("table").getByRole("link").first().click();
    await page.waitForURL(/\/partners\/[0-9a-f-]{36}$/); // client-side navigation: wait for it to land
    const partnerUrl = page.url();
    await expect(page.getByRole("button", { name: "Edit primary rep" })).toBeVisible();

    await viewAs(context, request, REP);
    await page.goto(partnerUrl);
    await expect(page.getByText("(admins change this)")).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit primary rep" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Edit territory" })).toBeVisible(); // shared facts stay editable
  });
});

test.describe("bound referral", () => {
  test("its policy fields are locked for the rep and open for an admin", async ({ page, context, request }) => {
    const bound = await referralOf(request, REP, "bound");

    await viewAs(context, request, REP);
    await page.goto(`/referrals/${bound.id}`);
    await expect(page.getByRole("heading", { name: bound.client_name })).toBeVisible();
    await expect(page.getByText("(admins change bound referrals)").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /^Edit (line|carrier|premium)$/ })).toHaveCount(0);

    await viewAs(context, request, ADMIN);
    await page.goto(`/referrals/${bound.id}`);
    await expect(page.getByRole("button", { name: "Edit line" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit premium" })).toBeVisible();
  });
});

test("a rep can't open someone else's referral", async ({ page, context, request }) => {
  const theirs = await referralOf(request, OTHER_REP, "quoted");
  await viewAs(context, request, REP);
  const res = await page.goto(`/referrals/${theirs.id}`);
  expect(res?.status()).toBe(404);
  await expect(page.getByText(theirs.client_name)).toHaveCount(0);
});
