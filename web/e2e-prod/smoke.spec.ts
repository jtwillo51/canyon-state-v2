import { expect, test } from "@playwright/test";
const PAGES = ["/dashboard", "/pipeline", "/partners", "/top-partners", "/referrals", "/notifications"];
test("the demo, as a visitor would use it", async ({ page, request, browser }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  const notFound: string[] = [];
  page.on("response", (r) => { if (r.status() === 404) notFound.push(new URL(r.url()).pathname); });

  await page.goto("/");
  await expect(page.getByText("every person, partner and client here is fictional")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Who do you want to be?" })).toBeVisible();
  await page.getByRole("group", { name: "Admins" }).getByRole("button", { name: "Dana Whitfield" }).click();
  await expect(page.getByRole("heading", { name: "Reps" })).toBeVisible();
  for (const p of [...PAGES, "/team"]) {
    const res = await page.goto(p);
    expect(res?.status(), p).toBe(200);
    await expect(page.getByRole("main")).toBeVisible();
  }
  await page.goto("/referrals");
  await page.getByRole("table").getByRole("link").first().click();
  await page.waitForURL(/\/referrals\/[0-9a-f-]{36}$/);
  await page.getByText("Change history").click();

  await page.getByLabel("View as").selectOption({ label: "Jordan Pike" });
  await expect(page.getByText("Your clients bound").first()).toBeVisible(); // the switch has taken effect
  await page.goto("/dashboard");
  await expect(page.getByRole("group", { name: "Your clients bound" })).toBeVisible();
  for (const p of PAGES) expect((await page.goto(p))?.status(), p).toBe(200);
  expect((await page.goto("/team"))?.status()).toBe(404);

  // Real sign-in in production mode: the __Host- cookie must be set and work.
  const users = await (await request.get("http://localhost:8300/dev/users")).json();
  const dana = users.find((u: { name: string }) => u.name === "Dana Whitfield").id;
  const created = await (await request.post("http://localhost:8300/team", { headers: { "X-Dev-User": dana },
    data: { name: "Prod Check", email: `prod.check.${Date.now()}@example.com`, role: "rep" } })).json();
  const fresh = await browser.newContext();
  const p2 = await fresh.newPage();
  p2.on("pageerror", (e) => errors.push(String(e)));
  await p2.goto(`/set-password#token=${created.link.token}`);
  await p2.getByLabel("New password").fill("copper kettle midnight harbor");
  await p2.getByLabel("Type it again").fill("copper kettle midnight harbor");
  await p2.getByRole("button", { name: "Set password and sign in" }).click();
  await p2.waitForURL("**/dashboard");
  const cookies = await fresh.cookies();
  const session = cookies.find((c) => c.name === "__Host-session");
  expect(session?.httpOnly && session.secure && session.sameSite === "Lax").toBeTruthy();
  await expect(p2.getByRole("link", { name: "Prod Check" })).toBeVisible();
  await p2.getByRole("button", { name: "Sign out" }).click();
  await p2.waitForURL("**/sign-in");
  await fresh.close();

  expect(notFound).toEqual(["/team"]); // only the rep's deliberate visit: no missing pages or assets
  expect(errors.filter((e) => !e.includes("status of 404")), errors.join("\n")).toEqual([]);
});
