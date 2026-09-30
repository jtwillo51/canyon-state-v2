"use server";
// Public endpoint, like every Server Action: it only forwards to the API as the current viewer,
// and the API checks the referral, the date and the person.

import { refresh } from "next/cache";

import type { components } from "@/lib/api/schema";
import type { ActivityIn } from "@/lib/api/types";
import { getApi } from "@/lib/viewer";

/** Inline edit of line, carrier or premium. The API enforces the rules (after bind: admins only). */
export async function updateReferral(referralId: string, patch: components["schemas"]["ReferralPatch"]) {
  const api = await getApi();
  if (!api) return { ok: false as const, message: "Choose a person in View as first." };
  const { error, response } = await api.PATCH("/referrals/{referral_id}", {
    params: { path: { referral_id: referralId } },
    body: patch,
  });
  if (response.ok) {
    refresh();
    return { ok: true as const };
  }
  if (error && "message" in error) return { ok: false as const, message: error.message };
  return { ok: false as const, message: "Couldn't save that change." };
}

export type LogResult = { ok: true } | { ok: false; message: string; field?: string | null };

export async function logActivity(referralId: string, entry: ActivityIn): Promise<LogResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };

  const { error, response } = await api.POST("/referrals/{referral_id}/activities", {
    params: { path: { referral_id: referralId } },
    body: entry,
  });
  if (response.ok) {
    refresh();
    return { ok: true };
  }
  if (error && "message" in error) return { ok: false, message: error.message, field: error.field };
  if (response.status === 404) return { ok: false, message: "That referral isn't one you can see." };
  return { ok: false, message: "Couldn't save that. Check the fields and try again." };
}
