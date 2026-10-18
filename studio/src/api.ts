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
  frameBox?: { width: number; height: number; cropX: number; cropY: number };
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
  kind: "portrait" | "pixel_action" | "pixel_family" | "voice_line" | "ability_edit";
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
  leaderName: string;
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

/** abilityRequest.text (wf text); skill c0/c1 travel as asserted operations instead. */
export interface AbilityTextSections {
  desc_override?: Record<string, TextPair>;
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
  slot?: string;
  findings: TextFinding[];
  rules: TextRuleRecord[];
  house: HouseRuleState[];
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
  standard: { version: string; name: string; scope: string };
}

export interface KeySearchResult {
  table: string;
  total: number;
  results: { key: string; rows: number; levels: string[] | null; owners: { id: string; name: string }[]; descriptions: string[] }[];
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
  compat?: RuleResult[];
  deviceValidation: string;
}

export interface DeliverySummary {
  name: string;
  ok: boolean;
  error: string | null;
  from: string | null;
  to: string | null;
  draftRevision: number | null;
  prepush: string | null;
  counts: Record<string, number>;
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
  deviceValidation: string;
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

export const deliveries = {
  defaults: () => get<DeliveryDefaults>("/api/deliveries/defaults"),
  list: (cid: string) => get<{ root: string; deliveries: DeliverySummary[]; running: Record<string, string> }>(
    `/api/deliveries?cid=${cid}`),
  detail: (name: string) => get<DeliveryDetail>(`/api/deliveries/${encodeURIComponent(name)}`),
  fileUrl: (name: string, path: string) => `/api/deliveries/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`,
  build: (cid: string, body: { from: string; to: string; provides?: string }) =>
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

export const workshop = {
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
