// Helpers every composition uses: wait for the brand font, and *emphasis* in brand colour.
import { useEffect, useState } from "react";
import { useThree } from "@react-three/fiber";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import type { BrandProps } from "./types";

// Wait for the brand font before the first frame, so text never renders in a fallback font
export function useBrandFont(brand: BrandProps) {
  const [handle] = useState(() => delayRender("Loading brand font"));
  useEffect(() => {
    const weights = [400, 600, 700, 800];
    Promise.all(weights.map((w) => document.fonts.load(`${w} 40px "${brand.fontFamily}"`)))
      .then(() => document.fonts.ready)
      .then(() => continueRender(handle));
  }, [brand.fontFamily, handle]);
}

// *words* in asterisks -> brand colour
export function Emphasis({ text, color }: { text: string; color: string }) {
  const parts = text.split(/\*(.+?)\*/g);
  return <>{parts.map((part, i) => (i % 2 ? <span key={i} style={{ color }}>{part}</span> : part))}</>;
}

// For 3D canvases (frameloop="demand"): redraw once whenever the video frame changes, instead
// of continuously. Previews in the web app and Remotion Studio stay light; renders are unaffected.
export function RedrawOnFrame() {
  const frame = useCurrentFrame();
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => { invalidate(); }, [frame, invalidate]);
  return null;
}
