import { Changeset, deliveryApi, get, post, RuleResult } from "./api";
import { Json } from "./modeApi";

export interface SceneSetting { id: string; kind: string; value: Json; bindings: Json[] }
export interface SceneGroup { id: string; name?: string; quest?: string; sourceQuest?: string; settings: SceneSetting[] }
export interface SceneSpec {
  schema: string; id: string; name: string; sourceVersion: string;
  event: SceneGroup; tiers: SceneGroup[]; phases: SceneGroup[];
  summons: SceneSetting[]; mechanisms: SceneSetting[]; trials: SceneSetting[];
  shops: SceneGroup[]; drops: SceneGroup[];
  tables: Json[]; resources: Json[]; requirements: Json[];
  provenance?: { kind: string; version?: string; note?: string };
  creation?: { sourceEvent: string; tableTargets: { logical: string; path: string[] }[]; resourceTargets: string[] };
}
export interface SceneDraftSummary {
  slot: string; name: string; eventId: string; isClone: boolean;
  revision: number; baseView?: string; updatedAt?: string;
}
export interface SceneDraft extends Changeset { payload: SceneSpec; preview?: ScenePreview }
export interface SceneDifference { logical?: string; path?: string | (string | number)[]; before?: Json; after?: Json; [key: string]: unknown }
export interface ScenePreview {
  ok: boolean; canGenerate: boolean; blockers: string[]; checks: RuleResult[]; version: string;
  slot?: string; drafts?: SceneDraftSummary[];
  diff?: SceneDifference[]; audit?: { aligned: boolean; differences: SceneDifference[]; note?: string; [key: string]: unknown };
  summary?: Record<string, number>; runtime?: string; outputSha256?: Record<string, string> | string; draft?: SceneDraft;
  [key: string]: unknown;
}
export interface SceneRead {
  mode: "scene"; slot?: string; version: string; spec: SceneSpec | null; payload: SceneSpec | null;
  draft: SceneDraft | null; drafts?: SceneDraftSummary[]; migratedSlot?: string | null; preview?: ScenePreview;
}
export interface SceneClone {
  slot?: string; payload: SceneSpec; draft?: SceneDraft | null; drafts?: SceneDraftSummary[];
  allocation: { eventId: string; quests: string[]; reserved: false }; preview: ScenePreview;
}

const PREFIX = "/api/scenes";
const DEFAULT_SLOT = "hell-pumpkin";
export const sceneDeliveries = deliveryApi(PREFIX, id => "scene:" + id);
export const scenes = {
  read: (slot = DEFAULT_SLOT) => get<SceneRead>(`${PREFIX}/${encodeURIComponent(slot)}`),
  drafts: () => get<{ drafts: SceneDraftSummary[]; migratedSlot?: string | null }>(`${PREFIX}/drafts`),
  preview: (payload: SceneSpec, slot = payload.id || DEFAULT_SLOT) =>
    post<ScenePreview>(`${PREFIX}/${encodeURIComponent(slot)}/preview`, { payload }),
  save: (payload: SceneSpec, revision: number, slot = payload.id || DEFAULT_SLOT) =>
    post<ScenePreview>(`${PREFIX}/${encodeURIComponent(slot)}/save`, { payload, revision }),
  clone: (payload: SceneSpec, name: string) => post<SceneClone>(`${PREFIX}/hell-pumpkin/clone`, { payload, name }),
  schemaUrl: `${PREFIX}/schema`,
};
