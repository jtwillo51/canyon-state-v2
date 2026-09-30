"use client";
// The pipeline board. A Client Component: dragging needs the browser. Data arrives as props from the
// Server Component page; moves go through a Server Action, and the API has the final say on every rule.

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useId, useOptimistic, useState, useTransition } from "react";

import { moveReferral } from "@/app/(app)/pipeline/actions";
import type { Me, Referral, ReferralStatus, StatusChange, UserRef } from "@/lib/api/types";
import { COLUMNS, needsDialog, type PendingMove } from "@/lib/pipeline";

import { Card, Column } from "./column";
import { MoveDialog } from "./move-dialog";

const LABEL = Object.fromEntries(COLUMNS.map((c) => [c.status, c.label])) as Record<ReferralStatus, string>;

type Props = { referrals: Referral[]; viewer: Me; reps: UserRef[]; today: string };

export function PipelineBoard({ referrals, viewer, reps, today }: Props) {
  // useOptimistic: show the card in its new column immediately. When the transition ends the board
  // shows the real data again: the refreshed page on success, the old column on failure.
  const [cards, moveCard] = useOptimistic(referrals, (state, move: { id: string; status: ReferralStatus }) =>
    state.map((r) => (r.id === move.id ? { ...r, status: move.status } : r)),
  );
  const [, startTransition] = useTransition();
  const [dragging, setDragging] = useState<Referral | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = viewer.role === "admin";
  // A stable id keeps dnd-kit's generated attributes identical on server and client (no hydration mismatch).
  const dndId = useId();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), // a click on a card's link isn't a drag
    useSensor(KeyboardSensor), // space to pick up, arrows to move, space to drop
  );
  const byId = (id: unknown) => cards.find((r) => r.id === id);

  function submit(referral: Referral, change: StatusChange) {
    setError(null);
    startTransition(async () => {
      moveCard({ id: referral.id, status: change.status });
      const result = await moveReferral(referral.id, change);
      if (!result.ok) setError(`${referral.client_name}: ${result.message}`);
    });
  }

  function onDragStart({ active }: DragStartEvent) {
    setDragging(byId(active.id) ?? null);
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setDragging(null);
    const referral = byId(active.id);
    const target = over?.id as ReferralStatus | undefined;
    if (!referral || !target || target === referral.status) return;

    const move = { referral, target };
    if (needsDialog(move, isAdmin)) setPending(move);
    else submit(referral, { status: target });
  }

  // What screen readers hear while dragging with the keyboard.
  const name = (id: unknown) => byId(id)?.client_name ?? "Referral";
  const announcements: Announcements = {
    onDragStart: ({ active }) => `Picked up ${name(active.id)}.`,
    onDragOver: ({ active, over }) =>
      over ? `${name(active.id)} is over ${LABEL[over.id as ReferralStatus]}.` : `${name(active.id)} is not over a column.`,
    onDragEnd: ({ active, over }) =>
      over ? `${name(active.id)} dropped in ${LABEL[over.id as ReferralStatus]}.` : `${name(active.id)} was dropped.`,
    onDragCancel: ({ active }) => `Moving ${name(active.id)} was cancelled.`,
  };

  return (
    <>
      {error && (
        <p role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <DndContext
        id={dndId}
        sensors={sensors}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={() => setDragging(null)}
        accessibility={{ announcements }}
      >
        <div className="grid auto-cols-[minmax(13rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-2">
          {COLUMNS.map((col) => (
            <Column key={col.status} status={col.status} label={col.label} referrals={cards.filter((r) => r.status === col.status)} />
          ))}
        </div>
        <DragOverlay>{dragging && <Card referral={dragging} overlay />}</DragOverlay>
      </DndContext>

      <MoveDialog
        pending={pending}
        isAdmin={isAdmin}
        reps={reps}
        today={today}
        onCancel={() => setPending(null)}
        onConfirm={(change) => {
          if (pending) submit(pending.referral, change);
          setPending(null);
        }}
      />
    </>
  );
}
