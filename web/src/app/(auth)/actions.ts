"use server";
// Signing in and using a one-time link. These run on the Next server: the password goes browser → Next → API
// and the session token comes back into an httpOnly cookie; page JavaScript never holds either.

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { publicApi } from "@/lib/api/client";
import { setSessionCookie } from "@/lib/viewer";

// `email` comes back with an error: React 19 resets a form after its action, and retyping it is needless.
export type FormState = { message?: string; field?: string; email?: string } | null;

/** Only paths on this site: "/pipeline" yes; "//evil.example" or "https://…" no (an open redirect). */
function safeNext(next: FormDataEntryValue | null): string {
  const path = typeof next === "string" ? next : "";
  return path.startsWith("/") && !path.startsWith("//") && !path.startsWith("/\\") ? path : "/dashboard";
}

async function userAgent(): Promise<Record<string, string>> {
  return { "User-Agent": ((await headers()).get("user-agent") ?? "").slice(0, 200) };
}

export async function signIn(_prev: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "");
  const password = String(form.get("password") ?? "");
  const { data, response } = await publicApi().POST("/auth/sign-in", { body: { email, password }, headers: await userAgent() });
  if (!data) {
    if (response.status === 429) {
      const minutes = Math.max(1, Math.ceil(Number(response.headers.get("Retry-After") ?? 60) / 60));
      return { message: `Too many attempts. Try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`, email };
    }
    const message = response.status === 401 ? "That email and password don't match. Check both and try again." : "Couldn't sign in. Try again.";
    return { message, email };
  }
  await setSessionCookie(data.token, data.expires_at);
  redirect(safeNext(form.get("next")));
}

export async function checkLink(token: string): Promise<{ ok: true; purpose: "setup" | "reset"; name: string } | { ok: false }> {
  const { data } = await publicApi().POST("/auth/links/check", { body: { token } });
  return data ? { ok: true, ...data } : { ok: false };
}

export async function redeemLink(token: string, password: string): Promise<FormState> {
  const { data, error, response } = await publicApi().POST("/auth/links/redeem", {
    body: { token, password },
    headers: await userAgent(),
  });
  if (!data) {
    if (response.status === 404) return { message: "This link has expired or has already been used. Ask an admin for a new one." };
    const e = error as { message?: string; field?: string } | undefined;
    return { message: e?.message ?? "Couldn't set your password. Try again.", field: e?.field };
  }
  await setSessionCookie(data.token, data.expires_at);
  redirect("/dashboard");
}
