import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface StaleBannerProps {
  staleReason: string | null;
  onRegenerate?: () => void;
  regenerating?: boolean;
}

export function StaleBanner({ staleReason, onRegenerate, regenerating }: StaleBannerProps) {
  if (!staleReason) return null;

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm">
      <span className="flex items-center gap-2 text-amber-200">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        {staleReason}
      </span>
      {onRegenerate && (
        <Button type="button" onClick={onRegenerate} disabled={regenerating} size="sm" variant="outline">
          {regenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          {regenerating ? "Regenerating…" : "Regenerate"}
        </Button>
      )}
    </div>
  );
}
