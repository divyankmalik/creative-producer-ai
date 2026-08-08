interface StaleBannerProps {
  staleReason: string | null;
  onRegenerate?: () => void;
  regenerating?: boolean;
}

export function StaleBanner({ staleReason, onRegenerate, regenerating }: StaleBannerProps) {
  if (!staleReason) return null;

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-yellow-500/50 bg-yellow-500/10 p-2 text-sm">
      <span className="text-yellow-800">{staleReason}</span>
      {onRegenerate && (
        <button
          type="button"
          onClick={onRegenerate}
          disabled={regenerating}
          className="shrink-0 rounded-md border border-yellow-600/40 bg-white px-2 py-1 text-xs font-medium text-yellow-800 hover:bg-yellow-50 disabled:opacity-50"
        >
          {regenerating ? "Regenerating…" : "Regenerate"}
        </button>
      )}
    </div>
  );
}
