"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, Clock, Download, GripVertical, Loader2 } from "lucide-react";
import { useProjectPoll } from "@/hooks/useProjectPoll";
import { useResizableWidth } from "@/hooks/useResizableWidth";
import { useAuth } from "@/hooks/useAuth";
import { AuthControl } from "@/components/AuthControl";
import { ArtifactList } from "@/components/ArtifactList";
import { ArtifactEditor } from "@/components/ArtifactEditor";
import { DagView } from "@/components/DagView";
import { GatePanel } from "@/components/GatePanel";
import { StaleBanner } from "@/components/StaleBanner";
import { NodeFailureHelp } from "@/components/NodeFailureHelp";
import { ProductionTimeline } from "@/components/ProductionTimeline";
import { HowToUse } from "@/components/HowToUse";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Modal } from "@/components/ui/modal";
import {
  approveGate,
  exportProject,
  getArtifact,
  patchArtifact,
  regenerateArtifact,
} from "@/lib/api";
import type { Artifact, TaskNode } from "@/lib/types";
import { slugForNodeKey } from "@/lib/utils";
import { PROJECT_STATUS_META } from "@/lib/status";

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
  const { signedIn } = useAuth();
  // The right-hand sidebar (gate + artifact list) is anchored to the right
  // edge, so dragging left should grow it -- hence invert: true.
  const { width: sidebarWidth, startDrag } = useResizableWidth({
    storageKey: "showrunner:sidebarWidth",
    defaultWidth: 360,
    min: 260,
    max: 640,
    invert: true,
  });

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  // Set instead of selectedArtifactId when a clicked DAG node has no
  // matching artifact -- a HALTed node never gets one, so there's nothing
  // for the normal artifact editor to show. Mutually exclusive with
  // selectedArtifactId (selecting one always clears the other).
  const [selectedFailedNode, setSelectedFailedNode] = useState<TaskNode | null>(null);
  const [visualLanguageForFallback, setVisualLanguageForFallback] = useState<Artifact | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [howToUseOpen, setHowToUseOpen] = useState(false);

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

  // design.thumbnails is the one failure this UI knows how to help with --
  // fetch the visual language artifact (if it exists) to ground the
  // fallback prompt, whenever a failed thumbnails node gets selected.
  useEffect(() => {
    if (selectedFailedNode?.nodeKey !== "design.thumbnails") {
      setVisualLanguageForFallback(null);
      return;
    }
    const vlSummary = project?.artifacts.find((a) => a.slug === "design-visual-language");
    if (!vlSummary) {
      setVisualLanguageForFallback(null);
      return;
    }
    let cancelled = false;
    getArtifact(vlSummary.id)
      .then((artifact) => {
        if (!cancelled) setVisualLanguageForFallback(artifact);
      })
      .catch(() => {
        if (!cancelled) setVisualLanguageForFallback(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFailedNode, project?.artifacts]);

  function handleSelectArtifact(artifactId: string) {
    setSelectedFailedNode(null);
    setSelectedArtifactId(artifactId);
  }

  function handleSelectNode(nodeKey: string) {
    const slug = slugForNodeKey(nodeKey);
    const artifact = project?.artifacts.find((a) => a.slug === slug);
    if (artifact) {
      setSelectedFailedNode(null);
      setSelectedArtifactId(artifact.id);
      return;
    }
    // No artifact for this node -- it never succeeded. Show whatever help
    // we can instead of a dead click.
    const node = project?.nodes.find((n) => n.nodeKey === nodeKey);
    if (node) {
      setSelectedArtifactId(null);
      setSelectedFailedNode(node);
    }
  }

  function handleCloseDetail() {
    setSelectedArtifactId(null);
    setSelectedFailedNode(null);
    setArtifactError(null);
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
      <main className="flex h-screen items-center justify-center px-4">
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          Failed to load project: {error.message}
        </p>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="flex h-screen flex-col gap-4 p-4">
        <div className="flex items-center gap-2">
          <Logo />
        </div>
        <Skeleton className="h-8 w-64" />
        <div className="grid flex-1 grid-cols-[2fr_1fr] gap-4">
          <Skeleton className="h-full" />
          <Skeleton className="h-full" />
        </div>
      </main>
    );
  }

  const statusMeta = PROJECT_STATUS_META[project.status];
  const StatusIcon = statusMeta.icon;
  const detailOpen = Boolean(selectedArtifactId || selectedFailedNode);
  const modalTitle = selectedArtifact?.slug ?? selectedFailedNode?.nodeKey ?? "";
  const hasPackage = project.artifacts.some((a) => a.slug === "publishing-package");

  return (
    <main className="flex h-screen flex-col gap-4 p-4">
      <header className="flex items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <Logo />
        </div>
        <div className="flex items-center gap-3">
          {isPolling && <span className="flex items-center gap-1 text-xs text-slate-500">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            live
          </span>}
          {/* title goes on a wrapping span, not the Button itself -- a
              disabled button gets pointer-events-none, which also blocks
              the native title tooltip from showing on hover. */}
          <span title={signedIn ? undefined : "Sign in to use the timeline"}>
            <Button type="button" onClick={() => setTimelineOpen(true)} disabled={!signedIn} size="sm" variant="outline">
              <Clock className="h-3.5 w-3.5" />
              Timeline
            </Button>
          </span>
          <span title={signedIn ? undefined : "Sign in to export"}>
            <Button type="button" onClick={handleExport} disabled={exporting || !signedIn} size="sm" variant="outline">
              {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              {exporting ? "Exporting…" : "Export package"}
            </Button>
          </span>
          <AuthControl />
          {hasPackage && (
            <Button type="button" onClick={() => setHowToUseOpen(true)} size="sm" variant="outline">
              <BookOpen className="h-3.5 w-3.5" />
              How to use
            </Button>
          )}
        </div>
      </header>

      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-slate-50">{project.title}</h1>
        <Badge variant={statusMeta.variant}>
          <StatusIcon className={statusMeta.spin ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
          {statusMeta.label}
        </Badge>
      </div>

      <div className="flex min-h-0 flex-1 gap-0">
        <div className="min-w-0 flex-1">
          <DagView
            nodes={project.nodes}
            selectedNodeKey={selectedArtifact?.nodeKey ?? selectedFailedNode?.nodeKey}
            onSelectNode={handleSelectNode}
          />
        </div>

        {/* Drag-resizable divider -- the DAG needs more room as a project
            grows (more script sections, more columns), and a fixed 2:1
            split clips node cards at smaller window sizes. */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          onMouseDown={startDrag}
          className="group mx-1 flex w-3 shrink-0 cursor-col-resize items-center justify-center"
        >
          <div className="flex h-10 w-1 items-center justify-center rounded-full bg-slate-800 transition-colors group-hover:bg-blue-500/60">
            <GripVertical className="h-3 w-3 text-slate-600 opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
        </div>

        <div className="flex min-h-0 shrink-0 flex-col gap-4" style={{ width: sidebarWidth }}>
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
        </div>
      </div>

      {/* Clicking any DAG node or artifact list row opens the full result
          here -- scrollable, closeable (X, backdrop click, or Escape) --
          instead of squeezing everything into a fixed side panel. */}
      <Modal open={detailOpen} onClose={handleCloseDetail} title={modalTitle}>
        {artifactError && (
          <p className="m-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {artifactError}
          </p>
        )}
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
        ) : selectedFailedNode ? (
          <NodeFailureHelp
            node={selectedFailedNode}
            projectTitle={project.title}
            projectIdea={project.idea}
            visualLanguage={visualLanguageForFallback}
          />
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center">
            <Loader2 className="h-5 w-5 animate-spin text-slate-600" />
            <p className="text-sm text-slate-500">Loading…</p>
          </div>
        )}
      </Modal>

      <ProductionTimeline
        open={timelineOpen}
        onClose={() => setTimelineOpen(false)}
        artifacts={project.artifacts}
      />

      <HowToUse open={howToUseOpen} onClose={() => setHowToUseOpen(false)} />
    </main>
  );
}
