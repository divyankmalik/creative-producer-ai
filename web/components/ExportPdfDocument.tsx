import { Document, Page, View, Text, StyleSheet } from "@react-pdf/renderer";
import {
  buildTimeline,
  formatTime,
  type OutlinePayload,
  type ScriptPayload,
  type SeoPayload,
  type StoryboardPayload,
  type ThumbnailsPayload,
  type VisualLanguagePayload,
} from "@/lib/timeline";

interface ExportPdfDocumentProps {
  projectTitle: string;
  projectIdea: string;
  outline: OutlinePayload | null;
  storyboard: StoryboardPayload | null;
  scripts: ScriptPayload[];
  visualLanguage: VisualLanguagePayload | null;
  seo: SeoPayload | null;
  thumbnails: ThumbnailsPayload | null;
}

const styles = StyleSheet.create({
  page: { padding: 40, fontSize: 10, fontFamily: "Helvetica", color: "#1a1a1a" },
  h1: { fontSize: 20, fontWeight: 700, marginBottom: 4 },
  h2: { fontSize: 13, fontWeight: 700, marginTop: 18, marginBottom: 8, borderBottom: "1 solid #cccccc", paddingBottom: 4 },
  subtitle: { fontSize: 11, color: "#555555", marginBottom: 12 },
  label: { fontSize: 8, textTransform: "uppercase", color: "#888888", letterSpacing: 0.5, marginBottom: 3 },
  body: { fontSize: 10, lineHeight: 1.5, marginBottom: 8 },
  row: { flexDirection: "row", marginBottom: 12 },
  timeCol: { width: 60, fontSize: 9, color: "#888888" },
  contentCol: { flex: 1 },
  shot: { fontSize: 9, color: "#444444", marginBottom: 3, paddingLeft: 8, borderLeft: "2 solid #dddddd" },
  concept: { marginBottom: 10 },
  imagePrompt: { fontSize: 9, fontStyle: "italic", color: "#555555", marginBottom: 8 },
  tagRow: { flexDirection: "row", flexWrap: "wrap" },
  tag: { fontSize: 8, backgroundColor: "#eeeeee", paddingVertical: 2, paddingHorizontal: 6, borderRadius: 3, marginRight: 4, marginBottom: 4 },
});

export function ExportPdfDocument({
  projectTitle,
  projectIdea,
  outline,
  storyboard,
  scripts,
  visualLanguage,
  seo,
  thumbnails,
}: ExportPdfDocumentProps) {
  const blocks = outline && storyboard ? buildTimeline(outline, storyboard, scripts) : [];
  const totalSeconds = blocks.length > 0 ? blocks[blocks.length - 1].endS : 0;

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <Text style={styles.h1}>{seo?.seo_title || projectTitle}</Text>
        <Text style={styles.subtitle}>{projectIdea}</Text>
        {totalSeconds > 0 && <Text style={styles.body}>Total runtime: {formatTime(totalSeconds)}</Text>}

        {visualLanguage && (visualLanguage.mood || visualLanguage.imagery_style || visualLanguage.typography) && (
          <View>
            <Text style={styles.h2}>Visual style</Text>
            {visualLanguage.mood && <Text style={styles.body}>Mood: {visualLanguage.mood}</Text>}
            {visualLanguage.imagery_style && <Text style={styles.body}>Imagery: {visualLanguage.imagery_style}</Text>}
            {visualLanguage.typography && <Text style={styles.body}>Typography: {visualLanguage.typography}</Text>}
          </View>
        )}

        {blocks.length > 0 && (
          <View>
            <Text style={styles.h2}>Script &amp; storyboard</Text>
            {blocks.map((block, i) => (
              <View key={i} style={styles.row} wrap={false}>
                <View style={styles.timeCol}>
                  <Text>{formatTime(block.startS)}</Text>
                  <Text>–{formatTime(block.endS)}</Text>
                </View>
                <View style={styles.contentCol}>
                  <Text style={styles.label}>{block.sectionTitle}</Text>
                  {block.scriptText && <Text style={styles.body}>{block.scriptText}</Text>}
                  {block.shots.map((shot, j) => (
                    <Text key={j} style={styles.shot}>
                      {formatTime(shot.startS)}–{formatTime(shot.endS)}: {shot.visual}
                      {shot.overlayText ? `  "${shot.overlayText}"` : ""}
                    </Text>
                  ))}
                </View>
              </View>
            ))}
          </View>
        )}

        {thumbnails?.concepts && thumbnails.concepts.length > 0 && (
          <View>
            <Text style={styles.h2}>Thumbnail concepts</Text>
            {thumbnails.concepts.map((c, i) => (
              <View key={i} style={styles.concept} wrap={false}>
                <Text style={styles.label}>{c.concept_name || `Concept ${i + 1}`}</Text>
                {c.visual && <Text style={styles.body}>{c.visual}</Text>}
                {c.overlay_text && <Text style={styles.body}>Overlay text: &quot;{c.overlay_text}&quot;</Text>}
                {c.image_prompt && <Text style={styles.imagePrompt}>Image prompt: {c.image_prompt}</Text>}
              </View>
            ))}
          </View>
        )}

        {seo && (seo.seo_title || seo.seo_description || (seo.tags && seo.tags.length > 0)) && (
          <View wrap={false}>
            <Text style={styles.h2}>Publishing metadata</Text>
            {seo.seo_title && <Text style={styles.body}>Title: {seo.seo_title}</Text>}
            {seo.seo_description && <Text style={styles.body}>Description: {seo.seo_description}</Text>}
            {seo.tags && seo.tags.length > 0 && (
              <View style={styles.tagRow}>
                {seo.tags.map((tag, i) => (
                  <Text key={i} style={styles.tag}>
                    {tag}
                  </Text>
                ))}
              </View>
            )}
          </View>
        )}
      </Page>
    </Document>
  );
}
