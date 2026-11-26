// Event recap: one rich infographic (portrait 1080x1350) in the style of a magazine page.
//   header:  brand, event badge, two-line headline, intro, stat chips  | 3D hero on the right
//   middle:  2 to 4 takeaway cards (speaker, organisation, topic, what they said)
//   band:    "the bigger picture" on dark brand blue, with a themes list
//   footer:  closing line + brand
// The image is the last frame; render the whole thing for a short animated version.
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Icon } from "./icons";
import { LubricantHero } from "./LubricantHero";
import { Emphasis, useBrandFont } from "./shared";
import type { EventRecapProps } from "./types";

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const ACCENTS = (primary: string) => [primary, "#0E9F8E", "#6246EA", "#0B4FB3"];

// Rise + fade in, starting at `start` frames (fully visible from start + 18)
function useEnter(start: number) {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [start, start + 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return { opacity: k, transform: `translateY(${(1 - k) * 26}px)` };
}

// Brand mark: the logo file if there is one (logoHeight in px), else the name as text
function Wordmark({ p, color, size, logoHeight }: { p: EventRecapProps; color: string; size: number; logoHeight?: number }) {
  const { brand } = p;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: size * 0.35 }}>
      {brand.logo && <img src={brand.logo} style={{ height: logoHeight ?? size * 1.25 }} />}
      {(!brand.logo || brand.logoWithName) && (
        <span style={{ fontWeight: 800, fontSize: size, letterSpacing: "-0.02em", color }}>{brand.name}</span>
      )}
    </div>
  );
}

const Header: React.FC<{ p: EventRecapProps }> = ({ p }) => {
  const c = p.brand.colors;
  const a = useEnter(2), b = useEnter(8), d = useEnter(14), e = useEnter(20), f = useEnter(26);
  return (
    <div style={{ width: 545, position: "relative" }}>
      <div style={a}><Wordmark p={p} color={c.primary} size={32} logoHeight={54} /></div>
      {p.badge && (
        <div style={{ ...b, marginTop: 20, display: "inline-flex", alignItems: "center", gap: 10, padding: "8px 17px",
          borderRadius: 999, background: `${c.primary}14`, border: `1px solid ${c.primary}33`, color: c.primary,
          fontWeight: 700, fontSize: 16.5, letterSpacing: "0.01em" }}>
          <span style={{ width: 8, height: 8, borderRadius: 8, background: c.primary }} />{p.badge}
        </div>
      )}
      <div style={{ ...d, marginTop: 16, fontSize: 42, lineHeight: 1.06, letterSpacing: "-0.035em", fontWeight: 800, color: c.text }}>
        <Emphasis text={p.title} color={c.primary} />
        {p.titleAccent && <div style={{ color: c.primary }}>{p.titleAccent}</div>}
      </div>
      <p style={{ ...e, margin: "14px 0 0", fontSize: 18, lineHeight: 1.45, color: c.muted }}>{p.intro}</p>
      {p.stats.length > 0 && (
        <div style={{ ...f, marginTop: 18, display: "flex", gap: 12 }}>
          {p.stats.map((st, i) => (
            <div key={i} style={{ padding: "11px 18px", borderRadius: 18, background: "rgba(255,255,255,0.85)",
              border: "1px solid rgba(21,94,239,0.12)", boxShadow: "0 10px 30px rgba(11,27,63,0.08), inset 0 1px 0 #fff",
              minWidth: 140 }}>
              <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-0.03em", color: c.primary, lineHeight: 1 }}>{st.value}</div>
              <div style={{ marginTop: 6, fontSize: 14.5, fontWeight: 600, color: c.muted }}>{st.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Cards: React.FC<{ p: EventRecapProps }> = ({ p }) => {
  const c = p.brand.colors;
  const accents = ACCENTS(c.primary);
  const label = useEnter(32);
  const cols = p.cards.length <= 2 ? 1 : 2;
  const cardW = cols === 2 ? 470 : 960;
  return (
    <div style={{ marginTop: 26, width: 960 }}>
      <div style={{ ...label, fontSize: 15, fontWeight: 800, letterSpacing: "0.22em", textTransform: "uppercase", color: c.text }}>
        {p.cardsLabel}
      </div>
      <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 16 }}>
        {p.cards.map((card, i) => <Card key={i} p={p} i={i} width={cardW} accent={accents[i % accents.length]} card={card} />)}
      </div>
    </div>
  );
};

const Card: React.FC<{ p: EventRecapProps; i: number; width: number; accent: string; card: EventRecapProps["cards"][number] }> = ({ p, i, width, accent, card }) => {
  const c = p.brand.colors;
  const enter = useEnter(38 + i * 6);
  return (
    <div style={{ ...enter, width, boxSizing: "border-box", padding: "16px 22px 17px", borderRadius: 22,
      background: "linear-gradient(180deg, #FFFFFF 0%, #FBFCFF 100%)", border: "1px solid rgba(11,27,63,0.07)",
      boxShadow: "0 1px 0 #fff inset, 0 18px 40px -18px rgba(11,27,63,0.22), 0 2px 6px rgba(11,27,63,0.05)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 50, height: 50, borderRadius: 16, flex: "none", display: "flex", alignItems: "center", justifyContent: "center",
          background: `linear-gradient(145deg, ${accent}, ${accent}CC)`, boxShadow: `0 10px 20px -8px ${accent}AA, inset 0 1px 0 rgba(255,255,255,0.35)` }}>
          <Icon name={card.icon} size={26} color="#fff" />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 19, fontWeight: 800, color: accent, letterSpacing: "-0.01em", lineHeight: 1.15 }}>{card.name}</div>
          {card.org && <div style={{ fontSize: 14.5, fontWeight: 600, color: c.muted, marginTop: 2 }}>{card.org}</div>}
        </div>
      </div>
      <div style={{ marginTop: 12, fontSize: 17, fontWeight: 700, color: c.text, lineHeight: 1.25 }}>{card.topic}</div>
      <div style={{ marginTop: 6, fontSize: 15, lineHeight: 1.45, color: c.muted }}>{card.body}</div>
    </div>
  );
};

const Band: React.FC<{ p: EventRecapProps }> = ({ p }) => {
  const c = p.brand.colors;
  const enter = useEnter(64);
  const list = useEnter(72);
  const bp = p.bigPicture;
  return (
    <div style={{ position: "relative", margin: "22px -60px 0", padding: "24px 60px 24px", display: "flex", gap: 40, overflow: "hidden",
      background: `radial-gradient(70% 140% at 100% 0%, ${c.primary}AA 0%, rgba(0,0,0,0) 60%), linear-gradient(120deg, #07142F 0%, #0B1B3F 45%, #0D2A6B 100%)` }}>
      {/* faint grid, for depth */}
      <div style={{ position: "absolute", inset: 0, opacity: 0.12,
        backgroundImage: "linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px)",
        backgroundSize: "36px 36px", maskImage: "linear-gradient(90deg, transparent, #000 70%)" }} />
      <div style={{ ...enter, position: "relative", width: 500 }}>
        <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: "0.22em", textTransform: "uppercase", color: "#9DBBFF" }}>{bp.label}</div>
        <div style={{ marginTop: 12, fontSize: 23, lineHeight: 1.3, fontWeight: 700, color: "#fff", letterSpacing: "-0.01em" }}>
          <Emphasis text={bp.title} color="#8FB4FF" />
        </div>
      </div>
      <div style={{ ...list, position: "relative", flex: 1, paddingLeft: 26, borderLeft: "1px solid rgba(255,255,255,0.18)" }}>
        {bp.pointsLabel && <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: "0.22em", textTransform: "uppercase", color: "#9DBBFF", marginBottom: 10 }}>{bp.pointsLabel}</div>}
        {bp.points.map((pt, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, marginTop: i ? 7 : 0 }}>
            <div style={{ width: 30, height: 30, borderRadius: 30, flex: "none", border: "1px solid rgba(255,255,255,0.35)",
              display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(255,255,255,0.06)" }}>
              <Icon name={pt.icon} size={16} color="#fff" />
            </div>
            <div style={{ fontSize: 16, lineHeight: 1.3, color: "#E6EEFF", fontWeight: 500 }}>{pt.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const Footer: React.FC<{ p: EventRecapProps }> = ({ p }) => {
  const c = p.brand.colors;
  const enter = useEnter(78);
  return (
    <div style={{ ...enter, flex: 1, minHeight: 80, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ width: 560, fontSize: 17, lineHeight: 1.4, color: c.text, fontWeight: 500 }}>{p.closing}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <Wordmark p={p} color={c.primary} size={28} logoHeight={44} />
        <div style={{ height: 40, width: 1, background: `${c.muted}55` }} />
        <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: c.muted, lineHeight: 1.35, width: 170 }}>
          {p.brand.handle ?? ""}
        </div>
      </div>
    </div>
  );
};

export const EventRecap: React.FC<EventRecapProps> = (p) => {
  useBrandFont(p.brand);
  const c = p.brand.colors;
  const hero = useEnter(10);
  return (
    <AbsoluteFill style={{ fontFamily: `"${p.brand.fontFamily}", sans-serif`, background: c.background, color: c.text }}>
      <style>{p.brand.fontCss}</style>
      {/* soft light behind the hero, plus a fine dot texture for depth */}
      <AbsoluteFill style={{ background: `radial-gradient(42% 38% at 78% 26%, ${c.primary}38 0%, ${c.primary}10 45%, rgba(0,0,0,0) 70%), linear-gradient(180deg, #FFFFFF 0%, ${c.background} 46%)` }} />
      <AbsoluteFill style={{ opacity: 0.5, backgroundImage: `radial-gradient(${c.primary}22 1px, transparent 1.2px)`, backgroundSize: "22px 22px",
        maskImage: "radial-gradient(40% 40% at 80% 25%, #000, transparent 75%)" }} />
      <div style={{ ...hero, position: "absolute", left: 560, top: 10, width: 520, height: 540 }}>
        <LubricantHero width={520} height={540} accent={c.primary} />
      </div>
      <div id="page" style={{ position: "absolute", inset: 0, padding: "52px 60px 0", display: "flex", flexDirection: "column" }}>
        <Header p={p} />
        <Cards p={p} />
        <Band p={p} />
        <Footer p={p} />
      </div>
    </AbsoluteFill>
  );
};
