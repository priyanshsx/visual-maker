// Talking head: your own footage (sound included) with plain cards on top at chosen moments:
//   title  -> lower third near the bottom (name, topic)
//   stat / chart / points -> a card in the top part of the frame
// BASIC TEMPLATE: follows the explainer's plain style; the design will be reworked later.
import { AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { scale, Wordmark } from "./Explainer";
import { useBrandFont } from "./shared";
import type { HeadOverlay, TalkingHeadProps } from "./types";

const FADE = 7;

function useFade(frames: number) {
  const f = useCurrentFrame();
  return Math.min(
    interpolate(f, [0, FADE], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    interpolate(f, [frames - FADE, frames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
}

const Card: React.FC<{ p: TalkingHeadProps; o: HeadOverlay; frames: number }> = ({ p, o, frames }) => {
  const c = p.brand.colors;
  const s = scale(p.width, p.height);
  const opacity = useFade(frames);
  const pad = 56 * s;
  const panel: React.CSSProperties = { background: `${c.surface}F0`, color: c.text, borderRadius: 28 * s,
    padding: `${34 * s}px ${38 * s}px`, boxShadow: "0 20px 60px rgba(0,0,0,0.35)", border: `1px solid ${c.muted}33` };

  if (o.kind === "title") {
    return (
      <div style={{ position: "absolute", left: pad, right: pad, bottom: p.height * 0.13, opacity, display: "flex" }}>
        <div style={{ ...panel, borderRadius: 18 * s, padding: `${22 * s}px ${30 * s}px`, borderLeft: `${8 * s}px solid ${c.primary}` }}>
          <div style={{ fontSize: 40 * s, fontWeight: 800, letterSpacing: "-0.01em" }}>{o.text}</div>
          {o.subtext && <div style={{ marginTop: 6 * s, fontSize: 28 * s, color: c.muted }}>{o.subtext}</div>}
        </div>
      </div>
    );
  }
  const top: React.CSSProperties = { position: "absolute", left: pad, right: pad, top: p.height * 0.09, opacity };
  if (o.kind === "stat") {
    return (
      <div style={top}><div style={panel}>
        <div style={{ fontSize: 130 * s, fontWeight: 800, lineHeight: 1, letterSpacing: "-0.04em", color: c.primary }}>{o.value}</div>
        <div style={{ marginTop: 16 * s, fontSize: 38 * s, fontWeight: 700, lineHeight: 1.25 }}>{o.label}</div>
        <div style={{ marginTop: 18 * s, fontSize: 22 * s, color: c.muted }}>Source: {o.source}</div>
      </div></div>
    );
  }
  if (o.kind === "chart") {
    return (
      <div style={top}><div style={{ ...panel, padding: 22 * s }}>
        {o.caption && <div style={{ fontSize: 34 * s, fontWeight: 700, lineHeight: 1.25, margin: `${6 * s}px ${8 * s}px ${18 * s}px` }}>{o.caption}</div>}
        <div style={{ borderRadius: 16 * s, overflow: "hidden", aspectRatio: String(o.image.aspect) }}>
          <Img src={o.image.src} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
        <div style={{ marginTop: 14 * s, marginLeft: 8 * s, fontSize: 22 * s, color: c.muted }}>Source: {o.source}</div>
      </div></div>
    );
  }
  return (
    <div style={top}><div style={panel}>
      <div style={{ fontSize: 42 * s, fontWeight: 800, lineHeight: 1.15, marginBottom: 22 * s }}>{o.title}</div>
      {o.items.map((item, i) => (
        <div key={i} style={{ display: "flex", gap: 18 * s, alignItems: "flex-start", marginTop: i ? 16 * s : 0 }}>
          <div style={{ flex: "none", width: 40 * s, height: 40 * s, borderRadius: 40 * s, background: c.primary, color: c.on_primary,
            fontWeight: 800, fontSize: 22 * s, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
          <div style={{ fontSize: 32 * s, lineHeight: 1.3, paddingTop: 2 * s }}>{item}</div>
        </div>
      ))}
    </div></div>
  );
};

export const TalkingHead: React.FC<TalkingHeadProps> = (p) => {
  useBrandFont(p.brand);
  const s = scale(p.width, p.height);
  return (
    <AbsoluteFill style={{ background: "#000", fontFamily: `"${p.brand.fontFamily}", sans-serif` }}>
      <style>{p.brand.fontCss}</style>
      <OffthreadVideo src={staticFile(p.footage)} trimBefore={p.startFrame} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      {/* small brand mark, top left, always on */}
      <div style={{ position: "absolute", left: 56 * s, top: 48 * s, padding: `${10 * s}px ${18 * s}px`, borderRadius: 14 * s,
        background: `${p.brand.colors.background}B0` }}>
        <Wordmark brand={p.brand} size={26 * s} />
      </div>
      {p.overlays.map((o, i) => (
        <Sequence key={i} from={o.from} durationInFrames={o.frames}>
          <Card p={p} o={o} frames={o.frames} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
