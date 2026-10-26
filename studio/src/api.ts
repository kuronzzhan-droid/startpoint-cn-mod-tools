// Typed wrappers over the read-only backend (python -m wf.studio).

export interface ViewList {
  views: string[];
  /** View the process actually loaded; null = not a named view. */
  current: string | null;
  source: SourceInfo;
  runtimeSwitching: false;
  restartRequired: true;
}

export interface SourceInfo {
  /** Highest version after the extra ZIPs; `tip` is the manifest chain end point. */
  version: string;
  tip: number | string;
  /** Version the base store already has (chain-views.md); absent on older backends. */
  baseVersion?: string;
  /** Named view (profiles/local.json views) selected at launch; null = legacy view / local default chain. */
  view?: string | null;
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
  /** Frames past the last atlas endpoint (no image there). */
  overflow?: number;
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
  frameBox?: { width: number; height: number; cropX: number; cropY: number };
  scale: number;
  fps: number;
  actions: PixelAction[];
  /** Sequences that start past the last atlas endpoint (nothing to play). */
  unplayable?: string[];
}

export interface PixelMeta {
  characterId: string;
  code: string;
  families: PixelFamily[];
  slots: { name: string; label: string; present: boolean }[];
  note: string;
  /** draft endpoint: no pixel changes in the draft (show the view instead) */
  empty?: boolean;
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
  /** Clone drafts only: the 37 required assets (复用母本 / 待替换 / 已派生), updated by later draft edits. */
  cloneAssets?: import("./studioApi").CloneAsset[];
  /** Current view's resource version. */
  sourceVersion?: string;
  draftRevision?: number | null;
  /** SHA-256 over the whole inventory + draft: the cache key of this character's media. */
  assetsVersion?: string;
  /** Quoted assetsVersion (JSON only; no HTTP conditional requests). */
  etag?: string;
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

export async function get<T>(url: string): Promise<T> {
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

/** Last assetsVersion seen per character: media URLs carry it so a changed inventory never shows stale bytes. */
const assetVersions = new Map<string, string>();
const assetReads = new Map<string, Promise<CharacterAssets>>();
let assetListener = false;
function assetInventory(id: string): Promise<CharacterAssets> {
  if (!assetListener) {
    assetListener = true;
    // Any draft write may change the inventory (cloneAssets, derived portraits): drop that read.
    onDraftChange((cid) => { assetReads.delete(cid); });
  }
  if (!assetReads.has(id)) {
    const read = get<CharacterAssets>(`/api/characters/${id}/assets`).then((data) => {
      if (data.assetsVersion) assetVersions.set(id, data.assetsVersion);
      return data;
    });
    read.catch(() => assetReads.delete(id));
    assetReads.set(id, read);
  }
  return assetReads.get(id)!;
}

export const api = {
  meta: () => cached<Meta>("/api/meta"),
  characters: () => cached<{ version: string; count: number; characters: CharacterSummary[] }>("/api/characters"),
  character: (id: string) => cached<CharacterDetail>(`/api/characters/${id}`),
  pixels: (id: string) => cached<PixelMeta>(`/api/characters/${id}/pixels`),
  /** Asset inventory; re-read after any write to this character's draft, keyed by assetsVersion (character-media.md). */
  assets: (id: string) => assetInventory(id),
  avatarUrl: (id: string, form: "0" | "1" = "0") =>
    `/api/characters/${id}/avatar/${form}.png` + (assetVersions.has(id) ? `?v=${assetVersions.get(id)!.slice(0, 16)}` : ""),
  /** `version` (assetsVersion) busts the browser cache of media whose inventory changed. */
  assetUrl: (path: string, version?: string) =>
    `/api/asset?path=${encodeURIComponent(path)}${version ? "&v=" + version.slice(0, 16) : ""}`,
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
  kind: "portrait" | "pixel_action" | "pixel_family" | "voice_line" | "ability_edit" | "boss" | "weapon" | "character_clone";
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
  backdropSource?: string;
  suggestedBackdrop?: { inner: [number, number, number]; outer: [number, number, number] };
  /** Painted backdrop of the existing square icon, offered (not applied) for a new upload. */
  currentBackdrop?: { inner: [number, number, number]; outer: [number, number, number] };
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

export async function post<T>(url: string, body: unknown): Promise<T> {
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
/** Tell every draft listener that the draft behind `key` changed (boss drafts use "boss:<quest>"). */
export function notifyDraft<T>(key: string, promise: Promise<T>): Promise<T> {
  return notify(key, promise);
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

// ---------------------------------------------------------------------------
// M4: ability draft editing (shared AbilityEditor core) and local delivery

export type RuleState = "满足" | "问题" | "待验证" | "不适用" | "未执行";

export interface RuleResult {
  rule: string;
  status: RuleState | string;
  message: string;
  blocking: boolean;
  evidence_nature?: string;
  source?: string;
  character?: string;
  /** capability.* results: capability ID, its client patches and the ones the target client lacks. */
  id?: string;
  patches?: number[];
  missing_patches?: number[];
}

export type AbilityTable = "ability" | "leader_ability" | "action_skill";

export interface AbilityEntry {
  table: AbilityTable;
  key: string;
  slot: number;
  level: string | null;
  rows: string[][];
  owners: string[];
  descriptions: (string | null)[];
}

export interface AbilitySlots {
  ability: string[];
  leader_ability: string;
  action_skill: string;
  /** character c18 (synced copy) */
  leaderName: string;
  /** character_text c10 — what wf text asserts as the old leader name */
  leaderNameText?: string | null;
}

export interface AbilityState {
  characterId: string;
  entries: AbilityEntry[];
  slots?: AbilitySlots;
  checks: RuleResult[];
  runtime: string;
}

export interface AbilityCellOp {
  column: string;
  old: string | null;
  new: string | null;
}

export interface AbilityOp {
  op: "set_cells" | "insert_row" | "delete_row" | "move_row";
  table: AbilityTable;
  key: string;
  level?: string;
  row: number;
  row_count: number;
  to_row?: number;
  column_space: "native";
  cells: AbilityCellOp[];
  shared_ok?: boolean;
}

/** attach_key: put an existing (or new, asserted) key on a slot. */
export interface AttachOp {
  op: "attach_key";
  table: AbilityTable;
  key: string;
  slot: number;
  old_key: string;
  shared_ok?: boolean;
  column_space?: "native";
  rows?: AbilityCellOp[][];
  levels?: Record<string, AbilityCellOp[][]>;
}

export interface TextPair { old: string; new: string }
/** desc_override may also be created: old = null asserts the key does not exist yet. */
export interface OverridePair { old: string | null; new: string }

/** abilityRequest.text (wf text); skill c0/c1 travel as asserted operations instead. */
export interface AbilityTextSections {
  desc_override?: Record<string, OverridePair>;
  custom_ability_string?: Record<string, TextPair>;
  character_text?: Record<string, TextPair>;
  action_skill?: Record<string, Record<string, TextPair>>;
}

export interface AbilityRequest {
  operations: (AbilityOp | AttachOp)[];
  text?: AbilityTextSections;
  shared_ok?: boolean;
}

export interface AbilityPreviewChange {
  op?: string;
  table?: string;
  key?: string;
  row?: number;
  to_row?: number;
  level?: string;
  surface?: string;
  client_old?: string;
  old?: string;
  new?: string;
  old_key?: string;
  slot?: number;
  owners?: string[] | Record<string, string[]>;
  beforeDescription?: string | null;
  afterDescription?: string | null;
}

export interface AbilityCheckResult {
  characterId: string;
  changes: AbilityPreviewChange[];
  checks: RuleResult[];
  runtime: string;
}

export interface RowPreview {
  before: { cells: string[] | null; description: string | null };
  after: { cells: string[] | null; description: string | null };
  owners: string[];
  checks: RuleResult[];
}

export interface TextFinding {
  rule: string;
  state: string;
  location?: string;
  message: string;
  source?: string;
  evidence?: { matches?: string[]; key?: string; text?: string; [k: string]: unknown };
}

export interface TextRuleRecord {
  rule: string;
  state: string;
  mode: string;
  requirement: string;
  boundary: string;
  source: string;
  evidence_nature: string;
}

export interface HouseRuleState {
  id: string;
  title: string;
  requirement: string;
  state: string;
  findings: TextFinding[];
}

export interface TextField {
  surface: "action_skill" | "desc_override" | "custom_ability_string";
  location: string;
  key: string;
  value: string;
  original: string | null;
  base: string | null;
  owners: string[];
  enhancement: boolean;
  tier?: string;
  field?: "c0" | "c1";
  /** Exact slot label of a desc_override (desc_override_<slot row c0>), or 「未挂接」. */
  slot?: string;
  /** Slot main-limit: all rows / some rows / none (ability c1 ≠ true). */
  main?: "all" | "some" | "none";
  slotKey?: string;
  /** desc_override key that does not exist yet (being created). */
  created?: boolean;
  findings: TextFinding[];
  /** Panel-standard rules this field hits (only hits). */
  rules: TextRuleRecord[];
  house: HouseRuleState[];
  /** Number of 「问题」 on this field (author rules + wf text findings). */
  problems: number;
  standardChecked: number;
}

export interface OverrideSlot {
  label: string;
  table: "ability" | "leader_ability";
  slot: number;
  key: string;
  names: string[];
  overrideKeys: string[];
  existing: string[];
  main: "all" | "some" | "none";
  owners: string[];
  rows: number;
}

export interface TextPanel {
  characterId: string;
  skillKey: string;
  snapshot: string;
  skillOwners: string[];
  leaderName: { characterText: string | null; character: string | null };
  fields: TextField[];
  general: TextFinding[];
  server: {
    effectiveSource: string; rankOverridesBase: boolean; inBase: boolean; inRank: boolean; rule: string;
    columns: { column: number; label: string; client: string | null; server: string | null; match: boolean }[];
  };
  houseRules: { id: string; title: string; requirement: string; rules: string[] }[];
  standard: { version: string; name: string; scope: string; note?: string };
  slots: OverrideSlot[];
  mainIcon: string;
}

export interface KeySearchResult {
  table: string;
  total: number;
  /** Lower-cased query terms (for highlighting). */
  terms?: string[];
  /** The key whose name equals the whole query, when one exists (duplicate check for new keys). */
  exact?: string | null;
  results: {
    key: string; rows: number; levels: string[] | null; owners: { id: string; name: string }[]; descriptions: string[];
    /** Row numbers (0-based) of `descriptions`, and those among them that matched a term. */
    descriptionRows?: number[]; matches?: number[];
  }[];
}

export interface TemplateOption {
  kind: string;
  en?: string;
  cn?: string;
  status: RuleState | string;
  selectable: boolean;
  defaults: string[];
  precedentCount: number;
  precedents: { key: string; row: number }[];
}

export interface TemplateList {
  table: string;
  block: string;
  options: TemplateOption[];
  note: string;
}

export interface DeliveryDefaults {
  from: string;
  to: string;
  outRoot: string;
  serverDir: string | null;
  provides: string | null;
  /** Client profile the backend would use when the request names none (client_profiles.json default). */
  clientProfile?: string | null;
  defaultClientProfile?: string;
  note: string;
}

export interface BuildResult {
  ok: boolean;
  name: string;
  characterId: string;
  from: string;
  to: string;
  error?: string;
  seconds?: number;
  draftRevision?: number;
  delivery?: string;
  prepush?: { status: string; exit_code: number; limitations?: string[] };
  checks?: RuleResult[];
  /** Status string in build-report.json (e.g. 「满足」/「未确认」); older results carried the list here. */
  compat?: RuleResult[] | string;
  /** Per-item compat results (build-report.json compatChecks). */
  compatChecks?: RuleResult[];
  /** Draft rule results replayed at compile time (boss drafts: five-state boss rules). */
  draftChecks?: RuleResult[];
  /** Client profile the delivery was checked against (null: explicit provides file or none). */
  clientProfile?: string | null;
  deviceValidation: string;
}

/** Background 「生成」 job: stages 编译 / wf deliver / 兼容 / check, cancellable between stages. */
export interface BuildJob {
  name: string;
  characterId: string;
  from: string;
  to: string;
  state: "running" | "ok" | "failed" | "cancelled";
  stage: string | null;
  stages: { id: string; label: string; state: "waiting" | "running" | "done" | "failed" | "cancelled" }[];
  seconds: number;
  result: BuildResult | null;
  clientProfile?: string | null;
}

export interface DeliverySummary {
  name: string;
  ok: boolean;
  error: string | null;
  from: string | null;
  to: string | null;
  draftRevision: number | null;
  /** createdAt of the draft snapshot the delivery was built from (a re-created draft repeats revision numbers). */
  draftCreatedAt?: string | null;
  prepush: string | null;
  counts: Record<string, number>;
  /** device-result.json of this delivery (null: never tested). */
  device?: DeviceSummary | null;
}

// ---------------------------------------------------------------------------
// 实测（交付目录里的 device-result.json，结构见 schemas/device-result.schema.json）

export type DeviceStatus = "通过" | "失败" | "未执行" | "作废";
export const DEVICE_STATUSES: DeviceStatus[] = ["通过", "失败", "未执行", "作废"];

export interface DeviceSummary {
  /** 「无效」: the file exists but cannot be read. */
  status: DeviceStatus | "无效";
  testedAt?: string;
  tester?: string;
  draftRevision?: number | null;
  checks?: number;
  legacy?: boolean;
  imported?: boolean;
  /** The draft changed (revision or re-created) after this delivery was built. */
  stale?: boolean;
  errors?: string[];
}

export interface DeviceCheck {
  item: string;
  expected?: string;
  observed?: string;
  status?: "通过" | "失败" | "未执行";
  screenshot?: string;
}

export interface DeviceResult {
  schema: string;
  status: DeviceStatus;
  reason?: string;
  delivery: { name: string; kind: "character" | "boss" | "weapon"; subject?: string | null; draftRevision: number | null;
    draftCreatedAt?: string | null;
    from?: string | null; to?: string | null; archives?: { name: string; sha256: string }[] };
  device?: { id?: string; label?: string; emulator?: boolean; package?: string; apk?: string; apkSha256?: string };
  server?: string;
  client?: { versionBefore?: string; versionAfter?: string; profile?: string };
  chainEdges?: { version: string; note?: string }[];
  checks: DeviceCheck[];
  screenshots?: string[];
  errorCodes?: string[];
  errorScan?: string;
  notes?: string;
  tester?: string;
  testedAt: string;
  recordedAt?: string;
  restore?: { method?: string; edges?: string[]; verified?: boolean; notes?: string };
  importedFrom?: { path: string; sha256: string; schema: string; delivery?: string; archivesMatch?: boolean | null; at?: string };
  extra?: Record<string, unknown>;
}

export interface DeviceShot { path: string; name: string; allowed: boolean; exists: boolean }

export interface DeviceEntry {
  path: string;
  result: DeviceResult | null;
  /** Stored as the hand-written wf-device-result/1 (shown converted; the file is unchanged). */
  legacy: boolean;
  errors: string[];
  history: number;
  bindingMismatch?: boolean;
  screenshots: DeviceShot[];
  currentRevision: number | null;
  /** No draft exists for this delivery any more (staleness cannot be judged). */
  draftMissing?: boolean;
  /** The draft changed after this delivery was tested. */
  stale: boolean;
}

/** Body of a 「记录实测」 write: everything but the delivery binding (the editor fills it). */
export type DeviceWrite = Omit<DeviceResult, "schema" | "delivery" | "recordedAt" | "importedFrom">;

export function screenshotUrl(path: string): string {
  return `/api/device-screenshots?path=${encodeURIComponent(path)}`;
}

export interface DeliveryDetail {
  name: string;
  path: string;
  report: BuildResult | null;
  error: BuildResult | null;
  archives: { name: string; size: number; sha256: string; members: number; files: string[] }[];
  members: { root: string; logical: string; sha256: string; before: string | null }[];
  serverChanges: { target: string; sha256: string }[];
  requires: any;
  check: RuleResult[] | null;
  compat: RuleResult[] | null;
  files: { path: string; size: number }[];
  deviceResult?: DeviceEntry | null;
  deviceValidation: string;
  /** delivery/bundle-check.json: output tables vs the target APK's built-in _iosbundled tables (C7051). */
  bundleCheck?: BundleCheck | null;
  /** delivery/key-diff.json summary: per-table key changes against the baseline view's chain tip. */
  keyDiff?: KeyDiff | null;
  /** Derived UI icons that paint over transparent portrait areas. */
  iconAlpha?: IconAlphaResult | null;
  /** p12/p13 client keys (wfx_summon_flip_pf_<ball>, wfx_ball_pf_action_<ball>, …) and what they require. */
  clientExtensions?: ClientExtensions | null;
}

export interface BundleCheck {
  status: "ok" | "collision" | "skipped" | "error";
  reason?: string;
  apks?: { label: string; sha256: string; bundledTables: number }[];
  tables?: { logical: string; bundledLogical: string; collisions: string[] }[];
}

type KeyDiffCounts = { added: number; changed: number; removed: number; owned?: number; foreign: number; unknown: number };

export interface KeyDiffTable {
  logical: string;
  root?: string;
  archive?: string;
  counts: KeyDiffCounts;
  added?: string[];
  changed?: string[];
  removed?: string[];
  owned?: string[];
  foreign?: string[];
  unknown?: string[];
  /** Deletions inside a kept outer key: nested keys removed or CSV records dropped. */
  deletions?: { kind: string; path: string[]; beforeRows?: number; afterRows?: number; removedRows?: number }[];
  truncated?: boolean;
}

export interface KeyDiff {
  status: "ok" | "warning" | "blocked";
  blocking?: boolean;
  baseline?: { view?: string | null; tip?: string | null; version?: string | null };
  delivery?: { from?: string | null; to?: string | null; archives?: string[] };
  counts?: KeyDiffCounts;
  tables?: KeyDiffTable[];
  warnings?: string[];
}

export interface IconAlphaSlot {
  slot: string;
  form?: number | string;
  authorBackdrop?: boolean;
  ratio?: number;
  status: "ok" | "warning" | "info" | "skipped";
  code?: string;
  message?: string;
}

export interface IconAlphaResult {
  /** partial: some icons were checked and passed, others could not be checked. */
  status: "ok" | "warning" | "info" | "skipped" | "partial";
  threshold?: number;
  slots?: IconAlphaSlot[];
  reason?: string;
}

export interface ClientExtensions {
  status: "ok" | "warning" | "error";
  requires?: string[];
  checks?: RuleResult[];
}

export const ability = {
  state: (cid: string) => get<AbilityState>(`/api/characters/${cid}/ability`),
  rowPreview: (cid: string, table: string, key: string, row: number, level?: string | null) =>
    get<RowPreview>(`/api/drafts/${cid}/ability/preview?table=${table}&key=${encodeURIComponent(key)}&row=${row}` +
      (level ? `&level=${level}` : "")),
  templates: (table: string, block: string) =>
    cached<TemplateList>(`/api/studio/ability/templates?table=${table}&block=${block}`),
  check: (cid: string, body: AbilityRequest) => post<AbilityCheckResult>(`/api/drafts/${cid}/ability/check`, body),
  apply: (cid: string, body: AbilityRequest) => notify(cid, post<WriteResult>(`/api/drafts/${cid}/ability`, body)),
  text: (cid: string) => get<TextPanel>(`/api/characters/${cid}/text`),
  lint: (cid: string, text: AbilityTextSections) => post<TextPanel>(`/api/drafts/${cid}/text/lint`, { text }),
  keys: (table: AbilityTable, q: string, cid: string) =>
    get<KeySearchResult>(`/api/studio/ability/keys?table=${table}&q=${encodeURIComponent(q)}&cid=${cid}&limit=40`),
};

/** 生成请求：clientProfile = 页面顶部选的目标客户端；provides 只在填了自定义能力清单时发送。 */
export interface BuildRequest { from: string; to: string; provides?: string; clientProfile?: string }

/** 「生成」/「导出」 endpoints of one draft namespace (characters at /api, boss drafts at /api/boss). */
export interface DeliveryApi {
  /** Draft-change listener key of a draft id (characters: the id itself). */
  key: (cid: string) => string;
  defaults: () => Promise<DeliveryDefaults>;
  list: (cid: string) => Promise<{ root: string; deliveries: DeliverySummary[]; running: Record<string, string>; jobs: BuildJob[];
    currentRevision?: number | null }>;
  job: (name: string) => Promise<BuildJob>;
  start: (cid: string, body: BuildRequest) => Promise<BuildJob>;
  cancel: (cid: string) => Promise<{ name: string; cancelling: boolean; note: string }>;
  /** Tell listeners (status strip, export list) that a job finished. */
  finished: (cid: string) => Promise<null>;
  detail: (name: string) => Promise<DeliveryDetail>;
  fileUrl: (name: string, path: string) => string;
  device: (name: string) => Promise<{ name: string; deviceResult: DeviceEntry | null; screenshotDirs: string[] }>;
  writeDevice: (cid: string, name: string, body: DeviceWrite) => Promise<{ name: string; deviceResult: DeviceEntry }>;
  importDevice: (cid: string, name: string, path: string, allowUnverified?: boolean) =>
    Promise<{ name: string; deviceResult: DeviceEntry }>;
}

export function deliveryApi(prefix: string, key: (cid: string) => string = (cid) => cid): DeliveryApi {
  const id = (cid: string) => encodeURIComponent(cid);
  return {
    key,
    defaults: () => get<DeliveryDefaults>(`${prefix}/deliveries/defaults`),
    list: (cid) => get(`${prefix}/deliveries?cid=${id(cid)}`),
    job: (name) => get<BuildJob>(`${prefix}/deliveries/jobs/${encodeURIComponent(name)}`),
    start: (cid, body) => post<BuildJob>(`${prefix}/drafts/${id(cid)}/build`, { ...body, background: true }),
    cancel: (cid) => post(`${prefix}/drafts/${id(cid)}/build/cancel`, {}),
    finished: (cid) => notify(key(cid), Promise.resolve(null)),
    detail: (name) => get<DeliveryDetail>(`${prefix}/deliveries/${encodeURIComponent(name)}`),
    fileUrl: (name, path) => `${prefix}/deliveries/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`,
    device: (name) => get(`${prefix}/deliveries/${encodeURIComponent(name)}/device-result`),
    writeDevice: (cid, name, body) =>
      notify(key(cid), post(`${prefix}/drafts/${id(cid)}/deliveries/${encodeURIComponent(name)}/device-result`, body)),
    importDevice: (cid, name, path, allowUnverified) =>
      notify(key(cid), post(`${prefix}/drafts/${id(cid)}/deliveries/${encodeURIComponent(name)}/device-result/import`,
        { path, ...(allowUnverified ? { allowUnverified: true } : {}) })),
  };
}

export const deliveries = {
  ...deliveryApi("/api"),
  build: (cid: string, body: BuildRequest) =>
    notify(cid, post<BuildResult>(`/api/drafts/${cid}/build`, body)),
};

// ---------------------------------------------------------------------------
// 像素工坊（拆解 / 母本映射 / 程序化动作 / 画板）

export type PaletteGroup = "body" | "fx" | "template" | "outline";

export interface WorkshopCell {
  key: number;
  cell: number;
  start: number;
  frames: number;
  region: number;
  fx: number;
  fy: number;
  w: number;
  h: number;
  dy: number;
  dx: number;
  bbox: [number, number, number, number] | null;
  alphaPx: number;
}

export interface WorkshopAction {
  name: string;
  kind: string;
  begin: number;
  end: number;
  totalFrames: number;
  universal: boolean;
  cells: WorkshopCell[];
  overflow?: number;
}

export interface WorkshopRegion {
  id: number;
  x: number;
  y: number;
  w: number;
  h: number;
  rotated: boolean;
  keys: number[];
  actions: string[];
  alphaPx: number;
}

export interface WorkshopFamily {
  family: "pixelart" | "special";
  sheet: { width: number; height: number; fill: number; layer0Px: number; share: number };
  frame: { name: string; x: number; y: number; scale: number; smoothing: boolean };
  origin: [number, number];
  keys: number;
  regions: WorkshopRegion[];
  actions: WorkshopAction[];
  unusedKeys: number[];
  unusedRegions: number[];
  duplicateRegions: number[][];
  points: number;
  sounds: number;
  checks: DraftCheck[];
}

export interface PaletteColor {
  hex: string;
  rgb: [number, number, number];
  count: number;
  /** pixels of this colour that are fully opaque (0 = only on semi-transparent pixels) */
  opaque?: number;
  regions: number;
  luma: number;
  group: PaletteGroup;
  actions: string[];
  families: string[];
}

export interface WorkshopAnalysis {
  characterId: string;
  name: string;
  code: string;
  state: "view" | "draft";
  families: WorkshopFamily[];
  palette: PaletteColor[];
  groupLabels: Record<PaletteGroup, string>;
  universalRanges: Record<string, Record<string, [number, number]>>;
  notes: string[];
}

export interface ColorPair { from: string; to: string; group?: string }

export interface RemapResult {
  dryRun?: boolean;
  base: { id: string; code: string; name: string };
  families: { family: string; changedPixels: number; renamedEntries: number; sheet: [number, number]; checks: DraftCheck[]; mappingUsed: number; mappingSize: number }[];
  changes?: DraftChange[];
  status?: DraftStatus;
}

export type BaseImageSpec = { cell: { family: string; key: number } } | { png: string };

export interface GeneratedFrame { png: string; duration: number; dy: number; note: string; bbox: [number, number, number, number] }

export interface GenerateResult {
  action: string;
  label?: string;
  totalFrames?: number;
  frames: GeneratedFrame[];
  bases?: Record<string, BaseImageSpec>;
  change?: DraftChange;
  status?: DraftStatus;
}

export const GENERATE_ACTIONS: { id: string; label: string }[] = [
  { id: "walk_front", label: "向前移动" }, { id: "walk_back", label: "向后移动" }, { id: "kachidoki", label: "胜利" },
  { id: "into_coffin", label: "倒下入棺" }, { id: "ghost_raise", label: "幽灵升起" },
  { id: "ghost_neutral", label: "幽灵待机" }, { id: "revive", label: "复活" },
];

/** One action's images as raw RGBA (backend-decoded; never read back through a canvas). */
export interface ActionFrames {
  characterId: string;
  family: string;
  action: string;
  state: "view" | "draft";
  frameBox: [number, number];
  origin: [number, number];
  totalFrames: number;
  frames: { key: number; start: number; duration: number; box: [number, number, number, number] | null; rgba: string }[];
  note: string;
}

/** Raw RGBA image: 8-byte little-endian header (width, height) + width*height*4 bytes. */
export interface RawImage { width: number; height: number; data: Uint8ClampedArray }

export async function fetchRaw(url: string): Promise<RawImage> {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    throw new Error(body.error || `HTTP ${response.status}`);
  }
  const buffer = await response.arrayBuffer();
  const view = new DataView(buffer);
  const width = view.getUint32(0, true), height = view.getUint32(4, true);
  return { width, height, data: new Uint8ClampedArray(buffer, 8, width * height * 4) };
}

export function base64ToBytes(text: string): Uint8Array {
  const binary = atob(text);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) binary += String.fromCharCode(...bytes.subarray(i, i + step));
  return btoa(binary);
}

export const workshop = {
  actionFrames: (cid: string, family: string, action: string, state: "view" | "draft" = "draft") =>
    get<ActionFrames>(`/api/characters/${cid}/pixel-workshop/action/${family}/${action}?state=${state}`),
  sheetRaw: (cid: string, family: string, state: "view" | "draft", stamp: string | number = "") =>
    fetchRaw(state === "draft" ? `/api/drafts/${cid}/pixels/${family}.rgba?v=${stamp}` : `/api/characters/${cid}/pixels/${family}.rgba`),
  analyze: (cid: string, state: "view" | "draft" = "view") =>
    get<WorkshopAnalysis>(`/api/characters/${cid}/pixel-workshop?state=${state}`),
  cellUrl: (cid: string, family: string, key: number, state: "view" | "draft" = "view", stamp = "") =>
    `/api/characters/${cid}/pixel-workshop/cell/${family}/${key}.png?state=${state}${stamp ? "&v=" + stamp : ""}`,
  bases: (cid: string) => get<{ bases: Record<string, BaseImageSpec> }>(`/api/characters/${cid}/pixel-workshop/bases`),
  draftPixels: (cid: string) => get<PixelMeta & { draftRevision: number; draftStamp: string }>(`/api/drafts/${cid}/pixels`),
  draftSheetUrl: (cid: string, family: string, stamp: string | number) => `/api/drafts/${cid}/pixels/${family}.png?v=${stamp}`,
  remap: (cid: string, body: { base: string; mapping: ColorPair[]; families?: string[]; groups?: Record<string, PaletteGroup>; dryRun?: boolean }) =>
    body.dryRun ? post<RemapResult>(`/api/drafts/${cid}/pixel-remap`, body)
      : notify(cid, post<RemapResult>(`/api/drafts/${cid}/pixel-remap`, body)),
  generate: (cid: string, body: { action: string; bases?: Record<string, BaseImageSpec>; totalFrames?: number; save?: boolean }) =>
    body.save ? notify(cid, post<GenerateResult>(`/api/drafts/${cid}/pixel-generate`, body))
      : post<GenerateResult>(`/api/drafts/${cid}/pixel-generate`, body),
};

// ---------------------------------------------------------------------------
// 草稿角色（scratch：还没有游戏 ID，只承载像素）

export interface ScratchMeta {
  name: string;
  element: string;
  slug: string;
  base: { characterId: string | null; code: string; name?: string };
  note?: string;
  boundTo: { characterId: string; code: string; at: string; changes: string[] } | null;
}

export interface ScratchInfo {
  characterId: string;
  code: string;
  baseView: string;
  scratch: ScratchMeta;
  status: DraftStatus;
  changes: { id: string; kind: string; title: string }[];
  buildable: false;
  note: string;
}

export interface ImportFamilyResult {
  family: string;
  sourceCode: string;
  endpoints: number;
  sheet: [number, number];
  actions: string[];
  checks: DraftCheck[];
  provenance: { base: string; comparable: boolean; endpoints?: number; matchingEndpoints?: number; differingByAction?: Record<string, number> } | null;
}

export interface ImportResult {
  dryRun?: boolean;
  characterId: string;
  families: ImportFamilyResult[];
  remap?: { base: string | null; colors: number } | null;
  changes?: DraftChange[];
  status?: DraftStatus;
}

export interface BindResult {
  dryRun?: boolean;
  from: string;
  characterId: string;
  code: string;
  name: string;
  renamed: string;
  changes: { kind: string; title: string; auto?: boolean }[];
  /** e.g. a family with only per-action edits gets the base family added automatically. */
  notes?: string[];
  created?: string[];
}

export const scratchApi = {
  list: () => get<{ scratch: ScratchInfo[]; elements: string[] }>("/api/scratch"),
  get: (sid: string) => get<ScratchInfo>(`/api/scratch/${sid}`),
  create: (body: { name: string; element: string; base: string; slug?: string; note?: string }) =>
    post<ScratchInfo>("/api/drafts/scratch", body),
  importSet: (cid: string, body: { files?: Record<string, string>; zip?: string; remap?: unknown; name?: string; dryRun?: boolean }) =>
    body.dryRun ? post<ImportResult>(`/api/drafts/${cid}/pixel-import`, body)
      : notify(cid, post<ImportResult>(`/api/drafts/${cid}/pixel-import`, body)),
  bind: (sid: string, body: { characterId: string; dryRun?: boolean }) =>
    body.dryRun ? post<BindResult>(`/api/drafts/${sid}/bind`, body) : notify(sid, post<BindResult>(`/api/drafts/${sid}/bind`, body)),
  rename: (sid: string, body: { name?: string; element?: string }) =>
    notify(sid, post<ScratchInfo>(`/api/drafts/${sid}/scratch-rename`, body)),
  remove: (sid: string) => post<{ deleted: string }>(`/api/drafts/${sid}/scratch-delete`, {}),
};
