// The development "View as" switcher: a Server Component that loads the people, wrapping a tiny
// Client Component that submits the form when the choice changes.
import { viewAs } from "@/app/actions";
import { publicApi } from "@/lib/api/client";
import { getViewerId } from "@/lib/viewer";

import { ViewAsSelect } from "./view-as-select";

export async function ViewAs() {
  const [{ data: users }, current] = await Promise.all([publicApi().GET("/dev/users"), getViewerId()]);
  if (!users) return null; // DEV_AUTH is off, so there's nobody to switch to

  return (
    // key: React 19 resets a form after its action runs, which would put the select back on the old
    // person. A new key per viewer remounts the form with the right default instead.
    <form key={current ?? "none"} action={viewAs} className="flex items-center gap-2 text-sm">
      <label htmlFor="view-as" className="text-brand-mute">
        View as
      </label>
      <ViewAsSelect users={users} current={current} />
    </form>
  );
}
