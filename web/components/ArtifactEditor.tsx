import type { Artifact } from "@/lib/types";

interface ArtifactEditorProps {
  artifact: Artifact;
  onSave?: (payload: Record<string, unknown>) => void;
  onRegenerate?: () => void;
  saving?: boolean;
}

export function ArtifactEditor({ artifact, onSave, onRegenerate, saving }: ArtifactEditorProps) {
  // TODO: render an editable view of artifact.payload keyed by artifact.type,
  // call onSave with the edited payload on submit, onRegenerate on button click.
  return (
    <div className="flex flex-col gap-4 p-4">
      <p className="text-sm text-muted-foreground">Artifact editor placeholder</p>
    </div>
  );
}
