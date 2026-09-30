"use client";
// The shared list table, on TanStack Table v9. Headless: TanStack tracks sorting and column visibility;
// this component owns the markup. Both slices are controlled by the URL, and sorting is "manual": the
// API sorts every row, not just this page. Each list supplies its own columns.

import {
  columnVisibilityFeature,
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

import { useListParams } from "@/lib/use-list-params";

// Features are opt-in in v9: sorting and visibility state don't exist until registered.
export const gridFeatures = tableFeatures({ rowSortingFeature, columnVisibilityFeature });

/** What the grid needs to know about each column beyond TanStack's definition. */
export type GridColumn = { id: string; label: string; sort?: string; locked?: boolean };

type Props<T extends RowData> = {
  rows: T[];
  columns: ColumnDef<typeof gridFeatures, T, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
  meta: readonly GridColumn[];
  visible: readonly string[];
  sort: string; // API sort key, "-" prefix for descending
  defaultSort: string;
  rowId: (row: T) => string;
  empty: string;
};

const resolve = <S,>(updater: Updater<S>, old: S): S =>
  typeof updater === "function" ? (updater as (old: S) => S)(old) : updater;

export function DataGrid<T extends RowData>({ rows, columns, meta, visible, sort, defaultSort, rowId, empty }: Props<T>) {
  const { update } = useListParams();
  const sortKey = Object.fromEntries(meta.map((c) => [c.id, c.sort]));
  const columnForSort = Object.fromEntries(meta.flatMap((c) => (c.sort ? [[c.sort, c.id]] : [])));
  const label = Object.fromEntries(meta.map((c) => [c.id, c.label]));

  // URL -> table state
  const sorting: SortingState = [{ id: columnForSort[sort.replace(/^-/, "")] ?? "", desc: sort.startsWith("-") }];
  const columnVisibility: ColumnVisibilityState = Object.fromEntries(meta.map((c) => [c.id, visible.includes(c.id)]));

  const table = useTable({
    features: gridFeatures,
    columns: columns.map((c) => ({ ...c, enableSorting: !!sortKey[c.id ?? ""] })),
    data: rows,
    getRowId: rowId,
    manualSorting: true, // the API sorts
    enableSortingRemoval: false, // always sorted by something
    state: { sorting, columnVisibility },
    // table state -> URL (the page then re-renders with data from the API)
    onSortingChange: (updater) => {
      const [next] = resolve(updater, sorting);
      const key = next ? sortKey[next.id] : undefined;
      update({ sort: key ? `${next.desc ? "-" : ""}${key}` : defaultSort });
    },
    onColumnVisibilityChange: (updater) => {
      const next = resolve(updater, columnVisibility);
      update({ cols: meta.filter((c) => next[c.id]).map((c) => c.id).join(",") || null });
    },
  });

  return (
    <div className="space-y-2">
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
        {rows.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">{empty}</p>}
      </div>
    </div>
  );
}
