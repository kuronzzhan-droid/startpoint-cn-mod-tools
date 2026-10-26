// 召唤角色工坊 backend wrappers (contract: docs/studio/summon.md「前端对接」, backend wf/studio/summon*.py).
// Summons live in the host character's draft (work/studio-drafts/<cid>/changeset.json) as summon_clone changes,
// so writes announce the host character ID like every other character-draft writer.
import { Changeset, DraftChange, DraftStatus, drafts, get, notifyDraft, RuleResult } from "./api";
import type { IdCheck } from "./studioApi";

const enc = encodeURIComponent;

/** Internal element code 0..5 (the request field `element`); DSL explicit element codes are +1. */
export const SUMMON_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];
/** pf_type 0..4 (multiball c6). */
export const SUMMON_PF_TYPES = ["剑士", "格斗", "射击", "辅助", "特殊"];
export const summonElement = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : SUMMON_ELEMENTS[value] ?? String(value);
export const summonPfType = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : SUMMON_PF_TYPES[value] ?? String(value);

export type SummonTemplateKind = "character" | "multiball";

export interface SummonSkill {
  /** null when an existing ball's path is inherited directly. */
  key: string | null;
  level: string | null;
  name: string;
  path: string;
}

export interface SummonTemplate {
  kind: SummonTemplateKind;
  id: string;
  name: string;
  imagePrefix: string;
  rarity: number;
  element: number;
  pfType: number;
  skill: SummonSkill;
  panelAvailable: boolean;
}

export interface SummonTemplateList {
  schema: string;
  version: string;
  items: SummonTemplate[];
  total: number;
  count: number;
}

export interface SummonPanelPoint { level: number; hp: number; attack: number }

export type SummonPanelSpec =
  | { mode: "source" }
  | { mode: "scaled"; hp_scale?: number; attack_scale?: number }
  | { mode: "manual"; levels: SummonPanelPoint[] };

/** schemas/studio-draft.schema.json#/$defs/summonCloneRequest (preview is passed as a query parameter here). */
export interface SummonRequest {
  template: { kind: SummonTemplateKind; id: string };
  id?: string;
  image_prefix?: string;
  element?: number;
  panel?: SummonPanelSpec;
  pf_type?: number;
  skill?: { mode: "inherit"; level?: string } | { mode: "specified"; key: string; level?: string };
  assist?: boolean;
  lifetime?: { frames: number } | { seconds: number };
  extensions?: {
    flip_pf?: { enabled: boolean; min_interval_frames?: number };
    ball_pf_action?: string;
  };
}

/** One planned row: flat tables carry `rows` (2-D strings), curves carry `levels` (level → value). */
export interface SummonRow {
  logical: string;
  key: string;
  rows?: string[][];
  levels?: Record<string, string>;
}

export interface SummonPanelSummary {
  count: number;
  first: SummonPanelPoint;
  last: SummonPanelPoint;
  rounding: string;
  contextLevel: string;
  outsideDomain: string;
}

export interface SummonSkillTemplate {
  command: string;
  multiballId: string;
  lifetimeFrames: number;
  durationFrames: number;
  maxCount: number;
  selfOnly: boolean;
  summon: { multiballId: string; durationFrames: number; maxCount: number; selfOnly: boolean };
  parameters: unknown[];
  node: unknown[];
  inserted: boolean;
  callbackSubjectIds: number[];
  instructions?: string[];
}

/** Fields shared by POST results and GET items. */
export interface SummonDetail {
  characterId: string;
  multiballId: string;
  spec: SummonRequest & { id: string };
  rows: SummonRow[];
  checks: RuleResult[];
  requires: string[];
  skillTemplate: SummonSkillTemplate;
  skill: SummonSkill;
  panel: SummonPanelSummary;
  preservedColumns: Record<string, string>;
  ownedRows: Record<string, string[]>;
  reservations: Record<string, string[]>;
  runtime: string;
}

export interface SummonPreview extends SummonDetail {
  ok: true;
  preview: boolean;
  allocation: IdCheck;
}

export interface SummonApplied extends SummonPreview {
  change: DraftChange;
  changeset: Changeset;
  status: DraftStatus;
}

export interface SummonItem extends SummonDetail { changeId: string }

export interface SummonList {
  schema: string;
  version: string;
  characterId: string;
  items: SummonItem[];
  status: DraftStatus;
  runtime: string;
}

/** HTTP 400: summon.inputs check (or a synthetic one for guard errors without checks). */
export interface SummonFailure {
  ok: false;
  error: string;
  characterId: string | null;
  checks: RuleResult[];
  runtime: string;
}

export const isSummonFailure = (r: { ok: boolean }): r is SummonFailure => !r.ok;

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

/** POST that keeps the 400 body (five-state checks) instead of throwing it away. */
async function postChecked<T>(url: string, body: unknown): Promise<T | SummonFailure> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (response.ok && data.ok !== false) return data as T;
  const error = data.error ?? `HTTP ${response.status}`;
  return {
    ok: false, error, characterId: data.characterId ?? null, runtime: data.runtime ?? "未执行",
    checks: Array.isArray(data.checks) && data.checks.length ? data.checks
      : [{ rule: "summon.inputs", status: "问题", blocking: true, message: error }],
  };
}

export const summons = {
  templates: async (q = "") => {
    const first = await get<SummonTemplateList>(`/api/studio/summon/templates?q=${enc(q.trim())}&limit=500`);
    for (let offset = first.items.length; offset < first.total; offset += 500) {
      const page = await get<SummonTemplateList>(`/api/studio/summon/templates?q=${enc(q.trim())}&limit=500&offset=${offset}`);
      first.items.push(...page.items);
    }
    return { ...first, count: first.items.length };
  },
  list: (cid: string) => get<SummonList>(`/api/drafts/${enc(cid)}/summon`),
  /** Same checks as saving; writes nothing, reserves nothing (the allocated ID is not locked). */
  preview: (cid: string, request: SummonRequest) =>
    postChecked<SummonPreview>(`/api/drafts/${enc(cid)}/summon?preview=true`, request),
  apply: async (cid: string, request: SummonRequest) => {
    const result = await postChecked<SummonApplied>(`/api/drafts/${enc(cid)}/summon`, request);
    if (result.ok) notifyDraft(cid, Promise.resolve(null));
    return result;
  },
  /** Undo one summon_clone change (releases its reservations); notifies the host draft. */
  revert: (cid: string, changeId: string) => drafts.revert(cid, changeId),
};
