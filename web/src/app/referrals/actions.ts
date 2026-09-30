"use server";
// Saved views. Public endpoints like every Server Action; the API makes views private to their owner.

import { refresh } from "next/cache";

import { getApi } from "@/lib/viewer";

export type ViewResult = { ok: true } | { ok: false; message: string };

export async function saveView(name: string, query: string): Promise<ViewResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Choose a person in View as first." };
  const { error, response } = await api.POST("/views", { body: { list: "referrals", name, query } });
  if (response.ok) {
    refresh();
    return { ok: true };
  }
  if (error && "message" in error) return { ok: false, message: error.message };
  return { ok: false, message: "Couldn't save that view. Names can be up to 60 characters." };
}

export async function deleteView(id: string): Promise<void> {
  const api = await getApi();
  if (!api) return;
  await api.DELETE("/views/{view_id}", { params: { path: { view_id: id } } });
  refresh();
}
