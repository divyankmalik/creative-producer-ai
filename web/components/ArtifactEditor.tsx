"use client";

import { useEffect, useState } from "react";
import type { Artifact } from "@/lib/types";

interface ArtifactEditorProps {
  artifact: Artifact;
  onSave?: (payload: Record<string, unknown>) => void;
  onRegenerate?: () => void;
  saving?: boolean;
  regenerating?: boolean;
}

type PathSegment = string | number;
type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

function deepClone<T>(value: T): T {
  return typeof structuredClone === "function"
    ? structuredClone(value)
    : (JSON.parse(JSON.stringify(value)) as T);
}

// Immutably sets `value` at `path` inside `root`, cloning every object/array
// along the way so the caller can compare old vs new by reference.
function setIn(root: JsonValue, path: PathSegment[], value: JsonValue): JsonValue {
  if (path.length === 0) return value;
  const [head, ...rest] = path;

  if (Array.isArray(root)) {
    const copy = [...root];
    copy[head as number] = setIn(copy[head as number] ?? null, rest, value);
    return copy;
  }

  const obj = (root ?? {}) as Record<string, JsonValue>;
  return { ...obj, [head as string]: setIn(obj[head as string] ?? null, rest, value) };
}

function removeAt(root: JsonValue, path: PathSegment[]): JsonValue {
  if (path.length === 1 && Array.isArray(root)) {
    const copy = [...root];
    copy.splice(path[0] as number, 1);
    return copy;
  }
  if (path.length === 0) return root;
  const [head, ...rest] = path;
  if (Array.isArray(root)) {
    const copy = [...root];
    copy[head as number] = removeAt(copy[head as number], rest);
    return copy;
  }
  const obj = (root ?? {}) as Record<string, JsonValue>;
  return { ...obj, [head as string]: removeAt(obj[head as string], rest) };
}

function prettyLabel(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function defaultForSibling(sample: JsonValue | undefined): JsonValue {
  if (typeof sample === "number") return 0;
  if (typeof sample === "boolean") return false;
  if (Array.isArray(sample)) return [];
  if (sample && typeof sample === "object") {
    return Object.fromEntries(Object.keys(sample).map((k) => [k, ""]));
  }
  return "";
}

interface FieldEditorProps {
  label: string | null;
  value: JsonValue;
  path: PathSegment[];
  onChange: (path: PathSegment[], value: JsonValue) => void;
  onRemove?: () => void;
}

function FieldEditor({ label, value, path, onChange, onRemove }: FieldEditorProps) {
  const fieldId = path.join(".") || "root";

  if (typeof value === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(path, e.target.checked)}
        />
        {label && <span className="text-slate-700">{prettyLabel(label)}</span>}
      </label>
    );
  }

  if (typeof value === "number") {
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <input
          type="number"
          id={fieldId}
          value={value}
          onChange={(e) => onChange(path, e.target.valueAsNumber)}
          className="w-full rounded-md border px-2 py-1 text-sm"
        />
      </FieldShell>
    );
  }

  if (Array.isArray(value)) {
    const itemsAreObjects = value.some((item) => item && typeof item === "object" && !Array.isArray(item));
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <div className="flex flex-col gap-2">
          {value.length === 0 && <p className="text-xs italic text-slate-400">Empty list</p>}
          {value.map((item, i) =>
            itemsAreObjects ? (
              <div key={i} className="rounded-md border border-slate-200 p-2">
                <FieldEditor
                  label={null}
                  value={item}
                  path={[...path, i]}
                  onChange={onChange}
                  onRemove={() => onChange(path, removeAt(value, [i]) as JsonValue[])}
                />
              </div>
            ) : (
              <div key={i} className="flex items-center gap-2">
                <div className="flex-1">
                  <FieldEditor label={null} value={item} path={[...path, i]} onChange={onChange} />
                </div>
                <button
                  type="button"
                  onClick={() => onChange(path, removeAt(value, [i]) as JsonValue[])}
                  className="shrink-0 text-xs text-red-500 hover:text-red-700"
                  aria-label="Remove item"
                >
                  ✕
                </button>
              </div>
            )
          )}
          <button
            type="button"
            onClick={() => onChange(path, [...value, defaultForSibling(value[value.length - 1])])}
            className="self-start text-xs font-medium text-sky-600 hover:text-sky-800"
          >
            + Add item
          </button>
        </div>
      </FieldShell>
    );
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <div className="flex flex-col gap-3 border-l-2 border-slate-100 pl-3">
          {entries.map(([key, val]) => (
            <FieldEditor
              key={key}
              label={key}
              value={val}
              path={[...path, key]}
              onChange={onChange}
            />
          ))}
        </div>
      </FieldShell>
    );
  }

  // string | null | undefined
  const stringValue = value == null ? "" : String(value);
  const isLong = stringValue.length > 60 || stringValue.includes("\n");

  return (
    <FieldShell label={label} onRemove={onRemove}>
      {isLong ? (
        <textarea
          id={fieldId}
          value={stringValue}
          onChange={(e) => onChange(path, e.target.value)}
          rows={Math.min(10, Math.max(3, Math.ceil(stringValue.length / 60)))}
          className="w-full rounded-md border px-2 py-1 text-sm"
        />
      ) : (
        <input
          type="text"
          id={fieldId}
          value={stringValue}
          onChange={(e) => onChange(path, e.target.value)}
          className="w-full rounded-md border px-2 py-1 text-sm"
        />
      )}
    </FieldShell>
  );
}

function FieldShell({
  label,
  onRemove,
  children,
}: {
  label: string | null;
  onRemove?: () => void;
  children: React.ReactNode;
}) {
  if (label === null) return <>{children}</>;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label htmlFor={label} className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {prettyLabel(label)}
        </label>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-xs text-red-500 hover:text-red-700"
            aria-label="Remove item"
          >
            ✕
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

export function ArtifactEditor({
  artifact,
  onSave,
  onRegenerate,
  saving,
  regenerating,
}: ArtifactEditorProps) {
  const [draft, setDraft] = useState<JsonValue>(() => deepClone(artifact.payload) as JsonValue);

  // Reset the draft whenever a different artifact (or a newer version of the
  // same one) loads -- otherwise edits from the previous selection would
  // leak into the next artifact's form.
  useEffect(() => {
    setDraft(deepClone(artifact.payload) as JsonValue);
  }, [artifact.id, artifact.currentVersion]);

  function handleChange(path: PathSegment[], value: JsonValue) {
    setDraft((prev) => setIn(prev, path, value));
  }

  const entries = draft && typeof draft === "object" && !Array.isArray(draft) ? Object.entries(draft) : [];

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          v{artifact.currentVersion}
          {artifact.model ? ` · ${artifact.model}` : ""}
          {artifact.editedBy ? ` · edited by ${artifact.editedBy}` : ""}
        </span>
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            disabled={regenerating}
            className="rounded-md border px-2 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            {regenerating ? "Regenerating…" : "Regenerate from scratch"}
          </button>
        )}
      </div>

      <div className="flex flex-col gap-4 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="text-sm text-slate-400">This artifact has no editable fields.</p>
        ) : (
          entries.map(([key, value]) => (
            <FieldEditor key={key} label={key} value={value} path={[key]} onChange={handleChange} />
          ))
        )}
      </div>

      {onSave && (
        <button
          type="button"
          onClick={() => onSave(draft as Record<string, unknown>)}
          disabled={saving}
          className="self-start rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      )}
    </div>
  );
}
