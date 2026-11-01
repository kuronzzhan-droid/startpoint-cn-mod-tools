import { Changeset, deliveryApi, get, post } from "./api";

export type Mode = "five" | "rogue";
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export interface ModeDraft extends Changeset { payload: Json; preview: ModePreview }
export interface Floor {
  key: string; quest: string; folder: string; round: string; name: string; description: string;
  element: string; level: string; field: string; bosses: string[]; effects: { kind: string; strength: string }[];
}
export interface ManualStep { title: string; command: string }
export interface ModePreview {
  ok: boolean; canGenerate: boolean; blockers: string[]; version: string;
  diff?: { path: string; before: Json; after: Json }[];
  audit?: { aligned: boolean; differences: { logical: string; path: string }[]; hpRatios: Json[]; note: string;
    quests?: { quest: string; currentBossHpMultiplier: string; specBossHpMultiplier: string; statesMatch: boolean }[] };
  report?: { budget?: Record<string, { mpx: number; verdict: string; sheets: number }>;
    element_variants_in_apk?: string[] };
  warnings?: string[]; rows?: Floor[]; checks?: { ok: boolean; round: string; errors: string[] }[];
  manualSteps?: ManualStep[]; log?: string; draft?: ModeDraft;
}
export interface ModeRead {
  mode: Mode; version: string; payload: Json; spec?: Record<string, Json>; draft: ModeDraft | null;
  preview?: ModePreview;
  current?: { event: string; rounds: number; seasonNote: string; eventRow: string[]; fingerprint: string;
    rows: Floor[]; manualSteps: ManualStep[] };
}
export const modeDeliveries = deliveryApi("/api/modes", id => "mode:" + id);
export const modes = {
  read: (mode: Mode) => get<ModeRead>(`/api/modes/${mode}`),
  preview: (mode: Mode, payload: Json) => post<ModePreview>(`/api/modes/${mode}/preview`, { payload }),
  save: (mode: Mode, payload: Json, revision: number) => post<ModePreview>(`/api/modes/${mode}/save`, { payload, revision }),
};
