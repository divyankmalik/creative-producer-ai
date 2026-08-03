"use client";

import { useEffect, useRef, useState } from "react";
import { getProject } from "@/lib/api";
import type { ProjectDetail, ProjectStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES: ProjectStatus[] = ["done", "failed"];

interface UseProjectPollResult {
  project: ProjectDetail | null;
  error: Error | null;
  isPolling: boolean;
}

export function useProjectPoll(projectId: string): UseProjectPollResult {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const result = await getProject(projectId);
        if (cancelled) return;

        setProject(result);
        setError(null);

        if (TERMINAL_STATUSES.includes(result.status)) {
          setIsPolling(false);
          return;
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      }

      if (!cancelled) {
        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [projectId]);

  return { project, error, isPolling };
}
