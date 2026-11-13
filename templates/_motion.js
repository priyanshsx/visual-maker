// Shared helpers for motion templates. Every motion template defines:
//   motionSetup()    optional, runs before text fitting (e.g. split words into spans)
//   prepareMotion()  runs after fitting, returns the time (s) the animation ends
//   renderAt(t)      sets every element to how it looks at time t (seconds)
// The renderer calls renderAt for every frame, so the result is identical on every run.
// Animations only change opacity, transform and colour, never layout, so fitted text stays fitted.

const S = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--s")) || 1;

// Progress 0..1 of a step that starts at `start` and lasts `dur` seconds
function prog(t, start, dur) {
  return Math.min(1, Math.max(0, (t - start) / dur));
}

// Easing: fast start, soft landing
function easeOut(p) {
  return 1 - Math.pow(1 - p, 3);
}

// Fade in while rising `rise` pixels (scaled to the output size)
function rise(el, p, rise = 36) {
  if (!el) return;
  el.style.opacity = p;
  el.style.transform = `translateY(${(1 - p) * rise * S}px)`;
}

// Mix two #RRGGBB colours, p = 0 gives a, p = 1 gives b
function mix(a, b, p) {
  const ca = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const cb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = ca.map((v, i) => Math.round(v + (cb[i] - v) * p));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// The frame around the content: accent bar grows down, logo fades in, footer fades in at `footerAt`
function frameAt(t, footerAt) {
  const bar = document.querySelector(".accent-bar");
  if (bar) {
    bar.style.transformOrigin = "top";
    bar.style.transform = `scaleY(${easeOut(prog(t, 0, 0.6))})`;
  }
  rise(document.querySelector(".top"), easeOut(prog(t, 0.1, 0.5)), 0);
  rise(document.querySelector(".bottom"), easeOut(prog(t, footerAt, 0.5)), 12);
}
