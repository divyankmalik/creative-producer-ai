// Local mirrors of the relevant backend payload shapes (api/app/agents/
// content.py, design.py, publishing.py) -- artifact payloads are untyped
// JSON on the wire, so these are read defensively, not trusted blindly.
// Shared between ProductionTimeline (the in-app view) and the PDF export,
// so both compute the exact same real timestamps from one place instead of
// two copies of the same logic drifting apart.

export interface OutlineSection {
  key: string;
  title: string;
}
export interface OutlinePayload {
  sections: OutlineSection[];
}
export interface StoryboardShot {
  section_key: string;
  visual: string;
  overlay_text: string | null;
  duration_s: number;
}
export interface StoryboardPayload {
  shots: StoryboardShot[];
}
export interface ScriptPayload {
  section_key: string;
  text: string;
}
export interface VisualLanguagePayload {
  mood?: string;
  imagery_style?: string;
  typography?: string;
  color_palette?: Record<string, string>;
}
export interface ThumbnailConcept {
  concept_name?: string;
  visual?: string;
  overlay_text?: string | null;
  image_prompt?: string;
}
export interface ThumbnailsPayload {
  concepts?: ThumbnailConcept[];
}
export interface SeoPayload {
  seo_title?: string;
  seo_description?: string;
  tags?: string[];
}

export interface TimelineBlock {
  sectionKey: string;
  sectionTitle: string;
  startS: number;
  endS: number;
  scriptText: string | null;
  shots: { visual: string; overlayText: string | null; startS: number; endS: number }[];
}

export function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.round(totalSeconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Groups consecutive shots sharing a section_key into one timeline block --
// the storyboard is the only artifact with real elapsed-time information
// (duration_s per shot), so every timestamp here is derived from it, not
// guessed or evenly divided.
export function buildTimeline(
  outline: OutlinePayload,
  storyboard: StoryboardPayload,
  scripts: ScriptPayload[]
): TimelineBlock[] {
  const scriptBySection = new Map(scripts.map((s) => [s.section_key, s.text]));
  const titleBySection = new Map(outline.sections.map((s) => [s.key, s.title]));

  const blocks: TimelineBlock[] = [];
  let cursor = 0;

  for (const shot of storyboard.shots) {
    const startS = cursor;
    const endS = cursor + shot.duration_s;
    cursor = endS;

    const last = blocks[blocks.length - 1];
    const shotEntry = { visual: shot.visual, overlayText: shot.overlay_text, startS, endS };

    if (last && last.sectionKey === shot.section_key) {
      last.endS = endS;
      last.shots.push(shotEntry);
    } else {
      blocks.push({
        sectionKey: shot.section_key,
        sectionTitle: titleBySection.get(shot.section_key) ?? shot.section_key,
        startS,
        endS,
        scriptText: scriptBySection.get(shot.section_key) ?? null,
        shots: [shotEntry],
      });
    }
  }

  return blocks;
}
