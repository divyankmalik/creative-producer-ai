interface GatePanelProps {
  gateKey: string;
  isPending: boolean;
  onApprove?: () => void;
  approving?: boolean;
}

export function GatePanel({ gateKey, isPending, onApprove, approving }: GatePanelProps) {
  // TODO: render only when isPending; show gateKey and an "Approve" button
  // wired to onApprove (calls POST /projects/{id}/gates/{key}/approve).
  return (
    <div className="rounded-md border p-4">
      <p className="text-sm text-muted-foreground">Gate panel placeholder</p>
    </div>
  );
}
