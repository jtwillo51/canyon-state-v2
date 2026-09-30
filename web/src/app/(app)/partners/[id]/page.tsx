import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChooseViewer } from "@/components/choose-viewer";
import { ChangeHistory } from "@/components/history/change-history";
import { DoNotContactToggle, DoNotDiscuss, PartnerContactFields } from "@/components/partner/partner-fields";
import { LocalReferralGrid } from "@/components/referral/referral-grid";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Unavailable } from "@/components/unavailable";
import { agencyToday, bigMoney } from "@/lib/format";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Partner" };

export default async function PartnerPage({ params }: PageProps<"/partners/[id]">) {
  const { id } = await params;
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  // All in parallel. Referrals are scoped by the API: a rep sees only their own.
  const path = { params: { path: { partner_id: id } } };
  const [partnerRes, referralsRes, history, me, reps] = await Promise.all([
    api.GET("/partners/{partner_id}", path),
    api.GET("/referrals", { params: { query: { partner_id: id, limit: 200 } } }),
    api.GET("/partners/{partner_id}/history", path),
    api.GET("/users/me"),
    api.GET("/users/reps"),
  ]);
  if (partnerRes.response.status === 404 || partnerRes.response.status === 422) notFound();
  // Only the partner and who's viewing are essential; every other section degrades on its own.
  const partner = partnerRes.data;
  const referrals = referralsRes.data?.items;
  if (!partner || !me.data) throw new Error("Couldn't load this partner");

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
        <DoNotContactToggle partner={partner} />
      </div>

      {/* Shown to the whole team on purpose, so nobody raises the topic; anyone can edit it. */}
      <DoNotDiscuss partner={partner} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
          </CardHeader>
          <CardContent>
            <PartnerContactFields partner={partner} reps={reps.data ?? []} isAdmin={me.data.role === "admin"} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Production</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {partner.production.length === 0 && <p className="text-muted-foreground">None recorded</p>}
            {partner.production.map((y) => (
              <p key={y.year} className="flex justify-between font-mono">
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
        {referrals ? (
          <LocalReferralGrid rows={referrals} visible={["referred_date", "client", "line", "status", "premium", "last_touch"]} today={agencyToday()} />
        ) : (
          <Unavailable what="this partner's referrals" />
        )}
      </section>

      {history.data ? <ChangeHistory events={history.data} /> : <Unavailable what="the change history" />}
    </div>
  );
}
