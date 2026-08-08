import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Mirrors api/app/director/template.py's slug_for_node_key: dots and
// underscores both flatten to dashes (design.visual_language ->
// design-visual-language), matching every agent's hardcoded output slug.
export function slugForNodeKey(nodeKey: string): string {
  return nodeKey.replace(/\./g, "-").replace(/_/g, "-");
}

export function formatNodeLabel(nodeKey: string): string {
  const last = nodeKey.split(".").pop() ?? nodeKey;
  return last.replace(/_/g, " ");
}
