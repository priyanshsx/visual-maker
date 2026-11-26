// The props every composition receives. visual-maker's Python CLI builds these from
// brands/<client>/brand.yaml and the YAML entry (see visuals/remotion_bridge.py).

export type BrandProps = {
  name: string;
  handle: string | null;
  footer: string | null;
  logo: string | null;          // data URI, or null for a text wordmark
  logoWithName: boolean;        // show the name next to an icon-only logo
  fontFamily: string;
  fontCss: string;              // @font-face rules with the font files embedded
  colors: {
    primary: string;
    text: string;
    muted: string;
    background: string;
    surface: string;
    on_primary: string;
  };
};

export type DemoImage = { src: string; aspect: number };   // aspect = width / height

export type DemoStep = {
  image: number;                // index into images
  caption: string;
  focus: [number, number];      // point to look at, 0..1 across and down the screenshot
  zoom: number;                 // 1 = whole screenshot, 2 = twice as close
  marker: boolean;              // pulse a ring on the focus point
};

export type Look = "clean" | "cinematic";

export type DeviceDemoProps = {
  look: Look;                   // clean = flat background; cinematic = fog, reflections, glow, grain
  width: number;
  height: number;
  brand: BrandProps;
  kicker: string | null;
  title: string;                // *words* in asterisks are shown in brand colour
  cta: string | null;
  images: DemoImage[];
  steps: DemoStep[];
  introSeconds: number;
  stepSeconds: number;
  outroSeconds: number;
};

// ---- event recap: one infographic image (and an optional short animated version) ----
export type IconName =
  | "flask" | "leaf" | "globe" | "shield" | "recycle" | "thermometer" | "droplet"
  | "bearing" | "mic" | "molecule" | "chart" | "people" | "scale" | "gear";

export type RecapCard = { icon: IconName; name: string; org: string | null; topic: string; body: string };
export type RecapPoint = { icon: IconName; text: string };

export type EventRecapProps = {
  width: number;
  height: number;
  brand: BrandProps;
  badge: string | null;          // e.g. "Lubricant Expo Europe 2026 · Düsseldorf"
  title: string;                 // dark first line
  titleAccent: string | null;    // second line in brand colour
  intro: string;
  stats: { value: string; label: string }[];
  cardsLabel: string;            // e.g. "Key takeaways from the sessions"
  cards: RecapCard[];            // 2 to 4
  bigPicture: { label: string; title: string; pointsLabel: string | null; points: RecapPoint[] };
  closing: string;
  seconds: number;               // length of the animated version; the image is its last frame
};
