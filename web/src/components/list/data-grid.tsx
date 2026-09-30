"use client";
// The shared table, on TanStack Table v9, used by every table in the app so headers behave the same way:
// click a header to sort by it (click again to flip), shift-click another to add it as the next sort
// (up to three; small numbers show the order).
//
// Two modes:
// - "url" (paged lists): sorting and column visibility live in the URL and the API sorts every row, not
//   just this page ("manual" sorting). Sort keys are the API's.
// - "local" (small tables): the browser sorts the rows it has. Sort keys are column ids.

import {
  columnVisibilityFeature,
  createSortedRowModel,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type ColumnDef,
  type ColumnVisibilityState,
  type RowData,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Columns3 } from "lucide-react";
import { useState } from "react";

import { MAX_SORT } from "@/lib/list-views";
import { useListParams } from "@/lib/use-list-params";

// Features are opt-in in v9. The sorted row model is only used in local mode (url mode sorts manually).
export const gridFeatures = tableFeatures({
  rowSortingFeature,
  columnVisibilityFeature,
  sortedRowModel: createSortedRowModel(),
});

/** What the grid needs to know about each column beyond TanStack's definition. */
export type GridColumn = { id: string; label: string; sort?: string; locked?: boolean; noSort?: boolean };

type Props<T extends RowData> = {
  rows: T[];
  columns: ColumnDef<typeof gridFeatures, T, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
  meta: readonly GridColumn[];
  sort: readonly string[]; // "-" prefix for descending
  defaultSort: readonly string[];
  rowId: (row: T) => string;
  empty: string;
  mode?: "url" | "local";
  visible?: readonly string[]; // columns to show (default: all)
  columnPicker?: boolean;
};

const resolve = <S,>(updater: Updater<S>, old: S): S =>
  typeof updater === "function" ? (updater as (old: S) => S)(old) : updater;

/** Local-mode comparator: numbers and text in natural order; empty values count as lowest. */
function compareValues(a: unknown, b: unknown): number {
  const empty = (v: unknown) => v == null || v === "";
  if (empty(a) || empty(b)) return empty(a) === empty(b) ? 0 : empty(a) ? -1 : 1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "en", { numeric: true, sensitivity: "base" });
}

export function DataGrid<T extends RowData>(props: Props<T>) {
  const { rows, columns, meta, sort, defaultSort, rowId, empty, mode = "url", visible, columnPicker = mode === "url" } = props;
  const { update } = useListParams();
  const local = mode === "local";
  const label = Object.fromEntries(meta.map((c) => [c.id, c.label]));

  // Sort keys <-> column ids. In url mode the keys are the API's (client -> client_name); locally they're ids.
  const keyFor = (id: string) => (local ? id : meta.find((c) => c.id === id)?.sort);
  const idFor = (key: string) => (local ? key : meta.find((c) => c.sort === key)?.id);
  const toState = (keys: readonly string[]): SortingState =>
    keys.flatMap((k) => {
      const id = idFor(k.replace(/^-/, ""));
      return id ? [{ id, desc: k.startsWith("-") }] : [];
    });
  const toKeys = (state: SortingState) =>
    state.flatMap((s) => {
      const key = keyFor(s.id);
      return key ? [`${s.desc ? "-" : ""}${key}`] : [];
    });

  const [localSorting, setLocalSorting] = useState<SortingState>(() => toState(sort));
  const sorting = local ? localSorting : toState(sort);
  const columnVisibility: ColumnVisibilityState = Object.fromEntries(
    meta.map((c) => [c.id, !visible || visible.includes(c.id)]),
  );

  const table = useTable({
    features: gridFeatures,
    columns: columns.map((c) => {
      const m = meta.find((x) => x.id === c.id);
      return {
        ...c,
        enableSorting: local ? !m?.noSort : !!m?.sort,
        sortFn: (a: { getValue: (id: string) => unknown }, b: { getValue: (id: string) => unknown }, id: string) =>
          compareValues(a.getValue(id), b.getValue(id)),
      } as typeof c;
    }),
    data: rows,
    getRowId: rowId,
    manualSorting: !local, // url mode: the API sorts
    enableMultiSort: true, // shift-click adds a column
    maxMultiSortColCount: MAX_SORT,
    enableSortingRemoval: false, // a plain click always leaves something sorted
    state: { sorting, columnVisibility },
    onSortingChange: (updater) => {
      const next = resolve(updater, sorting);
      if (local) return setLocalSorting(next);
      const keys = toKeys(next);
      const same = keys.join(",") === defaultSort.join(",");
      update({ sort: keys.length && !same ? keys.join(",") : null });
    },
    onColumnVisibilityChange: (updater) => {
      const next = resolve(updater, columnVisibility);
      update({ cols: meta.filter((c) => next[c.id]).map((c) => c.id).join(",") || null });
    },
  });
  const multi = sorting.length > 1;

  return (
    <div className="space-y-2">
      {columnPicker && (
        <details className="relative ml-auto w-fit">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm">
            <Columns3 className="size-4" aria-hidden /> Columns
          </summary>
          <fieldset className="absolute right-0 z-10 mt-1 grid w-48 gap-1 rounded-lg border bg-popover p-2 text-sm shadow-md">
            <legend className="sr-only">Visible columns</legend>
            {table.getAllLeafColumns().map((column) => (
              <label key={column.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={column.getIsVisible()}
                  disabled={meta.find((c) => c.id === column.id)?.locked}
                  onChange={(e) => column.toggleVisibility(e.target.checked)}
                />
                {label[column.id]}
              </label>
            ))}
          </fieldset>
        </details>
      )}

      {/* Capped height with its own scrolling, so the sideways scrollbar is always on screen; the header stays pinned. */}
      <div className="max-h-[70vh] overflow-auto rounded-md border bg-card">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-muted text-left text-xs text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const Icon = sorted === "asc" ? ArrowUp : sorted === "desc" ? ArrowDown : ArrowUpDown;
                  const align = (header.column.columnDef.meta as { align?: string } | undefined)?.align;
                  return (
                    <th
                      key={header.id}
                      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
                      className={`px-3 py-2 font-medium whitespace-nowrap ${align === "right" ? "text-right" : ""}`}
                    >
                      {header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          title="Click to sort. Shift-click to add as a secondary sort."
                          className="inline-flex items-center gap-1 hover:text-foreground"
                        >
                          <table.FlexRender header={header} />
                          <Icon className={`size-3.5 ${sorted ? "" : "text-muted-foreground/50"}`} aria-hidden />
                          {multi && sorted && (
                            <span className="text-[10px] text-muted-foreground tabular-nums" aria-label={`sort ${header.column.getSortIndex() + 1}`}>
                              {header.column.getSortIndex() + 1}
                            </span>
                          )}
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
              <tr key={row.id} className="border-t first:border-t-0 hover:bg-accent/60">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    // Right-aligned columns are the numeric ones: set them in Plex Mono so digits line up.
                    className={`px-3 py-2 whitespace-nowrap ${(cell.column.columnDef.meta as { align?: string } | undefined)?.align === "right" ? "text-right font-mono text-[13px]" : ""}`}
                  >
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">{empty}</p>}
      </div>
    </div>
  );
}
