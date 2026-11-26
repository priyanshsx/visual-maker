// Talks to the Python API (visuals/web/app.py). Errors come back as { errors: [...] }.
export class ApiError extends Error {
  constructor(public errors: string[], public status: number) { super(errors.join("\n")); }
}

async function call<T>(method: string, url: string, body?: unknown, form?: FormData): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: form ? undefined : body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errors: string[] = Array.isArray(data.errors) ? data.errors
      : Array.isArray(data.detail) ? data.detail.map((d: { msg: string }) => d.msg) : [`Request failed (${res.status})`];
    throw new ApiError(errors, res.status);
  }
  return data as T;
}

export type Format = { templates: string[]; defaults: Record<string, unknown>; hint: string | null };
export type Bucket = { label: string; status: "ready" | "draft" | "samples_needed"; notes: string | null;
  status_note: string | null; model: string; formats: Partial<Record<"video" | "image", Format>>; brief: string; rules: string[] };
export type Client = { name: string; display_name: string; logo: string | null;
  colors: Record<string, string>; buckets: Record<string, Bucket> };
export type TemplateInfo = { kind: "video" | "image"; sizes: string[] };
export type FileInfo = { name: string; kind: string; bytes: number; url: string };
export type LibraryEntry = { file: string; modified: string; bucket: string | null; format: string | null;
  from_idea: boolean; notes: string[]; checks: string[]; entries: { name: string | null; template: string | null }[];
  yaml_error: string | null };
export type SpecFile = LibraryEntry & { header: string[]; items: Record<string, unknown>[]; yaml: string; sizes: string[][] };
export type Job = { id: number; client: string; file: string; item: number; name: string | null; sizes: string[] | null;
  status: "queued" | "running" | "done" | "failed"; urls: string[]; errors: string[]; created: string; finished: string | null };
export type Preview =
  | { kind: "remotion"; composition: string; props: Record<string, unknown>; durationInFrames: number; fps: number; width: number; height: number }
  | { kind: "html"; html: string; width: number; height: number };

const enc = encodeURIComponent;
export const api = {
  clients: () => call<Client[]>("GET", "/api/clients"),
  templates: () => call<Record<string, TemplateInfo>>("GET", "/api/templates"),
  files: (c: string) => call<FileInfo[]>("GET", `/api/files/${enc(c)}`),
  upload: (c: string, file: File) => { const f = new FormData(); f.append("file", file); return call<FileInfo>("POST", `/api/files/${enc(c)}`, undefined, f); },
  idea: (body: { client: string; bucket: string; idea: string; files: string[]; format?: string; template?: string; model?: string }) =>
    call<{ file: string; warnings: string[] }>("POST", "/api/ideas", body),
  library: (c: string) => call<LibraryEntry[]>("GET", `/api/specs/${enc(c)}`),
  spec: (c: string, file: string) => call<SpecFile>("GET", `/api/specs/${enc(c)}/${enc(file)}`),
  saveItem: (c: string, file: string, item: number, spec: unknown) => call<SpecFile>("PUT", `/api/specs/${enc(c)}/${enc(file)}/${item}`, { spec }),
  saveYaml: (c: string, file: string, text: string) => call<SpecFile>("PUT", `/api/specs/${enc(c)}/${enc(file)}`, { text }),
  preview: (client: string, spec: unknown, size: string) => call<Preview>("POST", "/api/preview", { client, spec, size }),
  render: (client: string, file: string, item: number, sizes: string[]) => call<Job>("POST", "/api/render", { client, file, item, sizes }),
  jobs: (c: string) => call<Job[]>("GET", `/api/jobs?client=${enc(c)}`),
};
