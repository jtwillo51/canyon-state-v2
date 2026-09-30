import type { Metadata } from "next";

import { ChooseViewer } from "@/components/choose-viewer";
import { Dashboard } from "@/components/progress/dashboard";
import { getProgress } from "@/lib/progress-server";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const progress = await getProgress();
  if (!progress) return <ChooseViewer />;
  return <Dashboard progress={progress} />;
}
