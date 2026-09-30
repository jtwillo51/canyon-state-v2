"use client";
// A multi-select filter as toggle chips, stored in the URL as a comma-separated list.

import { useListParams } from "@/lib/use-list-params";

type Props = { name: string; options: readonly string[]; label: string };

export function Chips({ name, options, label }: Props) {
  const { params, update } = useListParams();
  const selected = new Set((params.get(name) ?? "").split(",").filter(Boolean));
  const toggle = (value: string) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    update({ [name]: options.filter((o) => next.has(o)).join(",") || null });
  };
  return (
    <fieldset className="flex flex-wrap items-center gap-1">
      <legend className="sr-only">{label}</legend>
      {options.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={selected.has(o)}
          onClick={() => toggle(o)}
          className="rounded-full border px-2.5 py-0.5 text-xs first-letter:uppercase aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground"
        >
          {o}
        </button>
      ))}
    </fieldset>
  );
}
