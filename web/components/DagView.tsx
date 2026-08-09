import type { TaskNode } from "@/lib/types";
import { cn, formatNodeLabel } from "@/lib/utils";
import { agentIconFor, NODE_STATUS_META } from "@/lib/status";
import { Badge } from "@/components/ui/badge";

interface DagViewProps {
  nodes: TaskNode[];
  selectedNodeKey?: string | null;
  onSelectNode?: (nodeKey: string) => void;
}

const CARD_RING: Record<string, string> = {
  succeeded: "border-emerald-500/30 hover:border-emerald-500/50",
  failed: "border-red-500/30 hover:border-red-500/50",
  running: "border-blue-500/40 hover:border-blue-500/60",
  blocked: "border-amber-500/30 hover:border-amber-500/50",
  ready: "border-sky-500/30 hover:border-sky-500/50",
  queued: "border-slate-700 hover:border-slate-600",
  skipped: "border-slate-800 hover:border-slate-700",
};

// Groups nodes into columns by longest-path depth from any root (a node with
// no dependencies). This is computed from whatever dependency edges the
// nodes actually carry, so it lays out correctly regardless of section_count
// or future template changes -- it doesn't hardcode agent names or node keys.
function computeColumns(nodes: TaskNode[]): TaskNode[][] {
  const byKey = new Map(nodes.map((n) => [n.nodeKey, n]));
  const depthCache = new Map<string, number>();

  function depthOf(nodeKey: string, guard: Set<string>): number {
    if (depthCache.has(nodeKey)) return depthCache.get(nodeKey)!;
    if (guard.has(nodeKey)) return 0; // defensive: cycle guard, shouldn't happen
    const node = byKey.get(nodeKey);
    if (!node || node.dependencies.length === 0) {
      depthCache.set(nodeKey, 0);
      return 0;
    }
    guard.add(nodeKey);
    const depth =
      1 +
      Math.max(
        ...node.dependencies.map((dep) =>
          byKey.has(dep.nodeKey) ? depthOf(dep.nodeKey, guard) : -1
        )
      );
    guard.delete(nodeKey);
    depthCache.set(nodeKey, depth);
    return depth;
  }

  const columns: TaskNode[][] = [];
  for (const node of nodes) {
    const depth = depthOf(node.nodeKey, new Set());
    if (!columns[depth]) columns[depth] = [];
    columns[depth].push(node);
  }
  return columns.filter(Boolean).map((col) => [...col].sort((a, b) => a.nodeKey.localeCompare(b.nodeKey)));
}

export function DagView({ nodes, selectedNodeKey, onSelectNode }: DagViewProps) {
  if (nodes.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-slate-800 bg-slate-900/30">
        <p className="text-sm text-slate-500">Waiting for the task graph to plan…</p>
      </div>
    );
  }

  const columns = computeColumns(nodes);

  return (
    <div className="flex h-full w-full gap-6 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/30 p-5">
      {columns.map((column, i) => (
        <div key={i} className="flex min-w-[200px] flex-1 flex-col gap-3">
          {column.map((node) => {
            const meta = NODE_STATUS_META[node.status];
            const StatusIcon = meta.icon;
            const AgentIcon = agentIconFor(node.nodeKey);
            const selected = selectedNodeKey === node.nodeKey;
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => onSelectNode?.(node.nodeKey)}
                className={cn(
                  "flex flex-col gap-2 rounded-lg border bg-slate-900/80 px-3.5 py-3 text-left shadow-sm shadow-black/20 transition-all",
                  CARD_RING[node.status],
                  selected && "ring-2 ring-blue-500 ring-offset-2 ring-offset-slate-950"
                )}
                title={node.lastError ?? undefined}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-slate-100">
                    <AgentIcon className="h-3.5 w-3.5 text-slate-500" />
                    {formatNodeLabel(node.nodeKey)}
                  </span>
                  <StatusIcon className={cn("h-3.5 w-3.5 shrink-0", meta.spin && "animate-spin")} />
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                  {node.attempts > 0 && (
                    <span className="font-mono text-[10px] text-slate-500">×{node.attempts}</span>
                  )}
                </div>
                {node.dependencies.length > 0 && (
                  <span className="truncate font-mono text-[10px] text-slate-500">
                    ← {node.dependencies.map((d) => formatNodeLabel(d.nodeKey)).join(", ")}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
