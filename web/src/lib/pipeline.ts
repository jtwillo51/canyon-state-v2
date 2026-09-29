// The browser's view of the pipeline rules, for choosing what to ask before a move. The API
// (api/app/pipeline.py) is the authority: anything that slips past here is refused there.
import type { Referral, ReferralStatus } from "@/lib/api/types";

export const COLUMNS: { status: ReferralStatus; label: string }[] = [
  { status: "referred", label: "Referred" },
  { status: "contacted", label: "Contacted" },
  { status: "quoted", label: "Quoted" },
  { status: "bound", label: "Bound" },
  { status: "lost", label: "Lost" },
];

const RANK: Partial<Record<ReferralStatus, number>> = { referred: 0, contacted: 1, quoted: 2, bound: 3 };

/** Forward along the pipeline from an open status: the only move a rep may make besides "lost". */
export function isForward(from: ReferralStatus, to: ReferralStatus): boolean {
  const a = RANK[from];
  const b = RANK[to];
  return a !== undefined && b !== undefined && from !== "bound" && b > a;
}

export type PendingMove = { referral: Referral; target: ReferralStatus };

/** What the move dialog must ask for. `rep` is required for an admin's forward move. */
export function detailsFor({ referral, target }: PendingMove, isAdmin: boolean) {
  const reopening = referral.status === "lost" && target !== "lost";
  return {
    premium: target === "quoted" || target === "bound",
    bindDate: target === "bound",
    // Reopening may or may not pass uncredited steps, so the rep is offered but not required.
    rep: isAdmin && (isForward(referral.status, target) || reopening),
    repRequired: isAdmin && isForward(referral.status, target),
  };
}

/** Whether a drop needs the dialog before it can be sent. */
export function needsDialog(move: PendingMove, isAdmin: boolean): boolean {
  if (move.target === "lost") return false;
  // A rep's backward move goes straight to the API, which says why it's refused.
  if (!isAdmin && !isForward(move.referral.status, move.target)) return false;
  const d = detailsFor(move, isAdmin);
  return d.premium || d.bindDate || d.rep;
}
