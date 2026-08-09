"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseResizableWidthOptions {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
  /** Dragging right grows the pane by default; set true for panes anchored
   * to the right edge (dragging left should grow them instead). */
  invert?: boolean;
}

export function useResizableWidth({ storageKey, defaultWidth, min, max, invert }: UseResizableWidthOptions) {
  const [width, setWidth] = useState(defaultWidth);
  const draggingRef = useRef(false);

  const clamp = useCallback((value: number) => Math.min(max, Math.max(min, value)), [min, max]);

  // Restored after mount, not during initial render -- localStorage isn't
  // available during SSR and reading it there would mismatch the server-
  // rendered HTML.
  useEffect(() => {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === null) return;
    const parsed = Number(stored);
    if (!Number.isNaN(parsed)) setWidth(clamp(parsed));
  }, [storageKey, clamp]);

  const startDrag = useCallback(
    (startEvent: React.MouseEvent) => {
      startEvent.preventDefault();
      draggingRef.current = true;
      const startX = startEvent.clientX;
      const startWidth = width;
      const previousUserSelect = document.body.style.userSelect;
      document.body.style.userSelect = "none";

      function onMouseMove(e: MouseEvent) {
        if (!draggingRef.current) return;
        const delta = e.clientX - startX;
        setWidth(clamp(startWidth + (invert ? -delta : delta)));
      }
      function onMouseUp() {
        draggingRef.current = false;
        document.body.style.userSelect = previousUserSelect;
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
        setWidth((current) => {
          window.localStorage.setItem(storageKey, String(current));
          return current;
        });
      }

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [width, clamp, invert, storageKey]
  );

  return { width, startDrag };
}
