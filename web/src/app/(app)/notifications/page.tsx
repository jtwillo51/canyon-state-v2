import type { Metadata } from "next";
import Link from "next/link";

import { ChooseViewer } from "@/components/choose-viewer";
import { DigestCard } from "@/components/notifications/digest-card";
import { Button } from "@/components/ui/button";
import type { Notification } from "@/lib/api/types";
import { day } from "@/lib/format";
import { getNotifications } from "@/lib/notifications-server";
import { getApi } from "@/lib/viewer";

import { markAllRead, markRead } from "./actions";

export const metadata: Metadata = { title: "Notifications" };

function Unread({ n }: { n: Notification }) {
  return n.read_at ? null : <span aria-label="Unread" className="size-2 shrink-0 rounded-full bg-brand" />;
}

function MarkRead({ n }: { n: Notification }) {
  if (n.read_at) return null;
  return (
    <form action={markRead.bind(null, n.id)}>
      <Button type="submit" variant="ghost" size="sm" className="text-muted-foreground">
        Mark read
      </Button>
    </form>
  );
}

export default async function NotificationsPage() {
  const [page, api] = await Promise.all([getNotifications(), getApi()]);
  if (!page || !api) return <ChooseViewer />;
  const { data: me } = await api.GET("/users/me");
  const isAdmin = me?.role === "admin";
  const stale = page.items.filter((n) => n.stale);
  const digests = page.items.filter((n) => n.digest);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Notifications</h1>
          <p className="text-sm text-muted-foreground">
            {page.unread ? `${page.unread} unread` : "All caught up"} · checked every morning, digests on Mondays
          </p>
        </div>
        {page.unread > 0 && (
          <form action={markAllRead}>
            <Button type="submit" variant="outline" size="sm">
              Mark all as read
            </Button>
          </form>
        )}
      </div>

      <section aria-labelledby="attention" className="space-y-2">
        <h2 id="attention" className="text-lg font-semibold">
          Needs attention
        </h2>
        {/* Stale nudges go to the reps credited on a referral (app/jobs/stale.py), never to admins, so an
            admin's empty list says where to look instead of claiming there's nothing stale. */}
        {stale.length === 0 && isAdmin ? (
          <p className="text-sm text-muted-foreground">
            Stale-referral nudges go to the reps credited on them.{" "}
            <Link href="/referrals?stale=14&sort=last_touch" className="text-link hover:underline">
              See every open referral with no touch in 14 days
            </Link>
            .
          </p>
        ) : stale.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No stale referrals. Anything open with no touch in 14 days will show up here.
          </p>
        ) : (
          <ul className="divide-y rounded-md border bg-card">
            {stale.map((n) => {
              const s = n.stale!;
              return (
                <li key={n.id} className="flex items-center gap-3 px-4 py-3">
                  <Unread n={n} />
                  <div className="min-w-0 flex-1">
                    <Link href={`/referrals/${s.id}`} className="font-medium text-link hover:underline">
                      {s.client_name}
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {s.partner.name} · <span className="capitalize">{s.status}</span> · no touch in{" "}
                      <span className="font-mono">{s.days_since_touch}</span> days (last {day(s.last_touch)})
                    </p>
                  </div>
                  <MarkRead n={n} />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="digests" className="space-y-2">
        <h2 id="digests" className="text-lg font-semibold">
          Weekly digests
        </h2>
        {digests.length === 0 ? (
          <p className="text-sm text-muted-foreground">Your first digest arrives Monday at 7 am, with last week&apos;s numbers.</p>
        ) : (
          <div className="space-y-4">
            {digests.map((n) => (
              <DigestCard key={n.id} digest={n.digest!} unread={!n.read_at} action={<MarkRead n={n} />} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
