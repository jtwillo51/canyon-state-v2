"use server";
// Public endpoint, like every Server Action: it only forwards to the API as the current viewer,
// and the API checks the referral, the date and the person.

import { refresh } from "next/cache";

import type { ActivityIn } from "@/lib/api/types";
import { getApi } from "@/lib/viewer";

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
