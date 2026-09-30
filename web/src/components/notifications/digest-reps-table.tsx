"use client";
// An admin digest's per-rep table, on the shared DataGrid (local mode: a handful of rows, sorted in the browser).

import { createColumnHelper } from "@tanstack/react-table";

import { DataGrid, gridFeatures } from "@/components/list/data-grid";
import type { Digest } from "@/lib/api/types";
import { money } from "@/lib/format";

type RepWeek = Digest["reps"][number];

const helper = createColumnHelper<typeof gridFeatures, RepWeek>();
const RIGHT = { meta: { align: "right" } };
const META = [
  { id: "rep", label: "Rep" },
  { id: "new_referrals", label: "New referrals" },
  { id: "clients", label: "Clients bound" },
  { id: "sales", label: "Sales" },
  { id: "close_rate", label: "Close rate" },
];

const columns = helper.columns([
  helper.accessor((r) => r.rep.name, { id: "rep", header: "Rep" }),
  helper.accessor("new_referrals", { id: "new_referrals", header: "New referrals", ...RIGHT }),
  helper.accessor("clients", { id: "clients", header: "Clients bound", ...RIGHT }),
  helper.accessor("sales", { id: "sales", header: "Sales", ...RIGHT, cell: (i) => money(i.getValue()) }),
  helper.accessor("close_rate", {
    id: "close_rate",
    header: "Close rate",
    ...RIGHT,
    cell: (i) => (i.getValue() == null ? "—" : `${Math.round(i.getValue()! * 100)}%`),
  }),
]);

export function DigestRepsTable({ reps }: { reps: RepWeek[] }) {
  return (
    <DataGrid mode="local" rows={reps} columns={columns} meta={META} sort={["-clients"]} defaultSort={["-clients"]}
      rowId={(r) => r.rep.id} empty="No active reps." />  // prettier-ignore
  );
}
