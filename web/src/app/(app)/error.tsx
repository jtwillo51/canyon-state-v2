"use client";
// Shown in place of a page that failed to load (the header and navigation stay), instead of a raw error.
// The digest ties what the person saw to the server's log entry without exposing any detail.

import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-md space-y-4 rounded-md border bg-card p-6 text-center">
      <h1 className="text-lg font-semibold">This page didn&apos;t load</h1>
      <p className="text-sm text-muted-foreground">
        Something went wrong getting its data, usually a moment&apos;s interruption. Try again, or go back to the dashboard.
      </p>
      <div className="flex justify-center gap-2">
        <Button type="button" onClick={reset}>
          Try again
        </Button>
        <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
          Dashboard
        </Link>
      </div>
      {error.digest && <p className="font-mono text-xs text-muted-foreground">Reference {error.digest}</p>}
    </div>
  );
}
