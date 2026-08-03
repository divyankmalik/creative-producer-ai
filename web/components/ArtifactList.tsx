import type { ArtifactSummary } from "@/lib/types";

interface ArtifactListProps {
  artifacts: ArtifactSummary[];
  selectedArtifactId?: string;
  onSelect?: (artifactId: string) => void;
}

export function ArtifactList({ artifacts, selectedArtifactId, onSelect }: ArtifactListProps) {
  // TODO: render artifacts, highlight selectedArtifactId, call onSelect on click,
  // surface a stale indicator per row (see StaleBanner for the shared styling).
  return (
    <div className="flex flex-col gap-1 p-2">
      <p className="text-sm text-muted-foreground">Artifact list placeholder</p>
    </div>
  );
}
