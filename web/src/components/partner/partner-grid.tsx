"use client";
// The Partners list's columns. The table itself is the shared DataGrid.

import { createColumnHelper } from "@tanstack/react-table";
import Link from "next/link";

import { DataGrid, gridFeatures } from "@/components/list/data-grid";
import { Badge } from "@/components/ui/badge";
import type { PartnerRow } from "@/lib/api/types";
import { day, money } from "@/lib/format";
import { COLUMNS, DEFAULT_SORT, type ColumnId } from "@/lib/partner-list";

const helper = createColumnHelper<typeof gridFeatures, PartnerRow>();
const LABEL = Object.fromEntries(COLUMNS.map((c) => [c.id, c.label])) as Record<ColumnId, string>;
const num = (n: number) => <span className="font-mono">{n}</span>;

function makeColumns(premiumLabel: string) {
  return helper.columns([
    helper.accessor("name", {
      id: "name",
      header: LABEL.name,
      cell: (i) => (
        <>
          <Link href={`/partners/${i.row.original.id}`} className="font-medium text-link hover:underline">
            {i.getValue()}
          </Link>
          {i.row.original.do_not_contact && (
            <Badge variant="destructive" className="ml-2">
              Do not contact
            </Badge>
          )}
        </>
      ),
    }),
    helper.accessor((p) => (p.type === "Other" && p.type_other ? p.type_other : p.type), { id: "type", header: LABEL.type }),
    helper.accessor("business_name", { id: "business", header: LABEL.business }),
    helper.accessor("territory", { id: "territory", header: LABEL.territory }),
    helper.accessor((p) => p.primary_rep?.name ?? "", {
      id: "primary_rep",
      header: LABEL.primary_rep,
      cell: (i) => i.getValue() || <span className="text-muted-foreground">Unassigned</span>,
    }),
    helper.accessor((p) => p.stats.referrals, { id: "referrals", header: LABEL.referrals, cell: (i) => num(i.getValue()) }),
    helper.accessor((p) => p.stats.bound, { id: "bound", header: LABEL.bound, cell: (i) => num(i.getValue()) }),
    helper.accessor((p) => p.stats.close_rate, {
      id: "close_rate",
      header: LABEL.close_rate,
      cell: (i) => {
        const rate = i.getValue();
        return <span className="font-mono">{rate == null ? "—" : `${Math.round(rate * 100)}%`}</span>;
      },
    }),
    helper.accessor((p) => p.stats.bound_premium, {
      id: "bound_premium",
      header: premiumLabel,
      cell: (i) => <span className="font-mono">{i.getValue() ? money(i.getValue()) : "—"}</span>,
    }),
    helper.accessor((p) => p.stats.last_referred, { id: "last_referred", header: LABEL.last_referred, cell: (i) => day(i.getValue()) }),
  ]);
}

type Props = {
  rows: PartnerRow[];
  visible: readonly string[];
  sort: readonly string[];
  isAdmin: boolean;
  // For a ranking (Top partners): a "#" column, its own default sort, no column picker.
  ranked?: { defaultSort: readonly string[]; empty: string };
};

const RANK = { id: "rank", label: "#" };

export function PartnerGrid({ rows, visible, sort, isAdmin, ranked }: Props) {
  // v1's rule: a rep's premium counts only referrals they're credited on, so say so in the header.
  const premiumLabel = isAdmin ? LABEL.bound_premium : "Your bound premium";
  const meta = COLUMNS.map((c) => (c.id === "bound_premium" ? { ...c, label: premiumLabel } : c));
  const columns = makeColumns(premiumLabel);
  return (
    <DataGrid
      rows={rows}
      // Rank is the row's position in the API's order: re-sorting re-ranks.
      columns={ranked ? [helper.display({ id: RANK.id, header: RANK.label, cell: (i) => <span className="text-muted-foreground font-mono">{i.row.index + 1}</span> }), ...columns] : columns}
      meta={ranked ? [RANK, ...meta] : meta}
      visible={ranked ? [RANK.id, ...visible] : visible}
      sort={sort}
      defaultSort={ranked?.defaultSort ?? DEFAULT_SORT}
      rowId={(p) => p.id}
      empty={ranked?.empty ?? "No partners match these filters."}
      columnPicker={!ranked}
    />
  );
}
