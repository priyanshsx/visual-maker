// Explainer: a vertical video made of scenes (hook, chart, stat, points, text, cta).
// BASIC TEMPLATE: plain, readable text that simply fades in and out. The design will be
// reworked later; keep scene kinds and props stable so existing YAML files keep working.
import { AbsoluteFill, Easing, Img, Sequence, interpolate, useCurrentFrame } from "remotion";
import { FilmLayer } from "./cinematic/FilmLayer";
import { Emphasis, useBrandFont } from "./shared";
import type { BrandProps, ExplainerProps, ExplainerScene } from "./types";

const FADE = 8;   // frames

// Opacity for a scene that lasts `frames`: fade in at the start, out at the end
function useSceneFade(frames: number) {
  const f = useCurrentFrame();
  return Math.min(
    interpolate(f, [0, FADE], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    interpolate(f, [frames - FADE, frames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
}

// Appear (fade only) `delay` frames into the scene
function useAppear(delay: number) {
  const f = useCurrentFrame();
  return interpolate(f, [delay, delay + FADE], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
}

export function scale(width: number, height: number) {
  return Math.min(width / 1080, (height / 1920) * 1.4);
}

export const Wordmark: React.FC<{ brand: BrandProps; size: number }> = ({ brand, size }) => (
  <div style={{ display: "flex", alignItems: "center", gap: size * 0.35 }}>
    {brand.logo && <img src={brand.logo} style={{ height: size * 1.3 }} />}
    {(!brand.logo || brand.logoWithName) && (
      <span style={{ fontWeight: 800, fontSize: size, letterSpacing: "-0.02em", color: brand.logo ? brand.colors.text : brand.colors.primary }}>
        {brand.name}
      </span>
    )}
  </div>
);

const Scene: React.FC<{ p: ExplainerProps; scene: ExplainerScene; frames: number }> = ({ p, scene, frames }) => {
  const c = p.brand.colors;
  const s = scale(p.width, p.height);
  const fade = useSceneFade(frames);
  const second = useAppear(10);
  const f = useCurrentFrame();
  const box: React.CSSProperties = { position: "absolute", left: 72 * s, right: 72 * s, top: 0, bottom: 0,
    display: "flex", flexDirection: "column", justifyContent: "center", opacity: fade };

  if (scene.kind === "hook") {
    return <div style={box}><div style={{ fontSize: 80 * s, fontWeight: 800, lineHeight: 1.08, letterSpacing: "-0.03em" }}>
      <Emphasis text={scene.text} color={c.primary} /></div></div>;
  }
  if (scene.kind === "text") {
    return <div style={box}><div style={{ fontSize: 58 * s, fontWeight: 600, lineHeight: 1.25, letterSpacing: "-0.015em" }}>
      <Emphasis text={scene.text} color={c.primary} /></div></div>;
  }
  if (scene.kind === "stat") {
    return (
      <div style={box}>
        <div style={{ fontSize: 210 * s, fontWeight: 800, letterSpacing: "-0.05em", lineHeight: 1, color: c.primary }}>{scene.value}</div>
        <div style={{ marginTop: 28 * s, fontSize: 52 * s, fontWeight: 700, lineHeight: 1.2 }}>{scene.label}</div>
        {scene.note && <div style={{ opacity: second, marginTop: 22 * s, fontSize: 36 * s, lineHeight: 1.35, color: c.muted }}>{scene.note}</div>}
        <div style={{ marginTop: 40 * s, fontSize: 24 * s, color: c.muted }}>Source: {scene.source}</div>
      </div>
    );
  }
  if (scene.kind === "points") {
    return (
      <div style={box}>
        <div style={{ fontSize: 60 * s, fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.02em", marginBottom: 44 * s }}>
          <Emphasis text={scene.title} color={c.primary} /></div>
        {scene.items.map((item, i) => {
          const o = interpolate(f, [10 + i * 12, 10 + i * 12 + FADE], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ opacity: o, display: "flex", alignItems: "flex-start", gap: 26 * s, marginTop: i ? 30 * s : 0 }}>
              <div style={{ flex: "none", width: 56 * s, height: 56 * s, borderRadius: 56 * s, background: c.primary, color: c.on_primary,
                fontWeight: 800, fontSize: 28 * s, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
              <div style={{ fontSize: 42 * s, lineHeight: 1.3, fontWeight: 500, paddingTop: 4 * s }}>{item}</div>
            </div>
          );
        })}
      </div>
    );
  }
  if (scene.kind === "chart") {
    // slow, eased push-in towards the focus point
    const t = interpolate(f, [0, frames], [0, 1], { extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
    const zoom = 1 + (scene.zoom - 1) * t;
    const [fx, fy] = scene.focus;
    return (
      <div style={box}>
        <div style={{ fontSize: 50 * s, fontWeight: 700, lineHeight: 1.2, letterSpacing: "-0.015em", marginBottom: 36 * s }}>
          <Emphasis text={scene.caption} color={c.primary} /></div>
        <div style={{ borderRadius: 24 * s, overflow: "hidden", border: `1px solid ${c.muted}40`, background: c.surface,
          aspectRatio: String(scene.image.aspect) }}>
          <Img src={scene.image.src} style={{ width: "100%", height: "100%", objectFit: "contain",
            transform: `scale(${zoom})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }} />
        </div>
        <div style={{ marginTop: 22 * s, fontSize: 24 * s, color: c.muted }}>Source: {scene.source}</div>
      </div>
    );
  }
  // cta
  return (
    <div style={{ ...box, alignItems: "flex-start" }}>
      <Wordmark brand={p.brand} size={54 * s} />
      <div style={{ marginTop: 40 * s, fontSize: 64 * s, fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.025em" }}>
        <Emphasis text={scene.text} color={c.primary} /></div>
      {scene.url && <div style={{ opacity: second, marginTop: 40 * s, padding: `${18 * s}px ${34 * s}px`, borderRadius: 999,
        background: c.primary, color: c.on_primary, fontWeight: 700, fontSize: 34 * s }}>{scene.url}</div>}
    </div>
  );
};

export const Explainer: React.FC<ExplainerProps> = (p) => {
  useBrandFont(p.brand);
  const frame = useCurrentFrame();
  const c = p.brand.colors;
  const s = scale(p.width, p.height);
  const total = p.scenes.reduce((n, sc) => n + sc.frames, 0);
  let from = 0;
  return (
    <AbsoluteFill style={{ background: c.background, color: c.text, fontFamily: `"${p.brand.fontFamily}", sans-serif` }}>
      <style>{p.brand.fontCss}</style>
      {/* header: brand, handle, progress */}
      <div style={{ position: "absolute", left: 72 * s, right: 72 * s, top: 64 * s, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Wordmark brand={p.brand} size={34 * s} />
        {p.brand.handle && <span style={{ fontSize: 24 * s, fontWeight: 600, color: c.muted }}>{p.brand.handle}</span>}
      </div>
      <div style={{ position: "absolute", left: 72 * s, right: 72 * s, top: 136 * s, height: 6 * s, borderRadius: 6 * s, background: `${c.muted}33` }}>
        <div style={{ width: `${Math.min(frame / Math.max(total - 1, 1), 1) * 100}%`, height: "100%", borderRadius: 6 * s, background: c.primary }} />
      </div>
      {/* scenes */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 170 * s, bottom: 150 * s }}>
        {p.scenes.map((sc, i) => {
          const seq = <Sequence key={i} from={from} durationInFrames={sc.frames}><Scene p={p} scene={sc} frames={sc.frames} /></Sequence>;
          from += sc.frames;
          return seq;
        })}
      </div>
      {p.brand.footer && (
        <div style={{ position: "absolute", left: 72 * s, right: 72 * s, bottom: 64 * s, fontSize: 22 * s, color: c.muted,
          borderTop: `1px solid ${c.muted}33`, paddingTop: 20 * s }}>{p.brand.footer}</div>
      )}
      {p.look === "cinematic" && <FilmLayer />}
    </AbsoluteFill>
  );
};
