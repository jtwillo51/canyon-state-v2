// The bell in the header: a link to the notifications page, with the unread count.
import { Bell } from "lucide-react";
import Link from "next/link";

export function NotificationBell({ unread }: { unread: number }) {
  const label = unread ? `Notifications, ${unread} unread` : "Notifications";
  return (
    <Link
      href="/notifications"
      aria-label={label}
      title={label}
      className="relative grid size-8 place-items-center rounded-md text-brand-mute hover:bg-white/10 hover:text-white"
    >
      <Bell className="size-4" aria-hidden />
      {unread > 0 && (
        <span
          aria-hidden
          className="absolute -top-0.5 -right-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-white px-1 font-mono text-[10px] font-medium text-brand"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
