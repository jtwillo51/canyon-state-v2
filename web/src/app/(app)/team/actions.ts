"use server";
// The Team page's changes. The API enforces admin-only (a 404 for anyone else); these just forward.

import { refresh } from "next/cache";
import { headers } from "next/headers";

import { getApi } from "@/lib/viewer";

export type LinkResult = { ok: true; name: string; url: string; purpose: "setup" | "reset"; expires: string } | { ok: false; message: string; field?: string };

/** The link to hand over. The token goes in the #fragment, which browsers never send to any server. */
async function linkUrl(token: string): Promise<string> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const proto = h.get("x-forwarded-proto") ?? (host?.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}/set-password#token=${token}`;
}

export async function addPerson(_prev: LinkResult | null, form: FormData): Promise<LinkResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Sign in again." };
  const body = {
    name: String(form.get("name") ?? ""),
    email: String(form.get("email") ?? ""),
    role: form.get("role") === "admin" ? ("admin" as const) : ("rep" as const),
  };
  const { data, error } = await api.POST("/team", { body });
  if (!data) {
    const e = error as { message?: string; field?: string } | undefined;
    return { ok: false, message: e?.message ?? "Couldn't add that person.", field: e?.field };
  }
  refresh();
  return { ok: true, name: data.person.name, url: await linkUrl(data.link.token), purpose: data.link.purpose, expires: data.link.expires_at };
}

export async function newLink(userId: string, name: string): Promise<LinkResult> {
  const api = await getApi();
  if (!api) return { ok: false, message: "Sign in again." };
  const { data, error } = await api.POST("/team/{user_id}/link", { params: { path: { user_id: userId } } });
  if (!data) return { ok: false, message: (error as { message?: string } | undefined)?.message ?? "Couldn't make a link." };
  return { ok: true, name, url: await linkUrl(data.token), purpose: data.purpose, expires: data.expires_at };
}

export async function setActive(userId: string, active: boolean): Promise<void> {
  const api = await getApi();
  if (!api) return;
  await api.PATCH("/team/{user_id}", { params: { path: { user_id: userId } }, body: { active } });
  refresh();
}
