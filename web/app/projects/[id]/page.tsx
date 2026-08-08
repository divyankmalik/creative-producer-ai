"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useProjectPoll } from "@/hooks/useProjectPoll";
import { ArtifactList } from "@/components/ArtifactList";
import { ArtifactEditor } from "@/components/ArtifactEditor";
import { DagView } from "@/components/DagView";
import { GatePanel } from "@/components/GatePanel";
import { StaleBanner } from "@/components/StaleBanner";
import {
  approveGate,
  exportProject,
  getArtifact,
  patchArtifact,
  regenerateArtifact,
} from "@/lib/api";
import type { Artifact } from "@/lib/types";
import { slugForNodeKey } from "@/lib/utils";

// The backend template (api/app/director/template.py) currently defines
// exactly one human gate, blocking content.script.* until the outline is
// approved -- hardcoding it here mirrors that, same as the original skeleton.
const OUTLINE_GATE_KEY = "outline_review";

interface ProjectPageProps {
  params: Promise<{ id: string }>;
}

export default function ProjectPage({ params }: ProjectPageProps) {
  const { id } = use(params);
  const { project, error, isPolling } = useProjectPoll(id);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [exporting, setExporting] = useState(false);

  const loadArtifact = useCallback(async (artifactId: string) => {
    try {
      const artifact = await getArtifact(artifactId);
      setSelectedArtifact(artifact);
      setArtifactError(null);
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (selectedArtifactId) {
      void loadArtifact(selectedArtifactId);
    } else {
      setSelectedArtifact(null);
    }
  }, [selectedArtifactId, loadArtifact]);

  function handleSelectArtifact(artifactId: string) {
    setSelectedArtifactId(artifactId);
  }

  function handleSelectNode(nodeKey: string) {
    const slug = slugForNodeKey(nodeKey);
    const artifact = project?.artifacts.find((a) => a.slug === slug);
    if (artifact) setSelectedArtifactId(artifact.id);
  }

  async function handleSave(payload: Record<string, unknown>) {
    if (!selectedArtifactId) return;
    setSaving(true);
    try {
      const { artifact } = await patchArtifact(selectedArtifactId, { payload, editedBy: "user" });
      setSelectedArtifact(artifact);
      setArtifactError(null);
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleRegenerate() {
    if (!selectedArtifactId) return;
    setRegenerating(true);
    try {
      await regenerateArtifact(selectedArtifactId);
      await loadArtifact(selectedArtifactId);
      setArtifactError(null);
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : String(err));
    } finally {
      setRegenerating(false);
    }
  }

  async function handleApproveGate() {
    setApproving(true);
    try {
      await approveGate(id, OUTLINE_GATE_KEY);
      setArtifactError(null);
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : String(err));
    } finally {
      setApproving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const { bundle } = await exportProject(id);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${id}-export.json`;
      link.click();
      URL.revokeObjectURL(url);
      setArtifactError(null);
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  }

  if (error) {
    return (
      <main className="flex h-screen items-center justify-center">
        <p className="text-sm text-red-600">Failed to load project: {error.message}</p>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="flex h-screen items-center justify-center">
        <p className="text-sm text-slate-400">Loading project…</p>
      </main>
    );
  }

  const selectedSummary = project.artifacts.find((a) => a.id === selectedArtifactId);

  return (
    <main className="grid h-screen grid-cols-[2fr_1fr] gap-4 p-4">
      <div className="flex flex-col gap-2 overflow-hidden">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">{project.title}</h1>
            <p className="text-xs capitalize text-slate-500">
              {project.status.replace(/_/g, " ")}
              {isPolling ? " · live" : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export package"}
          </button>
        </div>
        <DagView
          nodes={project.nodes}
          selectedNodeKey={selectedArtifact?.nodeKey}
          onSelectNode={handleSelectNode}
        />
      </div>

      <div className="flex flex-col gap-4 overflow-hidden">
        <GatePanel
          gateKey={OUTLINE_GATE_KEY}
          isPending={project.status === "awaiting_gate"}
          onApprove={handleApproveGate}
          approving={approving}
        />

        <ArtifactList
          artifacts={project.artifacts}
          selectedArtifactId={selectedArtifactId ?? undefined}
          onSelect={handleSelectArtifact}
        />

        <div className="flex flex-1 flex-col overflow-y-auto rounded-md border">
          {artifactError && <p className="p-4 text-sm text-red-600">{artifactError}</p>}
          {selectedArtifact ? (
            <>
              <div className="px-4 pt-4">
                <StaleBanner
                  staleReason={selectedArtifact.staleReason}
                  onRegenerate={handleRegenerate}
                  regenerating={regenerating}
                />
              </div>
              <ArtifactEditor
                artifact={selectedArtifact}
                onSave={handleSave}
                onRegenerate={handleRegenerate}
                saving={saving}
                regenerating={regenerating}
              />
            </>
          ) : (
            <p className="p-4 text-sm text-slate-400">
              {selectedSummary ? "Loading artifact…" : "Select an artifact to view and edit it."}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
