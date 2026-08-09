import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock,
  FileText,
  type LucideIcon,
  Loader2,
  MinusCircle,
  Palette,
  Rocket,
  Search,
  XCircle,
} from "lucide-react";
import type { BadgeProps } from "@/components/ui/badge";
import type { NodeStatus, ProjectStatus } from "./types";

interface StatusMeta {
  label: string;
  variant: BadgeProps["variant"];
  icon: LucideIcon;
  spin?: boolean;
}

export const NODE_STATUS_META: Record<NodeStatus, StatusMeta> = {
  queued: { label: "Queued", variant: "neutral", icon: Clock },
  ready: { label: "Ready", variant: "sky", icon: CircleDashed },
  running: { label: "Running", variant: "blue", icon: Loader2, spin: true },
  succeeded: { label: "Succeeded", variant: "emerald", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "red", icon: XCircle },
  blocked: { label: "Blocked", variant: "amber", icon: AlertTriangle },
  skipped: { label: "Skipped", variant: "neutral", icon: MinusCircle },
};

export const PROJECT_STATUS_META: Record<ProjectStatus, StatusMeta> = {
  planning: { label: "Planning", variant: "neutral", icon: Clock },
  running: { label: "Running", variant: "blue", icon: Loader2, spin: true },
  blocked: { label: "Blocked", variant: "amber", icon: AlertTriangle },
  awaiting_gate: { label: "Awaiting review", variant: "sky", icon: Clock },
  done: { label: "Done", variant: "emerald", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "red", icon: XCircle },
};

// Every node_key / artifact slug in this system is prefixed by its owning
// agent ("research.brief" / "research-brief", "design.thumbnails" /
// "design-thumbnails", ...) -- see api/app/director/template.py.
export const AGENT_ICON: Record<string, LucideIcon> = {
  research: Search,
  content: FileText,
  design: Palette,
  publishing: Rocket,
};

export function agentIconFor(nodeKeyOrSlug: string): LucideIcon {
  const agent = nodeKeyOrSlug.split(/[.-]/)[0];
  return AGENT_ICON[agent] ?? FileText;
}
