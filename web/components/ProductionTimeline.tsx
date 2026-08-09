"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock, Loader2 } from "lucide-react";
import { getArtifact } from "@/lib/api";
import type { ArtifactSummary } from "@/lib/types";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";

interface ProductionTimelineProps {
  open: boolean;
  onClose: () => void;
  artifacts: ArtifactSummary[];
}

// Local mirrors of the relevant backend payload shapes (api/app/agents/
// content.py, design.py, publishing.py) -- artifact payloads are untyped
// JSON on the wire, so these are read defensively, not trusted blindly.
interface OutlineSection {
  key: string;
  title: string;
}
interface OutlinePayload {
  sections: OutlineSection[];
}
interface StoryboardShot {
  section_key: string;
  visual: string;
  overlay_text: string | null;
  duration_s: number;
}
interface StoryboardPayload {
  shots: StoryboardShot[];
}
interface ScriptPayload {
  section_key: string;
  text: string;
}
interface VisualLanguagePayload {
  mood?: string;
}
interface SeoPayload {
  seo_title?: string;
  seo_description?: string;
}

interface TimelineBlock {
  sectionKey: string;
  sectionTitle: string;
  startS: number;
  endS: number;
  scriptText: string | null;
  shots: { visual: string; overlayText: string | null; startS: number; endS: number }[];
}

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.round(totalSeconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Groups consecutive shots sharing a section_key into one timeline block --
// the storyboard is the only artifact with real elapsed-time information
// (duration_s per shot), so every timestamp here is derived from it, not
// guessed or evenly divided.
function buildTimeline(outline: OutlinePayload, storyboard: StoryboardPayload, scripts: ScriptPayload[]): TimelineBlock[] {
  const scriptBySection = new Map(scripts.map((s) => [s.section_key, s.text]));
  const titleBySection = new Map(outline.sections.map((s) => [s.key, s.title]));

  const blocks: TimelineBlock[] = [];
  let cursor = 0;

  for (const shot of storyboard.shots) {
    const startS = cursor;
    const endS = cursor + shot.duration_s;
    cursor = endS;

    const last = blocks[blocks.length - 1];
    const shotEntry = { visual: shot.visual, overlayText: shot.overlay_text, startS, endS };

    if (last && last.sectionKey === shot.section_key) {
      last.endS = endS;
      last.shots.push(shotEntry);
    } else {
      blocks.push({
        sectionKey: shot.section_key,
        sectionTitle: titleBySection.get(shot.section_key) ?? shot.section_key,
        startS,
        endS,
        scriptText: scriptBySection.get(shot.section_key) ?? null,
        shots: [shotEntry],
      });
    }
  }

  return blocks;
}

export function ProductionTimeline({ open, onClose, artifacts }: ProductionTimelineProps) {
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [outline, setOutline] = useState<OutlinePayload | null>(null);
  const [storyboard, setStoryboard] = useState<StoryboardPayload | null>(null);
  const [scripts, setScripts] = useState<ScriptPayload[]>([]);
  const [visualLanguage, setVisualLanguage] = useState<VisualLanguagePayload | null>(null);
  const [seo, setSeo] = useState<SeoPayload | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const outlineSummary = artifacts.find((a) => a.slug === "content-outline");
        const storyboardSummary = artifacts.find((a) => a.slug === "content-storyboard");
        if (!outlineSummary || !storyboardSummary) {
          setLoadError("The outline and storyboard need to succeed before a timeline can be built.");
          return;
        }

        const scriptSummaries = artifacts.filter((a) => a.slug.startsWith("content-script-"));
        const vlSummary = artifacts.find((a) => a.slug === "design-visual-language");
        const seoSummary = artifacts.find((a) => a.slug === "publishing-seo");

        const [outlineArtifact, storyboardArtifact, ...scriptArtifacts] = await Promise.all([
          getArtifact(outlineSummary.id),
          getArtifact(storyboardSummary.id),
          ...scriptSummaries.map((s) => getArtifact(s.id)),
        ]);
        const [vlArtifact, seoArtifact] = await Promise.all([
          vlSummary ? getArtifact(vlSummary.id) : Promise.resolve(null),
          seoSummary ? getArtifact(seoSummary.id) : Promise.resolve(null),
        ]);

        if (cancelled) return;
        setOutline(outlineArtifact.payload as unknown as OutlinePayload);
        setStoryboard(storyboardArtifact.payload as unknown as StoryboardPayload);
        setScripts(scriptArtifacts.map((a) => a.payload as unknown as ScriptPayload));
        setVisualLanguage(vlArtifact ? (vlArtifact.payload as unknown as VisualLanguagePayload) : null);
        setSeo(seoArtifact ? (seoArtifact.payload as unknown as SeoPayload) : null);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [open, artifacts]);

  const blocks = useMemo(
    () => (outline && storyboard ? buildTimeline(outline, storyboard, scripts) : []),
    [outline, storyboard, scripts]
  );
  const totalSeconds = blocks.length > 0 ? blocks[blocks.length - 1].endS : 0;

  return (
    <Modal open={open} onClose={onClose} title="Production timeline">
      <div className="flex flex-col gap-5 p-5">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading timeline…
          </div>
        )}

        {loadError && (
          <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            {loadError}
          </p>
        )}

        {!loading && !loadError && blocks.length > 0 && (
          <>
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-4">
              <Badge variant="blue">
                <Clock className="h-3 w-3" />
                {formatTime(totalSeconds)} total
              </Badge>
              {seo?.seo_title && <span className="text-sm font-medium text-slate-200">{seo.seo_title}</span>}
              {visualLanguage?.mood && (
                <span className="text-xs italic text-slate-500">— {visualLanguage.mood}</span>
              )}
            </div>

            <div className="flex flex-col gap-4">
              {blocks.map((block, i) => (
                <div key={i} className="flex gap-3">
                  <div className="w-16 shrink-0 pt-0.5 text-right font-mono text-xs text-slate-500">
                    {formatTime(block.startS)}
                    <br />
                    <span className="text-slate-700">↓</span>
                    <br />
                    {formatTime(block.endS)}
                  </div>
                  <div className="flex-1 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
                    <p className="mb-1.5 font-mono text-xs font-semibold uppercase tracking-wide text-blue-400">
                      {block.sectionTitle}
                    </p>
                    {block.scriptText && (
                      <p className="mb-2 text-sm text-slate-300">{block.scriptText}</p>
                    )}
                    <div className="flex flex-col gap-1.5">
                      {block.shots.map((shot, j) => (
                        <div key={j} className="rounded-md border border-slate-800/70 bg-slate-950/40 px-2.5 py-1.5 text-xs">
                          <span className="font-mono text-slate-600">
                            {formatTime(shot.startS)}–{formatTime(shot.endS)}
                          </span>{" "}
                          <span className="text-slate-400">{shot.visual}</span>
                          {shot.overlayText && (
                            <span className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">
                              &quot;{shot.overlayText}&quot;
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {seo?.seo_description && (
              <p className="border-t border-slate-800 pt-3 text-xs text-slate-500">{seo.seo_description}</p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
