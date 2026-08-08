import type { ArtifactSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ArtifactListProps {
  artifacts: ArtifactSummary[];
  selectedArtifactId?: string;
  onSelect?: (artifactId: string) => void;
}

export function ArtifactList({ artifacts, selectedArtifactId, onSelect }: ArtifactListProps) {
  if (artifacts.length === 0) {
    return (
      <div className="flex flex-col gap-1 rounded-md border p-4">
        <p className="text-sm text-slate-400">No artifacts yet.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 overflow-y-auto rounded-md border p-2">
      {artifacts.map((artifact) => (
        <button
          key={artifact.id}
          type="button"
          onClick={() => onSelect?.(artifact.id)}
          className={cn(
            "flex flex-col gap-0.5 rounded-md border border-transparent px-3 py-2 text-left text-sm transition hover:bg-slate-50",
            selectedArtifactId === artifact.id && "border-slate-300 bg-slate-100"
          )}
        >
          <span className="flex items-center gap-2 font-medium">
            {artifact.slug}
            {artifact.isStale && (
              <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                stale
              </span>
            )}
          </span>
          {artifact.summary && (
            <span className="truncate text-xs text-slate-500">{artifact.summary}</span>
          )}
        </button>
      ))}
    </div>
  );
}
