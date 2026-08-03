import type { TaskNode } from "@/lib/types";

interface DagViewProps {
  nodes: TaskNode[];
  onSelectNode?: (nodeKey: string) => void;
}

export function DagView({ nodes, onSelectNode }: DagViewProps) {
  // TODO: lay out nodes by dependency edges (dagre/elkjs or a hand-rolled
  // column layout keyed on node_key prefixes), color by status, call
  // onSelectNode on click.
  return (
    <div className="flex h-full w-full items-center justify-center border rounded-md">
      <p className="text-sm text-muted-foreground">DAG view placeholder</p>
    </div>
  );
}
