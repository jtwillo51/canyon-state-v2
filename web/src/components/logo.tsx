import Link from "next/link";

/** The "CS" mark and name: copper's one exception to "goals only" (it's the brand's signature). */
export function Logo({ href = "/dashboard" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5 py-2.5 text-[15px] font-semibold text-white">
      <span aria-hidden className="grid size-6 place-items-center rounded-[5px] bg-copper text-xs font-semibold text-brand">
        CS
      </span>
      Canyon State
    </Link>
  );
}
