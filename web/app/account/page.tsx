"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FolderOpen, LogIn } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { listMyProjects } from "@/lib/api";
import type { ProjectSummary } from "@/lib/types";
import { Logo } from "@/components/Logo";
import { AuthControl } from "@/components/AuthControl";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PROJECT_STATUS_META } from "@/lib/status";

export default function AccountPage() {
  const { signedIn, email, loading: authLoading } = useAuth();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;

    listMyProjects()
      .then(({ projects }) => {
        if (!cancelled) setProjects(projects);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <Logo />
        </div>
        <AuthControl hideAccountLink />
      </header>

      {authLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : !signedIn ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 p-8 text-center">
            <LogIn className="h-5 w-5 text-slate-600" />
            <p className="text-sm text-slate-400">Sign in above to see your account and past projects.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-0.5">
            <h1 className="text-lg font-semibold text-slate-50">Your projects</h1>
            <p className="text-sm text-slate-500">
              Signed in as <span className="text-slate-300">{email}</span>. Only projects created while signed in
              show up here.
            </p>
          </div>

          {error && (
            <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          {projects === null && !error ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : projects && projects.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 p-8 text-center">
                <FolderOpen className="h-5 w-5 text-slate-600" />
                <p className="text-sm text-slate-400">
                  No projects yet. Anything you start while signed in will show up here.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-2">
              {projects?.map((project) => {
                const meta = PROJECT_STATUS_META[project.status];
                return (
                  <Link key={project.id} href={`/projects/${project.id}`}>
                    <Card className="transition-colors hover:border-blue-500/50 hover:bg-slate-900/80">
                      <CardContent className="flex items-center justify-between gap-4 p-4">
                        <div className="flex flex-col gap-0.5">
                          <p className="text-sm font-medium text-slate-100">{project.title}</p>
                          <p className="text-xs text-slate-500">
                            {new Date(project.createdAt).toLocaleDateString(undefined, {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                            })}
                          </p>
                        </div>
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
