// 技能模板 backend wrappers (contract: docs/studio/skill-templates.md 「HTTP 与前端对接」).
// Donors are official-only; preview never writes or reserves; save writes one skill_template change per character.
import { Changeset, DraftChange, DraftStatus, get, notifyDraft, RuleResult } from "./api";

const enc = encodeURIComponent;

/** 火水雷风光暗 = internal element 0..5; DSL explicit code = element + 1. */
export const SKILL_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];
export const elementName = (value: number | null | undefined): string | null =>
  value === null || value === undefined ? null : SKILL_ELEMENTS[value] ?? (value === 6 ? "无色" : String(value));

export const ATTRIBUTION_LABEL: Record<number, string> = { 0: "自动", 1: "技能", 2: "能力", 3: "强化弹射", 4: "直击" };
export const COEFFICIENT_KIND_LABEL: Record<string, string> = {
  attack_multiplier: "攻击力倍率", hp_ratio: "生命值比例", fixed_damage: "固定伤害",
};

export interface TemplateCharacter { id: string; code: string; name: string; element: number | null }

export interface SkillTemplateItem {
  key: string;
  characters: TemplateCharacter[];
  names: string[];
  tiers: string[];
  damageNodeCount: number;
  effectFamilies: string[];
  cloneable: boolean;
}

export interface SkillTemplateList {
  templates: SkillTemplateItem[];
  count: number;
  officialOnly: boolean;
  provenance: string;
  unavailable: { key: string; reason: string }[];
}

/** One SLvValue term: min/max plus optional alv*_min/max, vlv and runtime refs (vid/mul). */
export type Coefficient = Record<string, unknown> & { min?: number; max?: number };

export interface DamageNode {
  path: string;
  constructor: "CreateNormalAttack" | "CreateRatioAttack" | "CreateFixedAttack" | string;
  coefficientKind: "attack_multiplier" | "hp_ratio" | "fixed_damage" | string;
  coefficient: Coefficient[];
  element: number | null;
  elementCode: number | null;
  elementInherited: boolean;
  attribution: number;
  subject: unknown;
}

export interface TemplateTier {
  level: string;
  name: string;
  row: string[];
  program: string;
  logical: string;
  inputSha256: string;
  damageNodes: DamageNode[];
  effectFamilies: string[];
  effectPaths: string[];
  cloneable: boolean;
  /** Native level/code/message (not five-state). */
  checks: { level: string; code: string; message: string }[];
}

export interface TemplateEffect { path: string; family: string; previewUrl: string | null; previewIssues?: string[] }

export interface SkillTemplateDetail {
  key: string;
  officialOnly: boolean;
  provenance: string;
  characters: TemplateCharacter[];
  contextElement: number | null;
  tiers: TemplateTier[];
  cloneable: boolean;
  damageNodeCount: number;
  effectFamilies: string[];
  effects: TemplateEffect[];
}

export interface SummonBlock {
  multiballId: string;
  maxCount?: number;
  selfOnly?: boolean;
  durationFrames?: number;
  effectPrefix?: string;
}

export interface SkillTemplateRequest {
  source: { key?: string; characterId?: string };
  newKey: string;
  scale?: number;
  text?: Record<string, { name?: string; description?: string }>;
  nodeCoefficients?: Record<string, Record<string, number | Coefficient[]>>;
  element?: number;
  attribution?: 1 | 3;
  recolor?: { hueShift: number } | { pairs: { from: string; to: string }[] };
  summon?: SummonBlock;
}

export interface LevelSummary {
  level: string;
  logical: string;
  damageNodes: DamageNode[];
  summary: {
    damageNodeCount: number;
    scale: number;
    nodeOverrideCount: number;
    element: number | null;
    elementCode: number | null;
    attribution: number | null;
    summon: (SummonBlock & { countMode?: "live-including-pending" | "native-party-count" }) | null;
    timingAndGeometryPreserved: boolean;
    effectFamilies: string[];
  };
}

export interface FamilyResource { root: string; source: string; target: string; sourceSha256: string; sha256: string }

export interface FamilySummary {
  source: string;
  target: string;
  effects: { source: string; target: string }[];
  changedPixels: number | null;
  resources: FamilyResource[];
  completeDependencies: boolean;
}

export interface PlannedFile { root: string; logical: string; size: number; sha256: string }

export interface SkillTemplateResult {
  ok: boolean;
  preview?: boolean;
  characterId: string | null;
  code?: string;
  newKey?: string;
  summary?: {
    sourceKey: string;
    newKey: string;
    levels: LevelSummary[];
    damageNodeCount: number;
    effectFamilies: FamilySummary[];
    files?: PlannedFile[];
  };
  checks: RuleResult[];
  buildable?: boolean;
  reservations?: Record<string, string[]>;
  runtime: string;
  error?: string;
  change?: DraftChange;
  changeset?: Changeset;
  status?: DraftStatus;
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

/** POST that keeps a 400 body (skill-template.inputs + checks) instead of throwing it away. */
async function postChecked(url: string, body: unknown, cid: string): Promise<SkillTemplateResult> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
      body: JSON.stringify(body),
    });
  } catch (e) {
    return failure(cid, (e as Error).message);
  }
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (response.ok && data.ok !== false) return data as SkillTemplateResult;
  const message = data.error ?? `HTTP ${response.status}`;
  return {
    ...failure(cid, message),
    characterId: data.characterId ?? cid,
    checks: Array.isArray(data.checks) && data.checks.length ? data.checks : failure(cid, message).checks,
  };
}

function failure(cid: string, message: string): SkillTemplateResult {
  return {
    ok: false, characterId: cid, runtime: "未执行", error: message,
    checks: [{ rule: "skill-template.inputs", status: "问题", blocking: true, message }],
  };
}

export const skillTemplates = {
  list: (q: string) => get<SkillTemplateList>(`/api/studio/skill-templates${q.trim() ? "?q=" + enc(q.trim()) : ""}`),
  detail: (key: string) => get<SkillTemplateDetail>(`/api/studio/skill-templates/${enc(key)}`),
  preview: (cid: string, request: SkillTemplateRequest) =>
    postChecked(`/api/drafts/${cid}/skill-template?preview=true`, request, cid),
  /** Notifies draft listeners only when the write succeeded. */
  save: async (cid: string, request: SkillTemplateRequest) => {
    const result = await postChecked(`/api/drafts/${cid}/skill-template`, request, cid);
    if (result.ok) await notifyDraft(cid, Promise.resolve(result));
    return result;
  },
};
