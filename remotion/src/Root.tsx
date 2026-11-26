// All compositions. Size and length come from the props, so one composition covers
// portrait, square, landscape and story. Preview with real props:
//   npx remotion studio src/index.ts --props=<file>.props.json
// (python -m visuals ... --html saves that file next to the video)
import { Composition, type CalculateMetadataFunction } from "remotion";
import { DeviceDemo } from "./DeviceDemo";
import { EventRecap } from "./EventRecap";
import { Explainer } from "./Explainer";
import { TalkingHead } from "./TalkingHead";
import { FPS, totalFrames } from "./timeline";
import type { DeviceDemoProps, EventRecapProps, ExplainerProps, TalkingHeadProps } from "./types";

const GREY_PIXEL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkqGv4DwAEhgJAgO6xAAAAAElFTkSuQmCC";

const sample: DeviceDemoProps = {
  look: "cinematic",
  textStyle: "animated",
  width: 1080,
  height: 1350,
  brand: {
    name: "Brand", handle: "example.com", footer: "Footer line", logo: null, logoWithName: false,
    fontFamily: "Inter", fontCss: "",
    colors: { primary: "#155EEF", text: "#0B1B3F", muted: "#51607F", background: "#F5F8FF", surface: "#FFFFFF", on_primary: "#FFFFFF" },
  },
  kicker: "New feature",
  title: "Run this from *visual-maker*",
  cta: "example.com",
  images: [{ src: GREY_PIXEL, aspect: 16 / 10 }],
  steps: [
    { image: 0, caption: "Overview", focus: [0.5, 0.5], zoom: 1, marker: false },
    { image: 0, caption: "A closer look", focus: [0.3, 0.3], zoom: 2, marker: true },
  ],
  introSeconds: 2.2,
  stepSeconds: 3,
  outroSeconds: 3,
};

const metadata: CalculateMetadataFunction<DeviceDemoProps> = ({ props }) => ({
  durationInFrames: totalFrames(props),
  width: props.width,
  height: props.height,
  fps: FPS,
});

const recapSample: EventRecapProps = {
  width: 1080,
  height: 1350,
  brand: sample.brand,
  badge: "Example Expo 2026 · City",
  title: "On the ground at the expo.",
  titleAccent: "What we learned.",
  intro: "One short paragraph that sets the scene.",
  stats: [{ value: "5,000", label: "attendees" }, { value: "200+", label: "exhibitors" }],
  cardsLabel: "Key takeaways",
  cards: [
    { icon: "flask", name: "Speaker One", org: "Company", topic: "Topic", body: "What they said." },
    { icon: "leaf", name: "Speaker Two", org: "Company", topic: "Topic", body: "What they said." },
  ],
  bigPicture: { label: "The bigger picture", title: "One sentence that ties it together.", pointsLabel: null, points: [] },
  closing: "Closing line.",
  seconds: 5,
};

const recapMetadata: CalculateMetadataFunction<EventRecapProps> = ({ props }) => ({
  durationInFrames: Math.round(props.seconds * FPS),
  width: props.width,
  height: props.height,
  fps: FPS,
});

const explainerSample: ExplainerProps = {
  width: 1080, height: 1920, brand: sample.brand, look: "clean",
  scenes: [
    { kind: "hook", text: "One idea, *explained*.", frames: 90 },
    { kind: "points", title: "Three things", items: ["First", "Second", "Third"], frames: 150 },
    { kind: "cta", text: "Try it", url: "example.com", frames: 90 },
  ],
};
const explainerMetadata: CalculateMetadataFunction<ExplainerProps> = ({ props }) => ({
  durationInFrames: props.scenes.reduce((n, s) => n + s.frames, 0),
  width: props.width, height: props.height, fps: FPS,
});

const headSample: TalkingHeadProps = {
  width: 1080, height: 1920, brand: sample.brand, footage: "talk.mp4", startFrame: 0, durationFrames: 150,
  overlays: [{ kind: "title", text: "Your name", subtext: "Topic", from: 15, frames: 90 }],
};
const headMetadata: CalculateMetadataFunction<TalkingHeadProps> = ({ props }) => ({
  durationInFrames: props.durationFrames, width: props.width, height: props.height, fps: FPS,
});

export const RemotionRoot: React.FC = () => (
  <>
  <Composition
    id="DeviceDemo"
    component={DeviceDemo}
    defaultProps={sample}
    calculateMetadata={metadata}
    durationInFrames={totalFrames(sample)}
    fps={FPS}
    width={sample.width}
    height={sample.height}
  />
  <Composition
    id="EventRecap"
    component={EventRecap}
    defaultProps={recapSample}
    calculateMetadata={recapMetadata}
    durationInFrames={Math.round(recapSample.seconds * FPS)}
    fps={FPS}
    width={recapSample.width}
    height={recapSample.height}
  />
  <Composition id="Explainer" component={Explainer} defaultProps={explainerSample} calculateMetadata={explainerMetadata}
    durationInFrames={330} fps={FPS} width={1080} height={1920} />
  <Composition id="TalkingHead" component={TalkingHead} defaultProps={headSample} calculateMetadata={headMetadata}
    durationInFrames={150} fps={FPS} width={1080} height={1920} />
  </>
);
