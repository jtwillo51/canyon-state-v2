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

/** Blocked values come back as the literal string "blocked" (see the API's app/policy.py). */
export function blockedOr<T>(value: T | "blocked", show: (v: T) => string): string {
  return value === "blocked" ? "Blocked" : show(value);
}
