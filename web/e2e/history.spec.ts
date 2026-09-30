// The audit trail, end to end: an edit made in the UI shows up in the record's change history with who made
// it, from what, to what. (Seeded data isn't audited, so a seeded record's history starts empty.)
import { expect, test } from "@playwright/test";

import { REP, viewAs } from "./helpers";

test("an inline edit appears in the partner's change history", async ({ page, context, request }) => {
  await viewAs(context, request, REP);
  await page.goto("/partners");
  await page.getByRole("table").getByRole("link").nth(3).click();
  await page.waitForURL(/\/partners\/[0-9a-f-]{36}$/);

  const territory = `East Valley ${Date.now() % 100000}`; // unique per run
  await page.getByRole("button", { name: "Edit territory" }).click();
  await page.getByLabel("Territory").fill(territory);
  await page.getByLabel("Territory").press("Enter");
  await expect(page.getByText(territory)).toBeVisible();

  await page.reload();
  await page.getByText("Change history").click(); // collapsed by default
  const latest = page.locator("details ol > li").first();
  await expect(latest).toContainText(`${REP} changed the partner`);
  await expect(latest).toContainText(`Territory:`);
  await expect(latest).toContainText(`→ ${territory}`);
});
