// Seeded random numbers and smooth "noise", so every render of a video is identical
// (Math.random would give different dust and shake each time).

export function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// Smooth wobble in roughly -1..1: a few sine waves at unrelated speeds
export function wobble(t: number, seed: number): number {
  return (
    0.55 * Math.sin(t * 1.13 + seed * 1.7) +
    0.3 * Math.sin(t * 2.37 + seed * 4.1) +
    0.15 * Math.sin(t * 4.91 + seed * 2.3)
  );
}
