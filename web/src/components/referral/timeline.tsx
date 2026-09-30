import { CircleCheck, CircleX, Flag, Mail, Phone, Users, type LucideIcon } from "lucide-react";

import { day } from "@/lib/format";
import type { TimelineEntry } from "@/lib/timeline";

const ICON: Record<TimelineEntry["icon"], LucideIcon> = {
  "in-person": Users,
  phone: Phone,
  email: Mail,
  referred: Flag,
  step: CircleCheck,
  bound: CircleCheck,
  lost: CircleX,
};

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <ol className="relative space-y-4 border-l pl-6">
      {entries.map((e) => {
        const Icon = ICON[e.icon];
        return (
          <li key={e.key} className="relative">
            <span
              className={`absolute top-0.5 -left-[2.1rem] flex size-6 items-center justify-center rounded-full border bg-background ${
                e.icon === "bound" ? "text-primary" : e.icon === "lost" ? "text-destructive" : "text-muted-foreground"
              }`}
            >
              <Icon className="size-3.5" aria-hidden />
            </span>
            <p className="text-sm">
              <span className={e.kind === "milestone" ? "font-medium" : undefined}>{e.title}</span>
              <span className="text-muted-foreground"> · {day(e.date)}</span>
            </p>
            {e.notes && <p className="mt-0.5 text-sm text-muted-foreground">{e.notes}</p>}
            {e.loggedBy && <p className="mt-0.5 text-xs text-muted-foreground">Logged by {e.loggedBy}</p>}
          </li>
        );
      })}
    </ol>
  );
}
