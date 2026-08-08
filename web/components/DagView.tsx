import type { NodeStatus, TaskNode } from "@/lib/types";
import { cn, formatNodeLabel } from "@/lib/utils";

interface DagViewProps {
  nodes: TaskNode[];
  selectedNodeKey?: string | null;
  onSelectNode?: (nodeKey: string) => void;
}

const STATUS_STYLES: Record<NodeStatus, string> = {
  queued: "border-slate-300 bg-slate-50 text-slate-600",
  ready: "border-sky-300 bg-sky-50 text-sky-700",
  running: "border-sky-400 bg-sky-100 text-sky-800 animate-pulse",
  succeeded: "border-emerald-300 bg-emerald-50 text-emerald-700",
  failed: "border-red-400 bg-red-50 text-red-700",
  blocked: "border-amber-300 bg-amber-50 text-amber-700",
  skipped: "border-slate-200 bg-slate-50 text-slate-400",
};

const STATUS_DOT: Record<NodeStatus, string> = {
  queued: "bg-slate-400",
  ready: "bg-sky-500",
  running: "bg-sky-500",
  succeeded: "bg-emerald-500",
  failed: "bg-red-500",
  blocked: "bg-amber-500",
  skipped: "bg-slate-300",
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
      <div className="flex h-full w-full items-center justify-center rounded-md border border-dashed">
        <p className="text-sm text-slate-400">Waiting for the task graph to plan…</p>
      </div>
    );
  }

  const columns = computeColumns(nodes);

  return (
    <div className="flex h-full w-full gap-4 overflow-x-auto rounded-md border p-4">
      {columns.map((column, i) => (
        <div key={i} className="flex min-w-[180px] flex-1 flex-col gap-3">
          {column.map((node) => (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelectNode?.(node.nodeKey)}
              className={cn(
                "flex flex-col gap-1 rounded-md border px-3 py-2 text-left text-xs shadow-sm transition",
                STATUS_STYLES[node.status],
                selectedNodeKey === node.nodeKey && "ring-2 ring-offset-1 ring-slate-500"
              )}
              title={node.lastError ?? undefined}
            >
              <span className="flex items-center gap-1.5 font-medium capitalize">
                <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[node.status])} />
                {formatNodeLabel(node.nodeKey)}
              </span>
              <span className="text-[10px] uppercase tracking-wide opacity-70">{node.agent}</span>
              <span className="text-[10px] opacity-70">
                {node.status}
                {node.attempts > 0 ? ` · attempt ${node.attempts}` : ""}
              </span>
              {node.dependencies.length > 0 && (
                <span className="truncate text-[10px] opacity-60">
                  ← {node.dependencies.map((d) => formatNodeLabel(d.nodeKey)).join(", ")}
                </span>
              )}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
