// Device demo: a product screenshot on a floating 3D screen. The camera glides between
// the points you choose while captions explain each one; brand header, footer and
// progress dots stay on top. Text is HTML (sharp, brand font); only the screen is 3D.
import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { FilmLayer } from "./cinematic/FilmLayer";
import { focusIn } from "./cinematic/text";
import { Screen3D } from "./Screen3D";
import { Emphasis, useBrandFont } from "./shared";
import { FPS, MOVE_SECONDS, layout, phaseAt, phases } from "./timeline";
import type { DeviceDemoProps } from "./types";

const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

// Fade + rise in at `start`, fade + rise out at `end` (frames).
// Cinematic look: text comes into focus (blur -> sharp) instead of a plain fade.
function useInOut(start: number, end: number | null, s: number, cine = false, plain = false) {
  const frame = useCurrentFrame();
  if (plain) {                       // plain text: a short fade, no movement or blur
    const inP = interpolate(frame, [start, start + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const outP = end === null ? 0 : interpolate(frame, [end - 6, end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return { opacity: inP * (1 - outP) };
  }
  const inT = interpolate(frame, [start, start + (cine ? 20 : 14)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeOut });
  const outT = end === null ? 0 : interpolate(frame, [end - 8, end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (cine) {
    const style = focusIn(inT, s);
    return { ...style, opacity: inT * (1 - outT), filter: outT > 0 ? `blur(${outT * 10 * s}px)` : style.filter };
  }
  return {
    opacity: inT * (1 - outT),
    transform: `translateY(${(1 - inT) * 36 * s - outT * 28 * s}px)`,
  };
}

const Header: React.FC<{ p: DeviceDemoProps }> = ({ p }) => {
  const L = layout(p.width, p.height);
  const { brand } = p;
  const s = L.s;
  return (
    <div style={{ position: "absolute", left: L.header.x, top: L.header.y, width: L.header.w, height: L.header.h,
      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 * s }}>
        {brand.logo && <img src={brand.logo} style={{ height: 46 * s }} />}
        {(!brand.logo || brand.logoWithName) && (
          <span style={{ fontWeight: 800, fontSize: 32 * s, letterSpacing: "-0.02em",
            color: brand.logo ? brand.colors.text : brand.colors.primary }}>{brand.name}</span>
        )}
      </div>
      {brand.handle && <span style={{ fontWeight: 600, fontSize: 22 * s, color: brand.colors.muted }}>{brand.handle}</span>}
    </div>
  );
};

const Footer: React.FC<{ p: DeviceDemoProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  const L = layout(p.width, p.height);
  const s = L.s;
  const ph = phaseAt(p, frame);
  const active = ph.kind === "step" ? ph.index : ph.kind === "outro" ? p.steps.length : -1;
  return (
    <div style={{ position: "absolute", left: L.footer.x, top: L.footer.y, width: L.footer.w, height: L.footer.h,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      borderTop: `1px solid ${p.brand.colors.muted}33`, paddingTop: 14 * s }}>
      <span style={{ fontSize: 20 * s, color: p.brand.colors.muted }}>{p.brand.footer ?? ""}</span>
      <div style={{ display: "flex", gap: 8 * s }}>
        {p.steps.map((_, i) => (
          <div key={i} style={{ height: 8 * s, borderRadius: 8 * s, width: (i === active ? 34 : 8) * s,
            background: i <= active ? p.brand.colors.primary : `${p.brand.colors.muted}66` }} />
        ))}
      </div>
    </div>
  );
};

// Solid background behind the text area, fading out towards the screen, so captions
// stay readable when the camera zooms and the screen slides under them
const Scrim: React.FC<{ p: DeviceDemoProps }> = ({ p }) => {
  const L = layout(p.width, p.height);
  const bg = p.brand.colors.background;
  const solid = L.row ? L.text.x + L.text.w : L.text.y + L.text.h;
  const fade = 90 * L.s;
  return (
    <>
      <AbsoluteFill style={{ background: L.row
        ? `linear-gradient(90deg, ${bg} 0px, ${bg} ${solid}px, ${bg}00 ${solid + fade}px)`
        : `linear-gradient(180deg, ${bg} 0px, ${bg} ${solid}px, ${bg}00 ${solid + fade}px)` }} />
      <AbsoluteFill style={{ background:
        `linear-gradient(0deg, ${bg} 0px, ${bg} ${p.height - L.footer.y + 8 * L.s}px, ${bg}00 ${p.height - L.footer.y + 60 * L.s}px)` }} />
      {L.row && <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: L.header.y + L.header.h + 30 * L.s,
        background: `linear-gradient(180deg, ${bg} 70%, ${bg}00)` }} />}
    </>
  );
};

const Intro: React.FC<{ p: DeviceDemoProps; end: number }> = ({ p, end }) => {
  const L = layout(p.width, p.height);
  const s = L.s;
  const cine = p.look === "cinematic";
  const plain = p.textStyle === "plain";
  const kick = useInOut(4, end + 4, s, cine, plain);
  const title = useInOut(10, end + 6, s, cine, plain);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: `0 ${L.pad * 1.3}px`, textAlign: "center" }}>
      {p.kicker && (
        <div style={{ ...kick, display: "inline-flex", alignItems: "center", gap: 12 * s, padding: `${10 * s}px ${22 * s}px`,
          borderRadius: 999, border: `1.5px solid ${p.brand.colors.primary}88`, color: p.brand.colors.primary,
          fontWeight: 600, fontSize: 26 * s, marginBottom: 34 * s }}>
          <span style={{ width: 10 * s, height: 10 * s, borderRadius: 10 * s, background: p.brand.colors.primary }} />
          {p.kicker}
        </div>
      )}
      <div style={{ ...title, fontWeight: 800, fontSize: (L.row ? 84 : 100) * s, lineHeight: 1.04,
        letterSpacing: "-0.035em", color: p.brand.colors.text, textWrap: "balance" }}>
        <Emphasis text={p.title} color={p.brand.colors.primary} />
      </div>
    </AbsoluteFill>
  );
};

const Caption: React.FC<{ p: DeviceDemoProps; i: number; start: number; end: number | null }> = ({ p, i, start, end }) => {
  const L = layout(p.width, p.height);
  const s = L.s;
  const cine = p.look === "cinematic";
  const plain = p.textStyle === "plain";
  const num = useInOut(start, end, s, cine, plain);
  const text = useInOut(start + 4, end, s, cine, plain);
  return (
    <div style={{ position: "absolute", left: L.text.x, top: L.text.y, width: L.text.w, height: L.text.h,
      display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ ...num, fontWeight: 700, fontSize: 24 * s, letterSpacing: "0.08em", color: p.brand.colors.primary, marginBottom: 16 * s }}>
        {String(i + 1).padStart(2, "0")} / {String(p.steps.length).padStart(2, "0")}
      </div>
      <div style={{ ...text, fontWeight: 700, fontSize: (L.row ? 46 : 54) * s, lineHeight: 1.12, letterSpacing: "-0.02em",
        color: p.brand.colors.text, textWrap: "balance" }}>
        <Emphasis text={p.steps[i].caption} color={p.brand.colors.primary} />
      </div>
    </div>
  );
};

const Outro: React.FC<{ p: DeviceDemoProps; start: number }> = ({ p, start }) => {
  const L = layout(p.width, p.height);
  const s = L.s;
  const cine = p.look === "cinematic";
  const plain = p.textStyle === "plain";
  const title = useInOut(start, null, s, cine, plain);
  const cta = useInOut(start + 8, null, s, cine, plain);
  return (
    <div style={{ position: "absolute", left: L.text.x, top: L.text.y, width: L.text.w, height: L.text.h,
      display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "flex-start" }}>
      <div style={{ ...title, fontWeight: 800, fontSize: (L.row ? 56 : 66) * s, lineHeight: 1.05, letterSpacing: "-0.03em",
        color: p.brand.colors.text, textWrap: "balance" }}>
        <Emphasis text={p.title} color={p.brand.colors.primary} />
      </div>
      {p.cta && (
        <div style={{ ...cta, marginTop: 26 * s, padding: `${14 * s}px ${26 * s}px`, borderRadius: 999,
          background: p.brand.colors.primary, color: p.brand.colors.on_primary, fontWeight: 700, fontSize: 26 * s }}>
          {p.cta}
        </div>
      )}
    </div>
  );
};

export const DeviceDemo: React.FC<DeviceDemoProps> = (p) => {
  useBrandFont(p.brand);
  const frame = useCurrentFrame();
  const list = phases(p);
  const move = Math.round(MOVE_SECONDS * FPS);
  const { colors } = p.brand;
  const ph = phaseAt(p, frame);
  return (
    <AbsoluteFill style={{ background: colors.background, fontFamily: `"${p.brand.fontFamily}", sans-serif`, color: colors.text }}>
      <style>{p.brand.fontCss}</style>
      {p.look !== "cinematic" && (
        <AbsoluteFill style={{ background: `radial-gradient(60% 50% at 65% 62%, ${colors.primary}22, ${colors.background}00 70%)` }} />
      )}
      <Screen3D p={p} />
      <Scrim p={p} />
      <Header p={p} />
      {ph.kind === "intro" || frame < list[1].start + 8 ? <Intro p={p} end={list[1].start} /> : null}
      {list.filter((x) => x.kind === "step").map((x) =>
        frame >= x.start && frame < x.end + 2 ? (
          <Caption key={x.index} p={p} i={x.index} start={x.start + Math.round(move * 0.45)} end={x.end} />
        ) : null)}
      {ph.kind === "outro" && <Outro p={p} start={ph.start + Math.round(move * 0.5)} />}
      <Footer p={p} />
      {p.look === "cinematic" && <FilmLayer />}
    </AbsoluteFill>
  );
};
