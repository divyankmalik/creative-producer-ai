interface GatePanelProps {
  gateKey: string;
  isPending: boolean;
  onApprove?: () => void;
  approving?: boolean;
}

export function GatePanel({ gateKey, isPending, onApprove, approving }: GatePanelProps) {
  if (!isPending) return null;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-sky-300 bg-sky-50 p-4">
      <p className="text-sm font-medium text-sky-900">
        Waiting on your review: <span className="font-mono text-xs">{gateKey}</span>
      </p>
      <p className="text-xs text-sky-800">
        The outline is ready. Approve to let the Director continue writing the full script.
      </p>
      <button
        type="button"
        onClick={onApprove}
        disabled={approving}
        className="self-start rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
      >
        {approving ? "Approving…" : "Approve & continue"}
      </button>
    </div>
  );
}
