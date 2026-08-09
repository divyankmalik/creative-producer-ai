"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { createProject } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";

const MIN_VIDEO_MINUTES = 1;
const MAX_VIDEO_MINUTES = 10;

function clampVideoMinutes(value: number): number {
  if (Number.isNaN(value)) return MIN_VIDEO_MINUTES;
  return Math.min(MAX_VIDEO_MINUTES, Math.max(MIN_VIDEO_MINUTES, value));
}

export default function HomePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [referenceMaterial, setReferenceMaterial] = useState("");
  const [sectionCount, setSectionCount] = useState(2);
  const [videoMinutes, setVideoMinutes] = useState(6);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { projectId } = await createProject({
        title,
        idea,
        params: {
          section_count: sectionCount,
          total_seconds: clampVideoMinutes(videoMinutes) * 60,
          ...(referenceMaterial.trim() ? { reference_material: referenceMaterial.trim() } : {}),
        },
      });
      router.push(`/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-16">
      <div className="mb-8">
        <Logo />
      </div>

      <Card className="w-full max-w-xl">
        <CardContent className="flex flex-col gap-6 p-8">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-blue-400">
              <Sparkles className="h-3.5 w-3.5" />
              New project
            </div>
            <h1 className="text-xl font-semibold text-slate-50">Describe a content idea</h1>
            <p className="text-sm text-slate-400">
              The Director will plan research, script, storyboard, visuals, and publishing metadata for it.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="title" className="text-xs font-medium text-slate-300">
                Title
              </label>
              <Input
                id="title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Why remote teams burn out on async standups"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="idea" className="text-xs font-medium text-slate-300">
                Idea
              </label>
              <Textarea
                id="idea"
                required
                rows={4}
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
                placeholder="A short video explaining why fully-async daily standups quietly kill remote team morale, and what teams do instead."
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="referenceMaterial" className="text-xs font-medium text-slate-300">
                Product/feature details <span className="font-normal text-slate-500">(optional)</span>
              </label>
              <Textarea
                id="referenceMaterial"
                rows={4}
                value={referenceMaterial}
                onChange={(e) => setReferenceMaterial(e.target.value)}
                placeholder="Paste specifics about your own feature or product here -- what it's called, what it does, how it works, key benefits. A web search can't find something that isn't public yet, so anything here becomes the actual source of truth instead."
              />
            </div>

            <div className="flex gap-5">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="videoMinutes" className="text-xs font-medium text-slate-300">
                  Video length (minutes)
                </label>
                <Input
                  id="videoMinutes"
                  type="number"
                  min={MIN_VIDEO_MINUTES}
                  max={MAX_VIDEO_MINUTES}
                  value={videoMinutes}
                  onChange={(e) => setVideoMinutes(Number(e.target.value))}
                  onBlur={(e) => setVideoMinutes(clampVideoMinutes(Number(e.target.value)))}
                  className="w-24"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="sectionCount" className="text-xs font-medium text-slate-300">
                  Number of script sections
                </label>
                <Input
                  id="sectionCount"
                  type="number"
                  min={1}
                  max={10}
                  value={sectionCount}
                  onChange={(e) => setSectionCount(Number(e.target.value))}
                  className="w-24"
                />
              </div>
            </div>
            <p className="-mt-3 text-xs text-slate-500">
              Up to {MAX_VIDEO_MINUTES} minutes. Word budgets per section scale from the target length, split across
              sections by the outline&apos;s own weighting.
            </p>

            {error && (
              <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <Button type="submit" disabled={submitting} size="lg" className="self-start">
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting…
                </>
              ) : (
                <>
                  Start project
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
