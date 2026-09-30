"use client";
// The tabs in the header. A Client Component only because the active tab depends on the URL, which
// Server Components can't read (usePathname). The active tab gets the copper underline.

import { ArrowLeftRight, LayoutDashboard, SquareKanban, Store, Trophy } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/pipeline", label: "Pipeline", icon: SquareKanban },
  { href: "/partners", label: "Partners", icon: Store },
  { href: "/top-partners", label: "Top partners", icon: Trophy },
  { href: "/referrals", label: "Referrals", icon: ArrowLeftRight },
] as const;

export function AppNav() {
  const pathname = usePathname();
  // "/" redirects to the dashboard; a record page (/partners/123) keeps its list's tab lit.
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`) || (href === "/dashboard" && pathname === "/");

  return (
    <nav aria-label="Main" className="flex overflow-x-auto">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          aria-current={active(href) ? "page" : undefined}
          className="flex items-center gap-2 border-b-3 border-transparent px-3.5 pt-3.5 pb-2.5 text-sm whitespace-nowrap text-brand-mute hover:text-white aria-[current=page]:border-copper aria-[current=page]:text-white"
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </Link>
      ))}
    </nav>
  );
}
