// 强化弹射动作工坊 backend wrappers (contract: docs/studio/pf-actions.md 「前端对接：HTTP」).
// Templates merge view CDN keys and the target APK's bundled table; preview never writes or reserves.
import { Changeset, DraftChange, DraftStatus, get, notifyDraft, RuleResult } from "./api";

const enc = encodeURIComponent;

export const PF_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"] as const;
export type PfElement = (typeof PF_ELEMENTS)[number];
export const PF_KEY = /^[a-z][a-z0-9_]{0,79}$/;
export const PF_EFFECT_TARGET = /^battle\/effect\/skill_unique\/[A-Za-z0-9_/-]+\/?$/;

export interface PfLevelNominal { level: number; nominalMultiplier: number | null }

export interface PfListItem {
  key: string;
  source: "cdn" | "bundled" | string;
  type: string;
  selectable: boolean;
  levels: PfLevelNominal[];
  error?: string;
}

export interface PfList { items: PfListItem[]; warnings: string[]; bundledAvailable: boolean }

export interface PfCoefficient { index: number; elementCode: number | null; terms: (Record<string, unknown> & { min?: number; max?: number })[] }

export interface PfLevelDetail {
  level: number;
  path: string;
  hitCount: number;
  hitAreaCount: number;
  coefficients: PfCoefficient[];
  elements: (number | null)[];
  effectFamilies: string[];
  markers: unknown[];
  nominalMultiplier: number | null;
  nominalNote: string;
}

export interface PfDetail {
  key: string;
  source: "cdn" | "bundled" | string;
  type: string;
  selectable: boolean;
  warnings: string[];
  levels: PfLevelDetail[];
}

export interface PfCloneRequest {
  key: string;
  source: string;
  element: PfElement;
  scale: number | [number, number, number];
  effects?: Record<string, string>;
}

export interface PfDependency {
  kind: string;
  root: string;
  logical: string;
  required: boolean;
  status: "existing" | "compiled_reference" | string;
  references: unknown;
  sha256?: string;
  size?: number;
}

export interface PfCloneResult {
  ok: boolean;
  preview?: boolean;
  characterId: string | null;
  key?: string;
  source?: string;
  sourceKind?: string;
  element?: string;
  elementCode?: number;
  scale?: number[];
  levels?: PfLevelDetail[];
  dependencies?: PfDependency[];
  tables?: { logical: string; addedKeys: string[] }[];
  files?: { root: string; logical: string; size: number; sha256: string }[];
  checks: RuleResult[];
  warnings?: string[];
  buildable?: boolean;
  runtime: string;
  error?: string;
  change?: DraftChange;
  changeset?: Changeset;
  status?: DraftStatus;
}

export interface PfDraftKey {
  key: string;
  source: string;
  element: string;
  changeId: string;
  reference: string;
  state: "draft" | string;
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

function failure(cid: string, message: string): PfCloneResult {
  return { ok: false, characterId: cid, runtime: "未执行", error: message,
    checks: [{ rule: "pf.inputs", status: "问题", blocking: true, message }] };
}

/** POST that keeps the 400 body (pf.inputs check: 键占用、输入非法) instead of throwing it away. */
async function postChecked(url: string, body: unknown, cid: string): Promise<PfCloneResult> {
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
  if (response.ok && data.ok !== false) return data as PfCloneResult;
  const message = data.error ?? `HTTP ${response.status}`;
  return { ...failure(cid, message), characterId: data.characterId ?? cid,
    checks: Array.isArray(data.checks) && data.checks.length ? data.checks : failure(cid, message).checks };
}

const profileQuery = (profile: string | null | undefined, first: boolean) =>
  profile ? `${first ? "?" : "&"}clientProfile=${enc(profile)}` : "";

export const pfActions = {
  list: (q: string, profile?: string | null) => {
    const query = q.trim() ? `?q=${enc(q.trim())}` : "";
    return get<PfList>(`/api/studio/pf-actions${query}${profileQuery(profile, !query)}`);
  },
  detail: (key: string, profile?: string | null) =>
    get<PfDetail>(`/api/studio/pf-actions/${enc(key)}${profileQuery(profile, true)}`),
  preview: (cid: string, request: PfCloneRequest, profile?: string | null) =>
    postChecked(`/api/drafts/${cid}/pf-action?preview=true${profileQuery(profile, false)}`, request, cid),
  /** Each successful write adds one pf_action_clone; notifies draft listeners only on success. */
  clone: async (cid: string, request: PfCloneRequest, profile?: string | null) => {
    const result = await postChecked(`/api/drafts/${cid}/pf-action${profileQuery(profile, true)}`, request, cid);
    if (result.ok) await notifyDraft(cid, Promise.resolve(result));
    return result;
  },
  draftKeys: (cid: string) => get<{ characterId: string; items: PfDraftKey[] }>(`/api/drafts/${cid}/pf-actions`),
};
