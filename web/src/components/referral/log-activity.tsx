"use client";
// Log a call, email or meeting. Uses onSubmit rather than <form action>: React 19 resets a form after
// its action runs, even when the save failed, which would throw away what was typed. Here the form
// clears only on success.

import { useRef, useState, useTransition } from "react";

import { logActivity } from "@/app/referrals/[id]/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { ActivityIn, UserRef } from "@/lib/api/types";

type Props = { referralId: string; referredDate: string; today: string; viewerId: string; team: UserRef[] };

const METHODS: ActivityIn["method"][] = ["Phone", "Email", "In person"];

export function LogActivity({ referralId, referredDate, today, viewerId, team }: Props) {
  const form = useRef<HTMLFormElement>(null);
  const [saving, startSaving] = useTransition();
  const [error, setError] = useState<{ message: string; field?: string | null } | null>(null);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const entry: ActivityIn = {
      method: data.get("method") as ActivityIn["method"],
      date: String(data.get("date")),
      rep_id: String(data.get("rep_id")),
      notes: String(data.get("notes") ?? ""),
    };
    startSaving(async () => {
      const result = await logActivity(referralId, entry);
      if (result.ok) {
        setError(null);
        form.current?.reset();
      } else {
        setError(result);
      }
    });
  }

  const invalid = (field: string) => (error?.field === field ? true : undefined);

  return (
    <form ref={form} onSubmit={onSubmit} className="grid gap-3 rounded-xl border p-4" aria-label="Log activity">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="grid gap-1.5">
          <Label htmlFor="method">How</Label>
          <NativeSelect id="method" name="method" defaultValue="Phone" className="w-full">
            {METHODS.map((m) => (
              <NativeSelectOption key={m} value={m}>
                {m}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="date">When</Label>
          <Input id="date" name="date" type="date" required min={referredDate} max={today} defaultValue={today} aria-invalid={invalid("date")} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="rep_id">Who made contact</Label>
          <NativeSelect id="rep_id" name="rep_id" defaultValue={viewerId} className="w-full" aria-invalid={invalid("rep_id")}>
            {team.map((u) => (
              <NativeSelectOption key={u.id} value={u.id}>
                {u.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="notes">Notes</Label>
        <Textarea id="notes" name="notes" maxLength={2000} rows={2} placeholder="What happened?" aria-invalid={invalid("notes")} />
      </div>
      <div className="flex items-center justify-between gap-3">
        <p role="alert" className="text-sm text-destructive">
          {error?.message}
        </p>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Log activity"}
        </Button>
      </div>
    </form>
  );
}
