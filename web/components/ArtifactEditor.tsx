"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2, Plus, RefreshCw, Save, X } from "lucide-react";
import type { Artifact } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";

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
      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(path, e.target.checked)}
          className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-slate-950"
        />
        {label && <span>{prettyLabel(label)}</span>}
      </label>
    );
  }

  if (typeof value === "number") {
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <Input type="number" id={fieldId} value={value} onChange={(e) => onChange(path, e.target.valueAsNumber)} />
      </FieldShell>
    );
  }

  if (Array.isArray(value)) {
    const itemsAreObjects = value.some((item) => item && typeof item === "object" && !Array.isArray(item));
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <div className="flex flex-col gap-2">
          {value.length === 0 && <p className="text-xs italic text-slate-500">Empty list</p>}
          {value.map((item, i) =>
            itemsAreObjects ? (
              <div key={i} className="rounded-md border border-slate-800 bg-slate-900/50 p-2.5">
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
                  className="shrink-0 text-slate-500 hover:text-red-400"
                  aria-label="Remove item"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )
          )}
          <button
            type="button"
            onClick={() => onChange(path, [...value, defaultForSibling(value[value.length - 1])])}
            className="inline-flex items-center gap-1 self-start text-xs font-medium text-blue-400 hover:text-blue-300"
          >
            <Plus className="h-3 w-3" />
            Add item
          </button>
        </div>
      </FieldShell>
    );
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    return (
      <FieldShell label={label} onRemove={onRemove}>
        <div className="flex flex-col gap-3 border-l-2 border-slate-800 pl-3">
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
        <div className="relative">
          <Textarea
            id={fieldId}
            value={stringValue}
            onChange={(e) => onChange(path, e.target.value)}
            rows={Math.min(10, Math.max(3, Math.ceil(stringValue.length / 60)))}
            className="pr-9"
          />
          <CopyIconButton text={stringValue} />
        </div>
      ) : (
        <Input type="text" id={fieldId} value={stringValue} onChange={(e) => onChange(path, e.target.value)} />
      )}
    </FieldShell>
  );
}

function CopyIconButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="absolute right-2 top-2 rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-200"
      aria-label="Copy to clipboard"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
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
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={label} className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {prettyLabel(label)}
        </label>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-slate-500 hover:text-red-400"
            aria-label="Remove item"
          >
            <X className="h-3.5 w-3.5" />
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
      <div className="flex items-center justify-between gap-2 font-mono text-xs text-slate-500">
        <span>
          v{artifact.currentVersion}
          {artifact.model ? ` · ${artifact.model}` : ""}
          {artifact.editedBy ? ` · edited by ${artifact.editedBy}` : ""}
        </span>
        {onRegenerate && (
          <Button type="button" onClick={onRegenerate} disabled={regenerating} size="sm" variant="outline">
            {regenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            {regenerating ? "Regenerating…" : "Regenerate from scratch"}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-4 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="text-sm text-slate-500">This artifact has no editable fields.</p>
        ) : (
          entries.map(([key, value]) => (
            <FieldEditor key={key} label={key} value={value} path={[key]} onChange={handleChange} />
          ))
        )}
      </div>

      {onSave && (
        <Button
          type="button"
          onClick={() => onSave(draft as Record<string, unknown>)}
          disabled={saving}
          className={cn("self-start")}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? "Saving…" : "Save changes"}
        </Button>
      )}
    </div>
  );
}
