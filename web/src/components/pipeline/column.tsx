"use client";

import { useDraggable, useDroppable } from "@dnd-kit/core";
import Link from "next/link";

import type { Referral, ReferralStatus } from "@/lib/api/types";
import { day, money } from "@/lib/format";

type ColumnProps = { status: ReferralStatus; label: string; referrals: Referral[] };

export function Column({ status, label, referrals }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const total = referrals.reduce((sum, r) => sum + (r.premium ?? 0), 0);

  return (
    <section
      ref={setNodeRef}
      aria-label={`${label}, ${referrals.length} referrals`}
      className={`flex min-h-64 flex-col rounded-xl border bg-muted/40 p-2 transition-colors ${isOver ? "border-primary bg-primary/5" : ""}`}
    >
      <header className="mb-2 flex items-baseline justify-between px-1">
        <h2 className="text-sm font-semibold">
          {label} <span className="font-normal text-muted-foreground">{referrals.length}</span>
        </h2>
        {total > 0 && <span className="text-xs tabular-nums text-muted-foreground">{money(total)}</span>}
      </header>
      <ol className="flex flex-col gap-2">
        {referrals.map((r) => (
          <li key={r.id}>
            <DraggableCard referral={r} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function DraggableCard({ referral }: { referral: Referral }) {
  const { setNodeRef, attributes, listeners, isDragging } = useDraggable({ id: referral.id });
  return (
    <div ref={setNodeRef} {...attributes} {...listeners} className={isDragging ? "opacity-30" : undefined}>
      <Card referral={referral} />
    </div>
  );
}

export function Card({ referral: r, overlay = false }: { referral: Referral; overlay?: boolean }) {
  return (
    <div
      className={`cursor-grab rounded-lg border bg-card p-2.5 text-sm shadow-xs active:cursor-grabbing ${overlay ? "shadow-lg ring-2 ring-primary/30" : ""}`}
    >
      <Link href={`/referrals/${r.id}`} className="font-medium hover:underline">
        {r.client_name}
      </Link>
      <p className="text-xs text-muted-foreground">
        {r.line_of_business} · {r.partner.name}
      </p>
      <p className="mt-1 flex justify-between text-xs text-muted-foreground">
        <span>{day(r.referred_date)}</span>
        <span className="tabular-nums">{money(r.premium)}</span>
      </p>
    </div>
  );
}
