// Server-side reads for progress: the numbers and the viewer's display preferences.
import "server-only";

import { cookies } from "next/headers";

import { COLLAPSED_COOKIE, COMPARE_COOKIE, type Compare } from "@/lib/progress";
import { getApi } from "@/lib/viewer";

export async function getProgressPrefs(): Promise<{ compare: Compare; collapsed: boolean }> {
  const jar = await cookies();
  return {
    compare: jar.get(COMPARE_COOKIE)?.value === "team" ? "team" : "self",
    collapsed: jar.get(COLLAPSED_COOKIE)?.value === "1",
  };
}

/** This month's progress for the current viewer, or null if nobody is chosen or it failed to load. */
export async function getProgress() {
  const api = await getApi();
  if (!api) return null;
  const { data } = await api.GET("/progress");
  return data ?? null;
}
