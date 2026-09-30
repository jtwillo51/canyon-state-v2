"use client";
// Filters for the Referrals list. Every control writes to the URL; the page re-renders from it.

import { Search, X } from "lucide-react";

import { Chips } from "@/components/list/chips";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import type { UserRef } from "@/lib/api/types";
import { LINES, STALE_OPTIONS, STATUSES } from "@/lib/referral-list";
import { useListParams } from "@/lib/use-list-params";

const FILTER_KEYS = ["status", "line", "stale", "rep", "q", "bound_from", "bound_to", "has_premium"];

export function ReferralFilters({ reps }: { reps: UserRef[] | null }) {
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
        {/* key: a view change or "Clear" replaces the URL; remount so the box shows the new search */}
        <Input key={params.get("q") ?? ""} name="q" aria-label="Search clients" placeholder="Client name" defaultValue={params.get("q") ?? ""} className="h-8 w-44 pl-7" />
      </form>
      <Chips name="status" options={STATUSES} label="Status" />
      <Chips name="line" options={LINES} label="Line of business" />
      <NativeSelect
        size="sm"
        aria-label="Stale"
        value={params.get("stale") ?? ""}
        onChange={(e) => update({ stale: e.target.value || null })}
      >
        <NativeSelectOption value="">Any activity</NativeSelectOption>
        {STALE_OPTIONS.map((d) => (
          <NativeSelectOption key={d} value={String(d)}>
            No touch in {d}+ days
          </NativeSelectOption>
        ))}
      </NativeSelect>
      {reps && (
        <NativeSelect size="sm" aria-label="Rep" value={params.get("rep") ?? ""} onChange={(e) => update({ rep: e.target.value || null })}>
          <NativeSelectOption value="">All reps</NativeSelectOption>
          {reps.map((r) => (
            <NativeSelectOption key={r.id} value={r.id}>
              {r.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      )}
      {active && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => update(Object.fromEntries(FILTER_KEYS.map((k) => [k, null])))}
        >
          <X className="size-4" aria-hidden /> Clear filters
        </Button>
      )}
    </div>
  );
}
