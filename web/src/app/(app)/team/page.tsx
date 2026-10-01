import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { getApi } from "@/lib/viewer";

import { setActive } from "./actions";
import { AddPerson, NewLinkButton } from "./team-forms";

export const metadata: Metadata = { title: "Team" };

const when = new Intl.DateTimeFormat("en-US", { timeZone: "America/Phoenix", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export default async function TeamPage() {
  const api = await getApi();
  if (!api) notFound();
  const [people, me] = await Promise.all([api.GET("/team"), api.GET("/users/me")]);
  if (!people.data || !me.data) notFound(); // not an admin: the page doesn't exist for them

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Team</h1>
        <p className="text-sm text-muted-foreground">
          Add people and give them a one-time link to set their own password. Nobody, admins included, ever sees a password.
        </p>
      </div>

      <AddPerson />

      <div className="overflow-x-auto rounded-md border bg-card">
        <table className="w-full text-sm whitespace-nowrap">
          <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Email</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Last sign-in</th>
              <th className="px-3 py-2 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {people.data.map((p) => (
              <tr key={p.id} className="border-t first:border-t-0">
                <td className="px-3 py-2 font-medium">{p.name}</td>
                <td className="px-3 py-2 text-muted-foreground">{p.email}</td>
                <td className="px-3 py-2 capitalize">{p.role}</td>
                <td className="px-3 py-2">
                  {!p.active ? (
                    <Badge variant="outline">Deactivated</Badge>
                  ) : p.has_password ? (
                    <Badge variant="secondary">Active</Badge>
                  ) : (
                    <Badge variant="outline">Waiting to set a password</Badge>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-[13px] text-muted-foreground">
                  {p.last_sign_in_at ? when.format(new Date(p.last_sign_in_at)) : "—"}
                </td>
                <td className="px-3 py-2">
                  {p.id !== me.data.id && (
                    <div className="flex justify-end gap-2">
                      {p.active && <NewLinkButton userId={p.id} name={p.name} reset={p.has_password} />}
                      <form action={setActive.bind(null, p.id, !p.active)}>
                        <button type="submit" className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground">
                          {p.active ? "Deactivate" : "Reactivate"}
                        </button>
                      </form>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Deactivating someone signs them out everywhere at once. Their history stays, attributed to them.
      </p>
    </div>
  );
}
