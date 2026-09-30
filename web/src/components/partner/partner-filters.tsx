"use client";
// Filters for the Partners list. Every control writes to the URL; the page re-renders from it.

import { Search, X } from "lucide-react";

import { Chips } from "@/components/list/chips";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import type { UserRef } from "@/lib/api/types";
import { PERIODS, TYPES } from "@/lib/partner-list";
import { useListParams } from "@/lib/use-list-params";

const FILTER_KEYS = ["type", "rep", "unassigned", "dnc", "no_referrals", "q"];

export function PartnerFilters({ reps }: { reps: UserRef[] }) {
  const { params, update } = useListParams();
  const active = FILTER_KEYS.some((k) => params.has(k));

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border p-3">
      <form
        role="search"
        className="relative"
        onSubmit={(e) => {
          e.preventDefault();
          update({ q: String(new FormData(e.currentTarget).get("q") ?? "").trim() || null });
        }}
      >
        <Search className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input key={params.get("q") ?? ""} name="q" aria-label="Search partners" placeholder="Name or business" defaultValue={params.get("q") ?? ""} className="h-8 w-44 pl-7" />
      </form>
      <NativeSelect size="sm" aria-label="Period" value={params.get("period") ?? "r12"} onChange={(e) => update({ period: e.target.value === "r12" ? null : e.target.value })}>
        {PERIODS.map((p) => (
          <NativeSelectOption key={p.value} value={p.value}>
            {p.label}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      <Chips name="type" options={TYPES} label="Partner type" />
      <NativeSelect size="sm" aria-label="Primary rep" value={params.get("rep") ?? ""} onChange={(e) => update({ rep: e.target.value || null, unassigned: null })}>
        <NativeSelectOption value="">Any primary rep</NativeSelectOption>
        {reps.map((r) => (
          <NativeSelectOption key={r.id} value={r.id}>
            {r.name}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      <label className="flex items-center gap-1.5 text-sm">
        <input type="checkbox" checked={params.get("dnc") === "true"} onChange={(e) => update({ dnc: e.target.checked ? "true" : null })} />
        Do not contact
      </label>
      {active && (
        <Button type="button" variant="ghost" size="sm" onClick={() => update(Object.fromEntries(FILTER_KEYS.map((k) => [k, null])))}>
          <X className="size-4" aria-hidden /> Clear filters
        </Button>
      )}
    </div>
  );
}
