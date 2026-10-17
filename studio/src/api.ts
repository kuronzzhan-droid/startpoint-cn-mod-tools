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
