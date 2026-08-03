interface StaleBannerProps {
  staleReason: string | null;
  onRegenerate?: () => void;
}

export function StaleBanner({ staleReason, onRegenerate }: StaleBannerProps) {
  // TODO: render only when staleReason is set; show reason text and a
  // "Regenerate" action wired to onRegenerate.
  return (
    <div className="rounded-md border border-yellow-500/50 bg-yellow-500/10 p-2 text-sm">
      Stale banner placeholder
    </div>
  );
}
