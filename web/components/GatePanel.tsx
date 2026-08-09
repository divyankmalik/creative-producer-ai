import { Loader2, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface GatePanelProps {
  gateKey: string;
  isPending: boolean;
  onApprove?: () => void;
  approving?: boolean;
}

export function GatePanel({ gateKey, isPending, onApprove, approving }: GatePanelProps) {
  if (!isPending) return null;

  return (
    <Card className="border-sky-500/30 bg-sky-500/[0.06]">
      <CardContent className="flex flex-col gap-2.5 p-4">
        <p className="flex items-center gap-2 text-sm font-medium text-sky-200">
          <UserCheck className="h-4 w-4" />
          Waiting on your review
          <span className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] text-sky-300">{gateKey}</span>
        </p>
        <p className="text-xs text-sky-300/80">
          The outline is ready. Approve to let the Director continue writing the full script.
        </p>
        <Button
          type="button"
          onClick={onApprove}
          disabled={approving}
          size="sm"
          className="self-start bg-sky-600 hover:bg-sky-500"
        >
          {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserCheck className="h-3.5 w-3.5" />}
          {approving ? "Approving…" : "Approve & continue"}
        </Button>
      </CardContent>
    </Card>
  );
}
