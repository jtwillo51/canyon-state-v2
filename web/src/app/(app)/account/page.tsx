import type { Metadata } from "next";

import { signOutEverywhere } from "@/app/account-actions";
import { Button } from "@/components/ui/button";
import { getSessionToken } from "@/lib/viewer";

import { ChangePasswordForm } from "./change-password-form";

export const metadata: Metadata = { title: "Your account" };

export default async function AccountPage() {
  if (!(await getSessionToken())) {
    return (
      <p className="rounded-md border border-dashed p-8 text-center text-muted-foreground">
        You&apos;re using <strong>View as</strong>. Sign in with a password to manage an account.
      </p>
    );
  }
  return (
    <div className="max-w-md space-y-8">
      <h1 className="text-2xl font-semibold">Your account</h1>
      <section aria-labelledby="password" className="space-y-3">
        <h2 id="password" className="text-lg font-semibold">
          Change password
        </h2>
        <ChangePasswordForm />
      </section>
      <section aria-labelledby="everywhere" className="space-y-2">
        <h2 id="everywhere" className="text-lg font-semibold">
          Sign out everywhere
        </h2>
        <p className="text-sm text-muted-foreground">
          Ends every session you have, on this device and any other. Use it if you signed in on a shared computer.
        </p>
        <form action={signOutEverywhere}>
          <Button type="submit" variant="outline">
            Sign out everywhere
          </Button>
        </form>
      </section>
    </div>
  );
}
