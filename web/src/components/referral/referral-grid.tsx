"use client";
// The Referrals list table, on TanStack Table v9. Headless: TanStack tracks sorting and column
// visibility; this component owns the markup. Both slices are controlled by the URL, and sorting is
// "manual": the API sorts (the whole list, not just this page), the table only asks for it.

import {
  columnVisibilityFeature,
  createColumnHelper,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type ColumnVisibilityState,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Columns3 } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import type { Referral } from "@/lib/api/types";
import { day, money } from "@/lib/format";
import { COLUMNS, DEFAULT_SORT, type ColumnId } from "@/lib/referral-list";
import { useListParams } from "@/lib/use-list-params";

// Features are opt-in in v9: sorting and visibility state don't exist until registered.
const features = tableFeatures({ rowSortingFeature, columnVisibilityFeature });
const helper = createColumnHelper<typeof features, Referral>();

const SORT_KEY = Object.fromEntries(COLUMNS.map((c) => [c.id, "sort" in c ? c.sort : undefined]));
const COLUMN_FOR_SORT = Object.fromEntries(COLUMNS.flatMap((c) => ("sort" in c ? [[c.sort, c.id]] : [])));
const LABEL = Object.fromEntries(COLUMNS.map((c) => [c.id, c.label])) as Record<ColumnId, string>;

function daysAgo(iso: string, today: string): string {
  const days = Math.round((Date.parse(today) - Date.parse(iso)) / 86_400_000);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`;
}

function makeColumns(today: string) {
  const sortable = (id: ColumnId) => ({ enableSorting: SORT_KEY[id] !== undefined });
  return helper.columns([
    helper.accessor("referred_date", { header: LABEL.referred_date, cell: (i) => day(i.getValue()), ...sortable("referred_date") }),
    helper.accessor("client_name", {
      id: "client",
      header: LABEL.client,
      cell: (i) => (
        <Link href={`/referrals/${i.row.original.id}`} className="font-medium hover:underline">
          {i.getValue()}
        </Link>
      ),
      ...sortable("client"),
    }),
    helper.accessor((r) => r.partner.name, {
      id: "partner",
      header: LABEL.partner,
      cell: (i) => (
        <Link href={`/partners/${i.row.original.partner.id}`} className="hover:underline">
          {i.getValue()}
        </Link>
      ),
      ...sortable("partner"),
    }),
    helper.accessor("line_of_business", { id: "line", header: LABEL.line, ...sortable("line") }),
    helper.accessor("status", { header: LABEL.status, cell: (i) => <StatusBadge status={i.getValue()} />, ...sortable("status") }),
    helper.accessor("premium", {
      header: LABEL.premium,
      cell: (i) => <span className="tabular-nums">{money(i.getValue())}</span>,
      ...sortable("premium"),
    }),
    helper.accessor("last_touch", {
      header: LABEL.last_touch,
      cell: (i) => <span title={day(i.getValue())}>{daysAgo(i.getValue(), today)}</span>,
      ...sortable("last_touch"),
    }),
    helper.accessor((r) => r.carrier.name, { id: "carrier", header: LABEL.carrier, ...sortable("carrier") }),
  ]);
}

const resolve = <T,>(updater: Updater<T>, old: T): T =>
  typeof updater === "function" ? (updater as (old: T) => T)(old) : updater;

type Props = { rows: Referral[]; visible: ColumnId[]; sort: string; today: string };

export function ReferralGrid({ rows, visible, sort, today }: Props) {
  const { update } = useListParams();

  // URL -> table state
  const sorting: SortingState = [{ id: COLUMN_FOR_SORT[sort.replace("-", "")], desc: sort.startsWith("-") }];
  const columnVisibility: ColumnVisibilityState = Object.fromEntries(COLUMNS.map((c) => [c.id, visible.includes(c.id)]));

  const table = useTable({
    features,
    columns: makeColumns(today),
    data: rows,
    getRowId: (r) => r.id,
    manualSorting: true, // the API sorts
    enableSortingRemoval: false, // always sorted by something
    state: { sorting, columnVisibility },
    // table state -> URL (the page then re-renders with data from the API)
    onSortingChange: (updater) => {
      const [next] = resolve(updater, sorting);
      const key = next ? SORT_KEY[next.id] : undefined;
      update({ sort: key ? `${next.desc ? "-" : ""}${key}` : DEFAULT_SORT });
    },
    onColumnVisibilityChange: (updater) => {
      const next = resolve(updater, columnVisibility);
      update({ cols: COLUMNS.filter((c) => next[c.id]).map((c) => c.id).join(",") || null });
    },
  });

  return (
    <div className="space-y-2">
      <details className="relative ml-auto w-fit">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm">
          <Columns3 className="size-4" aria-hidden /> Columns
        </summary>
        <fieldset className="absolute right-0 z-10 mt-1 grid w-44 gap-1 rounded-lg border bg-popover p-2 text-sm shadow-md">
          <legend className="sr-only">Visible columns</legend>
          {table.getAllLeafColumns().map((column) => (
            <label key={column.id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={column.getIsVisible()}
                disabled={column.id === "client"} // the row's link; always shown
                onChange={(e) => column.toggleVisibility(e.target.checked)}
              />
              {LABEL[column.id as ColumnId]}
            </label>
          ))}
        </fieldset>
      </details>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const Icon = sorted === "asc" ? ArrowUp : sorted === "desc" ? ArrowDown : ArrowUpDown;
                  return (
                    <th
                      key={header.id}
                      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
                      className="px-3 py-2 font-medium whitespace-nowrap"
                    >
                      {header.column.getCanSort() ? (
                        <button type="button" onClick={header.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 hover:text-foreground">
                          <table.FlexRender header={header} />
                          <Icon className={`size-3.5 ${sorted ? "" : "text-muted-foreground/50"}`} aria-hidden />
                        </button>
                      ) : (
                        <table.FlexRender header={header} />
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 whitespace-nowrap">
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">No referrals match these filters.</p>}
      </div>
    </div>
  );
}
