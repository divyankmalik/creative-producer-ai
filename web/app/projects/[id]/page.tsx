"use client";

import { use } from "react";
import { useProjectPoll } from "@/hooks/useProjectPoll";
import { ArtifactList } from "@/components/ArtifactList";
import { DagView } from "@/components/DagView";
import { GatePanel } from "@/components/GatePanel";

interface ProjectPageProps {
  params: Promise<{ id: string }>;
}

export default function ProjectPage({ params }: ProjectPageProps) {
  const { id } = use(params);
  const { project, error, isPolling } = useProjectPoll(id);

  // TODO: once `project` is loaded, render DagView(nodes), ArtifactList(artifacts)
  // wired to a selected-artifact state, ArtifactEditor + StaleBanner for the
  // selection, and GatePanel for any pending gate on project.status === "awaiting_gate".
  return (
    <main className="grid h-screen grid-cols-[2fr_1fr] gap-4 p-4">
      <DagView nodes={project?.nodes ?? []} />
      <div className="flex flex-col gap-4">
        <ArtifactList artifacts={project?.artifacts ?? []} />
        <GatePanel gateKey="outline_review" isPending={project?.status === "awaiting_gate"} />
      </div>
    </main>
  );
}
