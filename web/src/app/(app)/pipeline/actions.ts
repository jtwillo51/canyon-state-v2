"use server";
// Server Actions are public endpoints: anyone can call them with any arguments. That's fine here
// because this only forwards to the API as the current viewer, and the API enforces every rule.

import { refresh } from "next/cache";

import type { components } from "@/lib/api/schema";
import { getApi } from "@/lib/viewer";

type StatusChange = components["schemas"]["StatusChange"];

export type MoveResult = { ok: true } | { ok: false; message: string; field?: string | null };

export async function moveReferral(referralId: string, change: StatusChange): Promise<MoveResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };

  const { error, response } = await api.POST("/referrals/{referral_id}/status", {
    params: { path: { referral_id: referralId } },
    body: change,
  });
  if (response.ok) {
    refresh(); // re-render the page with fresh data from the API
    return { ok: true };
  }
  if (error && "message" in error) return { ok: false, message: error.message, field: error.field };
  if (response.status === 404) return { ok: false, message: "That referral isn't one you can move." };
  return { ok: false, message: "Something went wrong. Try again." };
}
