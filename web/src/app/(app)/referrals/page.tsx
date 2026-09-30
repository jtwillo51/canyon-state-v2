import type { Metadata } from "next";
import Link from "next/link";

import { ChooseViewer } from "@/components/choose-viewer";
import { ReferralFilters } from "@/components/referral/referral-filters";
import { ReferralGrid } from "@/components/referral/referral-grid";
import { ViewTabs } from "@/components/list/view-tabs";
import { agencyToday } from "@/lib/format";
import type { ListView } from "@/lib/list-views";
import { builtInViews, DEFAULT_SORT, PAGE_SIZE, parseListParams } from "@/lib/referral-list";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Referrals" };

// A Server Component driven by the URL: filters, sort, columns and page all come from searchParams,
// go to the API, and come back as one page of rows. The interactive pieces only ever change the URL.
export default async function ReferralsPage({ searchParams }: PageProps<"/referrals">) {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const params = await searchParams;
  const { query, page, cols } = parseListParams(params);
  const [list, saved, me, reps] = await Promise.all([
    api.GET("/referrals", { params: { query } }),
    api.GET("/views", { params: { query: { list: "referrals" } } }),
    api.GET("/users/me"),
    api.GET("/users/reps"),
  ]);
  if (!list.data || !saved.data || !me.data || !reps.data) throw new Error("Couldn't load referrals");

  const today = agencyToday();
  const views: ListView[] = [
    ...builtInViews(today),
    ...saved.data.map((v) => ({ id: v.id, name: v.name, query: v.query, saved: true })),
  ];
  const { items, total } = list.data;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageHref = (n: number) => {
    const p = new URLSearchParams(Object.entries(params).flatMap(([k, v]) => (typeof v === "string" ? [[k, v]] : [])));
    p.set("page", String(n));
    return `/referrals?${p}`;
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Referrals</h1>
        <p className="text-sm text-muted-foreground">
          {total} {total === 1 ? "referral" : "referrals"}
          {me.data.role === "rep" && " you're credited on"}
        </p>
      </div>
      <ViewTabs views={views} list="referrals" basePath="/referrals" />
      {/* Only admins filter by rep: a rep's list is already just theirs. */}
      <ReferralFilters reps={me.data.role === "admin" ? reps.data : null} />
      <ReferralGrid rows={items} visible={cols} sort={query.sort ?? DEFAULT_SORT} today={today} />

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
