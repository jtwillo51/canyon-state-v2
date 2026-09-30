// A referral's timeline: logged activity and pipeline milestones in one newest-first stream.
// Built from data the page already has; nothing is stored twice.
import type { Activity, Referral } from "@/lib/api/types";

export type TimelineEntry = {
  key: string;
  date: string; // YYYY-MM-DD
  kind: "activity" | "milestone";
  icon: "in-person" | "phone" | "email" | "referred" | "step" | "bound" | "lost";
  title: string;
  notes?: string;
  loggedBy?: string; // shown when someone logged it for a colleague
};

const STEP_TITLE = { introduction: "Introduced", contact: "Contacted", quote: "Quoted", bind: "Bound" } as const;
const METHOD_ICON = { "In person": "in-person", Phone: "phone", Email: "email" } as const;
const METHOD_TITLE = { "In person": "Met in person", Phone: "Phone call", Email: "Email" } as const;

// Same-day entries: the later pipeline stage first, and activity above milestones.
const SAME_DAY_ORDER = { activity: 0, bind: 1, quote: 2, contact: 3, introduction: 4, lost: 0.5, referred: 5 };

export function buildTimeline(referral: Referral, activities: Activity[]): TimelineEntry[] {
  const entries: (TimelineEntry & { order: number })[] = [
    {
      key: "referred",
      date: referral.referred_date,
      kind: "milestone",
      icon: "referred",
      title: `Referred by ${referral.partner.name}`,
      order: SAME_DAY_ORDER.referred,
    },
    ...referral.steps.map((s) => ({
      key: `step-${s.step}`,
      date: s.date,
      kind: "milestone" as const,
      icon: s.step === "bind" ? ("bound" as const) : ("step" as const),
      title: `${STEP_TITLE[s.step]} by ${s.rep.name}`,
      order: SAME_DAY_ORDER[s.step],
    })),
    ...activities.map((a) => ({
      key: a.id,
      date: a.date,
      kind: "activity" as const,
      icon: METHOD_ICON[a.method],
      title: `${METHOD_TITLE[a.method]} · ${a.rep.name}`,
      notes: a.notes || undefined,
      loggedBy: a.logged_by.id !== a.rep.id ? a.logged_by.name : undefined,
      order: SAME_DAY_ORDER.activity,
    })),
  ];
  if (referral.status === "lost" && referral.lost_date) {
    entries.push({ key: "lost", date: referral.lost_date, kind: "milestone", icon: "lost", title: "Marked lost", order: SAME_DAY_ORDER.lost });
  }
  // Newest first; activities already arrive newest-first, and sort() keeps that order within a tie.
  return entries.sort((a, b) => b.date.localeCompare(a.date) || a.order - b.order);
}
