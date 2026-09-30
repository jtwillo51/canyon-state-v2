// Who is viewing: the signed-in person (a session cookie), or in development and the demo, the person chosen
// in "View as". A session always wins.
import "server-only";

import { cookies } from "next/headers";

import { apiAs, apiWithSession } from "@/lib/api/client";

export const VIEWER_COOKIE = "dev_user";

/**
 * The session token's cookie. In production the __Host- prefix makes the browser enforce the safest form:
 * HTTPS only, this exact host (no subdomains), whole site. httpOnly keeps it away from page JavaScript.
 */
export const SESSION_COOKIE = process.env.NODE_ENV === "production" ? "__Host-session" : "session";

export async function getViewerId(): Promise<string | null> {
  return (await cookies()).get(VIEWER_COOKIE)?.value ?? null;
}

export async function getSessionToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

/** An API client acting as the current viewer, or null if nobody is signed in or chosen. */
export async function getApi() {
  const token = await getSessionToken();
  if (token) return apiWithSession(token);
  const id = await getViewerId();
  return id ? apiAs(id) : null;
}

/** Keep the session token in its cookie until the session's own expiry. */
export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  const jar = await cookies();
  jar.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax", // sent on normal navigation to the site, not on cross-site form posts
    path: "/",
    expires: new Date(expiresAt),
  });
  jar.delete(VIEWER_COOKIE); // a real session replaces any "View as" choice
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}
