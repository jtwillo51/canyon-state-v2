"use client";
// The scoreboard under the header, on every page: this month's three numbers on a dark blue band, each
// with a copper goal meter. Collapsible; the choice is remembered.
// Admins see company totals (always vs last month: the company has no "everyone" to compare with).
// A rep sees their own numbers, with the vs myself / vs everyone switch, and the company as % of goal.

import { ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";

import type { Metric, Progress } from "@/lib/api/types";
import { delta, formatValue, pct, type Compare, type Kind } from "@/lib/progress";

import { Delta } from "./delta";
import { GoalMeter } from "./goal-meter";
import { CompareSwitch, useProgressPrefs } from "./prefs";

const METRICS: { key: "clients" | "sales" | "close_rate"; label: string; kind: Kind }[] = [
  { key: "clients", label: "Clients bound", kind: "count" },
  { key: "sales", label: "Sales", kind: "money" },
  { key: "close_rate", label: "Close rate", kind: "rate" },
];

function Item({ label, kind, m, share, fixed }: { label: string; kind: Kind; m: Metric; share?: string; fixed?: Compare }) {
  const prefs = useProgressPrefs();
  const compare = fixed ?? prefs.compare; // company totals ignore the switch: they always compare with last month
  return (
    <div className="min-w-0 border-brand-line px-4 py-2.5 max-md:border-t md:border-l">
      <p className="text-[11px] tracking-wider text-brand-mute uppercase">{label}</p>
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 font-mono">
        <span className="text-xl font-medium">{formatValue(kind, m.value)}</span>
        {m.goal != null && (
          <span className="text-xs text-brand-mute">
            {kind === "rate" ? "target" : "/"} {formatValue(kind, m.goal)}
          </span>
        )}
        <Delta d={delta(kind, m, compare)} onDark />
      </p>
      <GoalMeter kind={kind} value={m.value} goal={m.goal} onDark className="mt-1.5" />
      {share && <p className="mt-1 text-[11px] text-brand-mute">Company: {share}</p>}
    </div>
  );
}

export function ProgressStrip({ progress }: { progress: Progress }) {
  const { collapsed, setCollapsed, compare } = useProgressPrefs();
  const monthName = new Date(`${progress.month}-15`).toLocaleDateString("en-US", { month: "long" });
  const company = progress.company;
  const me = progress.reps[0];
  const share = progress.company_share;
  const against = company || compare === "self" ? "vs last month" : "vs everyone";

  const toggle = (
    <button
      type="button"
      onClick={() => setCollapsed(!collapsed)}
      aria-expanded={!collapsed}
      aria-label={collapsed ? "Show progress" : "Hide progress"}
      className="rounded p-1 text-brand-mute hover:text-white"
    >
      {collapsed ? <ChevronDown className="size-4" aria-hidden /> : <ChevronUp className="size-4" aria-hidden />}
    </button>
  );

  return (
    <section aria-label="Progress this month" className="relative border-b-3 border-copper bg-brand-deep text-white">
      <div className="mx-auto grid max-w-6xl md:grid-cols-[180px_repeat(3,minmax(0,1fr))_auto]">
        <div className={`flex gap-2 px-4 ${collapsed ? "items-center py-1.5 md:col-span-4" : "flex-col justify-center py-2.5"}`}>
          <Link href="/dashboard" className="text-[11px] font-medium tracking-wider text-copper-soft uppercase hover:underline">
            {monthName}
          </Link>
          {!collapsed && <p className="text-xs text-brand-mute">so far, {against}</p>}
          {!collapsed && !company && <CompareSwitch size="sm" onDark />}
        </div>
        {!collapsed && company &&
          METRICS.map((x) => <Item key={x.key} label={x.label} kind={x.kind} m={company[x.key]} fixed="self" />)}
        {!collapsed && !company && me && share &&
          METRICS.map((x) => (
            <Item
              key={x.key}
              label={`Your ${x.label.toLowerCase()}`}
              kind={x.kind}
              m={me[x.key]}
              share={
                x.key === "clients"
                  ? `${pct(share.clients_pct_of_goal)} of goal`
                  : x.key === "sales"
                    ? `${pct(share.sales_pct_of_goal)} of goal`
                    : pct(share.close_rate)
              }
            />
          ))}
        <div className="flex items-start justify-end px-2 py-1.5 max-md:absolute max-md:right-2">{toggle}</div>
      </div>
    </section>
  );
}
