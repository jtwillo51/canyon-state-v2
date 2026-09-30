// Notifications: the bell's unread count, a rep's own stale nudges and digest, an admin's company digest,
// and marking read. The e2e API runs the jobs once after seeding (scripts.run_jobs), so there's data.
import { expect, test } from "@playwright/test";

import { ADMIN, OTHER_REP, REP, apiGet, viewAs } from "./helpers";

type Page = { unread: number; items: { kind: string; stale?: { client_name: string } }[] };

test("a rep sees their own nudges and digest, and can mark them read", async ({ page, context, request }) => {
  const mine = await apiGet<Page>(request, REP, "/notifications");
  const theirs = await apiGet<Page>(request, OTHER_REP, "/notifications");
  const myClients = mine.items.flatMap((n) => (n.stale ? [n.stale.client_name] : []));
  const theirClients = theirs.items.flatMap((n) => (n.stale ? [n.stale.client_name] : []));
  expect(myClients.length).toBeGreaterThan(0); // the seed always has stale referrals (dates are relative to today)

  await viewAs(context, request, REP);
  await page.goto("/dashboard");
  const bell = page.getByRole("link", { name: `Notifications, ${mine.unread} unread` });
  await expect(bell).toBeVisible();
  await bell.click();
  await page.waitForURL("**/notifications");

  const attention = page.getByRole("region", { name: "Needs attention" });
  await expect(attention.getByRole("link", { name: myClients[0] })).toBeVisible();
  for (const client of theirClients.filter((c) => !myClients.includes(c))) {
    await expect(page.getByRole("main").getByText(client, { exact: true })).toHaveCount(0); // not a colleague's
  }
  const digest = page.getByRole("article", { name: /^Weekly digest/ });
  await expect(digest.getByRole("group", { name: "Your numbers, last week" })).toBeVisible();
  await expect(digest.getByRole("table")).toHaveCount(0); // no per-rep table for a rep

  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(page.getByText("All caught up")).toBeVisible();
  await expect(page.getByRole("link", { name: "Notifications", exact: true })).toBeVisible(); // no count
});

test("an admin's digest shows the company and every rep", async ({ page, context, request }) => {
  await viewAs(context, request, ADMIN);
  await page.goto("/notifications");
  const digest = page.getByRole("article", { name: /^Weekly digest/ });
  await expect(digest.getByRole("group", { name: "Company, last week" })).toBeVisible();
  await expect(digest.getByRole("table").getByText(REP, { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs attention" }).getByRole("listitem")).toHaveCount(0); // admins aren't credited
});
