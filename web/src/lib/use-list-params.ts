"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * Change the list's URL. The page is a Server Component that reads the URL, so a new URL means new
 * data from the API. Any change other than the page itself sends you back to page 1.
 */
export function useListParams() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    if (!("page" in changes)) next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  return { params, update };
}
