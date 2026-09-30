const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function money(value: number | null | undefined): string {
  return value == null ? "—" : usd.format(value);
}

/** A compact dollar figure for large numbers: $12M. */
export function bigMoney(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact" }).format(value);
}

/**
 * The API sends dates as "YYYY-MM-DD". Formatted from the parts, never via `new Date(string)`,
 * which reads a bare date as UTC midnight and shows the previous day in Arizona.
 */
export function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** "Today", "Yesterday" or "12 days ago", counting from `today` (both "YYYY-MM-DD"). */
export function daysAgo(iso: string, today: string): string {
  const days = Math.round((Date.parse(today) - Date.parse(iso)) / 86_400_000);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`;
}

/** Today in Arizona as "YYYY-MM-DD" (the agency's today, whatever time zone the server runs in). */
export function agencyToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Phoenix" }).format(new Date());
}

/** Blocked values come back as the literal string "blocked" (see the API's app/policy.py). */
export function blockedOr<T>(value: T | "blocked", show: (v: T) => string): string {
  return value === "blocked" ? "Blocked" : show(value);
}
