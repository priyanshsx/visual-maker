// Film finish drawn on top of everything (3D and text alike): moving grain and a vignette.
// Plain HTML/SVG, so it also works over a talking-head video or any other composition.
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const FilmLayer: React.FC<{ grain?: number; vignette?: number }> = ({ grain = 0.07, vignette = 0.55 }) => {
  const frame = useCurrentFrame();
  const seed = (frame % 24) + 1;                 // new grain pattern every frame, same per render
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity: grain, mixBlendMode: "overlay" }}>
        <filter id={`grain-${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain-${seed})`} />
      </svg>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 75% 70% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${vignette}) 100%)` }} />
    </AbsoluteFill>
  );
};
