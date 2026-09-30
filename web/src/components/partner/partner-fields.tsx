"use client";
// The partner page's editable fields. A client wrapper because each field's save maps a value onto a
// Server Action call; a Server Component can pass actions down, but not arbitrary callbacks.

import { useOptimistic, useTransition } from "react";

import { updatePartner } from "@/app/partners/[id]/actions";
import { InlineField } from "@/components/inline-field";
import type { Partner, UserRef } from "@/lib/api/types";

type Props = { partner: Partner; reps: UserRef[]; isAdmin: boolean };

export function PartnerContactFields({ partner, reps, isAdmin }: Props) {
  const save = (patch: Parameters<typeof updatePartner>[1]) => updatePartner(partner.id, patch);
  return (
    <div className="space-y-1.5 text-sm">
      <p>{partner.phone || "—"}</p>
      <p>{partner.email || "—"}</p>
      <InlineField kind="text" label="Territory" value={partner.territory} maxLength={100} save={(v) => save({ territory: v })} />
      <InlineField
        kind="select"
        label="Primary rep"
        value={partner.primary_rep?.id ?? ""}
        display={() => partner.primary_rep?.name ?? "Unassigned"}
        options={[{ value: "", label: "Unassigned" }, ...reps.map((r) => ({ value: r.id, label: r.name }))]}
        save={(v) => save({ primary_rep_id: v || null })}
        canEdit={isAdmin}
        readOnlyReason="admins change this"
      />
    </div>
  );
}

export function DoNotDiscuss({ partner }: { partner: Partner }) {
  return (
    <div role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
      <InlineField
        kind="textarea"
        label="Do not discuss"
        value={partner.sensitive_items}
        display={(v) => v || <span className="text-amber-900/60">Nothing noted. Add anything the team shouldn&apos;t bring up.</span>}
        maxLength={2000}
        placeholder="e.g. Going through a divorce; don't ask about their spouse."
        save={(v) => updatePartner(partner.id, { sensitive_items: v })}
      />
    </div>
  );
}

export function DoNotContactToggle({ partner }: { partner: Partner }) {
  const [pending, start] = useTransition();
  const [on, setOn] = useOptimistic(partner.do_not_contact);
  return (
    <label className="inline-flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={on}
        disabled={pending}
        onChange={(e) => {
          const next = e.target.checked;
          start(async () => {
            setOn(next);
            await updatePartner(partner.id, { do_not_contact: next });
          });
        }}
      />
      Do not contact
    </label>
  );
}
