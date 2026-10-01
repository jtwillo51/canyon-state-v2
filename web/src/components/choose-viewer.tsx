// Shown in place of a page's data until someone is chosen in "View as". It's the first thing a demo visitor
// sees, so it offers the people directly (one click each) rather than pointing at the dropdown. Only reachable
// in development and the demo: without DEV_AUTH or DEMO_MODE the app layout sends everyone to sign in.
import { viewAs } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { publicApi } from "@/lib/api/client";

const ROLES = [
  { role: "admin", label: "Admins", blurb: "The whole agency: every rep, partner and referral, plus goals and the team." },
  { role: "rep", label: "Reps", blurb: "Only the referrals they worked on and their own numbers against goal." },
] as const;

export async function ChooseViewer() {
  const { data: users } = await publicApi().GET("/dev/users");

  return (
    <section aria-labelledby="choose-viewer" className="mx-auto max-w-2xl space-y-5 rounded-md border bg-card p-6">
      <div className="space-y-1">
        <h1 id="choose-viewer" className="text-xl font-semibold">
          Who do you want to be?
        </h1>
        <p className="text-sm text-muted-foreground">
          Pick someone to see the app as they would. You can also choose a person in <strong>View as</strong> (top
          right) at any time to switch.
        </p>
      </div>
      {ROLES.map(({ role, label, blurb }) => {
        const people = users?.filter((u) => u.role === role) ?? [];
        if (!people.length) return null;
        return (
          <div key={role} role="group" aria-label={label} className="space-y-2">
            <div>
              <h2 className="text-sm font-semibold">{label}</h2>
              <p className="text-xs text-muted-foreground">{blurb}</p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {people.map((u) => (
                <form key={u.id} action={viewAs}>
                  <input type="hidden" name="userId" value={u.id} />
                  <Button type="submit" variant="outline" className="w-full justify-start">
                    {u.name}
                  </Button>
                </form>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
