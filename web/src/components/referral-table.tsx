import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Referral } from "@/lib/api/types";
import { day, money } from "@/lib/format";

export function ReferralTable({ referrals, showPartner = true }: { referrals: Referral[]; showPartner?: boolean }) {
  if (referrals.length === 0) {
    return <p className="py-6 text-sm text-muted-foreground">No referrals you can see.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Referred</TableHead>
          <TableHead>Client</TableHead>
          {showPartner && <TableHead>Partner</TableHead>}
          <TableHead>Line</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Premium</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {referrals.map((r) => (
          <TableRow key={r.id}>
            <TableCell className="text-muted-foreground">{day(r.referred_date)}</TableCell>
            <TableCell>
              <Link href={`/referrals/${r.id}`} className="font-medium hover:underline">
                {r.client_name}
              </Link>
            </TableCell>
            {showPartner && (
              <TableCell>
                <Link href={`/partners/${r.partner.id}`} className="hover:underline">
                  {r.partner.name}
                </Link>
              </TableCell>
            )}
            <TableCell>{r.line_of_business}</TableCell>
            <TableCell>
              <StatusBadge status={r.status} />
            </TableCell>
            <TableCell className="text-right tabular-nums">{money(r.premium)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
