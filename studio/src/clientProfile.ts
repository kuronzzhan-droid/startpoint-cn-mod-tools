// 目标客户端（client profile）：页面顶部全局选择，按浏览器记住；能力查询走后端只读接口
// /api/studio/client-profiles、/api/studio/caps/*（缓存的 wf.caps 比较）与入库的全角色兼容报告。
import { useEffect, useRef, useState } from "preact/hooks";
import { drafts, get, post } from "./api";

export interface ClientProfileInfo {
  id: string;
  /** Short label for chips and badges, e.g. "v34". */
  label: string;
  default: boolean;
  description: string;
  packageName: string | null;
  versionCode: number | null;
  verification: string | null;
  capabilityCount: number;
  /** Capabilities this profile provides beyond the default profile (atomic patch entries included). */
  extraCount: number;
  /** The feature-level ones among them (no per-patch entries). */
  extra: { id: string; title: string }[];
  available: boolean;
  error: string | null;
}

export interface ClientProfiles {
  defaultClientProfile: string;
  profiles: ClientProfileInfo[];
  note: string;
}

export interface CapInfo {
  id: string;
  title: string;
  layer: string | null;
  /** Official client system (registry layer B): no client patch needed. */
  official: boolean;
  patches: number[];
}

export interface MissingCap {
  id: string | null;
  rule: string;
  message: string;
  title: string | null;
  patches: number[];
  missingPatches: number[];
}

export interface CapReference {
  type: "unique" | "string" | "skill" | "power_flip" | "program";
  id?: string;
  stringId?: string;
  name?: string;
  key?: string;
  path?: string;
  missing?: boolean;
  error?: string;
}

export interface CapRequirement {
  capabilities: CapInfo[];
  requiredClientProfiles: string[];
  /** degraded: a known p12/p13 capability is missing and the client falls back (not blocking);
   *  declared: support rests only on an external patch report, not on verified methods. */
  profiles: Record<string, { compatible: boolean; missing: MissingCap[]; pending: { id: string; message: string }[];
    degraded?: boolean; declared?: boolean; error?: string }>;
  recognized: boolean;
  unsupported: string[];
  placement: string[];
  references: CapReference[];
  note: string;
}

export interface CharacterCompatEntry {
  name: string;
  title: string;
  origin: string;
  profiles: Record<string, { status: string | null; satisfied: boolean; missing: { id: string; title: string; patches: number[] }[] }>;
}

export interface CharacterCompatReport {
  source: string;
  tip: string;
  scope: string;
  liveServerVerified: boolean;
  deviceVerified: boolean;
  scanComplete: boolean;
  profiles: string[];
  summary: Record<string, Record<string, number>>;
  characters: Record<string, CharacterCompatEntry>;
  note: string;
}

// ---------------------------------------------------------------------------
// Selected profile (per browser)

const STORAGE = "studio.clientProfile";
const listeners = new Set<() => void>();
let profilesPromise: Promise<ClientProfiles> | null = null;
let profilesValue: ClientProfiles | null = null;
let stored: string | null = readStored();

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE);
  } catch {
    return null;
  }
}

// Another 编辑台 tab of this browser switched the target: follow it.
window.addEventListener("storage", (event) => {
  if (event.key !== STORAGE) return;
  stored = event.newValue;
  listeners.forEach((listener) => listener());
});

export function loadProfiles(): Promise<ClientProfiles> {
  if (!profilesPromise) {
    profilesPromise = get<ClientProfiles>("/api/studio/client-profiles").then((value) => {
      profilesValue = value;
      listeners.forEach((listener) => listener());
      return value;
    });
    profilesPromise.catch(() => { profilesPromise = null; });
  }
  return profilesPromise;
}

/** Selected profile id; falls back to the backend default when nothing (valid) is stored. */
export function currentProfile(): string | null {
  if (!profilesValue) return stored;
  const usable = profilesValue.profiles.filter((p) => p.available).map((p) => p.id);
  return stored && usable.includes(stored) ? stored : profilesValue.defaultClientProfile;
}

export function setProfile(id: string) {
  stored = id;
  try {
    localStorage.setItem(STORAGE, id);
  } catch {
    /* storage unavailable: keep it for this page only */
  }
  listeners.forEach((listener) => listener());
}

export function profileLabel(profiles: ClientProfiles | null, id: string | null | undefined): string {
  if (!id) return "—";
  return profiles?.profiles.find((p) => p.id === id)?.label ?? id.replace(/^test-/, "");
}

export interface ClientProfileState {
  profiles: ClientProfiles | null;
  error: string | null;
  /** Selected profile id (null until the list has loaded and nothing is stored). */
  selected: string | null;
  info: ClientProfileInfo | null;
  label: (id: string | null | undefined) => string;
  set: (id: string) => void;
}

export function useClientProfile(): ClientProfileState {
  const [, bump] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const listener = () => bump((n) => n + 1);
    listeners.add(listener);
    loadProfiles().then(listener, (e: Error) => setError(e.message));
    return () => { listeners.delete(listener); };
  }, []);
  const selected = currentProfile();
  return {
    profiles: profilesValue, error, selected,
    info: profilesValue?.profiles.find((p) => p.id === selected) ?? null,
    label: (id) => profileLabel(profilesValue, id),
    set: setProfile,
  };
}

// ---------------------------------------------------------------------------
// Capability lookups (cached per page; the backend caches the comparisons too)

const lookups = new Map<string, Promise<CapRequirement>>();

function cachedGet<T>(url: string, cache: Map<string, Promise<any>>): Promise<T> {
  if (!cache.has(url)) {
    const promise = get<T>(url);
    promise.catch(() => cache.delete(url));
    cache.set(url, promise);
  }
  return cache.get(url) as Promise<T>;
}

export type LookupParams = Partial<Record<"kind" | "unique" | "uniqueId" | "dsl" | "selector" | "customKey" | "capability", string | string[]>>;

export function lookupCaps(params: LookupParams): Promise<CapRequirement> {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    for (const item of Array.isArray(value) ? value : value === undefined ? [] : [value]) search.append(name, item);
  }
  return cachedGet<CapRequirement>(`/api/studio/caps/lookup?${search}`, lookups);
}

export function programCaps(path: string): Promise<CapRequirement> {
  return cachedGet<CapRequirement>(`/api/studio/caps/program?path=${encodeURIComponent(path)}`, lookups);
}

export function kindCaps(table: string, block: string): Promise<{ kinds: Record<string, CapRequirement> }> {
  return cachedGet(`/api/studio/caps/kinds?table=${table}&block=${block}`, lookups);
}

let compatPromise: Promise<CharacterCompatReport> | null = null;
export function characterCompat(): Promise<CharacterCompatReport> {
  if (!compatPromise) {
    compatPromise = get<CharacterCompatReport>("/api/studio/character-compat");
    compatPromise.catch(() => { compatPromise = null; });
  }
  return compatPromise;
}

export interface RowQuery {
  id: string;
  table: "ability" | "leader_ability" | "action_skill";
  key: string;
  level?: string | null;
  cells: string[];
}

const rowResults = new Map<string, CapRequirement>();
const rowKey = (r: RowQuery) => `${r.table}\u0000${r.key}\u0000${r.level ?? ""}\u0000${JSON.stringify(r.cells)}`;

// Rows asked for within one short window (every key editor on a page mounts together) go out as one request.
// The endpoint lives under the character's draft path (POST bodies stay under /api/drafts/); it never writes.
const inflight = new Map<string, Promise<void>>();
const waiting = new Map<string, Map<string, RowQuery>>();
const flushing = new Map<string, Promise<void>>();

async function sendRows(cid: string, entries: [string, RowQuery][]): Promise<void> {
  for (let i = 0; i < entries.length; i += 150) {
    const chunk = entries.slice(i, i + 150);
    const body = { rows: chunk.map(([, r], index) => ({ ...r, id: String(index) })) };
    const result = await post<{ rows: Record<string, CapRequirement> }>(`/api/drafts/${encodeURIComponent(cid)}/caps/rows`, body);
    chunk.forEach(([key], index) => { const value = result.rows[String(index)]; if (value) rowResults.set(key, value); });
  }
}

function enqueueRow(cid: string, r: RowQuery): Promise<void> {
  const key = rowKey(r);
  if (rowResults.has(key)) return Promise.resolve();
  const running = inflight.get(key);
  if (running) return running;
  if (!waiting.has(cid)) waiting.set(cid, new Map());
  waiting.get(cid)!.set(key, r);
  if (!flushing.has(cid)) {
    flushing.set(cid, new Promise<void>((resolve, reject) => setTimeout(() => {
      const batch = [...(waiting.get(cid) ?? new Map()).entries()];
      waiting.delete(cid);
      flushing.delete(cid);
      sendRows(cid, batch).then(resolve, reject);
    }, 40)));
  }
  const done = flushing.get(cid)!.finally(() => inflight.delete(key));
  inflight.set(key, done);
  return done;
}

/** Requirements of whole data rows (kinds, referenced unique strings, config strings, DSL), batched and cached. */
export async function rowCaps(cid: string, rows: RowQuery[]): Promise<Record<string, CapRequirement>> {
  await Promise.all(rows.map((r) => enqueueRow(cid, r)));
  const out: Record<string, CapRequirement> = {};
  for (const r of rows) {
    const value = rowResults.get(rowKey(r));
    if (value) out[r.id] = value;
  }
  return out;
}

/** Debounced row requirements for the rows on screen (empty when the page has no write token). */
export function useRowCaps(cid: string, rows: RowQuery[]): { results: Record<string, CapRequirement>; error: string | null } {
  const [results, setResults] = useState<Record<string, CapRequirement>>({});
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const signature = cid + JSON.stringify(rows.map((r) => [r.id, rowKey(r)]));
  useEffect(() => {
    if (!rows.length || !drafts.hasToken()) { setResults({}); return; }
    const id = ++sequence.current;
    const timer = setTimeout(() => {
      rowCaps(cid, rows).then((value) => { if (id === sequence.current) { setResults(value); setError(null); } },
        (e: Error) => { if (id === sequence.current) setError(e.message); });
    }, 250);
    return () => clearTimeout(timer);
  }, [signature]);
  return { results, error };
}

/** One cached lookup as state: `key` identifies the request (null = nothing to ask). */
export function useCaps<T = CapRequirement>(key: string | null, load: () => Promise<T>): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    setValue(null);
    if (key === null) return;
    let alive = true;
    load().then((v) => { if (alive) setValue(v); }, () => undefined);
    return () => { alive = false; };
  }, [key]);
  return value;
}

// ---------------------------------------------------------------------------
// Verdict for chips: 「v34 即可」 / 「需要 v35e」 / problems

export type Verdict =
  | { kind: "none" }
  | { kind: "ok"; label: string; profile: string }
  | { kind: "needs"; label: string; profile: string; satisfied: boolean }
  | { kind: "pending"; label: string; profile: string; reason: string }
  | { kind: "bad"; label: string; reason: string };

export function verdict(req: CapRequirement | null | undefined, state: Pick<ClientProfileState, "profiles" | "selected" | "label">): Verdict {
  if (!req || !state.profiles) return { kind: "none" };
  if (req.placement.length) return { kind: "bad", label: "能力推导报错", reason: req.placement.join("；") };
  if (req.unsupported.length) return { kind: "bad", label: "标记未登记或写错", reason: req.unsupported.join("；") };
  const relevant = req.capabilities.filter((c) => !c.official);
  if (!relevant.length) return { kind: "none" };
  const order = state.profiles.profiles.map((p) => p.id);
  const required = order.filter((id) => req.requiredClientProfiles.includes(id));
  if (!required.length) {
    // p12/p13 keys: a profile can be 「报告声明，待验证」 or 「降级」 without being incompatible outright.
    const pick = (flag: "declared" | "degraded") => order.find((id) => req.profiles[id]?.[flag] && !req.profiles[id]?.missing.length);
    const declared = pick("declared");
    if (declared) return { kind: "pending", label: `${state.label(declared)}（报告声明，待验证）`, profile: declared,
      reason: req.profiles[declared].pending.map((p) => p.message).join("；") };
    const degraded = pick("degraded");
    if (degraded) return { kind: "pending", label: `${state.label(degraded)} 会降级`, profile: degraded,
      reason: req.profiles[degraded].pending.map((p) => p.message).join("；") };
    return { kind: "bad", label: "所有档案都不满足", reason: "已登记的客户端档案都没有这些能力" };
  }
  const fallback = state.profiles.defaultClientProfile;
  if (required.includes(fallback)) return { kind: "ok", label: `${state.label(fallback)} 即可`, profile: fallback };
  return { kind: "needs", label: `需要 ${state.label(required[0])}`, profile: required[0],
    satisfied: !!state.selected && required.includes(state.selected) };
}

/** Plain-text explanation for a chip tooltip / warning list. */
export function describeRequirement(req: CapRequirement, state: Pick<ClientProfileState, "selected" | "label">): string {
  const lines: string[] = [];
  for (const c of req.capabilities.filter((c) => !c.official)) {
    lines.push(`· ${c.title}（${c.id}）${c.patches.length ? " 补丁 " + c.patches.map((n) => "#" + n).join(" ") : ""}`);
  }
  for (const r of req.references) {
    if (r.type === "unique" && r.stringId) lines.push(`· 固有状态 ${r.id}「${r.name ?? ""}」= ${r.stringId}`);
    else if (r.type === "unique" && r.missing) lines.push(`· 固有状态 ${r.id} 在当前视图里不存在`);
    else if (r.type === "string" && r.key && !r.key.startsWith("desc_override_")) lines.push(`· 配置文本 ${r.key}`);
  }
  const selected = state.selected ? req.profiles[state.selected] : null;
  if (selected && !selected.compatible && selected.missing.length) {
    lines.push(`目标客户端 ${state.label(state.selected)} 缺：` + selected.missing.map((m) => m.title ?? m.id ?? m.message).join("、"));
  }
  if (selected?.degraded) lines.push(`目标客户端 ${state.label(state.selected)} 会降级：` + selected.pending.map((p) => p.message).join("；"));
  else if (selected?.declared) lines.push(`目标客户端 ${state.label(state.selected)} 只有补丁报告声明支持，待验证`);
  if (req.placement.length) lines.push(...req.placement.map((p) => "· " + p));
  if (req.unsupported.length) lines.push(...req.unsupported.map((p) => "· " + p));
  return lines.join("\n");
}
