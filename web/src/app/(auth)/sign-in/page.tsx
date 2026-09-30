import type { Metadata } from "next";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default async function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  const { expired, next } = await searchParams;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Sign in</h1>
        {expired ? (
          <p role="status" className="mt-1 text-sm text-muted-foreground">
            Your session ended. Sign in again to continue.
          </p>
        ) : null}
      </div>
      <SignInForm next={typeof next === "string" ? next : undefined} />
      <p className="text-xs text-muted-foreground">Forgot your password? Ask an admin for a reset link.</p>
    </div>
  );
}
