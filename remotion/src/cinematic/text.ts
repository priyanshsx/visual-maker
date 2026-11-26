// Cinematic text entrance: comes into focus (blur -> sharp) while rising slightly.
// Returns CSS for a 0..1 progress value, so any composition can use it.
export function focusIn(t: number, s: number): React.CSSProperties {
  const k = Math.min(Math.max(t, 0), 1);
  return {
    opacity: k,
    filter: k < 1 ? `blur(${(1 - k) * 14 * s}px)` : undefined,
    transform: `translateY(${(1 - k) * 24 * s}px) scale(${1.04 - 0.04 * k})`,
  };
}
