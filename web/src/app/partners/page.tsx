import type { Metadata } from "next";
import Link from "next/link";

import { ChooseViewer } from "@/components/choose-viewer";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Partners" };

export default async function PartnersPage() {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const { data: partners, error } = await api.GET("/partners");
  if (error) throw new Error("Couldn't load partners");

  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold">Partners</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Business</TableHead>
            <TableHead>Territory</TableHead>
            <TableHead>Primary rep</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {partners.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <Link href={`/partners/${p.id}`} className="font-medium hover:underline">
                  {p.name}
                </Link>
                {p.do_not_contact && (
                  <Badge variant="destructive" className="ml-2">
                    Do not contact
                  </Badge>
                )}
              </TableCell>
              <TableCell>{p.type === "Other" && p.type_other ? p.type_other : p.type}</TableCell>
              <TableCell>{p.business_name}</TableCell>
              <TableCell>{p.territory}</TableCell>
              <TableCell>{p.primary_rep?.name ?? <span className="text-muted-foreground">Unassigned</span>}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}
