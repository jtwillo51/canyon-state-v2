import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

/** "Not found" in the app's own style: a missing record, a mistyped address, or a page this viewer can't see. */
export function NotFoundCard() {
  return (
    <div className="mx-auto max-w-md space-y-4 rounded-md border bg-card p-6 text-center">
      <h1 className="text-lg font-semibold">This page isn&apos;t here</h1>
      <p className="text-sm text-muted-foreground">
        The link may be mistyped, the record may have been removed, or it isn&apos;t one you have access to.
      </p>
      <div className="flex justify-center gap-2">
        <Link href="/dashboard" className={buttonVariants()}>
          Dashboard
        </Link>
        <Link href="/referrals" className={buttonVariants({ variant: "outline" })}>
          Referrals
        </Link>
      </div>
    </div>
  );
}
