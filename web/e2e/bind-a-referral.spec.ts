// The critical path: a rep drags a quoted referral to Bound on the board, confirms the bind, and it counts
// toward their clients bound this month. It changes data, so it compares its own before and after rather
// than expecting seed numbers; the other tests don't depend on what it moved.
import { expect, test } from "@playwright/test";

import { REP, apiGet, viewAs } from "./helpers";

type Progress = { reps: { clients: { value: number | null } }[] };

test("a rep binds a quoted referral and it shows in their progress", async ({ page, context, request }) => {
  const clientsBound = async () => (await apiGet<Progress>(request, REP, "/progress")).reps[0].clients.value ?? 0;
  const before = await clientsBound();

  await viewAs(context, request, REP);
  await page.goto("/pipeline");
  const quoted = page.getByRole("region", { name: /^Quoted, / });
  const bound = page.getByRole("region", { name: /^Bound, / });
  const card = quoted.getByRole("listitem").first();
  const client = (await card.getByRole("link").textContent())!.trim();

  // Drag with the mouse, in steps: the board only starts a drag after 6 px of movement.
  const from = (await card.boundingBox())!;
  const to = (await bound.boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, to.y + 80, { steps: 20 });
  await page.mouse.up();

  // Binding asks for the premium (prefilled from the quote) and the bind date (defaults to today).
  const dialog = page.getByRole("dialog", { name: `Bind: ${client}` });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Annual premium ($)")).not.toHaveValue("");
  await dialog.getByRole("button", { name: "Bind" }).click();

  await expect(bound.getByRole("link", { name: client })).toBeVisible();
  await expect(quoted.getByRole("link", { name: client })).toHaveCount(0);

  // The API counts it, and the dashboard shows the new number.
  await expect.poll(clientsBound).toBe(before + 1);
  await page.goto("/dashboard");
  await expect(page.getByRole("group", { name: "Your clients bound" }).locator("[data-value]")).toHaveText(String(before + 1));
});
