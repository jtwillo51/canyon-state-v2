import type { Metadata } from "next";
import Link from "next/link";

import { ChooseViewer } from "@/components/choose-viewer";
import { PartnerGrid } from "@/components/partner/partner-grid";
import { one, parseSort } from "@/lib/list-views";
import { PERIODS, SORTS, type PartnerSort } from "@/lib/partner-list";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Top partners" };

const TOP = 10;
const MIN_REFERRALS = 3; // one lucky bind shouldn't put a partner on top
const DEFAULT_SORT: PartnerSort[] = ["-close_rate", "-referrals"]; // close rate first, then referrals
const PHRASE = { r12: "in the last 12 months", ytd: "so far this year", all: "all time" } as const;
const COLUMNS = ["name", "primary_rep", "referrals", "bound", "close_rate", "bound_premium"];

// The top referral partners. Clicking a header re-ranks by that column (the API picks the top 10 by it);
// shift-click adds a tie-breaker. Only partners with enough referrals in the period are ranked.
export default async function TopPartnersPage({ searchParams }: PageProps<"/top-partners">) {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const params = await searchParams;
  const period = PERIODS.find((p) => p.value === one(params.period)) ?? PERIODS[0];
  const sort = parseSort<PartnerSort>(params.sort, SORTS, DEFAULT_SORT);
  const [top, me] = await Promise.all([
    api.GET("/partners", { params: { query: { sort, min_referrals: MIN_REFERRALS, period: period.value, limit: TOP } } }),
    api.GET("/users/me"),
  ]);
  if (!top.data || !me.data) throw new Error("Couldn't load top partners");

  const sortParam = one(params.sort);
  const periodHref = (value: string) => {
    const q = new URLSearchParams();
    if (value !== "r12") q.set("period", value);
    if (sortParam) q.set("sort", sortParam); // keep the ranking when switching period
    return q.size ? `/top-partners?${q}` : "/top-partners";
  };
  const byDefault = sort.join(",") === DEFAULT_SORT.join(",");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Top referral partners</h1>
          <p className="text-sm text-muted-foreground">
            {byDefault ? "Ranked by close rate, then number of referrals." : "Re-ranked by the sorted columns."} Partners
            with {MIN_REFERRALS}+ referrals {PHRASE[period.value]}. Click a header to re-rank; shift-click to add a
            tie-breaker.
          </p>
        </div>
        <nav aria-label="Period" className="inline-flex overflow-hidden rounded-md border bg-card text-sm">
          {PERIODS.map((p) => (
            <Link
              key={p.value}
              href={periodHref(p.value)}
              aria-current={p.value === period.value ? "page" : undefined}
              className="px-3 py-1 text-muted-foreground hover:text-foreground aria-[current=page]:bg-primary aria-[current=page]:text-primary-foreground"
            >
              {p.label}
            </Link>
          ))}
        </nav>
      </div>

      <PartnerGrid
        rows={top.data.items}
        visible={COLUMNS}
        sort={sort}
        isAdmin={me.data.role === "admin"}
        ranked={{ defaultSort: DEFAULT_SORT, empty: `No partner has ${MIN_REFERRALS}+ referrals in this period yet.` }}
      />
      <p className="text-xs text-muted-foreground">
        {top.data.total} partners qualify. Close rate here is a partner&apos;s: bound ÷ referred, by count. (The
        dashboard&apos;s: bound ÷ decided, bound or lost, this month.) Both are placeholders until the agency confirms how
        it measures close rate.
      </p>
    </div>
  );
}
