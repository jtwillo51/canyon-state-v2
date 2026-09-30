"use server";
// Marking notifications read. The API only ever touches the caller's own (someone else's id is a 404).

import { refresh } from "next/cache";

import { getApi } from "@/lib/viewer";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function markRead(id: string): Promise<void> {
  const api = await getApi();
  if (!api || !UUID.test(id)) return;
  await api.POST("/notifications/{notification_id}/read", { params: { path: { notification_id: id } } });
  refresh();
}

export async function markAllRead(): Promise<void> {
  const api = await getApi();
  if (!api) return;
  await api.POST("/notifications/read-all");
  refresh();
}
