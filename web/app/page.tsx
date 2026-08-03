"use client";

export default function HomePage() {
  // TODO: form for { title, idea, params } -> lib/api.ts createProject(),
  // then router.push(`/projects/${projectId}`).
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 p-8">
      <h1 className="text-2xl font-semibold">showrunner</h1>
      <p className="text-sm text-muted-foreground">New project form placeholder</p>
    </main>
  );
}
