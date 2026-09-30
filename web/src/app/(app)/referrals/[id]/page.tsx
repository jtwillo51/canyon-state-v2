import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChooseViewer } from "@/components/choose-viewer";
import { ChangeHistory } from "@/components/history/change-history";
import { LogActivity } from "@/components/referral/log-activity";
import { ReferralPolicyFields } from "@/components/referral/referral-fields";
import { Timeline } from "@/components/referral/timeline";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Unavailable } from "@/components/unavailable";
import { agencyToday, blockedOr, day } from "@/lib/format";
import { buildTimeline } from "@/lib/timeline";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Referral" };

export default async function ReferralPage({ params }: PageProps<"/referrals/[id]">) {
  const { id } = await params;
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const path = { params: { path: { referral_id: id } } };
  const [referral, activities, history, me, team, carriers] = await Promise.all([
    api.GET("/referrals/{referral_id}", path),
    api.GET("/referrals/{referral_id}/activities", path),
    api.GET("/referrals/{referral_id}/history", path),
    api.GET("/users/me"),
    api.GET("/users"),
    api.GET("/carriers"),
  ]);
  // The API returns 404 for someone else's referral too, so it's indistinguishable from "doesn't exist".
  if (referral.response.status === 404 || referral.response.status === 422) notFound();
  // Only the referral itself and who's viewing are essential; every other section degrades on its own
  // (a notice in its place) so one slow or failed call can't take the whole page down.
  const r = referral.data;
  if (!r || !me.data) throw new Error("Couldn't load this referral");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          {r.client_name} <StatusBadge status={r.status} />
        </h1>
        <p className="text-muted-foreground">
          {r.line_of_business} · referred by{" "}
          <Link href={`/partners/${r.partner.id}`} className="text-link hover:underline">
            {r.partner.name}
          </Link>{" "}
          on {day(r.referred_date)}
        </p>
      </div>

      {r.sensitive_items && (
        <div role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>Do not discuss:</strong> {r.sensitive_items}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Policy</CardTitle>
          </CardHeader>
          <CardContent>
            <ReferralPolicyFields referral={r} carriers={carriers.data ?? [r.carrier]} isAdmin={me.data.role === "admin"} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Client</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Address: {blockedOr(r.client_address, (v) => v || "—")}</p>
            <p>Birthday: {blockedOr(r.client_birthday, day)}</p>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Timeline</h2>
        {/* key: switching viewer remounts the form, so "who made contact" defaults to the new viewer
            and nothing typed as someone else carries over. */}
        {team.data ? (
          <LogActivity
            key={me.data.id}
            referralId={r.id}
            referredDate={r.referred_date}
            today={agencyToday()}
            viewerId={me.data.id}
            team={team.data}
          />
        ) : (
          <Unavailable what="the team list for logging activity" />
        )}
        {!activities.data && <Unavailable what="logged activity (the pipeline steps below are complete)" />}
        <Timeline entries={buildTimeline(r, activities.data ?? [])} />
      </section>

      {history.data ? <ChangeHistory events={history.data} /> : <Unavailable what="the change history" />}
    </div>
  );
}
