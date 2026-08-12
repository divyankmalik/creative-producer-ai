"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Lightbulb, Loader2, Megaphone, Sparkles } from "lucide-react";
import { createProject } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { AuthControl } from "@/components/AuthControl";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";

const MIN_VIDEO_MINUTES = 1;
const MAX_VIDEO_MINUTES = 10;
const MIN_SECTIONS = 1;
const MAX_SECTIONS = 10;

// Rounds to a whole number and clamps to [min, max] -- used onBlur, not
// onChange, so typing a multi-digit number doesn't get clobbered mid-keystroke.
function clampInt(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}

// These two fields are controlled as raw strings, not numbers -- with a
// number as the controlled value, typing "0" then "9" produces DOM text
// "09" that parses to the number 9; since 9 doesn't differ from whatever
// React last recorded, its input-value tracker can skip re-syncing the DOM
// text, leaving the stale "09" visible even though state is correctly 9.
// Stripping the leading zero directly in the string prevents that "09" from
// ever being committed to state in the first place.
function stripLeadingZero(raw: string): string {
  return raw.replace(/^0+(?=\d)/, "");
}

// Number inputs silently change value when the mouse wheel scrolls over a
// focused one -- a well-known browser quirk that reads as "the field
// changes on its own." Blurring on wheel disables that without blocking
// scrolling the page itself.
function blurOnWheel(e: React.WheelEvent<HTMLInputElement>) {
  e.currentTarget.blur();
}

type Mode = "idea" | "feature";

interface ModeOption {
  mode: Mode;
  icon: typeof Lightbulb;
  title: string;
  description: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    mode: "idea",
    icon: Lightbulb,
    title: "Video idea",
    description: "Describe a topic or angle. The Director researches it and figures out the rest.",
  },
  {
    mode: "feature",
    icon: Megaphone,
    title: "Product/feature introduction",
    description: "Announce something specific -- your own facts become the source of truth, not a web search.",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode | null>(null);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [referenceMaterial, setReferenceMaterial] = useState("");
  const [sectionCount, setSectionCount] = useState("2");
  const [videoMinutes, setVideoMinutes] = useState("6");
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
          section_count: clampInt(Number(sectionCount), MIN_SECTIONS, MAX_SECTIONS),
          total_seconds: clampInt(Number(videoMinutes), MIN_VIDEO_MINUTES, MAX_VIDEO_MINUTES) * 60,
          ...(mode === "feature" && referenceMaterial.trim()
            ? { reference_material: referenceMaterial.trim() }
            : {}),
        },
      });
      router.push(`/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center px-4 py-16">
      <div className="absolute right-4 top-4">
        <AuthControl />
      </div>

      <div className="mb-8">
        <Logo />
      </div>

      {mode === null ? (
        <div className="flex w-full max-w-xl flex-col gap-3">
          <div className="mb-2 flex flex-col gap-1.5 text-center">
            <div className="flex items-center justify-center gap-2 text-xs font-medium uppercase tracking-wide text-blue-400">
              <Sparkles className="h-3.5 w-3.5" />
              New project
            </div>
            <h1 className="text-xl font-semibold text-slate-50">What are you making a video about?</h1>
          </div>

          {MODE_OPTIONS.map((option) => (
            <button key={option.mode} type="button" onClick={() => setMode(option.mode)} className="text-left">
              <Card className="transition-colors hover:border-blue-500/50 hover:bg-slate-900/80">
                <CardContent className="flex items-start gap-4 p-5">
                  <div className="rounded-lg bg-blue-500/10 p-2.5 text-blue-400">
                    <option.icon className="h-5 w-5" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium text-slate-100">{option.title}</p>
                    <p className="text-sm text-slate-400">{option.description}</p>
                  </div>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      ) : (
        <Card className="w-full max-w-xl">
          <CardContent className="flex flex-col gap-6 p-8">
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => setMode(null)}
                className="mb-1 inline-flex w-fit items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-300"
              >
                <ArrowLeft className="h-3 w-3" />
                Back
              </button>
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-blue-400">
                <Sparkles className="h-3.5 w-3.5" />
                New project
              </div>
              <h1 className="text-xl font-semibold text-slate-50">
                {mode === "feature" ? "Introduce your product or feature" : "Describe a content idea"}
              </h1>
              <p className="text-sm text-slate-400">
                {mode === "feature"
                  ? "The Director will plan research, script, storyboard, visuals, and publishing metadata for it -- grounded in the specifics you provide below."
                  : "The Director will plan research, script, storyboard, visuals, and publishing metadata for it."}
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
                  placeholder={
                    mode === "feature"
                      ? "Introducing Smart Filters: Find What You Need in Seconds"
                      : "Why remote teams burn out on async standups"
                  }
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
                  placeholder={
                    mode === "feature"
                      ? "A short product video announcing our new Smart Filters feature -- the problem it solves, how it works, and a clear call to action."
                      : "A short video explaining why fully-async daily standups quietly kill remote team morale, and what teams do instead."
                  }
                />
              </div>

              {mode === "feature" && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="referenceMaterial" className="text-xs font-medium text-slate-300">
                    Product/feature details
                  </label>
                  <Textarea
                    id="referenceMaterial"
                    rows={4}
                    value={referenceMaterial}
                    onChange={(e) => setReferenceMaterial(e.target.value)}
                    placeholder="Paste specifics about your own feature or product here -- what it's called, what it does, how it works, key benefits. A web search can't find something that isn't public yet, so anything here becomes the actual source of truth instead."
                  />
                </div>
              )}

              <div className="flex gap-5">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="videoMinutes" className="text-xs font-medium text-slate-300">
                    Video length (minutes)
                  </label>
                  <Input
                    id="videoMinutes"
                    type="number"
                    inputMode="numeric"
                    step={1}
                    min={MIN_VIDEO_MINUTES}
                    max={MAX_VIDEO_MINUTES}
                    value={videoMinutes}
                    onChange={(e) => setVideoMinutes(stripLeadingZero(e.target.value))}
                    onBlur={(e) =>
                      setVideoMinutes(String(clampInt(Number(e.target.value), MIN_VIDEO_MINUTES, MAX_VIDEO_MINUTES)))
                    }
                    onWheel={blurOnWheel}
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
                    inputMode="numeric"
                    step={1}
                    min={MIN_SECTIONS}
                    max={MAX_SECTIONS}
                    value={sectionCount}
                    onChange={(e) => setSectionCount(stripLeadingZero(e.target.value))}
                    onBlur={(e) =>
                      setSectionCount(String(clampInt(Number(e.target.value), MIN_SECTIONS, MAX_SECTIONS)))
                    }
                    onWheel={blurOnWheel}
                    className="w-24"
                  />
                </div>
              </div>
              <p className="-mt-3 text-xs text-slate-500">
                Up to {MAX_VIDEO_MINUTES} minutes. Word budgets per section scale from the target length, split
                across sections by the outline&apos;s own weighting.
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
      )}
    </main>
  );
}
