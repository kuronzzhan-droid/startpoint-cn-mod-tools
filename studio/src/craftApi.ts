// 交稿四件套：像素批量预检、场地比例、图集重排、稿主交接单（wf/studio/craft_routes.py）。
import { DraftChange, DraftCheck, DraftStatus, get, notifyDraft, PixelBudget, post } from "./api";

export interface ActionMark { includesCompanion: boolean; purpose: string }

export interface PrecheckAction {
  action: string;
  label: string | null;
  files: string[];
  frames: number;
  includesCompanion: boolean;
  purpose: string;
  checks: DraftCheck[];
  ok: boolean;
  durations?: number[];
  totalFrames?: number;
  sizes?: string[];
  budget?: PixelBudget;
}

export interface PrecheckResult {
  characterId: string;
  family: "pixelart" | "special";
  actions: PrecheckAction[];
  composite: { file: string; action: string; index: number | null }[];
  unmatched: string[];
  ignored: string[];
  checks: DraftCheck[];
  counts: { error: number; warn: number; info: number };
  ready: string[];
  saved: { action: string; change: string }[];
  applied: boolean;
}

export interface PrecheckRequest {
  family: "pixelart" | "special";
  files?: Record<string, string>;
  zip?: string;
  actions?: Record<string, ActionMark>;
  apply?: boolean;
}

export interface StagePoint { x: number; y: number }
export interface StageInfo {
  quest: { id: string; kind: string; category: string; name: string; fieldData: string; alternatives: number } | null;
  terrain: string;
  wave: string;
  waves: number;
  bounds: { x: number; y: number; width: number; height: number };
  runtimeScale: number;
  coffins: (StagePoint & { party: number; member: number })[];
  positions: (StagePoint & { name: string; type: string })[];
  objects: { type: string; name: string; x: number; y: number; width: number; height: number; polygon: [number, number][] }[];
  note: string;
}

export interface SheetSize { width: number; height: number; area: number; share: number }
export interface RepackReport {
  family: string;
  code: string;
  source: SheetSize;
  output: SheetSize;
  records: number;
  regions: number;
  regionArea: number;
  fill: number;
  saving: number;
  worthIt: boolean;
  targetWidth: number;
  sortMode: string;
  gap: number;
  loadedInBattle: boolean;
  equivalence: { signature: string; framesCompared: number; method: string };
}

export interface HandoffNotes {
  title: string;
  author: string;
  summary: string;
  actions: Record<string, { purpose: string; includesCompanion: boolean; note: string }>;
  notes: string;
  updatedAt: string | null;
}

export interface HandoffSheet {
  characterId: string;
  code: string;
  name: string | null;
  generatedAt: string;
  status: { state: string; label: string };
  notes: HandoffNotes;
  actions: { action: string; label: string | null; purpose: string; includesCompanion: boolean; note: string; inDraft: boolean; frames: number }[];
  files: { logical: string; size: number; sha256: string; change: string; approximate: boolean }[];
  frames: { file: string; sha256: string | null; change: string; index: number; size: [number, number] }[];
  changes: { id: string; kind: string; title: string; errors: number; warnings: number }[];
  notInGame: { kind: string; text: string; change?: string }[];
}

export const craft = {
  precheck: (cid: string, body: PrecheckRequest) => body.apply
    ? notifyDraft(cid, post<PrecheckResult>(`/api/drafts/${cid}/pixel-precheck`, body))
    : post<PrecheckResult>(`/api/drafts/${cid}/pixel-precheck`, body, { readonly: true }),
  stage: (quest: string, terrain = "") =>
    get<StageInfo>(`/api/stage-scale?${terrain ? "terrain=" + encodeURIComponent(terrain) : "quest=" + encodeURIComponent(quest)}`),
  repack: (cid: string, family: string) => get<RepackReport>(`/api/characters/${cid}/atlas-repack?family=${family}`),
  repackPngUrl: (cid: string, family: string) => `/api/characters/${cid}/atlas-repack/${family}.png`,
  applyRepack: (cid: string, family: string) =>
    notifyDraft(cid, post<{ report: RepackReport; change: DraftChange; status: DraftStatus }>(`/api/drafts/${cid}/atlas-repack`, { family })),
  handoff: (cid: string) => get<HandoffSheet>(`/api/drafts/${cid}/handoff`),
  handoffMarkdownUrl: (cid: string) => `/api/drafts/${cid}/handoff?format=md`,
  saveNotes: (cid: string, notes: Omit<HandoffNotes, "updatedAt">) =>
    post<{ notes: HandoffNotes }>(`/api/drafts/${cid}/handoff-notes`, notes),
};
