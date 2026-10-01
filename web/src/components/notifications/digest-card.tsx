// One weekly digest: last week's numbers. A rep's shows their own; an admin's shows the company and every
// rep (the API decides which, the same split as the dashboard).
import Link from "next/link";

import type { Digest, WeekTally } from "@/lib/api/types";
import { day, money } from "@/lib/format";

import { DigestRepsTable } from "./digest-reps-table";

const rate = (r: number | null) => (r == null ? "—" : `${Math.round(r * 100)}%`);

function Stats({ t, label }: { t: WeekTally; label: string }) {
  const stats = [
    ["New referrals", String(t.new_referrals)],
    ["Clients bound", String(t.clients)],
    ["Sales", money(t.sales)],
    ["Close rate", rate(t.close_rate)],
  ];
  return (
    <dl role="group" aria-label={label} className="grid grid-cols-2 gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-4">
      {stats.map(([k, v]) => (
        <div key={k} className="bg-card px-3 py-2">
          <dt className="text-[11px] tracking-wider text-muted-foreground uppercase">{k}</dt>
          <dd className="font-mono text-xl font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DigestCard({ digest, unread, action }: { digest: Digest; unread: boolean; action?: React.ReactNode }) {
  const week = `${day(digest.week_start)} – ${day(digest.week_end)}`;
  const tally = digest.company ?? digest.mine;
  return (
    <article aria-label={`Weekly digest, ${week}`} className="space-y-3 rounded-md border bg-card p-4">
      <header className="flex items-center gap-3">
        {unread && <span aria-label="Unread" className="size-2 shrink-0 rounded-full bg-brand" />}
        <h3 className="flex-1 font-medium">
          Week of {week}
          <span className="ml-2 text-sm font-normal text-muted-foreground">{digest.company ? "Company" : "Your numbers"}</span>
        </h3>
        {action}
      </header>
      {tally && <Stats t={tally} label={digest.company ? "Company, last week" : "Your numbers, last week"} />}
      <p className="text-sm text-muted-foreground">
        {digest.stale === 0 ? (
          "No stale referrals when this digest was made."
        ) : (
          <>
            <Link href="/referrals?stale=14" className="text-link hover:underline">
              {digest.stale} stale {digest.stale === 1 ? "referral" : "referrals"}
            </Link>{" "}
            when this digest was made (open, no touch in 14 days).
          </>
        )}{" "}
        Close rate is the share bound of referrals decided in the week (bound or lost), a placeholder definition.
      </p>
      {digest.reps.length > 0 && <DigestRepsTable reps={digest.reps} />}
    </article>
  );
}
