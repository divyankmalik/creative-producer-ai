"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { createProject } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [sectionCount, setSectionCount] = useState(2);
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
        params: { section_count: sectionCount },
      });
      router.push(`/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">showrunner</h1>
        <p className="text-sm text-slate-500">
          Describe a content idea. The Director will plan research, script, storyboard,
          visuals, and publishing metadata for it.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="title" className="text-sm font-medium text-slate-700">
            Title
          </label>
          <input
            id="title"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Why remote teams burn out on async standups"
            className="rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="idea" className="text-sm font-medium text-slate-700">
            Idea
          </label>
          <textarea
            id="idea"
            required
            rows={4}
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="A short video explaining why fully-async daily standups quietly kill remote team morale, and what teams do instead."
            className="rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="sectionCount" className="text-sm font-medium text-slate-700">
            Number of script sections
          </label>
          <input
            id="sectionCount"
            type="number"
            min={1}
            max={10}
            value={sectionCount}
            onChange={(e) => setSectionCount(Number(e.target.value))}
            className="w-24 rounded-md border px-3 py-2 text-sm"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="self-start rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {submitting ? "Starting…" : "Start project"}
        </button>
      </form>
    </main>
  );
}
