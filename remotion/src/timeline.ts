// Pure maths for the device demo: where each phase starts, where the text and the
// screen sit, and where the camera is at any frame. No React here, so it is easy to test.
import { Easing, interpolate } from "remotion";
import { wobble } from "./cinematic/random";
import type { DeviceDemoProps } from "./types";

export const FPS = 30;
export const MOVE_SECONDS = 0.9;          // camera move between steps
export const LEAD_FRAMES = 12;            // camera starts moving this early, under the outgoing text
export const PANEL_WORLD_WIDTH = 4;       // screen width in 3D units
export const FOV = 30;                    // camera field of view (degrees)

const ease = Easing.bezier(0.65, 0, 0.35, 1);

// ---- timing ----
export type Phase = { kind: "intro" | "step" | "outro"; index: number; start: number; end: number };

export function phases(p: DeviceDemoProps): Phase[] {
  const intro = Math.round(p.introSeconds * FPS);
  const step = Math.round(p.stepSeconds * FPS);
  const outro = Math.round(p.outroSeconds * FPS);
  const list: Phase[] = [{ kind: "intro", index: 0, start: 0, end: intro }];
  p.steps.forEach((_, i) => {
    list.push({ kind: "step", index: i, start: intro + i * step, end: intro + (i + 1) * step });
  });
  const last = list[list.length - 1].end;
  list.push({ kind: "outro", index: 0, start: last, end: last + outro });
  return list;
}

export function totalFrames(p: DeviceDemoProps): number {
  const list = phases(p);
  return list[list.length - 1].end;
}

export function phaseAt(p: DeviceDemoProps, frame: number): Phase {
  const list = phases(p);
  return list.find((ph) => frame < ph.end) ?? list[list.length - 1];
}

// ---- layout (pixels) ----
export type Box = { x: number; y: number; w: number; h: number };
export type Layout = {
  s: number;                // text scale (1 = 1080px-wide portrait)
  row: boolean;             // landscape: text left, screen right
  pad: number;
  header: Box;
  footer: Box;
  text: Box;                // where captions go
  panel: Box;               // where the screen sits at zoom 1
};

export function layout(width: number, height: number): Layout {
  const row = width > height * 1.2;
  const s = Math.min(width / 1080, (height / 1080) * 1.25);
  const pad = 64 * s;
  const header: Box = { x: pad, y: pad * 0.8, w: width - 2 * pad, h: 56 * s };
  const footer: Box = { x: pad, y: height - pad * 0.8 - 36 * s, w: width - 2 * pad, h: 36 * s };
  const top = header.y + header.h + 28 * s;
  const bottom = footer.y - 28 * s;
  if (row) {
    const textW = (width - 2 * pad) * 0.36;
    return {
      s, row, pad, header, footer,
      text: { x: pad, y: top, w: textW, h: bottom - top },
      panel: { x: pad + textW + 40 * s, y: top, w: width - 2 * pad - textW - 40 * s, h: bottom - top },
    };
  }
  const textH = (bottom - top) * (height > width * 1.5 ? 0.22 : 0.28);
  return {
    s, row, pad, header, footer,
    text: { x: pad, y: top, w: width - 2 * pad, h: textH },
    panel: { x: pad * 0.5, y: top + textH + 24 * s, w: width - pad, h: bottom - top - textH - 24 * s },
  };
}

// ---- camera ----
type View = { fx: number; fy: number; zoom: number; rotX: number; rotY: number; lift: number; depth: number };

function viewFor(p: DeviceDemoProps, ph: Phase): View {
  const cine = p.look === "cinematic";
  if (ph.kind === "intro") {
    return cine
      ? { fx: 0.5, fy: 0.5, zoom: 0.9, rotX: 0.04, rotY: 0.5, lift: 0, depth: -10 }   // far back, in the fog
      : { fx: 0.5, fy: 0.5, zoom: 0.9, rotX: -0.7, rotY: 0, lift: -2.4, depth: 0 };  // below the frame
  }
  if (ph.kind === "outro") return { fx: 0.5, fy: 0.5, zoom: 0.84, rotX: 0.1, rotY: -0.3, lift: 0, depth: 0 };
  const st = p.steps[ph.index];
  const tilt = st.zoom <= 1.05 ? (ph.index % 2 === 0 ? 0.14 : -0.14) : 0;   // a little 3D on overviews
  return { fx: st.focus[0], fy: st.focus[1], zoom: st.zoom, rotX: Math.abs(tilt) * 0.4, rotY: tilt, lift: 0, depth: 0 };
}

function mix(a: View, b: View, t: number): View {
  const m = (x: number, y: number) => x + (y - x) * t;
  return {
    fx: m(a.fx, b.fx), fy: m(a.fy, b.fy), zoom: Math.exp(m(Math.log(a.zoom), Math.log(b.zoom))),
    rotX: m(a.rotX, b.rotX), rotY: m(a.rotY, b.rotY), lift: m(a.lift, b.lift), depth: m(a.depth, b.depth),
  };
}

// Smooth view at a frame: move from the previous phase's view at the start of each phase,
// then drift slowly (a gentle push-in and sway) so the shot never looks frozen.
export function viewAt(p: DeviceDemoProps, frame: number): View {
  const list = phases(p);
  const f = frame + LEAD_FRAMES;
  const found = list.findIndex((x) => f < x.end);
  const i = found === -1 ? list.length - 1 : found;
  const ph = list[i];
  const target = viewFor(p, ph);
  const move = Math.round(MOVE_SECONDS * FPS);
  let v = target;
  if (i > 0) {
    const t = interpolate(f, [ph.start, ph.start + move], [0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease,
    });
    v = mix(viewFor(p, list[i - 1]), target, t);
  }
  const held = Math.min(Math.max((f - ph.start) / Math.max(ph.end - ph.start, 1), 0), 1);
  const sec = frame / FPS;
  const approach = ph.kind === "intro" && p.look === "cinematic" ? -4 * (1 - held) : 0;  // drifts closer under the title
  return {
    ...v,
    depth: v.depth + approach,
    zoom: v.zoom * (1 + 0.035 * held),
    rotX: v.rotX + 0.012 * Math.sin(sec * 0.9),
    rotY: v.rotY + 0.02 * Math.sin(sec * 0.6),
  };
}

export type Camera = {
  x: number; y: number; z: number; roll: number;            // camera position + tilt
  rotX: number; rotY: number; lift: number; depth: number;  // screen placement
  wpp: number;                                              // world units per pixel at the screen
};

// Place the camera so the focus point sits in the middle of the screen area,
// without ever showing past the screenshot's edges once zoomed in.
export function cameraAt(p: DeviceDemoProps, frame: number): Camera {
  const L = layout(p.width, p.height);
  const aspect = p.images[0].aspect;
  const v = viewAt(p, frame);
  const fitPx = Math.min(L.panel.w * 0.92, L.panel.h * 0.92 * aspect);   // screen width at zoom 1
  const panelPx = fitPx * v.zoom;
  const half = (zonePx: number, sizePx: number) => zonePx / (2 * sizePx);
  const clamp = (f: number, h: number) => (h >= 0.5 ? Math.min(Math.max(f, 1 - h), h) : Math.min(Math.max(f, h), 1 - h));
  const fx = clamp(v.fx, half(L.panel.w, panelPx));
  const fy = clamp(v.fy, half(L.panel.h, panelPx / aspect));
  const wpp = PANEL_WORLD_WIDTH / panelPx;                     // world units per pixel
  const dist = (wpp * p.height) / (2 * Math.tan((FOV * Math.PI) / 360));
  const worldH = PANEL_WORLD_WIDTH / aspect;
  const fxW = (fx - 0.5) * PANEL_WORLD_WIDTH;
  const fyW = (0.5 - fy) * worldH;
  const cx = L.panel.x + L.panel.w / 2;
  const cy = L.panel.y + L.panel.h / 2;
  // Cinematic: a slow handheld drift of a few pixels, plus a hint of roll
  const t = frame / FPS;
  const hand = p.look === "cinematic" ? 6 * (p.width / 1080) : 0;
  return {
    x: fxW - (cx - p.width / 2) * wpp + hand * wpp * wobble(t * 0.7, 1),
    y: fyW + (cy - p.height / 2) * wpp + hand * wpp * wobble(t * 0.6, 2),
    z: dist,
    roll: p.look === "cinematic" ? 0.004 * wobble(t * 0.5, 3) : 0,
    rotX: v.rotX, rotY: v.rotY, lift: v.lift, depth: v.depth, wpp,
  };
}
