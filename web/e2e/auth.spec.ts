// Real sign-in, end to end: an admin adds a person, the person sets their password through the one-time link,
// signs out, fails with a wrong password, and signs back in. Plus: an ended session goes back to sign-in, and
// reps never see the Team page.
import { expect, test } from "@playwright/test";

import { ADMIN, REP, viewAs } from "./helpers";

const PASSWORD = "copper kettle midnight harbor";

test("a new person sets their password through a one-time link and signs in", async ({ page, context, request, browser }) => {
  const email = `new.person.${Date.now()}@example.com`;

  // The admin adds them and gets the link (shown once).
  await viewAs(context, request, ADMIN);
  await page.goto("/team");
  await page.getByLabel("Name").fill("Casey Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Add and make link" }).click();
  const link = await page.getByLabel("One-time link").inputValue();
  expect(link).toMatch(/\/set-password#token=[\w-]{40,}$/); // the token rides in the #fragment
  await expect(page.getByRole("row", { name: /Casey Tester/ })).toContainText("Waiting to set a password");

  // The new person, in their own browser.
  const theirs = await browser.newContext();
  const them = await theirs.newPage();
  await them.goto(link);
  await expect(them.getByRole("heading", { name: "Welcome, Casey" })).toBeVisible();
  expect(them.url()).not.toContain("token="); // dropped from the address bar once read

  await them.getByLabel("New password").fill("casey tester password");
  await them.getByLabel("Type it again").fill("casey tester password");
  await them.getByRole("button", { name: "Set password and sign in" }).click();
  await expect(them.getByRole("main").getByRole("alert")).toContainText("name or email"); // the API's reason, next to the field

  await them.getByLabel("New password").fill(PASSWORD);
  await them.getByLabel("Type it again").fill(PASSWORD);
  await them.getByRole("button", { name: "Set password and sign in" }).click();
  await them.waitForURL("**/dashboard");
  await expect(them.getByRole("link", { name: "Casey Tester" })).toBeVisible(); // signed in, their name in the header

  // Signing out, a wrong password, and back in.
  await them.getByRole("button", { name: "Sign out" }).click();
  await them.waitForURL("**/sign-in");
  await them.getByLabel("Email").fill(email);
  await them.getByLabel("Password").fill("not the right password at all");
  await them.getByRole("button", { name: "Sign in" }).click();
  await expect(them.getByRole("main").getByRole("alert")).toHaveText("That email and password don't match. Check both and try again.");
  await them.getByLabel("Password").fill(PASSWORD);
  await them.getByRole("button", { name: "Sign in" }).click();
  await them.waitForURL("**/dashboard");

  // The link was single-use.
  await them.goto(link);
  await expect(them.getByRole("heading", { name: "This link doesn't work" })).toBeVisible();
  await theirs.close();
});

test("an ended session sends you back to sign in", async ({ page, context }) => {
  await context.clearCookies();
  await context.addCookies([{ name: "session", value: "a-session-that-no-longer-exists-000000000000", url: "http://localhost:3100" }]);
  await page.goto("/dashboard");
  await page.waitForURL("**/sign-in?expired=1");
  await expect(page.getByText("Your session ended.")).toBeVisible();
});

test("reps never see the Team page", async ({ page, context, request }) => {
  await viewAs(context, request, REP);
  await page.goto("/dashboard");
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Team" })).toHaveCount(0);
  const res = await page.goto("/team");
  expect(res?.status()).toBe(404);
});
