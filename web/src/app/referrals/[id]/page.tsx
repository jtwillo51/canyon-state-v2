import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChooseViewer } from "@/components/choose-viewer";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { blockedOr, day, money } from "@/lib/format";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Referral" };

const STEP_LABEL = { introduction: "Introduced", contact: "Contacted", quote: "Quoted", bind: "Bound" } as const;

export default async function ReferralPage({ params }: PageProps<"/referrals/[id]">) {
  const { id } = await params;
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const { data: r, response } = await api.GET("/referrals/{referral_id}", {
    params: { path: { referral_id: id } },
  });
  // The API returns 404 for someone else's referral too, so it's indistinguishable from "doesn't exist".
  if (response.status === 404 || response.status === 422) notFound();
  if (!r) throw new Error("Couldn't load this referral");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          {r.client_name} <StatusBadge status={r.status} />
        </h1>
        <p className="text-muted-foreground">
          {r.line_of_business} · referred by{" "}
          <Link href={`/partners/${r.partner.id}`} className="hover:underline">
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
          <CardContent className="space-y-1 text-sm">
            <p>Carrier: {r.carrier.name}</p>
            <p>Premium: {r.premium == null ? "Not quoted yet" : `${money(r.premium)} / yr`}</p>
            <p>Bound: {day(r.bound_date)}</p>
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

      <section>
        <h2 className="mb-2 text-lg font-semibold">Steps</h2>
        <ol className="space-y-2 border-l pl-4 text-sm">
          {r.steps.map((s) => (
            <li key={s.step}>
              <span className="font-medium">{STEP_LABEL[s.step]}</span> by {s.rep.name}{" "}
              <span className="text-muted-foreground">· {day(s.date)}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
