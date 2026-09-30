"use client";

import { useActionState } from "react";

import { changePassword, type PasswordState } from "@/app/account-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ChangePasswordForm() {
  const [state, action, pending] = useActionState<PasswordState, FormData>(changePassword, null);
  const invalid = (field: string) => (state?.field === field ? true : undefined);
  return (
    <form action={action} className="grid gap-4" key={state?.ok ? "done" : "form"}>
      <div className="grid gap-1.5">
        <Label htmlFor="current">Current password</Label>
        <Input id="current" name="current" type="password" autoComplete="current-password" required aria-invalid={invalid("current_password")} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="new">New password</Label>
        <Input id="new" name="new" type="password" autoComplete="new-password" minLength={15} maxLength={128} required aria-invalid={invalid("new_password")} />
        <p className="text-xs text-muted-foreground">At least 15 characters. A few unrelated words work well.</p>
      </div>
      {state?.message && (
        <p role={state.ok ? "status" : "alert"} className={`text-sm ${state.ok ? "text-up" : "text-destructive"}`}>
          {state.message}
        </p>
      )}
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}
