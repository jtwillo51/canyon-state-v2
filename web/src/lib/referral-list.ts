// The Referrals list's URL is its state: filters, sort, columns and page. A view is just a query
// string. This module turns the URL into an API query (dropping anything invalid rather than
// erroring, since URLs get hand-edited) and defines the built-in views.
import type { paths } from "@/lib/api/schema";
import type { ReferralStatus } from "@/lib/api/types";

export type ApiQuery = NonNullable<paths["/referrals"]["get"]["parameters"]["query"]>;
type Sort = NonNullable<ApiQuery["sort"]>;
type Line = NonNullable<ApiQuery["line"]>[number];

export const PAGE_SIZE = 50;
export const STATUSES: ReferralStatus[] = ["referred", "contacted", "quoted", "bound", "lost"];
export const LINES: Line[] = ["Auto", "Home", "Umbrella", "Life", "Commercial"];
export const STALE_OPTIONS = [14, 30, 60, 90];

/** Table columns. `sort` is the API sort key, for the sortable ones. */
export const COLUMNS = [
  { id: "referred_date", label: "Referred", sort: "referred_date" },
  { id: "client", label: "Client", sort: "client_name" },
  { id: "partner", label: "Partner" },
  { id: "line", label: "Line" },
  { id: "status", label: "Status", sort: "status" },
  { id: "premium", label: "Premium", sort: "premium" },
  { id: "last_touch", label: "Last touch", sort: "last_touch" },
  { id: "carrier", label: "Carrier" },
] as const;
export type ColumnId = (typeof COLUMNS)[number]["id"];
export const DEFAULT_COLUMNS: ColumnId[] = ["referred_date", "client", "partner", "line", "status", "premium", "last_touch"];
export const DEFAULT_SORT: Sort = "-referred_date";

type Params = Record<string, string | string[] | undefined>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const SORTS = new Set<string>(COLUMNS.flatMap((c) => ("sort" in c ? [c.sort, `-${c.sort}`] : [])));

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const list = <T extends string>(v: string | string[] | undefined, allowed: readonly T[]) =>
  (one(v) ?? "").split(",").filter((x): x is T => (allowed as readonly string[]).includes(x));

/** Read the list state from the page's search params. */
export function parseListParams(params: Params) {
  const stale = Number(one(params.stale));
  const page = Math.max(1, Math.floor(Number(one(params.page))) || 1);
  const sort = one(params.sort);
  const cols = list(params.cols, COLUMNS.map((c) => c.id));
  const rep = one(params.rep);
  const boundFrom = one(params.bound_from);
  const boundTo = one(params.bound_to);

  const query: ApiQuery = {
    status: list(params.status, STATUSES),
    line: list(params.line, LINES),
    stale_days: STALE_OPTIONS.includes(stale) ? stale : undefined,
    rep_id: rep && UUID.test(rep) ? rep : undefined,
    bound_from: boundFrom && ISO_DATE.test(boundFrom) ? boundFrom : undefined,
    bound_to: boundTo && ISO_DATE.test(boundTo) ? boundTo : undefined,
    has_premium: one(params.has_premium) === "true" ? true : undefined,
    q: one(params.q)?.slice(0, 100) || undefined,
    sort: sort && SORTS.has(sort) ? (sort as Sort) : DEFAULT_SORT,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };
  return { query, page, cols: cols.length ? cols : DEFAULT_COLUMNS };
}

/** A query string's view-defining part (no page), in a stable order, for "is this view active?". */
export function viewKey(query: string): string {
  const p = new URLSearchParams(query);
  p.delete("page");
  p.sort();
  return p.toString();
}

export type ListView = { id: string; name: string; query: string; saved?: boolean };

/** Views everyone gets. Dates are the agency's (Arizona) today. */
export function builtInViews(today: string): ListView[] {
  const monthStart = `${today.slice(0, 8)}01`;
  return [
    { id: "all", name: "All referrals", query: "" },
    { id: "open", name: "Open referrals", query: "status=referred,contacted,quoted&sort=last_touch" },
    { id: "stale", name: "Stale 30+ days", query: "stale=30&sort=last_touch" },
    { id: "bound-month", name: "Bound this month", query: `status=bound&bound_from=${monthStart}&bound_to=${today}&sort=-premium` },
    { id: "lost-quoted", name: "Lost after quoting", query: "status=lost&has_premium=true&sort=-premium" },
  ];
}
