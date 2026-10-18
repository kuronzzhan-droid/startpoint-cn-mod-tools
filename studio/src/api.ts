// Typed wrappers over the read-only backend (python -m wf.studio).

export interface SourceInfo {
  version: string;
  tip: number;
  zipCount: number;
  memberCount: number;
  extraZips: string[];
  chain: { manifest: string; resolved: number; missing: { version: string; name: string }[] } | null;
  officialBaseline: boolean;
  officialBaselineError: string | null;
}

export interface Meta {
  source: SourceInfo;
  boardRule: string;
  slots: { name: string; label: string }[];
  mode: string;
  writes: boolean;
}

export type Origin = "official" | "modified" | "new" | "unknown";

export interface CharacterSummary {
  id: string;
  code: string;
  name: string;
  title: string;
  rarity: number | string | null;
  elementId: string;
  element: string;
  type: string;
  origin: Origin;
}

export interface AbilityRow {
  index: number;
  description: string;
  values: string[];
  restrictions?: unknown;
  awake?: { kind: string; level: string };
}

export interface RelatedProgram {
  kind: string;
  key: string;
  program: string;
  commands: string[];
  commandCount: number;
  warning?: string;
}

export interface AbilityGroup {
  slot?: number;
  key: string;
  name: string;
  description: string;
  descriptionSource: string;
  rows: AbilityRow[];
  baseRows?: AbilityRow[];
  awakeRows?: AbilityRow[];
  customText: Record<string, string>;
  relatedPrograms: RelatedProgram[];
}

export interface Board {
  id: "board1" | "board2" | "board3";
  label: string;
  slots: AbilityGroup[];
  rowsKey: "baseRows" | "awakeRows";
}

export interface Skill {
  kind: string;
  level: string;
  label: string;
  name: string;
  description: string;
  gauge: number | string | null;
  gaugeMin: number | string | null;
  gaugeLabel: string;
  program: string;
  raw: string[];
  commands: string[];
  commandCount: number;
  warning?: string;
}

export interface ColumnLabel {
  block: string;
  field: string;
  note: string;
}

export interface CharacterDetail extends CharacterSummary {
  nameEn: string;
  role: string;
  races: string[];
  gender: string;
  cv: string;
  profile: string;
  boardRule: string;
  boards: Board[];
  leader: AbilityGroup;
  abilities: AbilityGroup[];
  skills: Skill[];
  switch: Record<string, string> | null;
  levels: { level: number; hp: number; atk: number }[];
  describeNote: string;
  sources: { logical: string; source: string | null }[];
  columns: { ability: ColumnLabel[]; leader_ability: ColumnLabel[] };
}

export interface PixelCell {
  cell: number;
  frames: number;
  start: number;
}

export interface PixelAction {
  name: string;
  label: string;
  kind: string;
  kindLabel: string;
  begin: number;
  end: number;
  totalFrames: number;
  cells: PixelCell[];
}

export interface PixelFamily {
  family: "pixelart" | "special";
  label: string;
  error?: string;
  cellWidth: number;
  cellHeight: number;
  columns: number;
  cellCount: number;
  anchor: { x: number; y: number };
  scale: number;
  fps: number;
  actions: PixelAction[];
}

export interface PixelMeta {
  characterId: string;
  code: string;
  families: PixelFamily[];
  slots: { name: string; label: string; present: boolean }[];
  note: string;
}

export interface AssetRoot {
  root: string;
  layer: string;
  layerLabel: string;
}

export interface AssetItem {
  path: string;
  layer: string | null;
  layerLabel: string;
  media: "image" | "audio" | "data";
  group: string;
  expected: "required" | "optional" | "referenced" | null;
  notes: string[];
  text: string;
  tag: string;
  status: "存在" | "缺失" | "引用但缺失";
  size?: number;
  width?: number;
  height?: number;
  official?: string;
  roots?: AssetRoot[];
}

export interface AssetGroup {
  id: string;
  label: string;
  items: AssetItem[];
  present: number;
  missing: number;
}

export interface SpeechLine {
  row: number;
  kind: string;
  constraint: string;
  evoLevel: string;
  text: string;
  voice: string;
  path?: string;
  present?: boolean;
}

export interface CharacterAssets {
  characterId: string;
  code: string;
  groups: AssetGroup[];
  speech: SpeechLine[];
  cutins: { form: string; png: boolean; atf: boolean; pngLayer: string | null; atfLayer: string | null }[];
  total: number;
  note: string;
}

export interface LookupHit {
  characterId: string;
  characterName: string;
  characterTitle: string;
  slot: string;
  key: string;
  row: number;
  table: string;
  description: string;
}

export interface Patch {
  id: string;
  name: string;
  description: string;
  version: string | null;
  dependsOn: string | null;
  enabled: boolean | null;
  archive: string;
  archiveSize: number | null;
  createdAt: string | null;
  changes: string[];
  fileCount: number | null;
  presentInActive: boolean;
  inView: boolean;
  origin: string;
}

export interface PatchChain {
  cdnVersion: string;
  viewVersion: string;
  manifest: string;
  count: number;
  patches: Patch[];
  note: string;
}

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body as T;
}

const cache = new Map<string, Promise<unknown>>();
function cached<T>(url: string): Promise<T> {
  if (!cache.has(url)) {
    const promise = get<T>(url);
    promise.catch(() => cache.delete(url));
    cache.set(url, promise);
  }
  return cache.get(url) as Promise<T>;
}

export const api = {
  meta: () => cached<Meta>("/api/meta"),
  characters: () => cached<{ version: string; count: number; characters: CharacterSummary[] }>("/api/characters"),
  character: (id: string) => cached<CharacterDetail>(`/api/characters/${id}`),
  pixels: (id: string) => cached<PixelMeta>(`/api/characters/${id}/pixels`),
  assets: (id: string) => cached<CharacterAssets>(`/api/characters/${id}/assets`),
  avatarUrl: (id: string, form: "0" | "1" = "0") => `/api/characters/${id}/avatar/${form}.png`,
  assetUrl: (path: string) => `/api/asset?path=${encodeURIComponent(path)}`,
  pixelSheetUrl: (id: string, family: string) => `/api/characters/${id}/pixels/${family}.png`,
  lookup: (q: string) =>
    get<{ total: number; count: number; results: LookupHit[]; note: string }>(
      `/api/lookup?q=${encodeURIComponent(q)}&limit=80`,
    ),
  patches: () => cached<PatchChain>("/api/patches"),
  patchMembers: (archive: string) =>
    cached<{ archive: string; members: string[]; count: number }>(
      `/api/patches/${encodeURIComponent(archive)}/members`,
    ),
};

// ---------------------------------------------------------------------------
// M3.2 draft workspace (writes only work/studio-drafts/<cid>/, guarded by token)

export interface DraftCheck {
  level: "error" | "warn" | "info";
  code: string;
  message: string;
}

export interface DraftFile {
  logical: string;
  root: "common" | "medium" | "android";
  draft: string;
  sha256: string;
  size: number;
  encoding: string;
  storeSha256?: string;
  base: { sha256: string | null; layer: string | null };
  approximate: boolean;
  note?: string;
}

export interface DraftChange {
  id: string;
  kind: "portrait" | "pixel_action" | "voice_line";
  title: string;
  createdAt: string;
  target: Record<string, string>;
  params: Record<string, any>;
  files: DraftFile[];
  pending: { logical: string; reason: string; value?: unknown }[];
  checks: DraftCheck[];
}

export interface Changeset {
  schema: string;
  characterId: string;
  code: string;
  baseView: string;
  createdAt: string;
  updatedAt: string;
  savedAt: string | null;
  revision: number;
  savedRevision: number | null;
  changes: DraftChange[];
}

export interface DraftStatus {
  state: "clean" | "dirty" | "saved";
  label: string;
  changes: number;
  savedAt?: string | null;
}

export interface DraftAction {
  id: string;
  label: string;
  enabled: boolean;
  note: string;
}

export interface DraftView {
  characterId: string;
  changeset: Changeset | null;
  status: DraftStatus;
  actions: DraftAction[];
}

export interface IconGroupSpec {
  anchor: [number, number];
  factor: number;
}

export interface CropTemplate {
  face: [number, number];
  squareHeight: number;
  groups: Record<string, IconGroupSpec>;
  cutin: { center: [number, number]; height: number; anchor: [number, number] };
  backdrop: { inner: [number, number, number]; outer: [number, number, number] } | null;
}

export interface PortraitSource {
  path?: string;
  file?: string;
  size: [number, number];
  originalSize?: [number, number];
  trim?: [number, number, number, number];
  hasAlpha?: boolean;
  template: CropTemplate;
}

export interface PortraitInfo {
  form: string;
  geometry: { characterImage: string | null; fullShotAttribute: string | null; face: [number, number] | null };
  current: PortraitSource | null;
  upload: PortraitSource | null;
  groups: { name: string; label: string; slots: string[]; anchor: [number, number]; factor: number }[];
  slotSizes: Record<string, [number, number]>;
  shapeSlots: string[];
  shapeLabels: Record<string, string>;
  slotUse: Record<string, string>;
  notes: string[];
}

export interface VoiceLine {
  voice: string | null;
  speechRow: number | null;
  kind: string;
  subtitle: string;
  label: string;
  path?: string;
  present?: boolean;
  layer?: string | null;
  durationSeconds?: number | null;
  loudness?: number;
  draft?: { id: string; file: string; durationSeconds: number; checks: DraftCheck[]; sourceName: string };
}

export interface VoiceLines {
  characterId: string;
  code: string;
  lines: VoiceLine[];
  format: string;
  note: string;
}

export interface PixelBudget {
  current: { width: number; height: number; share: number };
  estimate: { width: number; height: number; share: number; px: number } | null;
  loadedInBattle: boolean;
  officialShareMax: number;
  officialShareMedian: number;
  method: string;
}

export interface PixelCheckResult {
  dryRun: true;
  checks: DraftCheck[];
  budget: PixelBudget;
  originalTotalFrames: number | null;
  frameBox: [number, number];
}

export interface WriteResult {
  change?: DraftChange;
  changeset: Changeset;
  status: DraftStatus;
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data as T;
}

const draftListeners = new Set<(cid: string) => void>();
export function onDraftChange(listener: (cid: string) => void): () => void {
  draftListeners.add(listener);
  return () => draftListeners.delete(listener);
}
function notify<T>(cid: string, promise: Promise<T>): Promise<T> {
  return promise.then((value) => {
    draftListeners.forEach((listener) => listener(cid));
    return value;
  });
}

export function fileToBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).replace(/^data:[^,]*,/, ""));
    reader.onerror = () => reject(reader.error ?? new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

export const drafts = {
  hasToken: () => token() !== "",
  get: (cid: string) => get<DraftView>(`/api/drafts/${cid}`),
  fileUrl: (cid: string, path: string, version = "") =>
    `/api/drafts/${cid}/file?path=${encodeURIComponent(path)}${version ? "&v=" + version : ""}`,
  portraitInfo: (cid: string, form: string) => get<PortraitInfo>(`/api/characters/${cid}/portrait/${form}`),
  maskUrl: (slot: string) => `/api/studio/masks/${slot}.png`,
  voiceLines: (cid: string) => get<VoiceLines>(`/api/characters/${cid}/voice`),
  uploadPortrait: (cid: string, form: string, png: string) =>
    post<{ upload: PortraitSource; info: PortraitInfo }>(`/api/drafts/${cid}/portrait/${form}/source`, { png }),
  savePortrait: (cid: string, body: { form: string; source: string; template: CropTemplate; atf: boolean }) =>
    notify(cid, post<WriteResult>(`/api/drafts/${cid}/portrait`, body)),
  checkPixel: (cid: string, body: unknown) => post<PixelCheckResult>(`/api/drafts/${cid}/pixel`, { ...(body as object), dryRun: true }),
  savePixel: (cid: string, body: unknown) => notify(cid, post<WriteResult>(`/api/drafts/${cid}/pixel`, body)),
  saveVoice: (cid: string, body: { voice: string; audio: string; filename: string }) =>
    notify(cid, post<WriteResult>(`/api/drafts/${cid}/voice`, body)),
  revert: (cid: string, change: string) => notify(cid, post<WriteResult>(`/api/drafts/${cid}/changes/${change}/revert`, {})),
  save: (cid: string) => notify(cid, post<WriteResult>(`/api/drafts/${cid}/save`, {})),
};
