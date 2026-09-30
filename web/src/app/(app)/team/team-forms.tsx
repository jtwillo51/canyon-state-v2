"use client";
// Adding a person and making links: client pieces only for the inline result (the link to copy) and errors.

import { Check, Copy } from "lucide-react";
import { useActionState, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import { addPerson, newLink, type LinkResult } from "./actions";

const hours = (iso: string) => Math.round((Date.parse(iso) - Date.now()) / 3_600_000);

/** The one-time link, shown once, with a copy button. It isn't stored anywhere: copy it now or make a new one. */
function LinkBox({ result }: { result: Extract<LinkResult, { ok: true }> }) {
  const [copied, setCopied] = useState(false);
  return (
    <div role="status" className="space-y-2 rounded-md border border-brand-line/30 bg-muted/40 p-3 text-sm">
      <p>
        {result.purpose === "setup" ? "Setup" : "Reset"} link for <strong>{result.name}</strong>. Send it to them directly;
        it works once, for {hours(result.expires)} hours.
      </p>
      <div className="flex gap-2">
        <Input readOnly value={result.url} aria-label="One-time link" className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
        <Button
          type="button"
          variant="outline"
          onClick={async () => {
            await navigator.clipboard.writeText(result.url);
            setCopied(true);
          }}
        >
          {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">It won&apos;t be shown again. If it&apos;s lost, make a new one (the old one stops working).</p>
    </div>
  );
}

export function AddPerson() {
  const [state, action, pending] = useActionState<LinkResult | null, FormData>(addPerson, null);
  const invalid = (field: string) => (state && !state.ok && state.field === field ? true : undefined);
  return (
    <section aria-labelledby="add" className="space-y-3 rounded-md border bg-card p-4">
      <h2 id="add" className="font-semibold">
        Add a person
      </h2>
      <form action={action} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end" key={state?.ok ? state.url : "form"}>
        <div className="grid gap-1.5">
          <Label htmlFor="name">Name</Label>
          <Input id="name" name="name" required maxLength={100} aria-invalid={invalid("name")} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" name="email" type="email" required aria-invalid={invalid("email")} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="role">Role</Label>
          <NativeSelect id="role" name="role" defaultValue="rep">
            <NativeSelectOption value="rep">Rep</NativeSelectOption>
            <NativeSelectOption value="admin">Admin</NativeSelectOption>
          </NativeSelect>
        </div>
        <Button type="submit" disabled={pending}>
          {pending ? "Adding…" : "Add and make link"}
        </Button>
      </form>
      {state && !state.ok && (
        <p role="alert" className="text-sm text-destructive">
          {state.message}
        </p>
      )}
      {state?.ok && <LinkBox result={state} />}
    </section>
  );
}

export function NewLinkButton({ userId, name, reset }: { userId: string; name: string; reset: boolean }) {
  const [result, setResult] = useState<LinkResult | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        disabled={pending}
        onClick={() => start(async () => setResult(await newLink(userId, name)))}
        className="rounded-md px-2 py-1 text-xs text-link hover:bg-accent"
      >
        {reset ? "Reset link" : "Setup link"}
      </button>
      {result?.ok && (
        <div className="w-96 text-left">
          <LinkBox result={result} />
        </div>
      )}
      {result && !result.ok && <p className="text-xs text-destructive">{result.message}</p>}
    </div>
  );
}
