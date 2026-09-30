// A record's change history, from the audit trail: who changed what, and when (newest first).
// Collapsed by default: it's there for "who did this?", not for everyday reading.
import type { FieldChange, HistoryEvent } from "@/lib/api/types";
import { day, money } from "@/lib/format";

const FIELD: Record<string, string> = {
  status: "Status",
  premium: "Premium",
  carrier_id: "Carrier",
  line_of_business: "Line",
  bound_date: "Bind date",
  lost_date: "Lost date",
  referred_date: "Referred",
  client_name: "Client name",
  client_address: "Client address",
  client_birthday: "Client birthday",
  sensitive_items: "Do not discuss",
  primary_rep_id: "Primary rep",
  territory: "Territory",
  do_not_contact: "Do not contact",
  step: "Step",
  rep_id: "Rep",
  logged_by_id: "Logged by",
  method: "How",
  notes: "Notes",
  date: "Date",
  name: "Name",
  business_name: "Business",
  phone: "Phone",
  email: "Email",
  year: "Year",
  amount: "Amount",
  verified: "Verified",
};
const MONEY = new Set(["premium", "amount"]);
const DATES = new Set(["bound_date", "lost_date", "referred_date", "date", "client_birthday"]);
const HIDDEN = new Set(["referral_id", "partner_id"]); // the page it's on already says which

const VERB: Record<string, Partial<Record<HistoryEvent["action"], string>>> = {
  referrals: { insert: "created the referral", update: "changed the referral", delete: "deleted the referral", restore: "restored the referral" },
  referral_steps: { insert: "credited a step", delete: "removed a step credit", restore: "restored a step credit" },
  activities: { insert: "logged an activity", update: "edited an activity", delete: "deleted an activity" },
  partners: { insert: "added the partner", update: "changed the partner", delete: "deleted the partner" },
  partner_production: { insert: "added production", update: "changed production", delete: "removed production" },
};
const JOB: Record<string, string> = { "stale-referrals": "The stale-referral check", "weekly-digest": "The weekly digest", run_jobs: "A scheduled job" };

const when = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Phoenix", // the agency's clock, wherever the server runs
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function value(field: string, v: FieldChange["before"], label: string | null | undefined): string {
  if (label) return label;
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (MONEY.has(field)) return money(Number(v));
  if (DATES.has(field) && typeof v === "string") return day(v);
  return String(v);
}

function Change({ c, inserted }: { c: FieldChange; inserted: boolean }) {
  const name = FIELD[c.field] ?? c.field.replaceAll("_", " ");
  if (c.redacted) return <li>{name}: changed <span className="text-muted-foreground">(value not recorded)</span></li>;
  const after = value(c.field, c.after, c.after_label);
  if (inserted) return <li>{name}: {after}</li>;
  return (
    <li>
      {name}: <span className="text-muted-foreground line-through decoration-muted-foreground/50">{value(c.field, c.before, c.before_label)}</span>{" "}
      → {after}
    </li>
  );
}

function who(e: HistoryEvent): string {
  if (e.actor) return e.actor.name;
  if (e.actor_label) return JOB[e.actor_label] ?? e.actor_label;
  return "System";
}

export function ChangeHistory({ events }: { events: HistoryEvent[] }) {
  return (
    <details className="group rounded-md border bg-card">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium select-none">
        Change history <span className="font-mono font-normal text-muted-foreground">{events.length}</span>
      </summary>
      {events.length === 0 ? (
        <p className="border-t px-4 py-3 text-sm text-muted-foreground">No changes recorded yet.</p>
      ) : (
        <ol className="divide-y border-t">
          {events.map((e) => {
            const changes = e.changes.filter((c) => !HIDDEN.has(c.field));
            return (
              <li key={e.id} className="px-4 py-2.5 text-sm">
                <p>
                  <span className="font-medium">{who(e)}</span> {VERB[e.entity]?.[e.action] ?? `${e.action}d ${e.entity}`}
                  <time dateTime={e.occurred_at} className="ml-2 text-xs text-muted-foreground">
                    {when.format(new Date(e.occurred_at))}
                  </time>
                </p>
                {changes.length > 0 && (
                  <ul className="mt-0.5 text-muted-foreground [&>li]:text-foreground/80">
                    {changes.map((c) => (
                      <Change key={c.field} c={c} inserted={e.action === "insert"} />
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </details>
  );
}
