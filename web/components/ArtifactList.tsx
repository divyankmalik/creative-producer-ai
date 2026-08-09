import { AlertCircle } from "lucide-react";
import type { ArtifactSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { agentIconFor } from "@/lib/status";

interface ArtifactListProps {
  artifacts: ArtifactSummary[];
  selectedArtifactId?: string;
  onSelect?: (artifactId: string) => void;
}

export function ArtifactList({ artifacts, selectedArtifactId, onSelect }: ArtifactListProps) {
  if (artifacts.length === 0) {
    return (
      <div className="flex flex-col gap-1 rounded-lg border border-slate-800 bg-slate-900/30 p-4">
        <p className="text-sm text-slate-500">No artifacts yet.</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/30 p-1.5">
      {artifacts.map((artifact) => {
        const Icon = agentIconFor(artifact.slug);
        const selected = selectedArtifactId === artifact.id;
        return (
          <button
            key={artifact.id}
            type="button"
            onClick={() => onSelect?.(artifact.id)}
            className={cn(
              "flex items-start gap-2.5 rounded-md border border-transparent px-3 py-2 text-left text-sm transition-colors",
              selected ? "border-blue-500/40 bg-blue-500/10" : "hover:bg-slate-800/60"
            )}
          >
            <Icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", selected ? "text-blue-400" : "text-slate-500")} />
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="flex items-center gap-1.5 font-mono text-[13px] font-medium text-slate-200">
                {artifact.slug}
                {artifact.isStale && (
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                    <AlertCircle className="h-2.5 w-2.5" />
                    stale
                  </span>
                )}
              </span>
              {artifact.summary && (
                <span className="truncate text-xs text-slate-500">{artifact.summary}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
