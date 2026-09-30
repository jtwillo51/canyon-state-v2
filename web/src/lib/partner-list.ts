// The Partners list's URL state (filters, period, sort, columns, page) and its built-in views.
// Same pattern as referral-list.ts: the URL is the state, and invalid values are dropped.
import type { paths } from "@/lib/api/schema";
import { list, one, UUID, type ListView } from "@/lib/list-views";

export type PartnerApiQuery = NonNullable<paths["/partners"]["get"]["parameters"]["query"]>;
type Sort = NonNullable<PartnerApiQuery["sort"]>;
type Period = NonNullable<PartnerApiQuery["period"]>;
type PartnerType = NonNullable<PartnerApiQuery["type"]>[number];

export const PAGE_SIZE = 50;
export const TYPES: PartnerType[] = ["Loan officer", "Realtor", "Financial advisor", "Other"];
export const PERIODS: { value: Period; label: string }[] = [
  { value: "r12", label: "Last 12 months" },
  { value: "ytd", label: "Year to date" },
  { value: "all", label: "All time" },
];

export const COLUMNS = [
  { id: "name", label: "Partner", sort: "name", locked: true },
  { id: "type", label: "Type" },
  { id: "business", label: "Business" },
  { id: "territory", label: "Territory" },
  { id: "primary_rep", label: "Primary rep" },
  { id: "referrals", label: "Referrals", sort: "referrals" },
  { id: "bound", label: "Bound", sort: "bound" },
  { id: "close_rate", label: "Close rate", sort: "close_rate" },
  { id: "bound_premium", label: "Bound premium", sort: "bound_premium" },
  { id: "last_referred", label: "Last referral", sort: "last_referred" },
] as const;
export type ColumnId = (typeof COLUMNS)[number]["id"];
export const DEFAULT_COLUMNS: ColumnId[] = [
  "name", "type", "business", "primary_rep", "referrals", "bound", "close_rate", "bound_premium", "last_referred",
];  // prettier-ignore
export const DEFAULT_SORT: Sort = "-referrals";

const SORTS = new Set<string>(COLUMNS.flatMap((c) => ("sort" in c ? [c.sort, `-${c.sort}`] : [])));
const bool = (v: string | undefined) => (v === "true" ? true : v === "false" ? false : undefined);

export function parsePartnerParams(params: Record<string, string | string[] | undefined>) {
  const page = Math.max(1, Math.floor(Number(one(params.page))) || 1);
  const sort = one(params.sort);
  const period = one(params.period);
  const rep = one(params.rep);
  const cols = list(params.cols, COLUMNS.map((c) => c.id));

  const query: PartnerApiQuery = {
    type: list(params.type, TYPES),
    primary_rep_id: rep && UUID.test(rep) ? rep : undefined,
    unassigned: bool(one(params.unassigned)),
    do_not_contact: bool(one(params.dnc)),
    no_referrals: bool(one(params.no_referrals)),
    q: one(params.q)?.slice(0, 100) || undefined,
    period: PERIODS.some((p) => p.value === period) ? (period as Period) : "r12",
    sort: sort && SORTS.has(sort) ? (sort as Sort) : DEFAULT_SORT,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };
  return { query, page, cols: cols.length ? cols : DEFAULT_COLUMNS };
}

export function builtInPartnerViews(): ListView[] {
  return [
    { id: "all", name: "All partners", query: "" },
    { id: "top-bound", name: "Most bound", query: "sort=-bound" },
    { id: "best-rate", name: "Best close rate", query: "no_referrals=false&sort=-close_rate" },
    { id: "quiet", name: "No referrals in 12 months", query: "no_referrals=true&sort=name" },
    { id: "unassigned", name: "No primary rep", query: "unassigned=true&sort=name" },
  ];
}
