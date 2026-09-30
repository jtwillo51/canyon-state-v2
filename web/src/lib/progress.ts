// Formatting for progress numbers. Shared by the strip and the dashboard (no server-only imports).
import type { Metric } from "@/lib/api/types";

export type Kind = "count" | "money" | "rate";
export type Compare = "self" | "team";

export const COMPARE_COOKIE = "progress_compare";
export const COLLAPSED_COOKIE = "progress_collapsed";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function formatValue(kind: Kind, v: number | null | undefined): string {
  if (v == null) return "—";
  if (kind === "money") return usd.format(v);
  if (kind === "rate") return `${Math.round(v * 100)}%`;
  return String(Math.round(v));
}

/** Share of goal, e.g. 0.76 -> "76%". */
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export type DeltaParts = { value: number; label: string; aria: string } | null;

/** The comparison to show for a metric: vs last month ("self") or vs the other reps' average ("team"). */
export function delta(kind: Kind, m: Metric, compare: Compare): DeltaParts {
  if (compare === "self") return build(kind, m.vs_last_month, "last month");
  // Reps don't get colleagues' dollars: their sales comparison arrives only as a percentage.
  if (m.vs_team == null && m.vs_team_pct != null) {
    const p = Math.round(m.vs_team_pct * 100);
    return { value: p, label: `${Math.abs(p)}%`, aria: `${Math.abs(p)}% ${p >= 0 ? "above" : "below"} the team average` };
  }
  return build(kind, m.vs_team, "the team average");
}

function build(kind: Kind, d: number | null | undefined, against: string): DeltaParts {
  if (d == null) return null;
  const rounded = kind === "rate" ? Math.round(d * 100) : Math.round(d);
  const size = Math.abs(rounded);
  const label = kind === "money" ? usd.format(size) : kind === "rate" ? `${size} ${size === 1 ? "pt" : "pts"}` : String(size);
  const word = rounded > 0 ? "up" : rounded < 0 ? "down" : "level";
  return { value: rounded, label, aria: `${word} ${label} vs ${against}` };
}
