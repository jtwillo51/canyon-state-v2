"use client";
// The only Client Component so far: it exists because submitting on change needs a browser event.

import { NativeSelect, NativeSelectOptGroup, NativeSelectOption } from "@/components/ui/native-select";

type User = { id: string; name: string; role: "admin" | "rep" };

export function ViewAsSelect({ users, current }: { users: User[]; current: string | null }) {
  const group = (role: User["role"]) => users.filter((u) => u.role === role);

  return (
    <NativeSelect
      id="view-as"
      name="userId"
      size="sm"
      defaultValue={current ?? ""}
      onChange={(e) => e.currentTarget.form?.requestSubmit()}
    >
      <NativeSelectOption value="" disabled>
        Choose a person
      </NativeSelectOption>
      <NativeSelectOptGroup label="Admins">
        {group("admin").map((u) => (
          <NativeSelectOption key={u.id} value={u.id}>
            {u.name}
          </NativeSelectOption>
        ))}
      </NativeSelectOptGroup>
      <NativeSelectOptGroup label="Reps">
        {group("rep").map((u) => (
          <NativeSelectOption key={u.id} value={u.id}>
            {u.name}
          </NativeSelectOption>
        ))}
      </NativeSelectOptGroup>
    </NativeSelect>
  );
}
