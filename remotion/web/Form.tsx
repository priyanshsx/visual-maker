// Field editor: turns any spec (the YAML entry) into simple form fields.
//   text -> input / textarea, numbers -> number input, yes/no -> checkbox,
//   sizes -> toggles, focus -> two numbers + click-on-the-image picker,
//   lists of items (steps, scenes, cards...) -> cards you can reorder, duplicate or remove.
// Fields not in the entry yet can be added in the YAML tab.
import { useState } from "react";

type Json = string | number | boolean | null | Json[] | { [k: string]: Json };
type Ctx = { client: string; files: { name: string; kind: string; url: string }[]; sizes: string[]; rootImage?: string };

const LONG_TEXT = new Set(["body", "intro", "subtitle", "quote", "note", "text", "caption", "closing", "title"]);
const FILE_FIELDS: Record<string, string> = { image: "image", footage: "video", music: "audio" };
const LOCKED = new Set(["template", "kind"]);
const STEP: Record<string, number> = { zoom: 0.1, seconds: 0.5, at: 0.5, start: 0.5, end: 0.5, duration: 0.5 };

export function label(key: string) {
  return key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

// Click on the picture to set where the camera looks
function FocusPicker({ url, value, onChange }: { url: string; value: [number, number]; onChange: (v: [number, number]) => void }) {
  const [open, setOpen] = useState(false);
  const [x, y] = value;
  return (
    <div className="focus">
      <div className="row">
        <label className="mini">across <input type="number" step={0.01} min={0} max={1} value={x}
          onChange={(e) => onChange([clamp(+e.target.value), y])} /></label>
        <label className="mini">down <input type="number" step={0.01} min={0} max={1} value={y}
          onChange={(e) => onChange([x, clamp(+e.target.value)])} /></label>
        <button type="button" className="link" onClick={() => setOpen(!open)}>{open ? "Hide picture" : "Pick on picture"}</button>
      </div>
      {open && (
        <div className="picker" onClick={(e) => {
          const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
          onChange([round2((e.clientX - r.left) / r.width), round2((e.clientY - r.top) / r.height)]);
        }}>
          <img src={url} alt="" draggable={false} />
          <span className="dot" style={{ left: `${x * 100}%`, top: `${y * 100}%` }} />
        </div>
      )}
    </div>
  );
}

const clamp = (v: number) => Math.min(Math.max(isNaN(v) ? 0.5 : v, 0), 1);
const round2 = (v: number) => Math.round(clamp(v) * 100) / 100;

function Field({ name, value, onChange, ctx, parent }: {
  name: string; value: Json; onChange: (v: Json) => void; ctx: Ctx; parent?: Record<string, Json>;
}) {
  if (LOCKED.has(name)) return <div className="field"><span className="key">{label(name)}</span><code>{String(value)}</code></div>;

  if (name === "sizes" && Array.isArray(value)) {
    const chosen = value as string[];
    return (
      <div className="field"><span className="key">Sizes</span>
        <div className="chips">{ctx.sizes.map((s) => (
          <button type="button" key={s} className={chosen.includes(s) ? "chip on" : "chip"}
            onClick={() => onChange(chosen.includes(s) ? chosen.filter((c) => c !== s) : [...chosen, s])}>{s}</button>
        ))}</div>
      </div>
    );
  }

  if (name === "focus" && Array.isArray(value) && value.length === 2) {
    const img = (parent?.image as string) || ctx.rootImage;
    const url = img ? `/files/${encodeURIComponent(ctx.client)}/${encodeURIComponent(img.split("/").pop()!)}` : null;
    return (
      <div className="field"><span className="key">Focus</span>
        {url ? <FocusPicker url={url} value={value as [number, number]} onChange={onChange} />
          : <span className="hint">Add an image first</span>}
      </div>
    );
  }

  if (name in FILE_FIELDS && (typeof value === "string" || value === null)) {
    const kind = FILE_FIELDS[name];
    const options = ctx.files.filter((f) => f.kind === kind).map((f) => f.name);
    const current = (value ?? "") as string;
    return (
      <div className="field"><span className="key">{label(name)}</span>
        <select value={current} onChange={(e) => onChange(e.target.value || null)}>
          {name !== "image" || !parent?.template ? <option value="">(none)</option> : null}
          {!options.includes(current) && current && <option value={current}>{current}</option>}
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    );
  }

  if (typeof value === "string") {
    const long = LONG_TEXT.has(name) || value.length > 60;
    return (
      <label className="field"><span className="key">{label(name)} <small>{value.length}</small></span>
        {long ? <textarea rows={Math.min(5, Math.ceil(value.length / 55) + 1)} value={value} onChange={(e) => onChange(e.target.value)} />
          : <input value={value} onChange={(e) => onChange(e.target.value)} />}
      </label>
    );
  }
  if (typeof value === "number") {
    return (
      <label className="field"><span className="key">{label(name)}</span>
        <input type="number" step={STEP[name] ?? "any"} value={value} onChange={(e) => onChange(e.target.value === "" ? 0 : +e.target.value)} />
      </label>
    );
  }
  if (typeof value === "boolean") {
    return <label className="field check"><input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} /> {label(name)}</label>;
  }
  if (Array.isArray(value)) {
    const items = value as Json[];
    const objects = items.every((i) => i && typeof i === "object" && !Array.isArray(i));
    const move = (i: number, d: number) => { const a = [...items]; const [x] = a.splice(i, 1); a.splice(i + d, 0, x); onChange(a); };
    return (
      <div className="field list"><span className="key">{label(name)} <small>{items.length}</small></span>
        {items.map((item, i) => (
          <div key={i} className={objects ? "card" : "row"}>
            {objects && <div className="card-head">
              <b>{i + 1}</b>{(item as Record<string, Json>).kind ? <span className="badge">{String((item as Record<string, Json>).kind)}</span> : null}
              <span className="grow" />
              <button type="button" disabled={i === 0} onClick={() => move(i, -1)} title="Move up">↑</button>
              <button type="button" disabled={i === items.length - 1} onClick={() => move(i, 1)} title="Move down">↓</button>
              <button type="button" onClick={() => onChange([...items.slice(0, i + 1), structuredClone(item), ...items.slice(i + 1)])} title="Duplicate">⧉</button>
              <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} title="Remove">✕</button>
            </div>}
            {objects
              ? <Fields value={item as Record<string, Json>} onChange={(v) => onChange(items.map((x, j) => (j === i ? v : x)))} ctx={ctx} />
              : <>
                  <input value={String(item ?? "")} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
                  <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} title="Remove">✕</button>
                </>}
          </div>
        ))}
        {!objects && <button type="button" className="link" onClick={() => onChange([...items, ""])}>+ Add</button>}
      </div>
    );
  }
  if (value && typeof value === "object") {
    return (
      <fieldset className="field group"><legend>{label(name)}</legend>
        <Fields value={value as Record<string, Json>} onChange={onChange} ctx={ctx} />
      </fieldset>
    );
  }
  return <div className="field"><span className="key">{label(name)}</span><span className="hint">empty (set it in YAML)</span></div>;
}

export function Fields({ value, onChange, ctx }: { value: Record<string, Json>; onChange: (v: Record<string, Json>) => void; ctx: Ctx }) {
  return (
    <div className="fields">
      {Object.entries(value).map(([k, v]) => (
        <Field key={k} name={k} value={v} parent={value} ctx={ctx} onChange={(nv) => onChange({ ...value, [k]: nv })} />
      ))}
    </div>
  );
}

export type { Json, Ctx };
