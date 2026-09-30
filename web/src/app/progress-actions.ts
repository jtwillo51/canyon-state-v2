"use server";
// Progress preferences (per person, in cookies) and goal edits (admins; the API enforces it).

import { refresh } from "next/cache";
import { cookies } from "next/headers";

import type { SaveResult } from "@/components/inline-field";
import { COLLAPSED_COOKIE, COMPARE_COOKIE, type Compare } from "@/lib/progress";
import { getApi } from "@/lib/viewer";

const YEAR = 60 * 60 * 24 * 365;

export async function saveProgressPrefs(prefs: { compare?: Compare; collapsed?: boolean }) {
  const jar = await cookies();
  const opts = { path: "/", sameSite: "lax" as const, maxAge: YEAR, secure: process.env.NODE_ENV === "production" };
  if (prefs.compare === "self" || prefs.compare === "team") jar.set(COMPARE_COOKIE, prefs.compare, opts);
  if (typeof prefs.collapsed === "boolean") jar.set(COLLAPSED_COOKIE, prefs.collapsed ? "1" : "0", opts);
}

async function afterSave(result: { error?: unknown; response: Response }): Promise<SaveResult> {
  if (result.response.ok) {
    refresh();
    return { ok: true };
  }
  const error = result.error as { message?: string } | undefined;
  return { ok: false, message: error?.message ?? "Couldn't save that goal." };
}

export async function saveRepGoal(repId: string, clients: number, sales: number): Promise<SaveResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };
  return afterSave(await api.PUT("/goals/reps/{user_id}", { params: { path: { user_id: repId } }, body: { clients, sales } }));
}

export async function saveCloseRateGoal(percent: number | null): Promise<SaveResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };
  return afterSave(await api.PUT("/goals/company", { body: { close_rate: percent == null ? null : percent / 100 } }));
}
