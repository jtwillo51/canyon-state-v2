"use client";
// The referral page's editable policy fields. The page works out what this viewer may edit; the API
// enforces the same rules (anyone who can see it before bind; admins only once bound).

import { updateReferral } from "@/app/(app)/referrals/[id]/actions";
import { InlineField } from "@/components/inline-field";
import type { Referral } from "@/lib/api/types";
import { day, money } from "@/lib/format";
import { LINES } from "@/lib/referral-list";

type Props = { referral: Referral; carriers: { id: string; name: string }[]; isAdmin: boolean };

export function ReferralPolicyFields({ referral: r, carriers, isAdmin }: Props) {
  const locked = r.status === "bound" && !isAdmin;
  const reason = locked ? "admins change bound referrals" : undefined;
  // Premium exists from quoted on (bound: admins). Before that it's set by the pipeline move to Quoted.
  const premiumEditable = (r.status === "quoted" || r.status === "bound") && !locked;
  const save = (patch: Parameters<typeof updateReferral>[1]) => updateReferral(r.id, patch);

  return (
    <div className="space-y-1.5 text-sm">
      <InlineField
        kind="select"
        label="Line"
        value={r.line_of_business}
        options={LINES.map((l) => ({ value: l, label: l }))}
        save={(v) => save({ line_of_business: v as Referral["line_of_business"] })}
        canEdit={!locked}
        readOnlyReason={reason}
      />
      <InlineField
        kind="select"
        label="Carrier"
        value={r.carrier.id}
        display={() => r.carrier.name}
        options={carriers.map((c) => ({ value: c.id, label: c.name }))}
        save={(v) => save({ carrier_id: v })}
        canEdit={!locked}
        readOnlyReason={reason}
      />
      <InlineField
        kind="number"
        label="Premium"
        value={r.premium == null ? "" : String(r.premium)}
        display={(v) => (v ? `${money(Number(v))} / yr` : "Not quoted yet")}
        min={0.01}
        step={0.01}
        save={(v) => save({ premium: Number(v) })}
        canEdit={premiumEditable}
        readOnlyReason={reason ?? (r.premium == null ? "set when quoted" : undefined)}
      />
      <p>
        <span className="text-muted-foreground">Bound: </span>
        {day(r.bound_date)}
      </p>
    </div>
  );
}
