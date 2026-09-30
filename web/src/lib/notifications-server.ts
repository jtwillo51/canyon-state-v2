// Server-side read of the viewer's notifications (stale-referral nudges and weekly digests).
import "server-only";

import { getApi } from "@/lib/viewer";

/** The viewer's notifications, or null if nobody is chosen or they failed to load. */
export async function getNotifications() {
  const api = await getApi();
  if (!api) return null;
  const { data } = await api.GET("/notifications");
  return data ?? null;
}
