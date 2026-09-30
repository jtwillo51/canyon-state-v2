import type { Kind } from "@/lib/progress";

/** A thin copper bar: how far a number is toward its goal. Copper in this app always means "measured
 *  against a goal". Counts and money fill toward the goal (full once it's met). A rate is drawn on its own
 *  0-100% scale with a tick at the target, so 87% against a 60% target reads as "well past the line". */
export function GoalMeter({ kind, value, goal, onDark = false, className = "" }: {
  kind: Kind; value: number | null; goal: number | null; onDark?: boolean; className?: string;
}) {  // prettier-ignore
  if (value == null || !goal) return null;
  const rate = kind === "rate";
  const fill = Math.min(1, Math.max(0, rate ? value : value / goal));
  return (
    <div
      role="progressbar"
      aria-label="Progress toward goal"
      aria-valuenow={Math.round((value / goal) * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`relative h-1 rounded-full ${onDark ? "bg-brand-line" : "bg-copper-wash"} ${className}`}
    >
      <div className={`h-full rounded-full ${onDark ? "bg-copper-soft" : "bg-copper"}`} style={{ width: `${fill * 100}%` }} />
      {rate && goal <= 1 && (
        <span
          aria-hidden
          className={`absolute -top-[3px] h-2.5 w-0.5 ${onDark ? "bg-white" : "bg-foreground"}`}
          style={{ left: `${goal * 100}%` }}
        />
      )}
    </div>
  );
}
