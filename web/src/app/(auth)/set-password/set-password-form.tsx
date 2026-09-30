"use client";
// Reads the one-time token from the URL fragment (never sent to a server), checks it, and sets the password.

import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { checkLink, redeemLink, type FormState } from "../actions";

type LinkInfo = { purpose: "setup" | "reset"; name: string };

export function SetPasswordForm() {
  const token = useRef<string | null>(null); // never rendered, so a ref, not state
  const [link, setLink] = useState<LinkInfo | null | "invalid">(null);
  const [state, setState] = useState<FormState>(null);
  const [pending, start] = useTransition();

  useEffect(() => {
    // Read the fragment once. Effects can run twice (React does so on purpose in development), and the second
    // run would find the address bar already cleaned below and lose the token.
    token.current ??= new URLSearchParams(window.location.hash.slice(1)).get("token");
    // Drop the token from the address bar and history, so it can't be copied or revisited.
    window.history.replaceState(null, "", window.location.pathname);
    const t = token.current;
    (t ? checkLink(t) : Promise.resolve({ ok: false as const })).then((r) =>
      setLink(r.ok ? { purpose: r.purpose, name: r.name } : "invalid"),
    );
  }, []);

  if (link === null) return <p className="text-sm text-muted-foreground">Checking your link…</p>;
  if (link === "invalid")
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-semibold">This link doesn&apos;t work</h1>
        <p className="text-sm text-muted-foreground">
          It has expired or has already been used. Ask an admin for a new one.
        </p>
        <Link href="/sign-in" className="text-sm text-link hover:underline">
          Go to sign in
        </Link>
      </div>
    );

  const first = link.name.split(" ")[0];
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const password = String(form.get("password") ?? "");
        if (password !== String(form.get("confirm") ?? "")) return setState({ message: "Those don't match.", field: "confirm" });
        start(async () => setState(await redeemLink(token.current!, password)));
      }}
    >
      <div>
        <h1 className="text-xl font-semibold">{link.purpose === "setup" ? `Welcome, ${first}` : `New password for ${first}`}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a password of at least 15 characters. A few unrelated words work well, like &ldquo;copper kettle midnight
          harbor&rdquo;.
        </p>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="password">New password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={15}
          maxLength={128}
          required
          autoFocus
          aria-invalid={state?.field === "password" ? true : undefined}
          aria-describedby="password-help"
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="confirm">Type it again</Label>
        <Input id="confirm" name="confirm" type="password" autoComplete="new-password" required aria-invalid={state?.field === "confirm" ? true : undefined} />
      </div>
      <p id="password-help" role={state?.message ? "alert" : undefined} className={state?.message ? "text-sm text-destructive" : "sr-only"}>
        {state?.message}
      </p>
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : "Set password and sign in"}
      </Button>
    </form>
  );
}
