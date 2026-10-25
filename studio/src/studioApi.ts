// P0 discovery and new-character wrappers (contracts: docs/studio/ids.md, character-clone.md, chain-views.md).
// ID / version answers are evidence queries, never reservations; formal clones still run their own collision checks.
import { Changeset, DraftStatus, get, notifyDraft, post, RuleResult, ViewList } from "./api";

const enc = encodeURIComponent;

export const ID_KINDS = [
  { id: "character", label: "角色" },
  { id: "weapon", label: "武器" },
  { id: "soul_item", label: "魂珠 / item" },
  { id: "multiball", label: "协力球" },
  { id: "unique_condition", label: "固有状态" },
  { id: "string_id", label: "文本键 string_id" },
  { id: "mana_node", label: "玛纳节点段（按角色 ID）" },
  { id: "enhancement_shop", label: "强化商品" },
] as const;
export type IdKind = (typeof ID_KINDS)[number]["id"];

export interface IdOwner { owner: string; source: "view" | "server" | "draft" | string; location: string }

export interface IdCheck {
  kind: IdKind;
  id: string;
  available: boolean;
  owners: IdOwner[];
  viewVersion: string;
  /** false: the editor was started without --server-dir, server mirrors were not consulted. */
  serverChecked: boolean;
  /** Always false: a query never reserves. */
  reserved: false;
  segment?: { characterId: string; start: string; end: string };
}

export interface IdNext extends IdCheck { skipped: { id: string; owners: IdOwner[] }[] }

export interface VersionNext {
  view: string | null;
  current: string;
  next: string;
  skipped: { version: string; source?: string; location?: string; purpose?: string; owner?: string }[];
  reservationsFile: string | null;
  reserved: Record<string, { purpose?: string; owner?: string; date?: string }>;
}

/** One of the 37 required character assets: 复用母本 / 待替换 / 已派生. */
export interface CloneAsset {
  logical: string;
  source: string;
  root: string;
  /** not_applicable: ★1–★3 special four-piece (not copied, not blocking). */
  status: "reuse" | "pending" | "derived" | "not_applicable";
  label: string;
}

/** No `rarity` (explicitly rejected) and `element` must equal the template's (cross-element clones block). */
export interface CharacterCloneRequest {
  from: string;
  to: string;
  code: string;
  skill?: "copy" | "reuse";
  element?: number;
  name?: string;
}

/** A client table the clone writes into the draft. */
export interface CloneTable { logical: string; root: string; addedKeys: string[]; size: number; sha256: string }
/** One of the five server tables a later delivery derives; baselineVerified=false without --server-dir. */
export interface CloneServerTable {
  target: string; addedKeys: string[]; baselineVerified: boolean; beforeSha256?: string; sha256?: string; size?: number;
}

export interface CloneCommon {
  ok: boolean;
  characterId: string | null;
  code?: string;
  tables?: CloneTable[];
  assets?: CloneAsset[];
  /** HTTP top-level checks are five-state (rule/status/message/blocking). */
  checks: RuleResult[];
  buildable?: boolean;
  runtime: string;
  error?: string;
}

export interface ClonePreview extends CloneCommon { preview: true; serverTables?: CloneServerTable[] }

export interface CharacterCloneResult extends CloneCommon {
  characterId: string;
  code: string;
  changeset: Changeset;
  status: DraftStatus;
  assets: CloneAsset[];
  /** false while assets are missing; delivery will still block. */
  buildable: boolean;
  scratch?: string;
}

export interface StoreExport {
  ok: true;
  version: string;
  view: string | null;
  /** `.../viewstore/production/upload`, ready for the existing builder. */
  store?: string;
  [key: string]: unknown;
}

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="wf-studio-token"]')?.content ?? "";
}

/** POST that returns the body of a 400 too (character.inputs + five-state checks) instead of throwing it away. */
async function postChecked<T extends { ok: boolean; checks: RuleResult[] }>(url: string, body: unknown): Promise<T | CloneCommon> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-WF-Studio-Token": token() },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (response.ok && data.ok !== false) return data as T;
  return {
    ok: false, characterId: data.characterId ?? null, runtime: data.runtime ?? "未执行", error: data.error ?? `HTTP ${response.status}`,
    checks: Array.isArray(data.checks) && data.checks.length ? data.checks
      : [{ rule: "character.inputs", status: "问题", blocking: true, message: data.error ?? `HTTP ${response.status}` }],
  };
}

export const isFailure = (r: { ok: boolean }): r is CloneCommon => !r.ok;

export const studio = {
  idCheck: (kind: IdKind, id: string) => get<IdCheck>(`/api/studio/ids/check?kind=${enc(kind)}&id=${enc(id)}`),
  idNext: (kind: IdKind, near?: string) =>
    get<IdNext>(`/api/studio/ids/next?kind=${enc(kind)}${near?.trim() ? "&near=" + enc(near.trim()) : ""}`),
  versionNext: (view?: string) => get<VersionNext>(`/api/studio/versions/next${view?.trim() ? "?view=" + enc(view.trim()) : ""}`),
  /** Dry run: client tables, server table plan, 37 assets and checks; writes nothing and reserves nothing. */
  previewClone: (body: CharacterCloneRequest) => postChecked<ClonePreview>("/api/studio/characters/clone?preview=true", body),
  cloneCharacter: async (body: CharacterCloneRequest) => {
    const result = await postChecked<CharacterCloneResult>("/api/studio/characters/clone", body);
    if (result.ok && result.characterId) notifyDraft(result.characterId, Promise.resolve(null));
    return result;
  },
  promoteScratch: async (sid: string, body: { to: string; code?: string }) => {
    const result = await postChecked<CharacterCloneResult>(`/api/studio/characters/${enc(sid)}/promote`, body);
    if (result.ok) {
      notifyDraft(sid, Promise.resolve(null));
      if (result.characterId) notifyDraft(result.characterId, Promise.resolve(null));
    }
    return result;
  },
  views: () => get<ViewList>("/api/studio/views"),
  /** Exports the process's current view only; `out` must not exist (never overwrites). */
  exportStore: (out: string, copy: boolean) => post<StoreExport>("/api/studio/views/export-store", { out, copy }),
};

/** Human summary of who holds an ID. */
export function ownersText(owners: IdOwner[]): string {
  const SOURCE: Record<string, string> = { view: "当前视图", server: "服务端镜像", draft: "草稿" };
  return owners.map((o) => `${SOURCE[o.source] ?? o.source} · ${o.owner}${o.location ? `（${o.location}）` : ""}`).join("；");
}
