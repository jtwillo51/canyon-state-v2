"use server";
// Inline edits to a partner. The API decides who may change what (primary rep: admins only).

import { refresh } from "next/cache";

import type { SaveResult } from "@/components/inline-field";
import type { components } from "@/lib/api/schema";
import { getApi } from "@/lib/viewer";

type PartnerPatch = components["schemas"]["PartnerPatch"];

export async function updatePartner(partnerId: string, patch: PartnerPatch): Promise<SaveResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };
  const { error, response } = await api.PATCH("/partners/{partner_id}", {
    params: { path: { partner_id: partnerId } },
    body: patch,
  });
  if (response.ok) {
    refresh();
    return { ok: true };
  }
  if (error && "message" in error) return { ok: false, message: error.message };
  return { ok: false, message: "Couldn't save that change." };
}
