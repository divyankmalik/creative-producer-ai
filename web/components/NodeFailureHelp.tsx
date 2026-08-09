"use client";

import { useState } from "react";
import { AlertTriangle, Check, Copy, ImageIcon } from "lucide-react";
import type { Artifact, TaskNode } from "@/lib/types";
import { Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatNodeLabel } from "@/lib/utils";

interface NodeFailureHelpProps {
  node: TaskNode;
  projectTitle: string;
  projectIdea: string;
  visualLanguage: Artifact | null;
}

interface VisualLanguagePayload {
  mood?: string;
  typography?: string;
  imagery_style?: string;
  palette?: { role: string; name: string; hex: string }[];
}

// Purely client-side fallback for when design.thumbnails permanently fails
// (no artifact ever gets created for a HALTed node, so there's nothing to
// show in the normal artifact editor). Built from whatever already
// succeeded -- the project's own title/idea, plus the visual language
// artifact if it exists -- so the user can still get a usable thumbnail via
// any external image generator instead of hitting a dead end.
function buildThumbnailFallbackPrompt(title: string, idea: string, visualLanguage: Artifact | null): string {
  const payload = visualLanguage?.payload as VisualLanguagePayload | undefined;

  const lines = [
    `Create a 16:9 YouTube-style thumbnail for a video titled "${title}".`,
    `Topic: ${idea}`,
  ];

  if (payload?.mood) lines.push(`Mood: ${payload.mood}`);
  if (payload?.imagery_style) lines.push(`Imagery style: ${payload.imagery_style}`);
  if (payload?.typography) lines.push(`Typographic feel to complement: ${payload.typography}`);
  if (payload?.palette?.length) {
    const paletteText = payload.palette.map((s) => `${s.role}: ${s.name} (${s.hex})`).join(", ");
    lines.push(`Color palette: ${paletteText}`);
  }

  lines.push(
    `Render bold, large, highly legible overlay text reading "${title}" (or a short 4-word-or-fewer version of it) directly into the image, positioned in the lower third so it doesn't collide with the main subject, with strong contrast against the background.`
  );

  return lines.join("\n");
}

export function NodeFailureHelp({ node, projectTitle, projectIdea, visualLanguage }: NodeFailureHelpProps) {
  const [copied, setCopied] = useState(false);
  const isThumbnails = node.nodeKey === "design.thumbnails";

  async function handleCopy(text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (!isThumbnails) {
    return (
      <div className="flex flex-col gap-3 p-6">
        <p className="flex items-center gap-2 text-sm font-medium text-red-300">
          <AlertTriangle className="h-4 w-4" />
          {formatNodeLabel(node.nodeKey)} didn&apos;t complete
        </p>
        {node.lastError && (
          <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 font-mono text-xs text-red-300">
            {node.lastError}
          </p>
        )}
        <p className="text-xs text-slate-500">
          Failed after {node.attempts} attempt{node.attempts === 1 ? "" : "s"}.
        </p>
      </div>
    );
  }

  const prompt = buildThumbnailFallbackPrompt(projectTitle, projectIdea, visualLanguage);

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-300">
        <ImageIcon className="h-4 w-4" />
        Thumbnail generation failed — here&apos;s a prompt to try elsewhere
      </div>
      <p className="text-xs text-slate-500">
        The Director couldn&apos;t produce a validated thumbnail concept after {node.attempts} attempts. Paste this
        into Gemini, ChatGPT, or any image generator to create one manually
        {visualLanguage ? ", built from your visual language" : ""}.
      </p>
      <Textarea readOnly rows={9} value={prompt} className="font-mono text-xs" />
      <Button type="button" size="sm" variant="outline" onClick={() => handleCopy(prompt)} className="self-start">
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "Copied" : "Copy prompt"}
      </Button>
      {node.lastError && <p className="font-mono text-[11px] text-slate-600">Last error: {node.lastError}</p>}
    </div>
  );
}
