"use server";
// The signed-in person's own account: signing out (here or everywhere) and changing their password.

import { redirect } from "next/navigation";

import { clearSessionCookie, getApi } from "@/lib/viewer";

export async function signOut(): Promise<void> {
  const api = await getApi();
  if (api) await api.POST("/auth/sign-out");
  await clearSessionCookie();
  redirect("/sign-in");
}

export async function signOutEverywhere(): Promise<void> {
  const api = await getApi();
  if (api) await api.POST("/auth/sign-out-everywhere");
  await clearSessionCookie();
  redirect("/sign-in");
}

export type PasswordState = { ok?: boolean; message?: string; field?: string } | null;

export async function changePassword(_prev: PasswordState, form: FormData): Promise<PasswordState> {
  const api = await getApi();
  if (!api) redirect("/sign-in");
  const { error, response } = await api.POST("/auth/password", {
    body: { current_password: String(form.get("current") ?? ""), new_password: String(form.get("new") ?? "") },
  });
  if (response.ok) return { ok: true, message: "Password changed. You've been signed out everywhere else." };
  if (response.status === 429) return { message: "Too many attempts. Try again in a few minutes." };
  const e = error as { message?: string; field?: string } | undefined;
  return { message: e?.message ?? "Couldn't change your password. Try again.", field: e?.field };
}
