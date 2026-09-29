import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { ViewAs } from "@/components/view-as";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans", // globals.css (shadcn's theme) reads --font-sans
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Canyon State", template: "%s · Canyon State" },
  description: "Referral partner reporting for Canyon State Insurance",
};

const NAV = [
  { href: "/pipeline", label: "Pipeline" },
  { href: "/partners", label: "Partners" },
  { href: "/referrals", label: "Referrals" },
] as const;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <header className="border-b">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <nav className="flex items-center gap-5">
              <Link href="/partners" className="font-semibold">
                Canyon State
              </Link>
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="text-sm text-muted-foreground hover:text-foreground">
                  {item.label}
                </Link>
              ))}
            </nav>
            <ViewAs />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
