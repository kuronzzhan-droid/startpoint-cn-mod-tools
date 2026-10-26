// 武器工坊 backend wrappers (python -m wf.studio → /api/studio/weapons…, contract: docs/studio/weapons.md).
// Weapon drafts live in work/studio-drafts/weapons/<id>/ and use the listener key "weapon:<id>".
import { Changeset, deliveryApi, DraftChange, DraftStatus, DraftView, get, notifyDraft, post, RuleResult } from "./api";
import type { AnyBossRequest, BossPreview, BossRecord, WeaponDoc, WeaponSpec, WeaponStage } from "./bossApi";
import type { DraftSubject } from "./views/Changes";

const PREFIX = "/api/studio/weapons";
const enc = encodeURIComponent;

/** 火水雷风光暗 = 0..5 (server equipment_element; -1 = 无属性分类). */
export const WEAPON_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];
export const weaponElement = (value: number | null | undefined) =>
  value === null || value === undefined ? null : value === -1 ? "无" : WEAPON_ELEMENTS[value] ?? String(value);

export interface WeaponListItem {
  id: string;
  name: string;
  rarity: number | null;
  /** Server equipment_element category (-1..5); null when the local server input is missing. */
  element: number | null;
  icon: string;
  soulId: string;
  /** null: official baseline unavailable. */
  isMod: boolean | null;
  hasEnhancement: boolean;
  hasAwakening: boolean | null;
}

export interface WeaponList {
  schema: string;
  version: string;
  items: WeaponListItem[];
  total: number;
  count: number;
  limit: number;
  notes: string[];
}

export interface CurvePoint { level: number | null; hp: number | null; attack: number | null }
export interface CurveSummary { count: number; first: CurvePoint | null; last: CurvePoint | null }

export interface WeaponAwakening {
  maxLevel: number | null;
  serverInputAvailable: boolean;
  materialId: string | null;
  material: BossRecord | null;
  clientMaterial: BossRecord | null;
  rarityOverride: unknown;
  standardMaterials: (BossRecord | null)[];
  note?: string;
}

export interface WeaponShopRef {
  scope: "client" | "server";
  kind: string;
  productId: string;
  categoryId?: string;
  eventId?: string;
  eventType?: string;
  matches?: unknown[];
  source?: string | { logical?: string };
  path?: string[];
  product?: Record<string, unknown>;
  table?: string;
}

export interface WeaponGachaRef {
  scope: "client" | "server";
  id: string;
  name: string | null;
  oddsId?: string;
  weight?: string;
  group?: string;
  source?: string;
}

/** GET /<id>: the boss WeaponDoc model (except `status`, renamed base_status) plus card and draft fields. */
export interface WeaponDetail extends Omit<WeaponDoc, "status">, Omit<WeaponListItem, "id"> {
  schema: string;
  version: string;
  weaponId: string;
  subjectKind: "weapon";
  base_status: WeaponDoc["status"];
  curves: { base: CurveSummary; enhancement: CurveSummary };
  awakening: WeaponAwakening;
  references: { shops: WeaponShopRef[]; gacha: WeaponGachaRef[] };
  referenceCoverage?: { clientShops: string[]; serverShops: Record<string, boolean>; clientGacha: string; serverGachaAvailable: boolean };
  elementInputAvailable?: boolean;
  changeset: Changeset | null;
  /** Draft save state; `status` is its compatibility alias (not the curve rows). */
  draft_status?: DraftStatus;
  status: DraftStatus;
  checks: RuleResult[];
  runtime: string;
  note?: string;
}

/** The boss WeaponDoc shape the shared editors read: the contract keeps `status` = draft state here,
 * so the curve rows (base_status) are mapped back under `status`. */
export function asWeaponDoc(detail: WeaponDetail): WeaponDoc {
  return { ...detail, status: detail.base_status ?? [] } as unknown as WeaponDoc;
}

export interface WeaponPreview extends Omit<BossPreview, "allocation" | "questId"> {
  weaponId?: string;
  subjectKind?: "weapon";
  allocation?: (WeaponSpec & { id: string; enhancementProducts?: string[] }) | null;
}

export interface WeaponApplied extends WeaponPreview {
  weaponId: string;
  change: DraftChange;
  changeset: Changeset;
  status: DraftStatus;
}

export interface WeaponDraftSummary {
  characterId: string;
  weaponId?: string;
  /** Clone request name, else the donor / weapon name; null when unknown. */
  name?: string | null;
  /** The draft holds a weapon_clone (vs. material edits of an existing weapon). */
  isNew?: boolean;
  code: string;
  changes: number;
  updatedAt: string;
  savedAt: string | null;
}

export const weaponKey = (id: string) => "weapon:" + id;
/** Announced on every weapon draft write (list / draft section). */
export const WEAPON_ANY = "weapon:*";

export const weaponDeliveries = deliveryApi(PREFIX, weaponKey);

function announce(id: string) {
  notifyDraft(weaponKey(id), Promise.resolve(null));
  notifyDraft(WEAPON_ANY, Promise.resolve(null));
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

/** Preview POST: rejected candidates come back as HTTP 400 with five-state checks (weapon.inputs first);
 * only a bare `{"error"}` (other input errors) is turned into one synthetic blocking check. */
async function previewPost(url: string, body: unknown): Promise<BossPreview> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (Array.isArray(data.checks)) return { ...data, ok: response.ok && data.ok !== false, questId: data.weaponId ?? "", allocation: null } as BossPreview;
  return {
    ok: false, questId: "", runtime: "未执行",
    checks: [{ rule: "weapon.inputs", status: "问题", blocking: true, message: data.error || `HTTP ${response.status}` }],
  };
}

/** The shared editors build boss-shaped requests; the weapon routes take the bare spec / stages. */
function route(request: AnyBossRequest): { url: string; body: unknown } {
  if (request.operation === "weapon_clone") return { url: `${PREFIX}/clone`, body: request.weapon };
  if (request.operation === "weapon_materials" && request.weapon.id)
    return { url: `${PREFIX}/${enc(request.weapon.id)}/materials`, body: { stages: request.weapon.stages ?? [] as WeaponStage[] } };
  throw new Error("武器工坊只接受克隆武器和改强化材料");
}

export const weapons = {
  list: (params: { q?: string; element?: string; rarity?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params.q?.trim()) query.set("q", params.q.trim());
    if (params.element) query.set("element", params.element);
    if (params.rarity) query.set("rarity", params.rarity);
    query.set("limit", String(params.limit ?? 500));
    return get<WeaponList>(`${PREFIX}?${query}`);
  },
  detail: (id: string) => get<WeaponDetail>(`${PREFIX}/${enc(id)}`),
  drafts: () => get<{ subjectKind: "weapon"; drafts: WeaponDraftSummary[] }>(`${PREFIX}/drafts`),
  draft: (id: string) => get<DraftView & { weaponId: string; subjectKind: "weapon" }>(`${PREFIX}/drafts/${enc(id)}`),
  preview: (request: AnyBossRequest) => {
    const { url, body } = route(request);
    return previewPost(url + "?preview=true", body);
  },
  apply: async (request: AnyBossRequest) => {
    const { url, body } = route(request);
    const result = await post<WeaponApplied>(url, body);
    announce(result.weaponId);
    return result;
  },
  save: async (id: string) => {
    const result = await post<{ status: DraftStatus }>(`${PREFIX}/drafts/${enc(id)}/save`, {});
    announce(id);
    return result;
  },
  revert: async (id: string, change: string) => {
    const result = await post<{ status: DraftStatus }>(`${PREFIX}/drafts/${enc(id)}/changes/${change}/revert`, {});
    announce(id);
    return result;
  },
};

/** POST /<id>/icon: 20×20 weapon PNG, or 40×40 soul / material into item_icon (weapons.md §8). */
export interface WeaponIconRequest { kind: "weapon" | "soul" | "material"; png: string; item_id?: string }
export interface WeaponIconResult {
  kind: "weapon" | "soul" | "material"; logical: string;
  /** Submitted PNG [width, height]. */
  size: [number, number];
  /** Actual item_icon atlas [width, height]; null for the standalone weapon PNG. */
  atlasSize: [number, number] | null;
  itemId?: string; thumbnail?: string; preservedEntries?: number;
}

/** GET /capabilities: whether the selected provides *declares* what the 629 templates need.
 * Candidates still check the real SWF branch at preview; this is never a device result. */
export interface WeaponCapabilities {
  invoke629: {
    supported: boolean;
    capabilities: { id: string; provided: boolean | null }[];
    patch20: { linked: boolean | null; recorded: boolean | null; supported: boolean };
    evidence: { status: "available" | "unavailable"; sha256: string | null; clientProfile: string | null };
    checks: RuleResult[];
  };
  scope: "provides-declaration";
  runtime: string;
  note: string;
}
export type WeaponIconPreview = BossPreview & { icons?: WeaponIconResult[] };

export const weaponCapabilities = () => get<WeaponCapabilities>(`${PREFIX}/capabilities`);

export const weaponIcons = {
  preview: (id: string, body: WeaponIconRequest) =>
    previewPost(`${PREFIX}/${enc(id)}/icon?preview=true`, body) as Promise<WeaponIconPreview>,
  apply: async (id: string, body: WeaponIconRequest) => {
    const result = await post<WeaponApplied & { icons?: WeaponIconResult[] }>(`${PREFIX}/${enc(id)}/icon`, body);
    announce(id);
    return result;
  },
};

/** 「本次修改」 adapter of one weapon draft. */
export function weaponSubject(id: string): DraftSubject {
  return {
    id, key: weaponKey(id), deliveries: weaponDeliveries,
    get: () => weapons.draft(id), save: () => weapons.save(id), revert: (change) => weapons.revert(id, change),
  };
}

// ------------------------------------------------------------------ 专属武器全套 (weapons.md §10)

/** One category row of GET /set-options; exchange `name` is the native c0 code (no text-name column). */
export interface WeaponSetCategoryOption { id: string; code: string; name: string; order: string; row: string[]; table: string }
/** Current item rows; serverAvailable null = no server item_ids input (not verified, never "passed"). */
export interface WeaponSetMaterial { id: string; name: string; icon: string; serverAvailable: boolean | null }
export interface WeaponSetOptions {
  version: string;
  categories: { enhancement: WeaponSetCategoryOption[]; exchange: WeaponSetCategoryOption[] };
  materials: WeaponSetMaterial[];
  serverInputAvailable: boolean;
  notes: string[];
  runtime: string;
}

/** Reuse: id or existing code/name. Create: sourceCategory + code + name (id auto-allocated). */
export interface WeaponSetCategory { id?: string; sourceCategory?: string; code?: string; name?: string }
export interface WeaponSetStage { maxLevel: number; costs: { itemId: string; amount: number }[]; requireAwakeningLevel?: number }
/** Omitted keys = option off. noSoul=false is "no action", not an undo (undo = draft revert). */
export interface WeaponSetRequest {
  noSoul?: boolean;
  awakeningMaterial?: string;
  enhancementCategory?: WeaponSetCategory;
  enhancement?: { sourceWeapon?: string; maxLevel: number; stages: WeaponSetStage[]; products?: string[] };
  exchange?: {
    category: WeaponSetCategory; sourceProduct: string; productId?: string; itemId: string;
    amount: number; count?: number; stock: number; description?: string;
  };
}

/** Five-state check plus the extras weapon.enhancement-cost / weapon.awakening-material carry. */
export interface WeaponSetCheck extends RuleResult {
  maxLevel?: number; purchaseMode?: string; materialTotals?: Record<string, number>;
  materialId?: string; clientCapability?: string; duplicateEquipmentAllowed?: boolean;
  internalSoulId?: string; generatedSoul?: boolean;
}

export interface WeaponSetResult {
  ok: boolean;
  error?: string;
  weaponId?: string;
  subjectKind?: "weapon";
  changes?: { table: string; path: string[]; old: unknown; new: unknown }[];
  serverTargets?: string[];
  checks: WeaponSetCheck[];
  /** Final rows of the whole draft sequence (clone + set …); value = CSV text or nested status object. */
  rows?: { client: { table: string; path: string[]; value: unknown }[]; server: { target: string; updates: unknown }[] };
  requires?: { clientCapabilities: string[]; serverFeatures: string[] };
  runtime: string;
  /** Save only. */
  change?: DraftChange;
  changeset?: Changeset;
  status?: DraftStatus;
}

/** Both preview and write keep the HTTP 400 body (ok:false + checks) instead of throwing. */
async function setPost(url: string, body: unknown): Promise<WeaponSetResult> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (Array.isArray(data.checks)) return { ...data, ok: response.ok && data.ok !== false } as WeaponSetResult;
  return {
    ok: false, error: data.error || `HTTP ${response.status}`, runtime: "未执行",
    checks: [{ rule: "weapon.inputs", status: "问题", blocking: true, message: data.error || `HTTP ${response.status}` }],
  };
}

export const weaponSet = {
  options: () => get<WeaponSetOptions>(`${PREFIX}/set-options`),
  preview: (id: string, body: WeaponSetRequest) => setPost(`${PREFIX}/${enc(id)}/set?preview=true`, body),
  apply: async (id: string, body: WeaponSetRequest) => {
    const result = await setPost(`${PREFIX}/${enc(id)}/set`, body);
    if (result.ok) announce(id);
    return result;
  },
};
