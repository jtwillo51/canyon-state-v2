"use server";
// Server Actions: functions the browser can call, that run only on the server.

import { cookies } from "next/headers";

import { VIEWER_COOKIE } from "@/lib/viewer";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Development "View as": remember which user to act as. The API still checks who that is. */
export async function viewAs(formData: FormData) {
  const id = formData.get("userId");
  if (typeof id !== "string" || !UUID.test(id)) return;
  (await cookies()).set(VIEWER_COOKIE, id, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production", // HTTPS only once deployed
  });
}
