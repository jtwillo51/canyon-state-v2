"use client";
// The Referrals list's columns. The table itself (sorting, column picker, markup) is the shared DataGrid.

import { createColumnHelper } from "@tanstack/react-table";
import Link from "next/link";

import { DataGrid, gridFeatures } from "@/components/list/data-grid";
import { StatusBadge } from "@/components/status-badge";
import type { Referral } from "@/lib/api/types";
import { day, daysAgo, money } from "@/lib/format";
import { COLUMNS, DEFAULT_SORT, type ColumnId } from "@/lib/referral-list";

const helper = createColumnHelper<typeof gridFeatures, Referral>();
const LABEL = Object.fromEntries(COLUMNS.map((c) => [c.id, c.label])) as Record<ColumnId, string>;

// Every column names its id: DataGrid matches columns to the URL and to sort keys by id.
function makeColumns(today: string) {
  return helper.columns([
    helper.accessor("referred_date", { id: "referred_date", header: LABEL.referred_date, cell: (i) => day(i.getValue()) }),
    helper.accessor("client_name", {
      id: "client",
      header: LABEL.client,
      cell: (i) => (
        <Link href={`/referrals/${i.row.original.id}`} className="font-medium hover:underline">
          {i.getValue()}
        </Link>
      ),
    }),
    helper.accessor((r) => r.partner.name, {
      id: "partner",
      header: LABEL.partner,
      cell: (i) => (
        <Link href={`/partners/${i.row.original.partner.id}`} className="hover:underline">
          {i.getValue()}
        </Link>
      ),
    }),
    helper.accessor("line_of_business", { id: "line", header: LABEL.line }),
    helper.accessor("status", { id: "status", header: LABEL.status, cell: (i) => <StatusBadge status={i.getValue()} /> }),
    helper.accessor("premium", {
      id: "premium",
      header: LABEL.premium,
      cell: (i) => <span className="tabular-nums">{money(i.getValue())}</span>,
    }),
    helper.accessor("last_touch", {
      id: "last_touch",
      header: LABEL.last_touch,
      cell: (i) => <span title={day(i.getValue())}>{daysAgo(i.getValue(), today)}</span>,
    }),
    helper.accessor((r) => r.carrier.name, { id: "carrier", header: LABEL.carrier }),
  ]);
}

type Props = { rows: Referral[]; visible: ColumnId[]; sort: string; today: string };

export function ReferralGrid({ rows, visible, sort, today }: Props) {
  return (
    <DataGrid
      rows={rows}
      columns={makeColumns(today)}
      meta={COLUMNS}
      visible={visible}
      sort={sort}
      defaultSort={DEFAULT_SORT}
      rowId={(r) => r.id}
      empty="No referrals match these filters."
    />
  );
}
