"use client";
// The progress dashboard. Admins: company totals, then every rep with inline-editable goals.
// A rep: their own numbers, each with the company's progress as a share of goal.
// The switch (vs myself / vs everyone) picks the one comparison shown next to each number.

import { createColumnHelper } from "@tanstack/react-table";

import { saveCloseRateGoal, saveRepGoal } from "@/app/progress-actions";
import { InlineField } from "@/components/inline-field";
import { DataGrid, gridFeatures } from "@/components/list/data-grid";
import type { Metric, Progress, RepProgress } from "@/lib/api/types";
import { delta, formatValue, pct, type Kind } from "@/lib/progress";

import { Delta } from "./delta";
import { GoalMeter } from "./goal-meter";
import { CompareSwitch, useProgressPrefs } from "./prefs";

const METRICS: { key: "clients" | "sales" | "close_rate"; label: string; kind: Kind }[] = [
  { key: "clients", label: "Clients bound", kind: "count" },
  { key: "sales", label: "Sales (bound premium)", kind: "money" },
  { key: "close_rate", label: "Close rate", kind: "rate" },
];

function Card({ label, kind, m, compare, footer, goalEditor }: {
  label: string; kind: Kind; m: Metric; compare: "self" | "team"; footer?: React.ReactNode; goalEditor?: React.ReactNode;
}) {  // prettier-ignore
  return (
    <div role="group" aria-label={label} className="rounded-md border bg-card p-4">
      <p className="text-[11px] tracking-wider text-muted-foreground uppercase">{label}</p>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-2 font-mono">
        <span data-value className="text-3xl font-medium">{formatValue(kind, m.value)}</span>
        {!goalEditor && m.goal != null && (
          <span className="text-sm whitespace-nowrap text-muted-foreground">
            {kind === "rate" ? "target" : "/"} {formatValue(kind, m.goal)}
          </span>
        )}
        <Delta d={delta(kind, m, compare)} />
      </div>
      {goalEditor && <div className="mt-1 text-sm">{goalEditor}</div>}
      <GoalMeter kind={kind} value={m.value} goal={m.goal} className="mt-3" />
      {footer && <p className="mt-2 text-xs text-muted-foreground">{footer}</p>}
    </div>
  );
}

function RepCell({ kind, m, goalEditor }: { kind: Kind; m: Metric; goalEditor?: React.ReactNode }) {
  const { compare } = useProgressPrefs();
  return (
    <div className="text-right">
      <div className="flex items-baseline justify-end gap-2">
        <Delta d={delta(kind, m, compare)} />
        <span className="font-mono font-medium">{formatValue(kind, m.value)}</span>
      </div>
      {goalEditor && <div className="text-xs">{goalEditor}</div>}
      <GoalMeter kind={kind} value={m.value} goal={m.goal} className="mt-1 ml-auto w-20" />
    </div>
  );
}

// The reps table on the shared DataGrid (local mode: 6 rows, sorted in the browser). Each metric column
// sorts by its value; click a header to sort, shift-click to add a second.
const repHelper = createColumnHelper<typeof gridFeatures, RepProgress>();
const REP_META = [
  { id: "rep", label: "Rep" },
  { id: "clients", label: "Clients bound" },
  { id: "sales", label: "Sales" },
  { id: "close_rate", label: "Close rate" },
];
const RIGHT = { meta: { align: "right" } };

const repColumns = repHelper.columns([
  repHelper.accessor((r) => r.rep.name, { id: "rep", header: "Rep", cell: (i) => <span className="font-medium">{i.getValue()}</span> }),
  repHelper.accessor((r) => r.clients.value, {
    id: "clients",
    header: "Clients bound",
    ...RIGHT,
    cell: ({ row: { original: r } }) => (
      <RepCell kind="count" m={r.clients} goalEditor={
        <InlineField kind="number" label="Goal" value={String(r.clients.goal ?? 0)} min={0} step={1}
          save={(v) => saveRepGoal(r.rep.id, Number(v), r.sales.goal ?? 0)} />
      } />  // prettier-ignore
    ),
  }),
  repHelper.accessor((r) => r.sales.value, {
    id: "sales",
    header: "Sales",
    ...RIGHT,
    cell: ({ row: { original: r } }) => (
      <RepCell kind="money" m={r.sales} goalEditor={
        <InlineField kind="number" label="Goal" value={String(r.sales.goal ?? 0)} min={0} step={100}
          display={(v) => formatValue("money", Number(v))} save={(v) => saveRepGoal(r.rep.id, r.clients.goal ?? 0, Number(v))} />
      } />  // prettier-ignore
    ),
  }),
  repHelper.accessor((r) => r.close_rate.value, {
    id: "close_rate",
    header: "Close rate",
    ...RIGHT,
    cell: ({ row: { original: r } }) => <RepCell kind="rate" m={r.close_rate} />,
  }),
]);

function RepsTable({ reps }: { reps: RepProgress[] }) {
  return (
    <DataGrid mode="local" rows={reps} columns={repColumns} meta={REP_META} sort={["rep"]} defaultSort={["rep"]}
      rowId={(r) => r.rep.id} empty="No active reps." />  // prettier-ignore
  );
}

export function Dashboard({ progress }: { progress: Progress }) {
  const { compare } = useProgressPrefs();
  const { company, company_share: share } = progress;
  const through = new Date(`${progress.through}T12:00`).toLocaleDateString("en-US", { month: "long", day: "numeric" });
  const against = new Date(`${progress.compared_through}T12:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Progress</h1>
          <p className="text-sm text-muted-foreground">
            This month through {through}.{" "}
            {compare === "self" ? `Compared with the same point last month (through ${against}).` : "Compared with the average of the other reps."}
          </p>
        </div>
        <CompareSwitch />
      </div>

      {company && (
        <>
          <section aria-label="Company" className="grid gap-4 md:grid-cols-3">
            {METRICS.map((x) => (
              <Card
                key={x.key}
                label={x.label}
                kind={x.kind}
                // The company has no "everyone" to compare with: its cards always compare with last month.
                m={company[x.key]}
                compare="self"
                footer={x.key === "close_rate" ? "Company vs last month. Close rate is a placeholder definition." : "Company vs last month"}
                goalEditor={
                  x.key === "close_rate" ? (
                    <InlineField kind="number" label="Target" value={company.close_rate.goal == null ? "" : String(Math.round(company.close_rate.goal * 100))}
                      display={(v) => (v ? `${v}%` : "not set")} min={0} step={1} save={(v) => saveCloseRateGoal(v === "" ? null : Number(v))} />  // prettier-ignore
                  ) : undefined
                }
              />
            ))}
          </section>

          <section aria-label="Reps">
            <h2 className="mb-2 text-lg font-semibold">Reps</h2>
            <RepsTable reps={progress.reps} />
            <p className="mt-2 text-xs text-muted-foreground">
              Clients and sales count toward the rep credited with the bind; close rate toward the rep who introduced
              the referral, over referrals decided this month (bound ÷ bound + lost).
            </p>
          </section>
        </>
      )}

      {!company && share && progress.reps[0] && (
        <section aria-label="Your progress" className="grid gap-4 md:grid-cols-3">
          {METRICS.map((x) => (
            <Card
              key={x.key}
              label={`Your ${x.label.charAt(0).toLowerCase()}${x.label.slice(1)}`}
              kind={x.kind}
              m={progress.reps[0][x.key]}
              compare={compare}
              footer={
                x.key === "clients"
                  ? `Company: ${pct(share.clients_pct_of_goal)} of goal`
                  : x.key === "sales"
                    ? `Company: ${pct(share.sales_pct_of_goal)} of goal`
                    : `Company: ${pct(share.close_rate)} (target ${pct(share.close_rate_goal)})`
              }
            />
          ))}
        </section>
      )}
    </div>
  );
}
