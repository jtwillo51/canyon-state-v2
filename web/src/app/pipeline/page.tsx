import type { Metadata } from "next";

import { ChooseViewer } from "@/components/choose-viewer";
import { PipelineBoard } from "@/components/pipeline/board";
import { agencyToday } from "@/lib/format";
import { getApi } from "@/lib/viewer";

export const metadata: Metadata = { title: "Pipeline" };

export default async function PipelinePage() {
  const api = await getApi();
  if (!api) return <ChooseViewer />;

  // Server Component: load everything in parallel, then hand it to the interactive board.
  const [board, me, reps] = await Promise.all([
    api.GET("/referrals/pipeline"),
    api.GET("/users/me"),
    api.GET("/users/reps"),
  ]);
  if (!board.data || !me.data || !reps.data) throw new Error("Couldn't load the pipeline");

  return (
    <>
      <h1 className="mb-1 text-2xl font-semibold">Pipeline</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Open referrals, plus those bound or lost in the last 30 days. Drag a card to move it.
      </p>
      {/* key: a different viewer gets a fresh board (no leftover error or dialog from the last person). */}
      <PipelineBoard key={me.data.id} referrals={board.data} viewer={me.data} reps={reps.data} today={agencyToday()} />
    </>
  );
}
