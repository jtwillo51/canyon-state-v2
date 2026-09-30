import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { ProgressPrefsProvider } from "@/components/progress/prefs";
import { ProgressStrip } from "@/components/progress/progress-strip";
import { ViewAs } from "@/components/view-as";
import { getProgress, getProgressPrefs } from "@/lib/progress-server";

import "./globals.css";

// IBM Plex: Sans for words, Mono for numbers (money, counts, rates), so columns line up like a scoreboard.
const plexSans = IBM_Plex_Sans({
  variable: "--font-sans", // globals.css (shadcn's theme) reads --font-sans
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: { default: "Canyon State", template: "%s · Canyon State" },
  description: "Referral partner reporting for Canyon State Insurance",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // Every page shows the progress strip, so the layout loads it (once per request, in parallel).
  const [progress, prefs] = await Promise.all([getProgress(), getProgressPrefs()]);
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        {/* The public demo: server-only env var, set on Vercel. */}
        {process.env.DEMO_MODE === "true" && (
          <p className="bg-copper-wash px-4 py-1.5 text-center text-xs text-copper-ink">
            <strong>Demo</strong> · every person, partner and client here is fictional · changes reset nightly · use{" "}
            <strong>View as</strong> to switch between an admin and a rep
          </p>
        )}
        <header className="bg-brand text-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-stretch gap-x-6 px-4">
            <Link href="/dashboard" className="flex items-center gap-2.5 py-2.5 text-[15px] font-semibold">
              <span aria-hidden className="grid size-6 place-items-center rounded-[5px] bg-copper text-xs font-semibold text-brand">
                CS
              </span>
              Canyon State
            </Link>
            <AppNav />
            <div className="ml-auto flex items-center py-2">
              <ViewAs />
            </div>
          </div>
        </header>
        {/* One provider around the strip and the page, so the dashboard and the strip share the switch. */}
        <ProgressPrefsProvider compare={prefs.compare} collapsed={prefs.collapsed}>
          {progress && <ProgressStrip progress={progress} />}
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
        </ProgressPrefsProvider>
      </body>
    </html>
  );
}
