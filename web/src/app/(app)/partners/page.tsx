import type { Metadata } from "next";
import Link from "next/link";

import { ChooseViewer } from "@/components/choose-viewer";
import { ViewTabs } from "@/components/list/view-tabs";
import { PartnerFilters } from "@/components/partner/partner-filters";
import { PartnerGrid } from "@/components/partner/partner-grid";
import type { ListView } from "@/lib/list-views";
import { builtInPartnerViews, DEFAULT_SORT, PAGE_SIZE, parsePartnerParams, PERIODS } from "@/lib/partner-list";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Partners" };

// "Which partners are worth the time": every partner with its referral numbers for the period.
// URL-driven like the Referrals list.
export default async function PartnersPage({ searchParams }: PageProps<"/partners">) {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const params = await searchParams;
  const { query, page, cols } = parsePartnerParams(params);
  const [list, saved, me, reps] = await Promise.all([
    api.GET("/partners", { params: { query } }),
    api.GET("/views", { params: { query: { list: "partners" } } }),
    api.GET("/users/me"),
    api.GET("/users/reps"),
  ]);
  if (!list.data || !saved.data || !me.data || !reps.data) throw new Error("Couldn't load partners");

  const views: ListView[] = [
    ...builtInPartnerViews(),
    ...saved.data.map((v) => ({ id: v.id, name: v.name, query: v.query, saved: true })),
  ];
  const { items, total } = list.data;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const period = PERIODS.find((p) => p.value === query.period)?.label.toLowerCase();
  const pageHref = (n: number) => {
    const p = new URLSearchParams(Object.entries(params).flatMap(([k, v]) => (typeof v === "string" ? [[k, v]] : [])));
    p.set("page", String(n));
    return `/partners?${p}`;
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Partners</h1>
        <p className="text-sm text-muted-foreground">
          {total} {total === 1 ? "partner" : "partners"} · referral numbers for the {period}
        </p>
      </div>
      <ViewTabs views={views} list="partners" basePath="/partners" />
      <PartnerFilters reps={reps.data} />
      <PartnerGrid rows={items} visible={cols} sort={query.sort ?? DEFAULT_SORT} isAdmin={me.data.role === "admin"} />
      <p className="text-xs text-muted-foreground">
        Close rate is bound ÷ referred, by count: a placeholder until the agency confirms how it measures it.
      </p>

      {pages > 1 && (
        <nav aria-label="Pages" className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Page {page} of {pages}
          </span>
          <span className="flex gap-2">
            {page > 1 && (
              <Link href={pageHref(page - 1)} className="rounded-md border bg-card px-3 py-1 hover:bg-accent">
                Previous
              </Link>
            )}
            {page < pages && (
              <Link href={pageHref(page + 1)} className="rounded-md border bg-card px-3 py-1 hover:bg-accent">
                Next
              </Link>
            )}
          </span>
        </nav>
      )}
    </div>
  );
}
