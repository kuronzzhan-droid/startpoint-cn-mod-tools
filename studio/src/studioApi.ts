// P0 discovery and new-character wrappers (contracts: docs/studio/ids.md, character-clone.md, chain-views.md).
// ID / version answers are evidence queries, never reservations; formal clones still run their own collision checks.
import { Changeset, DraftCheck, DraftStatus, get, notifyDraft, post } from "./api";

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
  status: "reuse" | "pending" | "derived";
  label: string;
}

export interface CharacterCloneRequest {
  from: string;
  to: string;
  code: string;
  skill?: "copy" | "reuse";
  element?: number;
  name?: string;
}

export interface CharacterCloneResult {
  ok: boolean;
  characterId: string;
  code: string;
  changeset: Changeset;
  status: DraftStatus;
  assets: CloneAsset[];
  checks: DraftCheck[];
  /** false while assets are missing; delivery will still block. */
  buildable: boolean;
  runtime: string;
  scratch?: string;
}

/** Tables a clone writes (character-clone.md); optional ones only when the template has rows. */
export const CLONE_TABLES = {
  required: ["character", "character_status", "character_text", "mana_board", "mana_node", "character_image",
    "full_shot_image_attribute", "trimmed_image", "character_speech", "skill_preview_character"],
  optional: ["character_gacha_sound", "character_awake_status", "upskill", "mana_board2_open_condition", "character_stance_detail"],
};

/** Native element order of the clone request: 0..5 = 火水雷风光暗. */
export const CLONE_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];

export const studio = {
  idCheck: (kind: IdKind, id: string) => get<IdCheck>(`/api/studio/ids/check?kind=${enc(kind)}&id=${enc(id)}`),
  idNext: (kind: IdKind, near?: string) =>
    get<IdNext>(`/api/studio/ids/next?kind=${enc(kind)}${near?.trim() ? "&near=" + enc(near.trim()) : ""}`),
  versionNext: (view?: string) => get<VersionNext>(`/api/studio/versions/next${view?.trim() ? "?view=" + enc(view.trim()) : ""}`),
  cloneCharacter: async (body: CharacterCloneRequest) => {
    const result = await post<CharacterCloneResult>("/api/studio/characters/clone", body);
    notifyDraft(result.characterId, Promise.resolve(null));
    return result;
  },
  promoteScratch: async (sid: string, body: { to: string; code?: string }) => {
    const result = await post<CharacterCloneResult>(`/api/studio/characters/${enc(sid)}/promote`, body);
    notifyDraft(sid, Promise.resolve(null));
    notifyDraft(result.characterId, Promise.resolve(null));
    return result;
  },
};

/** Human summary of who holds an ID. */
export function ownersText(owners: IdOwner[]): string {
  const SOURCE: Record<string, string> = { view: "当前视图", server: "服务端镜像", draft: "草稿" };
  return owners.map((o) => `${SOURCE[o.source] ?? o.source} · ${o.owner}${o.location ? `（${o.location}）` : ""}`).join("；");
}
