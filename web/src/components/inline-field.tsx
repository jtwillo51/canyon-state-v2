"use client";
// Salesforce-style inline edit: a value with an edit button; edit in place, Enter (or Save) saves,
// Escape cancels. The new value shows at once (useOptimistic) and reverts if the API refuses it.

import { Check, Pencil, X } from "lucide-react";
import { useId, useOptimistic, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

export type SaveResult = { ok: true } | { ok: false; message: string };

type Common = {
  label: string;
  value: string; // "" for none
  display?: (value: string) => React.ReactNode; // how to show it when not editing
  save: (value: string) => Promise<SaveResult>;
  canEdit?: boolean;
  readOnlyReason?: string; // shown as a hint when canEdit is false
  align?: "start" | "end"; // "end" in a right-aligned (numeric) table cell, so the editor opens in its column
};
type Props = Common &
  (
    | { kind: "text"; maxLength?: number; placeholder?: string }
    | { kind: "textarea"; maxLength?: number; placeholder?: string }
    | { kind: "number"; min?: number; step?: number }
    | { kind: "select"; options: { value: string; label: string }[] }
  );

export function InlineField(props: Props) {
  const { label, value, display, save, canEdit = true, readOnlyReason, align = "start" } = props;
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [shown, setShown] = useOptimistic(value);
  // What the person typed in a refused save, so reopening shows it. Kept apart from `shown`, which
  // reverts when the save fails: an input's starting value must not change while it's open.
  const [draft, setDraft] = useState<string | null>(null);
  const [opened, setOpened] = useState(0); // a fresh editor (key) each time it opens

  function open(withDraft: string | null) {
    setDraft(withDraft);
    setOpened((n) => n + 1);
    setEditing(true);
  }

  function commit(next: string) {
    if (next === value) return setEditing(false);
    setEditing(false);
    setError(null);
    start(async () => {
      setShown(next);
      const result = await save(next);
      if (!result.ok) {
        setError(result.message);
        open(next); // reopen with what they typed, so nothing is lost
      }
    });
  }

  if (!editing) {
    return (
      <div className="group">
        <span className="text-muted-foreground">{label}: </span>
        <span className={pending ? "opacity-60" : undefined}>{display ? display(shown) : shown || "—"}</span>
        {canEdit ? (
          <button
            type="button"
            onClick={() => open(null)}
            aria-label={`Edit ${label.toLowerCase()}`}
            className="ml-1.5 inline-flex rounded p-0.5 align-middle text-muted-foreground opacity-40 group-hover:opacity-100 hover:text-foreground focus-visible:opacity-100"
          >
            <Pencil className="size-3.5" aria-hidden />
          </button>
        ) : (
          readOnlyReason && <span className="ml-1.5 text-xs text-muted-foreground">({readOnlyReason})</span>
        )}
        {error && !editing && <p role="alert" className="text-xs text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <form
      className="grid gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        commit(String(new FormData(e.currentTarget).get("value") ?? ""));
      }}
      onKeyDown={(e) => e.key === "Escape" && (setEditing(false), setError(null))}
    >
      <label htmlFor={id} className="text-muted-foreground">
        {label}
      </label>
      <div className={`flex items-start gap-1 ${align === "end" ? "justify-end" : ""}`}>
        <Editor key={opened} id={id} {...props} defaultValue={draft ?? value} invalid={!!error} />
        <Button type="submit" size="icon-sm" aria-label="Save" disabled={pending}>
          <Check className="size-4" aria-hidden />
        </Button>
        <Button type="button" size="icon-sm" variant="ghost" aria-label="Cancel" onClick={() => (setEditing(false), setError(null))}>
          <X className="size-4" aria-hidden />
        </Button>
      </div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </form>
  );
}

function Editor(props: Props & { id: string; defaultValue: string; invalid: boolean }) {
  const common = { id: props.id, name: "value", defaultValue: props.defaultValue, autoFocus: true, "aria-invalid": props.invalid || undefined };
  switch (props.kind) {
    case "text":
      return <Input {...common} maxLength={props.maxLength} placeholder={props.placeholder} className="h-8" />;
    case "textarea":
      return (
        <Textarea
          {...common}
          maxLength={props.maxLength}
          placeholder={props.placeholder}
          rows={3}
          // Enter saves; Shift+Enter adds a line.
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
        />
      );
    case "number":
      return <Input {...common} type="number" required min={props.min} step={props.step} className="h-8 w-28" />;
    case "select":
      return (
        <NativeSelect {...common} size="sm">
          {props.options.map((o) => (
            <NativeSelectOption key={o.value} value={o.value}>
              {o.label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      );
  }
}
