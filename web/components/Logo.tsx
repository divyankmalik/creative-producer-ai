import { Clapperboard } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold text-slate-100", className)}>
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-600 text-white shadow-sm shadow-blue-950/50">
        <Clapperboard className="h-4 w-4" />
      </span>
      showrunner
    </span>
  );
}
