import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

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

// The shell every page shares. The app itself (header, progress strip, the sign-in requirement) is in
// (app)/layout.tsx; the sign-in pages are in (auth)/ and load nothing that needs a session, so an expired
// session can never bounce them back to themselves.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        {/* The public demo: server-only env var, set on Vercel. */}
        {process.env.DEMO_MODE === "true" && (
          <p className="bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-950">
            <strong>Demo</strong> · every person, partner and client here is fictional · changes reset nightly · use{" "}
            <strong>View as</strong> to switch between an admin and a rep
          </p>
        )}
        {children}
      </body>
    </html>
  );
}
