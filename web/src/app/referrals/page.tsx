import type { Metadata } from "next";

import { ChooseViewer } from "@/components/choose-viewer";
import { ReferralTable } from "@/components/referral-table";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Referrals" };

export default async function ReferralsPage() {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  const { data: referrals, error } = await api.GET("/referrals");
  if (error) throw new Error("Couldn't load referrals");

  return (
    <>
      <h1 className="mb-1 text-2xl font-semibold">Referrals</h1>
      <p className="mb-6 text-sm text-muted-foreground">{referrals.length} referrals, newest first</p>
      <ReferralTable referrals={referrals} />
    </>
  );
}
