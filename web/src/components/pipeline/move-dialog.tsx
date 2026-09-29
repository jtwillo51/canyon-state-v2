"use client";
// Asks for what a move needs: a premium (quoted, bound), a bind date (bound), and, when an admin
// moves a card forward, the rep who did the work. Browser validation is for convenience; the API
// checks everything again.

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import type { StatusChange, UserRef } from "@/lib/api/types";
import { detailsFor, type PendingMove } from "@/lib/pipeline";

type Props = {
  pending: PendingMove | null;
  isAdmin: boolean;
  reps: UserRef[];
  today: string;
  onCancel: () => void;
  onConfirm: (change: StatusChange) => void;
};

const VERB = { quoted: "Quote", bound: "Bind", contacted: "Mark contacted", referred: "Move to referred", lost: "Mark lost" };

export function MoveDialog({ pending, isAdmin, reps, today, onCancel, onConfirm }: Props) {
  const r = pending?.referral;
  const target = pending?.target;
  const ask = pending ? detailsFor(pending, isAdmin) : null;

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!target || !ask) return;
    const form = new FormData(e.currentTarget);
    const rep = form.get("credit_rep_id");
    onConfirm({
      status: target,
      premium: ask.premium ? Number(form.get("premium")) : null,
      bound_date: ask.bindDate ? String(form.get("bound_date")) : null,
      credit_rep_id: ask.rep && rep ? String(rep) : null,
    });
  }

  return (
    <Dialog open={!!pending} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        {r && target && (
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>
                {VERB[target]}: {r.client_name}
              </DialogTitle>
              <DialogDescription>
                {r.line_of_business} · referred by {r.partner.name}
              </DialogDescription>
            </DialogHeader>

            {ask?.premium && (
              <div className="grid gap-1.5">
                <Label htmlFor="premium">Annual premium ($)</Label>
                <Input
                  id="premium"
                  name="premium"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  autoFocus
                  defaultValue={r.premium ?? undefined}
                />
              </div>
            )}
            {ask?.bindDate && (
              <div className="grid gap-1.5">
                <Label htmlFor="bound_date">Bind date</Label>
                <Input id="bound_date" name="bound_date" type="date" required min={r.referred_date} max={today} defaultValue={today} />
              </div>
            )}
            {ask?.rep && (
              <div className="grid gap-1.5">
                <Label htmlFor="credit_rep_id">Who did this work?</Label>
                <NativeSelect id="credit_rep_id" name="credit_rep_id" required={ask.repRequired} defaultValue="" className="w-full">
                  <NativeSelectOption value="" disabled={ask.repRequired}>
                    Choose a rep
                  </NativeSelectOption>
                  {reps.map((rep) => (
                    <NativeSelectOption key={rep.id} value={rep.id}>
                      {rep.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <p className="text-xs text-muted-foreground">They get credit for every step this move passes{ask.repRequired ? "" : " (only needed if steps are missing)"}.</p>
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="submit">{VERB[target]}</Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
