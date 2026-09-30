"use client";
// Built-in and saved views as tabs, plus "Save view". A view is a link to a query string.

import { X } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";

import { deleteView, saveView } from "@/app/referrals/actions";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { viewKey, type ListView } from "@/lib/referral-list";
import { useListParams } from "@/lib/use-list-params";

export function ViewTabs({ views }: { views: ListView[] }) {
  const { params } = useListParams();
  const current = viewKey(params.toString());
  const matching = views.find((v) => viewKey(v.query) === current);
  const [saving, setSaving] = useState(false);

  return (
    <nav aria-label="Views" className="flex flex-wrap items-center gap-1 border-b pb-2">
      {views.map((v) => {
        const active = v === matching;
        return (
          <span key={v.id} className="group inline-flex items-center">
            <Link
              href={v.query ? `/referrals?${v.query}` : "/referrals"}
              aria-current={active ? "page" : undefined}
              className={`rounded-md px-2.5 py-1 text-sm ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
              {v.name}
            </Link>
            {v.saved && <DeleteView id={v.id} name={v.name} />}
          </span>
        );
      })}
      {!matching && (
        <Button type="button" variant="outline" size="sm" className="ml-auto" onClick={() => setSaving(true)}>
          Save view
        </Button>
      )}
      <SaveViewDialog open={saving} query={new URLSearchParams(params.toString())} onClose={() => setSaving(false)} />
    </nav>
  );
}

function DeleteView({ id, name }: { id: string; name: string }) {
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      aria-label={`Delete view ${name}`}
      disabled={pending}
      onClick={() => start(() => deleteView(id))}
      className="rounded p-0.5 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"
    >
      <X className="size-3.5" aria-hidden />
    </button>
  );
}

function SaveViewDialog({ open, query, onClose }: { open: boolean; query: URLSearchParams; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  query.delete("page");

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const name = String(new FormData(e.currentTarget).get("name") ?? "").trim();
            start(async () => {
              const result = await saveView(name, query.toString());
              if (result.ok) {
                setError(null);
                onClose();
              } else setError(result.message);
            });
          }}
        >
          <DialogHeader>
            <DialogTitle>Save this view</DialogTitle>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="view-name">Name</Label>
            <Input id="view-name" name="name" required maxLength={60} autoFocus aria-invalid={error ? true : undefined} />
            <p className="text-xs text-muted-foreground">Saves the current filters, sort and columns. Only you see it.</p>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
