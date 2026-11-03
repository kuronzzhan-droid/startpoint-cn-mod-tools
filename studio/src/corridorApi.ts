// 深渊回廊内容编辑 API（python -m wf.studio → /api/corridor/...）。
import { get, post } from "./api";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

export interface Finding {
  code: string; severity: "block" | "warning"; pointer: string; entity_type: string | null;
  entity_id: string | null; message: string; related_ids: string[]; suggested_fix: string | null;
}
export interface Validation { revision: number; input_digest: string; blockers: number; warnings: number; findings: Finding[] }
export interface ReleaseSummary {
  id: string; content_version: string; workspace_revision: number; created_at: string; message: string;
  active_profile: string; source_version: string; validation_summary: { blockers: number; warnings: number; warning_codes: string[] };
}
export interface SnapshotMeta { id: string; revision: number; message: string; kind: string; created_at: string; digest: string }
export interface CorridorStatus {
  configured: boolean; hint?: string;
  config?: { sources: Record<string, boolean>; trialctl: boolean; trial: boolean };
  master?: { errors: string[]; tier_sha256: string | null; soul_sha256: string | null; source_version: string;
    status: string; runtime_tested: boolean; characters: number; excluded_characters: number; weapons: number;
    pending_weapons: number; souls: number; counts_by_tier?: Record<string, Record<string, number>> };
  workspace: null | { revision: number; source: Record<string, Json>; counts: Record<string, number>; active_profile: string;
    locks_ok: boolean; upstream_changed: string[] };
  validation?: Validation; releases?: ReleaseSummary[]; snapshots?: SnapshotMeta[];
}
export interface CommandResult { revision: number; validation: { blockers: number; warnings: number }; results: Record<string, Json>[] }

export interface PoolItem {
  id: string; name: string | null; code?: string; element: number | null; element_name: string; rarity?: number;
  official?: boolean; source_tier: number | null; effective_tier?: number | null; tier_name?: string | null; category?: string;
  in_pool: boolean; boss_playable?: boolean; override?: string | null; override_reason?: string | null;
  starter_derived?: boolean; starter_eligible?: boolean; min_act?: number | null; min_act_derived?: number | null;
  shop_price?: number | null; pool_check_ok?: boolean; pool_check_reasons?: string[]; excluded_reason?: string | null;
  policy: Record<string, Json>; group?: string; level_min?: number; level_max?: number; awakening_max?: number;
  enhancement_cap?: number; soul_id?: number | null; soul_excluded_reason?: string | null; first_seen?: string | null;
  source_equipment_ids?: string[]; level_max_soul?: number; starter_role?: string | null;
}
export interface PoolPage { revision: number; total: number; page: number; size: number; items: PoolItem[];
  summary: Record<string, Json>; boss_playable?: { enabled: boolean; min_act: number }; rules?: Record<string, Json> }

export interface RelicEntry {
  relic: Record<string, Json>; effects: Record<string, Json>[]; shape: "effect" | "effects";
  zh: { name?: string; desc?: string }; en: { name?: string; desc?: string };
  settled: { ok: boolean; reason?: string; effects?: Record<string, Json>[] }; settled_text: string[]; combat: boolean;
  policy: Record<string, Json>; findings: Finding[];
}
export interface EventOptionEntry { option_id: string | null; index: number; option: Record<string, Json>; zh?: string; en?: string }
export interface EventEntry {
  event: Record<string, Json>; options: EventOptionEntry[]; settled: { ok: boolean; reason?: string };
  zh: { title?: string; text?: string }; en: { title?: string; text?: string }; policy: Record<string, Json>; findings: Finding[];
}
export interface Tombstone { kind: string; id: string; at_revision: number; reason: string }
export interface EncounterEntry {
  quest_id: string; round: number; threat: number; element: number; kind_hint: string; label: string; mechanic_text: string;
  element_damage: Record<string, number>; rank?: number; excluded: boolean; acts: number[]; policy: Record<string, Json>;
}
export interface ActView { act: number; ranks: [number, number]; quests: string[]; size: number; boss: string | null;
  boss_by_element: Record<string, string | null>; excluded_by_element: Record<string, string[]> }
export interface EncounterPage { revision: number; host: EncounterEntry[]; acts: ActView[]; problems: { act: number; message: string }[];
  excluded_rounds: number[]; boss_rounds: number[]; boss_elements: Record<string, Json>; threshold: number }
export interface RuleField { path: string; label: string; type: string; group: string; value: Json; present: boolean;
  min?: number; max?: number; options?: string[]; labels?: string[]; hint?: string; optional?: boolean }
export interface LocaleRow { key: string; zh: string | null; en: string | null; owner: [string, string] | null; missing: string[] }
export interface Registry {
  relic_kinds: Record<string, { label: string; unit?: string; value: string; min?: number; max?: number; combat?: boolean;
    extra?: Record<string, { label: string; value: string; min?: number; max?: number }> }>;
  event_kinds: Record<string, { label: string; value: string | null; min?: number; max?: number }>;
  rarities: Record<string, string>; elements: Record<string, string>; requires: Record<string, string>;
  templates: { relics: { id: string; label: string; rarity: string }[]; events: { id: string; label: string }[] };
}
export interface DiffResult {
  revision: number; against: string; label: string; readable: { area: string; entity: string; text: string }[];
  pointers: { path: string; op: string; before?: Json; after?: Json }[]; pointer_count: number;
  files: { name: string; before: string | null; after: string | null; server_reads: boolean }[];
  impact: { before: Record<string, Json>; after: Record<string, Json> };
}
export interface TrialActive { kind: string; label: string; version?: string; deployed_at?: string; note?: string }
export interface TrialStatus {
  status: { guard: string[]; ports: [number, number] | null; running: boolean | null; state?: string;
    listeners: Record<string, number[]> | null; recorded: Record<string, Json> | null; trialctl_output?: string };
  active: TrialActive; deploy_state: Record<string, Json> | null;
  open_runs: { run_id: string; player_id: number; status: string; floor?: number; error?: string }[];
}
export interface TrialPlan {
  guard: string[]; active: TrialActive; target: string; ports: [number, number] | null; blocked: boolean; needs_ack: boolean;
  manifest: Record<string, Json>;
  open_runs: { run_id: string | null; status?: string; floor?: number; breaking: string[]; notes: string[] }[];
}
export interface DeployEntry { at: string; action: string; from?: string; to?: string; result?: string;
  health?: Record<string, Json>; preflight?: Record<string, Json>; open_runs?: number; exit?: number }

export const corridor = {
  status: () => get<CorridorStatus>("/api/corridor/status"),
  registry: () => get<Registry>("/api/corridor/registry"),
  characters: (q: string) => get<PoolPage>("/api/corridor/characters?" + q),
  character: (id: string) => get<{ item: PoolItem; master: Record<string, Json> }>(`/api/corridor/characters/${id}`),
  weapons: (q: string) => get<PoolPage>("/api/corridor/weapons?" + q),
  souls: (q: string) => get<PoolPage>("/api/corridor/souls?" + q),
  relics: () => get<{ revision: number; relics: RelicEntry[]; tombstones: Tombstone[] }>("/api/corridor/relics"),
  events: () => get<{ revision: number; events: EventEntry[]; tombstones: Tombstone[] }>("/api/corridor/events"),
  encounters: () => get<EncounterPage>("/api/corridor/encounters"),
  locales: (q: string) => get<{ revision: number; count: number; items: LocaleRow[]; totals: Record<string, number> }>("/api/corridor/locales?" + q),
  rules: () => get<{ revision: number; fields: RuleField[]; groups: Record<string, string>; rules: Json }>("/api/corridor/rules"),
  validation: () => get<Validation>("/api/corridor/validation"),
  diff: (against: string) => get<DiffResult>("/api/corridor/diff?against=" + encodeURIComponent(against)),
  releases: () => get<{ releases: ReleaseSummary[] }>("/api/corridor/releases"),
  snapshots: () => get<{ snapshots: SnapshotMeta[] }>("/api/corridor/snapshots"),
  trial: () => get<TrialStatus>("/api/corridor/trial"),
  plan: (version: string) => get<TrialPlan>("/api/corridor/trial/plan?version=" + encodeURIComponent(version)),
  deploys: () => get<{ deploys: DeployEntry[] }>("/api/corridor/deploys"),
  audit: () => get<{ audit: Record<string, Json>[] }>("/api/corridor/audit"),
  importSource: (revision: number | null) => post<{ revision: number }>("/api/corridor/import/source", { revision }),
  importWorkspace: (revision: number, workspace: Json) => post<{ revision: number }>("/api/corridor/import/workspace", { revision, workspace }),
  commands: (revision: number, commands: Record<string, Json>[], message?: string) =>
    post<CommandResult>("/api/corridor/commands", { revision, commands, ...(message ? { message } : {}) }),
  build: (revision: number, message: string) => post<{ release: ReleaseSummary & { reused: boolean } }>("/api/corridor/build", { revision, message }),
  snapshot: (message: string) => post<{ snapshot: SnapshotMeta }>("/api/corridor/snapshots", { message }),
  restore: (id: string, revision: number) => post<{ revision: number }>(`/api/corridor/snapshots/${id}/restore`, { revision }),
  apply: (version: string, expected_active: string, acknowledge_open_runs: boolean, rollback = false) =>
    post<Record<string, Json>>(`/api/corridor/trial/${rollback ? "rollback" : "apply"}`, { version, expected_active, acknowledge_open_runs }),
  restoreOriginal: (expected_active: string) => post<Record<string, Json>>("/api/corridor/trial/restore-original", { expected_active }),
  stop: () => post<Record<string, Json>>("/api/corridor/trial/stop", {}),
  start: () => post<Record<string, Json>>("/api/corridor/trial/start", {}),
};

export const ELEMENTS: [string, string][] = [["1", "火"], ["2", "水"], ["3", "雷"], ["4", "风"], ["5", "光"], ["6", "暗"]];
export const short = (v: string | null | undefined) => (v ? v.replace(/^sha256:/, "").slice(0, 12) : "—");
