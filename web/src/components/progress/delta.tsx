import type { DeltaParts } from "@/lib/progress";

/** ▲ green when better, ▼ red when worse, – gray when level. Higher is better for every metric here.
 *  `onDark` for the scoreboard, where the regular green and red are too dark to read. */
export function Delta({ d, onDark = false, className = "" }: { d: DeltaParts; onDark?: boolean; className?: string }) {
  const level = onDark ? "text-brand-mute" : "text-muted-foreground";
  if (!d) return <span className={`text-xs ${level} ${className}`}>–</span>;
  const tone =
    d.value > 0 ? (onDark ? "text-up-soft" : "text-up") : d.value < 0 ? (onDark ? "text-down-soft" : "text-down") : level;
  const arrow = d.value > 0 ? "▲" : d.value < 0 ? "▼" : "–";
  return (
    <span className={`font-mono text-xs whitespace-nowrap ${tone} ${className}`} aria-label={d.aria} title={d.aria}>
      <span aria-hidden>
        {arrow} {d.value === 0 ? "" : d.label}
      </span>
    </span>
  );
}
