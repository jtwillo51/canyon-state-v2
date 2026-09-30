// Shared steps for the e2e tests: who's viewing, and reading records straight from the API.
import type { APIRequestContext, BrowserContext } from "@playwright/test";

import { API_URL, WEB_URL } from "./env";

// From the synthetic seed (api/scripts/seed.py). Jordan and Tessa are both reps.
export const ADMIN = "Dana Whitfield";
export const REP = "Jordan Pike";
export const OTHER_REP = "Tessa Moreno";

type User = { id: string; name: string; role: "admin" | "rep" };

async function userId(request: APIRequestContext, name: string): Promise<string> {
  const users: User[] = await (await request.get(`${API_URL}/dev/users`)).json();
  const user = users.find((u) => u.name === name);
  if (!user) throw new Error(`No seeded user named ${name}`);
  return user.id;
}

/** Act as this person: the same cookie the "View as" switcher sets. The API still decides what they see. */
export async function viewAs(context: BrowserContext, request: APIRequestContext, name: string): Promise<void> {
  await context.clearCookies();
  await context.addCookies([{ name: "dev_user", value: await userId(request, name), url: WEB_URL }]);
}

/** Call the API directly as this person (to find records, or to check what the page should show). */
export async function apiGet<T>(request: APIRequestContext, name: string, path: string): Promise<T> {
  const res = await request.get(`${API_URL}${path}`, { headers: { "X-Dev-User": await userId(request, name) } });
  if (!res.ok()) throw new Error(`GET ${path} as ${name}: ${res.status()}`);
  return res.json();
}

type Page<T> = { items: T[] };
type Referral = { id: string; client_name: string };

/** A referral with this status that `name` is credited on (reps only see their own). */
export async function referralOf(request: APIRequestContext, name: string, status: string): Promise<Referral> {
  const { items } = await apiGet<Page<Referral>>(request, name, `/referrals?status=${status}&limit=1`);
  if (!items[0]) throw new Error(`${name} has no ${status} referral in the seed`);
  return items[0];
}
