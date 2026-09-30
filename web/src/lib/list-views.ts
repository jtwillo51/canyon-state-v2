// Views are query strings. Shared by every list page.

export type ListView = { id: string; name: string; query: string; saved?: boolean };

/** A query string's view-defining part (no page), in a stable order, for "is this view active?". */
export function viewKey(query: string): string {
  const p = new URLSearchParams(query);
  p.delete("page");
  p.sort();
  return p.toString();
}

/** One value from Next's searchParams, which may be a string, an array, or missing. */
export const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

/** A comma-separated param as a list, keeping only allowed values. */
export const list = <T extends string>(v: string | string[] | undefined, allowed: readonly T[]) =>
  (one(v) ?? "").split(",").filter((x): x is T => (allowed as readonly string[]).includes(x));

export const MAX_SORT = 3;

/**
 * A multi-column sort from the URL ("-close_rate,-referrals"): valid keys only, each column once, at most
 * three. Falls back to the list's default sort.
 */
export function parseSort<T extends string>(v: string | string[] | undefined, allowed: ReadonlySet<string>, fallback: T[]): T[] {
  const seen = new Set<string>();
  const keys = (one(v) ?? "")
    .split(",")
    .filter((k) => allowed.has(k) && !seen.has(k.replace(/^-/, "")) && seen.add(k.replace(/^-/, "")))
    .slice(0, MAX_SORT) as T[];
  return keys.length ? keys : fallback;
}

export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
