import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChooseViewer } from "@/components/choose-viewer";
import { ReferralTable } from "@/components/referral-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { bigMoney } from "@/lib/format";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Partner" };

export default async function PartnerPage({ params }: PageProps<"/partners/[id]">) {
  const { id } = await params;
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  // Both requests run in parallel. Referrals are scoped by the API: a rep sees only their own.
  const [partnerRes, referralsRes] = await Promise.all([
    api.GET("/partners/{partner_id}", { params: { path: { partner_id: id } } }),
    api.GET("/referrals", { params: { query: { partner_id: id, limit: 200 } } }),
  ]);
  if (partnerRes.response.status === 404 || partnerRes.response.status === 422) notFound();
  const partner = partnerRes.data;
  const referrals = referralsRes.data?.items;
  if (!partner || !referrals) throw new Error("Couldn't load this partner");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          {partner.name}
          {partner.do_not_contact && (
            <Badge variant="destructive" className="ml-3 align-middle">
              Do not contact
            </Badge>
          )}
        </h1>
        <p className="text-muted-foreground">
          {partner.type === "Other" && partner.type_other ? partner.type_other : partner.type} ·{" "}
          {partner.business_name}
          {partner.territory && ` · ${partner.territory}`}
        </p>
      </div>

      {partner.sensitive_items && (
        <div role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>Do not discuss:</strong> {partner.sensitive_items}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>{partner.phone || "—"}</p>
            <p>{partner.email || "—"}</p>
            <p className="text-muted-foreground">Primary rep: {partner.primary_rep?.name ?? "Unassigned"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Production</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {partner.production.length === 0 && <p className="text-muted-foreground">None recorded</p>}
            {partner.production.map((y) => (
              <p key={y.year} className="flex justify-between tabular-nums">
                <span>{y.year}</span>
                <span>
                  {bigMoney(y.amount)}
                  {!y.verified && <span className="ml-2 text-muted-foreground">(unverified)</span>}
                </span>
              </p>
            ))}
          </CardContent>
        </Card>
      </div>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Referrals</h2>
        <ReferralTable referrals={referrals} showPartner={false} />
      </section>
    </div>
  );
}
