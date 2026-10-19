// BOSS工坊 backend wrappers (python -m wf.studio → /api/boss…). Boss drafts live in their own
// namespace (work/studio-drafts/boss/) and use the listener key "boss:<quest>".
import {
  Changeset, deliveryApi, DraftChange, DraftStatus, DraftView, get, notifyDraft, post, RuleResult,
} from "./api";
import type { DraftSubject } from "./views/Changes";

export type BossKind = "boss_battle" | "hard_multi" | "practice";
export type BossMode = "main_lord" | "lord" | "shared" | "five" | "practice" | "other";

/** Provenance of one table leaf (``scope=leaf``: last semantic change of the whole CSV leaf). */
export interface BossCitation {
  logical: string;
  table_layer: string | null;
  table_sha256: string | null;
  leaf_path?: string[];
  layer?: string | null;
  scope?: string;
  note?: string | null;
  local?: boolean;
}

export interface BossListItem {
  id: string;
  native_id: string;
  selector: string;
  kind: BossKind;
  category: string;
  name: string;
  group: string;
  table: string;
  path: string[];
  source: BossCitation;
  level: string;
  rank: string;
  hidden: boolean;
  recommendedElement: string;
  restrictedElement: string;
  fieldData: string;
  bothBoss: boolean;
  mode: BossMode;
}

export interface BossGroup {
  kind: BossKind;
  group: string;
  category: string;
  name: string;
  quests: string[];
  quest_count: number;
  mode: BossMode;
}

export interface BossList {
  schema: string;
  version: string;
  items: BossListItem[];
  groups: BossGroup[];
  quest_count: number;
  note: string;
  modes: { id: BossMode; label: string; rule: string }[];
}

export interface BossRecord {
  table: string;
  path: string[];
  row: string[];
  rows: string[][];
  source: BossCitation;
}

export interface ContentScope { kind: string; label: string; combat_content: boolean }

export interface BossEnemy {
  kind: "boss" | "zako";
  native_kind: string;
  code: string;
  level: number;
  mode: "single" | "multi" | "both";
  wave: string;
  slot: number;
  table?: string;
  path?: string[] | null;
  row: string[];
  source: BossCitation;
  zone_source?: BossCitation;
  zone_column?: number;
  missing: boolean | null;
  element: string | null;
  name: string;
  position_name: string | null;
  boss_level?: BossRecord | null;
  spawn_interval?: string;
  limitation?: string;
  content_scope?: ContentScope;
}

export interface BossWave {
  name: string;
  coffin_count: number;
  position_names: string[];
  objects: { type: string; name?: string }[];
}

export interface BossHidden {
  id: string;
  missing: boolean;
  selector?: string;
  name?: string;
  hidden?: boolean;
  field_data?: string;
  map_refs: { map: string; column: number }[];
}

export interface BossShop {
  id: string;
  category: BossRecord | null;
  products: BossRecord[];
  weapons: { id: string; product: string; equipment: BossRecord | null; source: BossCitation }[];
  association: { kind: string; field_data?: string; note?: string };
  server_sync: string;
}

export interface BossQuest {
  id: string;
  native_id: string;
  selector: string;
  kind: BossKind;
  category: string;
  name: string;
  group: string;
  table: string;
  path: string[];
  row: string[];
  fields: Record<string, any>;
  source: BossCitation;
  field_sources_semantics?: { granularity: string; column_origin_verified: boolean; note: string };
}

export interface BossDoc {
  schema: string;
  version: string;
  quest: BossQuest;
  entrance: {
    stage_node: BossRecord | null;
    stage_node_group: BossRecord | null;
    folder: BossRecord | null;
    event: BossRecord | null;
    event_folder: BossRecord[];
    event_folder_events: BossRecord[];
  };
  field_data: { id: string; missing: boolean } & Partial<BossRecord>;
  field: { id: string; missing: boolean } & Partial<BossRecord>;
  zone: { id: string; missing: boolean; rows: BossRecord[] };
  terrain: { logical: string; missing: boolean; waves: BossWave[]; wave_count: number | null; source: BossCitation | null; content_scope?: ContentScope };
  enemies: BossEnemy[];
  rewards: { key: string; missing: boolean; score_reward: BossRecord[]; rare_score_reward: BossRecord[]; item_ids: string[] };
  shops: BossShop[];
  routing: { kind: "none" | "BothBoss"; meaning?: string; group: BossRecord | null; maps: BossRecord[]; hidden_quests?: BossHidden[] };
  content_scope?: ContentScope;
  source_semantics: string;
}

export interface BossRead {
  questId: string;
  boss: BossDoc;
  changeset: Changeset | null;
  checks: RuleResult[];
  runtime: string;
}

export interface BossParameters {
  level?: number;
  hpMultiplier?: number;
  attackMultiplier?: number;
  restrictedElement?: number | null;
  recommendedElement?: number;
  bgm?: string;
  scene?: string;
}

export interface BossRequest {
  operation: "edit" | "create_shared";
  parameters?: BossParameters;
  tiers?: BossParameters[];
  acknowledgePreload?: boolean;
  sourceQuest?: string;
  name?: string;
}

// --- M6 phase-2 operations (terrain / shop & weapons / behavior) -------------------------

export interface MaterialCost { itemId: string; amount: number }
export interface ShopReward { kind: 0 | 4; id: string; amount: number }

export type TerrainRequest =
  | { operation: "terrain_replace"; terrain: string }
  | { operation: "terrain_position"; layer: string; action: "add" | "update" | "delete"; name: string;
      x?: number; y?: number; width?: number; height?: number }
  | { operation: "terrain_add_layer"; sourceQuest: string; sourceLayer: string; transitionSourceQuest?: string };

export interface ShopSpec {
  category: string; productId?: string; sourceProduct?: string; name?: string; description?: string;
  icon?: string; price?: MaterialCost[]; stock?: number; rewards?: ShopReward[];
  /** YYYY-MM-DD or YYYY-MM-DD HH:MM:SS; shop_add defaults to 2000-01-01 → no end (null). */
  availableFrom?: string; availableUntil?: string | null;
}

export interface WeaponAbilityChange {
  table: "ability_soul" | "equipment_enhancement_ability"; row: number;
  block: "instant_content" | "during_content"; kind?: number; strength?: [number, number];
}

export interface WeaponStage { productId: string; costs: MaterialCost[]; userCost?: { type: number; amount: number } | null }

export interface WeaponSpec {
  id?: string; sourceWeapon?: string; name?: string; description?: string; icon?: string; enhancedIcon?: string;
  hpMultiplier?: number; attackMultiplier?: number; abilities?: WeaponAbilityChange[];
  enhancementProducts?: string[]; stages?: WeaponStage[];
}

export type ShopWeaponRequest =
  | { operation: "shop_add" | "shop_edit" | "shop_delete"; shop: ShopSpec }
  | { operation: "weapon_clone" | "weapon_materials"; weapon: WeaponSpec };

export type BehaviorRequest =
  | { operation: "behavior_replace"; enemyCode: string; slot: number; sourceEnemyCode: string; sourceSlot: number }
  | { operation: "behavior_parameters"; enemyCode: string; slot?: number; state?: string; form?: number;
      intervalFrames?: number; damageMultiplier?: number; trialThreshold?: number };

/** Every request the boss draft endpoint accepts (one operation per POST). */
export type AnyBossRequest = BossRequest | TerrainRequest | ShopWeaponRequest | BehaviorRequest;

export interface Rect { x: number; y: number; width: number; height: number }
export interface Point2 { x: number; y: number }
export interface TerrainObject {
  id?: number; type?: string; name?: string; x?: number; y?: number; width?: number; height?: number;
  [key: string]: unknown;
}
export interface TerrainPosition { object_id?: number; name: string; type: string; rect: Rect; runtime_point: Point2 }
export interface TerrainLayer {
  name: string; objects: TerrainObject[]; bounds: Rect[];
  coffins: { index: number; party: number; member: number; object_id?: number; rect: Rect; runtime_point: Point2 }[];
  named_positions: TerrainPosition[]; custom_positions: TerrainPosition[]; coffin_count: number; position_names: string[];
}
export interface TerrainDoc {
  logical: string; missing: boolean; waves: TerrainLayer[]; wave_count: number | null; source: BossCitation | null;
  coordinate_semantics?: Record<string, string>;
  bindings?: { field_data: string; field: string; zone: string; waves: { layer: string; zone_paths: string[][] }[] };
}

export interface ProductFields {
  name: string; description: string; icon: string; rarity: string;
  price: { itemId: string; amount: string }[]; stock: string;
  limit: { frequency: string; daily: string; monthly: string };
  availableFrom: string; availableUntil: string;
  rewards: { kind: string; id: string; amount: string }[];
  currencies: { itemId: string; amount: string; item: BossRecord | null }[];
}
export interface ShopProduct extends BossRecord { id: string; fields: ProductFields; soul_item_ids: string[] }
export interface EnhancementStage extends BossRecord {
  id: string; categoryId: string; groupId: string; stage: string; maxLevel: string; requireAwakeningLevel: string;
  costs: { itemId: string; amount: string }[]; priceKind: string; userCost: { type: string; amount: string } | null;
  startLevel: number; purchaseCountTo120: number;
}
export interface WeaponDoc {
  id: string; product?: string;
  equipment: BossRecord | null; soul_item: BossRecord | null; ability_soul: BossRecord | null;
  equipment_enhancement: BossRecord | null; equipment_enhancement_ability: BossRecord | null;
  status: { level: string; row: string[]; source: BossCitation }[];
  enhancement_status: { level: string; row: string[]; source: BossCitation }[];
  enhancement_chain: EnhancementStage[];
  materials_to_120: { itemId: string; amount: number }[];
  user_costs_to_120: { type: string; amount: number }[];
  enhancement_start_level: number; reaches_120: boolean; material_semantics: string;
  kind_columns: Record<string, Record<string, number>>; kind_evidence: string;
  source?: BossCitation;
}
export interface ShopDoc {
  id: string; category: BossRecord | null; products: ShopProduct[]; shop_kind: string;
  contains_soul_products: boolean; weapons: WeaponDoc[]; association: { kind: string; note?: string }; server_sync: string;
}

export interface BehaviorAction {
  slot?: number; event?: unknown; begin: number; end: number | null; trigger_frame?: number;
  interval_semantics?: string; marker_frame?: number; positions?: Point2[]; dsl: string[]; offset?: number[];
}
export interface GeneralTrial { kind: string; threshold: string; countdown: string; wince: string; next: string; source: string }
export interface BehaviorState {
  id: string; name?: string; form?: number; animation: string; marker_sequence: string;
  marker_interval: { begin: number; end: number; name: string; kind: string } | null;
  begin: number; end: number | null; duration_frames: number | null; interval_semantics: string;
  termination: { kind: string; value: string } | unknown[];
  next: unknown; back: unknown;
  trial: GeneralTrial | unknown[] | null;
  invincible_by_phase_change: boolean; position?: string;
  actions: BehaviorAction[]; dsl: string[]; effects: string[]; immunity_links: unknown[]; missing: string[];
}
export interface BehaviorEnemy {
  enemyCode: string; wave: string; level: number; kind: string;
  routine?: string; initial_state?: string; logical?: string; marker?: string; marker_missing?: boolean;
  slots: { slot: number; program: string }[]; states: BehaviorState[];
  decoded?: { initialPosition?: unknown[]; [key: string]: unknown };
  slot_edit_supported?: boolean; preload?: { dsl: string[]; effects: string[]; missing: string[] };
  limitation?: string; missing?: boolean;
}
export interface BehaviorDoc { schema: string; enemies: BehaviorEnemy[] }

export interface WeaponIcons {
  equipment: { icon: string; id: string; name: string }[];
  enhanced: { icon: string; id: string; name: string }[];
  note: string;
}

export interface SectionResponse<T> { questId: string; section: string; data: T; checks: RuleResult[]; runtime: string }

export interface BossAllocation {
  event: string;
  quest: string;
  node: string;
  zone: string;
  fieldData: string;
  reward: string;
}

export interface BossPreview {
  ok: boolean;
  questId: string;
  allocation?: BossAllocation | null;
  changes?: { table: string; path: string[]; old: unknown; new: unknown }[];
  serverTargets?: string[];
  checks: RuleResult[];
  runtime: string;
}

export interface BossApplied extends BossPreview {
  change: DraftChange;
  changeset: Changeset;
  status: DraftStatus;
}

export interface BossDraftSummary {
  characterId: string;
  code: string;
  changes: number;
  updatedAt: string;
  savedAt: string | null;
  status: DraftStatus;
  baseView: string | null;
  requestCount: number;
  created: { name?: string; sourceQuest: string; ids?: { event: string; node: string } } | null;
}

export interface BossTemplateSource {
  selector: string;
  id: string;
  kind: BossKind;
  name: string;
  group: string;
  level: string;
  rank: string;
  mode: BossMode;
  recommendedElement: string;
  restrictedElement: string;
  source: BossCitation;
  default: boolean;
}

export interface BossTemplates {
  default: string;
  sources: BossTemplateSource[];
  excluded: { reason: string; count: number }[];
  note: string;
}

export interface BossOptions {
  bgm: { id: string; tracks: string[] }[];
  scenes: { id: string; background: string }[];
  terrains?: { path: string; uses: number; fieldData: string[] }[];
  note: string;
}

const enc = encodeURIComponent;
/** Listener key of a boss draft; "boss:*" is announced on every boss draft write (overview list). */
export const bossKey = (quest: string) => "boss:" + quest;
export const BOSS_ANY = "boss:*";

export const bossDeliveries = deliveryApi("/api/boss", bossKey);

const memo = new Map<string, Promise<unknown>>();
function once<T>(url: string): Promise<T> {
  if (!memo.has(url)) {
    const promise = get<T>(url);
    promise.catch(() => memo.delete(url));
    memo.set(url, promise);
  }
  return memo.get(url) as Promise<T>;
}

function announce(quest: string) {
  notifyDraft(bossKey(quest), Promise.resolve(null));
  notifyDraft(BOSS_ANY, Promise.resolve(null));
}

/** POST that keeps the JSON body of a rejected preview (HTTP 400 with five-state checks). */
async function previewPost(url: string, body: unknown): Promise<BossPreview> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (Array.isArray(data.checks)) return data as BossPreview;
  return {
    ok: false, questId: "", runtime: "未执行",
    checks: [{ rule: "boss.inputs", status: "问题", blocking: true, message: data.error || `HTTP ${response.status}` }],
  };
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

const draftUrl = (quest: string) => quest === "new" ? "/api/boss/drafts" : `/api/boss/drafts/${enc(quest)}`;

export const boss = {
  /** The base view never changes while the editor runs: read the list once per page load. */
  list: () => once<BossList>("/api/boss"),
  templates: () => once<BossTemplates>("/api/boss/templates"),
  options: () => once<BossOptions>("/api/boss/options"),
  read: (quest: string) => get<BossRead>(`/api/boss/${enc(quest)}`),
  drafts: () => get<{ drafts: BossDraftSummary[] }>("/api/boss/drafts"),
  draft: (quest: string) => get<DraftView>(`/api/boss/drafts/${enc(quest)}`),
  /** Read-only candidate sub-model with this quest's draft replayed; `rev` keys the cache to one draft revision. */
  section: <T>(quest: string, name: "terrain" | "shops" | "weapons" | "behavior" | "timeline", rev = "") =>
    once<SectionResponse<T>>(`/api/boss/${enc(quest)}/${name}?rev=${enc(rev)}`),
  terrainPreview: (path: string) => once<TerrainDoc>(`/api/boss/terrain-preview?path=${enc(path)}`),
  weaponIcons: () => once<WeaponIcons>("/api/boss/weapon-icons"),
  iconUrl: (path: string) => `/api/boss/icon.png?path=${enc(path)}`,
  preview: (quest: string, body: AnyBossRequest) => previewPost(draftUrl(quest) + "?preview=true", body),
  apply: async (quest: string, body: AnyBossRequest) => {
    const result = await post<BossApplied>(draftUrl(quest), body);
    announce(result.questId);
    return result;
  },
  save: async (quest: string) => {
    const result = await post<{ status: DraftStatus }>(`/api/boss/drafts/${enc(quest)}/save`, {});
    announce(quest);
    return result;
  },
  revert: async (quest: string, change: string) => {
    const result = await post<{ status: DraftStatus }>(`/api/boss/drafts/${enc(quest)}/changes/${change}/revert`, {});
    announce(quest);
    return result;
  },
};

/** 「本次修改」 adapter of one boss draft (canonical quest id from the backend). */
export function bossSubject(quest: string): DraftSubject {
  return {
    id: quest, key: bossKey(quest), deliveries: bossDeliveries,
    get: () => boss.draft(quest), save: () => boss.save(quest), revert: (change) => boss.revert(quest, change),
  };
}
