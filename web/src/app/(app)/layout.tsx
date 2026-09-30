import { LogOut } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { signOut } from "@/app/account-actions";
import { AppNav } from "@/components/app-nav";
import { Logo } from "@/components/logo";
import { NotificationBell } from "@/components/notifications/bell";
import { ProgressPrefsProvider } from "@/components/progress/prefs";
import { ProgressStrip } from "@/components/progress/progress-strip";
import { ViewAs } from "@/components/view-as";
import { publicApi } from "@/lib/api/client";
import { getNotifications } from "@/lib/notifications-server";
import { getProgress, getProgressPrefs } from "@/lib/progress-server";
import { getApi, getSessionToken } from "@/lib/viewer";

// Every page of the app. Signed in (a session), or in development and the demo, someone chosen in "View as";
// otherwise to the sign-in page. A session that has ended turns any API call into a 401, which the API client
// turns into a redirect to sign in (lib/api/client.ts).
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [api, session] = await Promise.all([getApi(), getSessionToken()]);
  if (!api) {
    const { data: devUsers } = await publicApi().GET("/dev/users"); // only answers in development and the demo
    if (!devUsers) redirect("/sign-in");
  }

  // Loaded here because every page shows them (once per request, in parallel).
  const [me, progress, prefs, notifications] = await Promise.all([
    api ? api.GET("/users/me").then((r) => r.data) : null,
    getProgress(),
    getProgressPrefs(),
    getNotifications(),
  ]);

  return (
    <>
      <header className="bg-brand text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-stretch gap-x-6 px-4">
          <Logo />
          <AppNav isAdmin={me?.role === "admin"} />
          <div className="ml-auto flex items-center gap-3 py-2">
            {notifications && <NotificationBell unread={notifications.unread} />}
            {session && me ? (
              <div className="flex items-center gap-1 text-sm">
                <Link href="/account" className="rounded-md px-2 py-1 text-brand-mute hover:bg-white/10 hover:text-white">
                  {me.name}
                </Link>
                <form action={signOut}>
                  <button
                    type="submit"
                    aria-label="Sign out"
                    title="Sign out"
                    className="grid size-8 place-items-center rounded-md text-brand-mute hover:bg-white/10 hover:text-white"
                  >
                    <LogOut className="size-4" aria-hidden />
                  </button>
                </form>
              </div>
            ) : (
              <ViewAs />
            )}
          </div>
        </div>
      </header>
      {/* One provider around the strip and the page, so the dashboard and the strip share the switch. */}
      <ProgressPrefsProvider compare={prefs.compare} collapsed={prefs.collapsed}>
        {progress && <ProgressStrip progress={progress} />}
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
      </ProgressPrefsProvider>
    </>
  );
}
