// The development "View as" switcher: a Server Component that loads the people, wrapping a tiny
// Client Component that submits the form when the choice changes.
import { viewAs } from "@/app/actions";
import { devApi } from "@/lib/api/client";
import { getViewerId } from "@/lib/viewer";

import { ViewAsSelect } from "./view-as-select";

export async function ViewAs() {
  const [{ data: users }, current] = await Promise.all([devApi().GET("/dev/users"), getViewerId()]);
  if (!users) return null; // DEV_AUTH is off, so there's nobody to switch to

  return (
    <form action={viewAs} className="flex items-center gap-2 text-sm">
      <label htmlFor="view-as" className="text-muted-foreground">
        View as
      </label>
      <ViewAsSelect users={users} current={current} />
    </form>
  );
}
