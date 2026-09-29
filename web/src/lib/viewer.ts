// Who is viewing. Until Stage 3 sign-in, a development "View as" cookie holds a user id.
import "server-only";

import { cookies } from "next/headers";

import { apiAs } from "@/lib/api/client";

export const VIEWER_COOKIE = "dev_user";

export async function getViewerId(): Promise<string | null> {
  return (await cookies()).get(VIEWER_COOKIE)?.value ?? null;
}

/** An API client acting as the current viewer, or null if nobody is chosen yet. */
export async function getApi() {
  const id = await getViewerId();
  return id ? apiAs(id) : null;
}
