import type { LucideIcon } from "lucide-react";
import { ArrowRight, MousePointerClick } from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { AGENT_ICON, NODE_STATUS_META } from "@/lib/status";
import type { NodeStatus } from "@/lib/types";

interface HowToUseProps {
  open: boolean;
  onClose: () => void;
}

interface ArtifactExplainer {
  slug: string;
  agent: keyof typeof AGENT_ICON;
  name: string;
  description: string;
}

// Listed in the same order the Director actually produces them (see
// api/app/director/template.py's NODE_TEMPLATE) -- research grounds the
// outline, the outline drives every script section and the visual
// language, the storyboard and SEO both build on those, and the package is
// the last thing to exist, assembled from everything before it.
const ARTIFACTS: ArtifactExplainer[] = [
  {
    slug: "research-brief",
    agent: "research",
    name: "Research brief",
    description:
      "The angle for this content, an audience insight, and 3-8 key points -- grounded either in a web search or, if you filled in \"Product/feature details,\" your own provided facts instead.",
  },
  {
    slug: "content-outline",
    agent: "content",
    name: "Outline",
    description:
      "Breaks the brief into sections (\"s1\", \"s2\", ...), one per script node the graph creates. Each section's relative weight controls how much of the total runtime and word budget it gets.",
  },
  {
    slug: "content-script-sN",
    agent: "content",
    name: "Script sections",
    description:
      "The actual narration text for one outline section, sized to hit that section's share of the target video length.",
  },
  {
    slug: "content-storyboard",
    agent: "content",
    name: "Storyboard",
    description:
      "Shot-by-shot visual plan built from the finished scripts -- each shot has a visual description, optional on-screen text, and a real duration in seconds. This is what the Production Timeline is computed from.",
  },
  {
    slug: "design-visual-language",
    agent: "design",
    name: "Visual language",
    description: "A mood/style guide (tone, imagery style, color palette) that keeps thumbnails visually consistent.",
  },
  {
    slug: "design-thumbnails",
    agent: "design",
    name: "Thumbnails",
    description:
      "Concept ideas for a thumbnail, each with a ready-to-paste image_prompt for an external image generator -- this system doesn't generate the image itself, only the prompt for it.",
  },
  {
    slug: "publishing-seo",
    agent: "publishing",
    name: "SEO metadata",
    description: "A title, description, and tags sized for search/discovery, aligned with the thumbnails when available.",
  },
  {
    slug: "publishing-package",
    agent: "publishing",
    name: "Publishing package",
    description:
      "The final deliverable -- an assembly step, not a generation step: the storyboard's shots plus the SEO metadata, merged into the one bundle \"Export package\" downloads.",
  },
];

const STATUS_LEGEND: NodeStatus[] = ["queued", "running", "succeeded", "failed", "blocked", "skipped"];

function AgentIcon({ agent }: { agent: keyof typeof AGENT_ICON }) {
  const Icon: LucideIcon = AGENT_ICON[agent];
  return <Icon className="h-4 w-4 shrink-0" />;
}

export function HowToUse({ open, onClose }: HowToUseProps) {
  return (
    <Modal open={open} onClose={onClose} title="How this works">
      <div className="flex flex-col gap-8 p-5">
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-slate-100">Reading the graph</h3>
          <p className="text-sm text-slate-400">
            Each card is one task the Director assigned to a specialist agent. Columns run left to right by
            dependency depth -- a card only becomes eligible once everything it points to (the{" "}
            <span className="font-mono text-xs text-slate-500">← labels</span>) has succeeded.
          </p>
          <div className="flex flex-wrap gap-2">
            {STATUS_LEGEND.map((status) => {
              const meta = NODE_STATUS_META[status];
              return (
                <div key={status} className="flex items-center gap-1.5">
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                </div>
              );
            })}
          </div>
          <ul className="flex flex-col gap-1.5 text-sm text-slate-400">
            <li className="flex items-start gap-2">
              <MousePointerClick className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
              Click any card to open what it produced -- or, if it failed with nothing to show, why.
            </li>
            <li className="flex items-start gap-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
              A{" "}
              <span className="font-mono text-xs text-slate-500">×N</span> next to a card is how many times the
              Director retried it before giving up (capped at 3 attempts) -- a failed dependency blocks everything
              downstream of it instead of running on incomplete input.
            </li>
          </ul>
        </section>

        <section className="flex flex-col gap-3 border-t border-slate-800 pt-6">
          <h3 className="text-sm font-semibold text-slate-100">What's in the package</h3>
          <div className="flex flex-col gap-3">
            {ARTIFACTS.map((artifact) => (
              <div key={artifact.slug} className="flex gap-3">
                <div className="mt-0.5 text-slate-500">
                  <AgentIcon agent={artifact.agent} />
                </div>
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium text-slate-200">{artifact.name}</p>
                  <p className="text-sm text-slate-400">{artifact.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </Modal>
  );
}
