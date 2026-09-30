"use client";
// The "vs myself / vs everyone" switch and the strip's collapsed state, shared between the strip (in the
// layout) and the dashboard (in the page) so flipping one updates the other. Saved per person in cookies.

import { createContext, useContext, useState } from "react";

import { saveProgressPrefs } from "@/app/progress-actions";
import type { Compare } from "@/lib/progress";

type Prefs = {
  compare: Compare;
  collapsed: boolean;
  setCompare: (c: Compare) => void;
  setCollapsed: (c: boolean) => void;
};

const PrefsContext = createContext<Prefs | null>(null);

export function ProgressPrefsProvider(props: { compare: Compare; collapsed: boolean; children: React.ReactNode }) {
  const [compare, setCompareState] = useState(props.compare);
  const [collapsed, setCollapsedState] = useState(props.collapsed);
  const value: Prefs = {
    compare,
    collapsed,
    setCompare: (c) => {
      setCompareState(c);
      void saveProgressPrefs({ compare: c });
    },
    setCollapsed: (c) => {
      setCollapsedState(c);
      void saveProgressPrefs({ collapsed: c });
    },
  };
  return <PrefsContext value={value}>{props.children}</PrefsContext>;
}

export function useProgressPrefs(): Prefs {
  const prefs = useContext(PrefsContext);
  if (!prefs) throw new Error("useProgressPrefs outside ProgressPrefsProvider");
  return prefs;
}

/** The two-way switch. `size` sm for the strip; `onDark` for the scoreboard. The chosen side is copper:
 *  it picks what every number is measured against. */
export function CompareSwitch({ size = "md", onDark = false }: { size?: "sm" | "md"; onDark?: boolean }) {
  const { compare, setCompare } = useProgressPrefs();
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";
  const on = onDark
    ? "aria-checked:bg-copper-soft/15 aria-checked:text-copper-soft aria-checked:shadow-[inset_0_-2px_0_var(--copper-soft)] aria-[checked=false]:text-brand-mute"
    : "aria-checked:bg-copper-wash aria-checked:font-medium aria-checked:text-copper-ink aria-checked:shadow-[inset_0_-2px_0_var(--copper)] aria-[checked=false]:text-muted-foreground";
  const option = (value: Compare, label: string) => (
    <button
      type="button"
      role="radio"
      aria-checked={compare === value}
      onClick={() => setCompare(value)}
      className={`${pad} ${on} whitespace-nowrap`}
    >
      {label}
    </button>
  );
  return (
    <div
      role="radiogroup"
      aria-label="Compare with"
      className={`inline-flex w-fit overflow-hidden rounded-md border ${onDark ? "border-brand-line" : "bg-card"}`}
    >
      {option("self", "vs myself")}
      {option("team", "vs everyone")}
    </div>
  );
}
