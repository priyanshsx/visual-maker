// Visual maker web app: the page. Served by `python -m visuals web`.
//   New      -> pick client + bucket, toggle image / video, write the idea, attach files -> draft
//   Library  -> every spec file for the client (made in the app or on the command line)
//   Edit     -> fields or YAML on the left, live preview on the right, render + downloads
//   Renders  -> the render queue and finished files
import { Player } from "@remotion/player";
import { StrictMode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { DeviceDemo } from "../src/DeviceDemo";
import { EventRecap } from "../src/EventRecap";
import { Explainer } from "../src/Explainer";
import { TalkingHead } from "../src/TalkingHead";
import { api, ApiError, type Client, type FileInfo, type Job, type LibraryEntry, type Preview, type SpecFile, type TemplateInfo } from "./api";
import { Fields, type Json } from "./Form";
import "./styles.css";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const COMPOSITIONS: Record<string, React.ComponentType<any>> = { DeviceDemo, EventRecap, Explainer, TalkingHead };

// ---- tiny router: #/<client>/<view>[/<file>] ----
type Route = { client: string | null; view: "new" | "library" | "edit" | "renders"; file?: string };
function readRoute(): Route {
  const [client, view, ...rest] = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split("/");
  const v = (["new", "library", "edit", "renders"].includes(view) ? view : "new") as Route["view"];
  return { client: client || null, view: v, file: rest.join("/") || undefined };
}
function go(r: Route) { location.hash = `#/${r.client ?? ""}/${r.view}${r.file ? "/" + encodeURIComponent(r.file) : ""}`; }

function errorsOf(e: unknown): string[] {
  return e instanceof ApiError ? e.errors : [String((e as Error)?.message ?? e)];
}

function Errors({ list }: { list: string[] }) {
  if (!list.length) return null;
  return <div className="errors">{list.map((e, i) => <div key={i}>{e}</div>)}</div>;
}

function StatusBadge({ status }: { status: string }) {
  const text: Record<string, string> = { ready: "ready", draft: "draft template", samples_needed: "samples for team review",
    queued: "queued", running: "rendering…", done: "done", failed: "failed" };
  return <span className={`status ${status}`}>{text[status] ?? status}</span>;
}

// ---------------------------------------------------------------- App
function App() {
  const [route, setRoute] = useState<Route>(readRoute());
  const [clients, setClients] = useState<Client[]>([]);
  const [templates, setTemplates] = useState<Record<string, TemplateInfo>>({});
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    const on = () => setRoute(readRoute());
    window.addEventListener("hashchange", on);
    Promise.all([api.clients(), api.templates()]).then(([c, t]) => { setClients(c); setTemplates(t); }).catch((e) => setErrors(errorsOf(e)));
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const client = clients.find((c) => c.name === route.client) ?? clients[0];
  useEffect(() => { if (client && route.client !== client.name) go({ ...route, client: client.name }); }, [client, route]);

  if (!client) return <div className="loading">{errors.length ? <Errors list={errors} /> : "Loading…"}</div>;
  const nav = (view: Route["view"]) => go({ client: client.name, view });
  return (
    <div className="app" style={{ ["--brand" as string]: client.colors.primary }}>
      <aside>
        <div className="logo">Visual maker</div>
        <div className="clients">
          {clients.map((c) => (
            <button key={c.name} className={c.name === client.name ? "client on" : "client"}
              onClick={() => go({ client: c.name, view: route.view === "edit" ? "library" : route.view })}>
              <span className="swatch" style={{ background: c.colors.primary }} />{c.display_name}
            </button>
          ))}
        </div>
        <nav>
          <button className={route.view === "new" ? "on" : ""} onClick={() => nav("new")}>＋ New</button>
          <button className={route.view === "library" || route.view === "edit" ? "on" : ""} onClick={() => nav("library")}>Library</button>
          <button className={route.view === "renders" ? "on" : ""} onClick={() => nav("renders")}>Renders</button>
        </nav>
      </aside>
      <main>
        {route.view === "new" && <NewView client={client} templates={templates} />}
        {route.view === "library" && <LibraryView client={client} />}
        {route.view === "edit" && route.file && <EditView key={client.name + route.file} client={client} file={route.file} templates={templates} />}
        {route.view === "renders" && <RendersView client={client} />}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------- files picker
function FilePicker({ client, chosen, setChosen }: { client: string; chosen: string[]; setChosen: (f: string[]) => void }) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const load = useCallback(() => api.files(client).then(setFiles).catch((e) => setErrors(errorsOf(e))), [client]);
  useEffect(() => { load(); }, [load]);
  const upload = async (list: FileList | null) => {
    if (!list?.length) return;
    setBusy(true); setErrors([]);
    try {
      const added: string[] = [];
      for (const f of Array.from(list)) added.push((await api.upload(client, f)).name);
      await load();
      setChosen([...chosen, ...added]);
    } catch (e) { setErrors(errorsOf(e)); } finally { setBusy(false); }
  };
  const toggle = (n: string) => setChosen(chosen.includes(n) ? chosen.filter((c) => c !== n) : [...chosen, n]);
  return (
    <div className="files">
      <label className="upload">{busy ? "Uploading…" : "＋ Upload screenshots, charts, CSVs, notes, footage"}
        <input type="file" multiple onChange={(e) => upload(e.target.files)} hidden />
      </label>
      <Errors list={errors} />
      <div className="file-grid">
        {files.map((f) => (
          <button type="button" key={f.name} className={chosen.includes(f.name) ? "file on" : "file"} onClick={() => toggle(f.name)} title={f.name}>
            {f.kind === "image" ? <img src={f.url} alt="" /> : <span className="ext">{f.kind}</span>}
            <span className="fname">{f.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- New
function NewView({ client, templates }: { client: Client; templates: Record<string, TemplateInfo> }) {
  const buckets = Object.entries(client.buckets);
  const [bucketName, setBucketName] = useState<string | null>(null);
  const bucket = bucketName ? client.buckets[bucketName] : null;
  const formats = bucket ? (Object.keys(bucket.formats) as ("video" | "image")[]) : [];
  const [format, setFormat] = useState<"video" | "image">("video");
  const fmt = bucket?.formats[formats.includes(format) ? format : formats[0]];
  const [template, setTemplate] = useState<string>("");
  const [idea, setIdea] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => { setBucketName(null); setFiles([]); }, [client.name]);
  useEffect(() => { if (bucket && !formats.includes(format)) setFormat(formats[0]); setTemplate(""); }, [bucketName]); // eslint-disable-line

  const submit = async () => {
    if (!bucketName || !idea.trim()) return;
    setBusy(true); setErrors([]);
    try {
      const chosenFormat = formats.includes(format) ? format : formats[0];
      const r = await api.idea({ client: client.name, bucket: bucketName, idea, files, format: chosenFormat,
        template: template || undefined, model: model || undefined });
      go({ client: client.name, view: "edit", file: r.file });
    } catch (e) { setErrors(errorsOf(e)); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <h1>New for {client.display_name}</h1>
      {!buckets.length && <p className="hint">This client has no buckets yet (brands/{client.name}/buckets.yaml).</p>}
      <div className="buckets">
        {buckets.map(([name, b]) => (
          <button key={name} className={name === bucketName ? "bucket on" : "bucket"} onClick={() => setBucketName(name)}>
            <div className="bucket-title">{b.label}</div>
            <div className="bucket-meta">{Object.keys(b.formats).join(" · ")} <StatusBadge status={b.status} /></div>
          </button>
        ))}
      </div>

      {bucket && fmt && (
        <div className="form">
          {bucket.status_note && <div className="note">{bucket.status_note}</div>}
          <div className="row">
            <div className="toggle">
              {(["image", "video"] as const).map((f) => (
                <button key={f} disabled={!formats.includes(f)} className={(formats.includes(format) ? format : formats[0]) === f ? "on" : ""}
                  onClick={() => setFormat(f)}>{f === "image" ? "Image" : "Video"}</button>
              ))}
            </div>
            {fmt.templates.length > 1 && (
              <select value={template} onChange={(e) => setTemplate(e.target.value)}>
                {fmt.templates.map((t, i) => <option key={t} value={i === 0 ? "" : t}>{t}{i === 0 ? " (default)" : ""}</option>)}
              </select>
            )}
            <select value={model} onChange={(e) => setModel(e.target.value)} title="Which LLM writes the draft">
              <option value="">Model: bucket default ({bucket.model})</option>
              <option value="fast">Model: fast</option>
              <option value="smart">Model: smart</option>
            </select>
            <span className="hint">{(template || fmt.templates[0])} · {templates[template || fmt.templates[0]]?.sizes.join(", ")}</span>
          </div>
          <label className="field"><span className="key">The idea</span>
            <textarea rows={6} value={idea} onChange={(e) => setIdea(e.target.value)}
              placeholder="What is this post about? Paste the post text, the feature, the numbers and where they come from." />
          </label>
          <div className="field"><span className="key">Files to use <small>{files.length} chosen</small></span>
            <FilePicker client={client.name} chosen={files} setChosen={setFiles} />
          </div>
          <Errors list={errors} />
          <button className="primary" disabled={busy || !idea.trim()} onClick={submit}>{busy ? "Writing the draft… (10–40 s)" : "Write draft"}</button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Library
function LibraryView({ client }: { client: Client }) {
  const [list, setList] = useState<LibraryEntry[] | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  useEffect(() => { setList(null); api.library(client.name).then(setList).catch((e) => setErrors(errorsOf(e))); }, [client.name]);
  return (
    <div className="page">
      <h1>Library <button className="primary small" onClick={() => go({ client: client.name, view: "new" })}>＋ New</button></h1>
      <Errors list={errors} />
      {!list ? <p className="hint">Loading…</p> : !list.length ? <p className="hint">Nothing yet.</p> : (
        <table className="table">
          <thead><tr><th>File</th><th>Makes</th><th>Bucket</th><th>Changed</th><th /></tr></thead>
          <tbody>{list.map((f) => (
            <tr key={f.file} onClick={() => go({ client: client.name, view: "edit", file: f.file })}>
              <td><b>{f.file.replace(/\.ya?ml$/, "")}</b>{f.yaml_error && <span className="status failed">YAML error</span>}</td>
              <td>{f.entries.map((e, i) => <span key={i} className="badge">{e.template}</span>)}</td>
              <td>{f.bucket ?? <span className="hint">by hand</span>}{f.format && <span className="hint"> · {f.format}</span>}</td>
              <td className="hint">{f.modified.replace("T", " ").slice(0, 16)}</td>
              <td>{f.checks.length > 0 && <span className="status failed" title={f.checks.join("\n")}>{f.checks.length} to check</span>}
                {f.notes.length > 0 && <span className="status draft" title={f.notes.join("\n")}>note</span>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Preview
function PreviewPane({ preview }: { preview: Preview }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(480);
  const [height, setHeight] = useState(preview.height);
  useEffect(() => {
    const el = box.current; if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth)); ro.observe(el);
    return () => ro.disconnect();
  }, []);
  if (preview.kind === "remotion") {
    const Comp = COMPOSITIONS[preview.composition];
    return (
      <div ref={box} className="player">
        <Player component={Comp} inputProps={preview.props} durationInFrames={preview.durationInFrames} fps={preview.fps}
          compositionWidth={preview.width} compositionHeight={preview.height} controls loop clickToPlay
          acknowledgeRemotionLicense style={{ width: "100%", aspectRatio: `${preview.width} / ${preview.height}` }} />
      </div>
    );
  }
  const scale = width / preview.width;
  return (
    <div ref={box} className="html-preview" style={{ height: height * scale }}>
      <iframe title="preview" srcDoc={preview.html} style={{ width: preview.width, height, transform: `scale(${scale})` }}
        onLoad={(e) => { const doc = (e.target as HTMLIFrameElement).contentDocument; if (doc) setHeight(Math.max(preview.height, doc.documentElement.scrollHeight)); }} />
    </div>
  );
}

// ---------------------------------------------------------------- Edit
function EditView({ client, file, templates }: { client: Client; file: string; templates: Record<string, TemplateInfo> }) {
  const [spec, setSpec] = useState<SpecFile | null>(null);
  const [item, setItem] = useState(0);
  const [draft, setDraft] = useState<Record<string, Json> | null>(null);
  const [yamlText, setYamlText] = useState("");
  const [tab, setTab] = useState<"fields" | "yaml">("fields");
  const [dirty, setDirty] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [size, setSize] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErrors, setPreviewErrors] = useState<string[]>([]);
  const [previewing, setPreviewing] = useState(false);
  const [renderSizes, setRenderSizes] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);

  const load = useCallback(async () => {
    const s = await api.spec(client.name, file);
    setSpec(s); setYamlText(s.yaml); setDirty(false);
    return s;
  }, [client.name, file]);

  useEffect(() => {
    load().catch((e) => setErrors(errorsOf(e)));
    api.files(client.name).then(setFiles).catch(() => {});
  }, [load, client.name]);

  const entry = spec?.items[item] as Record<string, Json> | undefined;
  useEffect(() => {
    if (!entry) return;
    setDraft(structuredClone(entry));
    const sizes = (entry.sizes as string[] | undefined) ?? spec?.sizes[item] ?? [];
    setSize((s) => s || sizes[0] || templates[String(entry.template)]?.sizes[0] || "portrait");
    setRenderSizes(sizes);
  }, [spec, item]); // eslint-disable-line

  const template = String(draft?.template ?? "");
  const allowed = templates[template]?.sizes ?? [];

  const runPreview = useCallback(async (data: Record<string, Json>, sz: string) => {
    setPreviewing(true); setPreviewErrors([]);
    try { setPreview(await api.preview(client.name, data, sz)); }
    catch (e) { setPreview(null); setPreviewErrors(errorsOf(e)); }
    finally { setPreviewing(false); }
  }, [client.name]);
  useEffect(() => { if (entry && size) runPreview(entry, size); }, [spec, item, size]); // eslint-disable-line

  // jobs for this file; poll while something is rendering
  const loadJobs = useCallback(() => api.jobs(client.name).then((all) => setJobs(all.filter((j) => j.file === file && j.item === item))), [client.name, file, item]);
  useEffect(() => { loadJobs(); }, [loadJobs]);
  useEffect(() => {
    if (!jobs.some((j) => j.status === "queued" || j.status === "running")) return;
    const t = setInterval(loadJobs, 3000); return () => clearInterval(t);
  }, [jobs, loadJobs]);

  const save = async () => {
    setSaving(true); setErrors([]);
    try {
      const s = tab === "yaml" ? await api.saveYaml(client.name, file, yamlText) : await api.saveItem(client.name, file, item, draft);
      setSpec(s); setYamlText(s.yaml); setDirty(false);
    } catch (e) { setErrors(errorsOf(e)); } finally { setSaving(false); }
  };

  const render = async () => {
    setErrors([]);
    if (dirty) { setErrors(["Save your changes first, then render."]); return; }
    try { const j = await api.render(client.name, file, item, renderSizes); setJobs([j, ...jobs]); }
    catch (e) { setErrors(errorsOf(e)); }
  };

  if (!spec) return <div className="page"><Errors list={errors} />{!errors.length && <p className="hint">Loading…</p>}</div>;
  return (
    <div className="edit">
      <section className="left">
        <div className="head">
          <button className="link" onClick={() => go({ client: client.name, view: "library" })}>← Library</button>
          <h1>{file.replace(/\.ya?ml$/, "")}</h1>
          <div className="hint">{spec.bucket ? `${client.buckets[spec.bucket]?.label ?? spec.bucket} · ${spec.format}` : "made by hand"} · {template}</div>
        </div>
        {spec.notes.map((n, i) => <div key={i} className="note">{n}</div>)}
        {spec.checks.length > 0 && <div className="checks"><b>Check before using:</b>{spec.checks.map((c, i) => <div key={i}>• {c}</div>)}</div>}
        {spec.items.length > 1 && (
          <div className="tabs">{spec.items.map((it, i) => (
            <button key={i} className={i === item ? "on" : ""} onClick={() => { if (!dirty || confirm("Discard unsaved changes?")) setItem(i); }}>
              {String((it as Record<string, Json>).name ?? `Entry ${i + 1}`)}</button>))}</div>
        )}
        <div className="tabs small">
          <button className={tab === "fields" ? "on" : ""} onClick={() => setTab("fields")}>Fields</button>
          <button className={tab === "yaml" ? "on" : ""} onClick={() => setTab("yaml")}>YAML (whole file)</button>
        </div>
        <div className="editor">
          {tab === "fields" && draft
            ? <Fields value={draft} ctx={{ client: client.name, files, sizes: allowed, rootImage: draft.image as string | undefined }}
                onChange={(v) => { setDraft(v); setDirty(true); }} />
            : <textarea className="yaml" spellCheck={false} value={yamlText} onChange={(e) => { setYamlText(e.target.value); setDirty(true); }} />}
        </div>
        <Errors list={errors} />
        <div className="bar">
          <button className="primary" disabled={!dirty || saving} onClick={save}>{saving ? "Saving…" : dirty ? "Save" : "Saved"}</button>
          {tab === "fields" && draft && <button onClick={() => runPreview(draft, size)} disabled={previewing}>Preview changes</button>}
          {dirty && <span className="hint">Unsaved changes</span>}
        </div>
      </section>

      <section className="right">
        <div className="row">
          <select value={size} onChange={(e) => setSize(e.target.value)}>{allowed.map((s) => <option key={s}>{s}</option>)}</select>
          {previewing && <span className="hint">Updating preview…</span>}
        </div>
        <Errors list={previewErrors} />
        {preview && <PreviewPane key={JSON.stringify([preview.width, preview.height, preview.kind])} preview={preview} />}

        <div className="render">
          <h2>Render</h2>
          <div className="row">
            <div className="chips">{allowed.map((s) => (
              <button key={s} className={renderSizes.includes(s) ? "chip on" : "chip"}
                onClick={() => setRenderSizes(renderSizes.includes(s) ? renderSizes.filter((x) => x !== s) : [...renderSizes, s])}>{s}</button>))}
            </div>
            <button className="primary" disabled={!renderSizes.length} onClick={render}>Render {templates[template]?.kind ?? ""}</button>
          </div>
          <p className="hint">Rendering runs on your Mac in the background. 3D videos take a few minutes per size.</p>
          {jobs.map((j) => <JobCard key={j.id} job={j} />)}
        </div>
      </section>
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <div className="job">
      <div className="row"><b>#{job.id}</b> <StatusBadge status={job.status} />
        <span className="hint">{(job.sizes ?? []).join(", ")} · {job.created.replace("T", " ").slice(0, 16)}</span></div>
      {job.errors.length > 0 && <Errors list={job.errors.slice(0, 1)} />}
      <div className="outputs">{job.urls.map((u) => (
        <div key={u} className="output">
          {/\.mp4$/.test(u) ? <video src={u} controls muted /> : /\.(png|jpe?g)$/.test(u) ? <img src={u} alt="" /> : null}
          <a href={u} download>{u.split("/").pop()}</a>
        </div>
      ))}</div>
    </div>
  );
}

// ---------------------------------------------------------------- Renders
function RendersView({ client }: { client: Client }) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const load = useCallback(() => api.jobs(client.name).then(setJobs), [client.name]);
  useEffect(() => { setJobs(null); load(); }, [load]);
  const active = useMemo(() => (jobs ?? []).some((j) => j.status === "queued" || j.status === "running"), [jobs]);
  useEffect(() => { if (!active) return; const t = setInterval(load, 3000); return () => clearInterval(t); }, [active, load]);
  return (
    <div className="page">
      <h1>Renders</h1>
      {!jobs ? <p className="hint">Loading…</p> : !jobs.length ? <p className="hint">No renders yet.</p> : jobs.map((j) => (
        <div key={j.id}>
          <button className="link" onClick={() => go({ client: client.name, view: "edit", file: j.file })}>{j.name ?? j.file}</button>
          <JobCard job={j} />
        </div>
      ))}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
