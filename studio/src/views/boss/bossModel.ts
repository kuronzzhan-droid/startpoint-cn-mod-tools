// Plain-language helpers for the BOSS工坊 (enums, provenance labels, grouping).
import { useEffect, useState } from "preact/hooks";
import { onDraftChange, RuleResult } from "../../api";
import { boss, BOSS_ANY, BossCitation, BossDraftSummary, BossGroup, BossList, BossListItem, BossMode } from "../../bossApi";

/** quest c72/c73（副本属性 / 推荐属性）与 c68/c69（出战限定）共用的 quest 枚举：0风 1火 2水 3雷 4暗 5光。 */
export const QUEST_ELEMENTS = ["风", "火", "水", "雷", "暗", "光"];
/** 显示顺序（与角色工坊一致）。 */
export const ELEMENT_ORDER = ["火", "水", "雷", "风", "光", "暗"];
/** general_boss c0（敌人自身属性）：0 继承副本属性，1火 2水 3雷 4风 5光 6暗 —— 与 quest 枚举不同。 */
export const ENEMY_ELEMENTS = ["继承", "火", "水", "雷", "风", "光", "暗"];

export function questElement(value: string | number | null | undefined): string | null {
  const n = typeof value === "number" ? value : /^\d+$/.test(String(value ?? "")) ? Number(value) : NaN;
  return QUEST_ELEMENTS[n] ?? null;
}

export function questElementValue(name: string): number {
  return QUEST_ELEMENTS.indexOf(name);
}

export const MODE_ORDER: BossMode[] = ["main_lord", "lord", "shared", "five", "practice", "other"];
export const MODE_LABEL: Record<BossMode, string> = {
  main_lord: "主线领主战", lord: "官方领主战", shared: "共同决战", five: "五重决战", practice: "练习木人", other: "其他",
};
export const KIND_LABEL: Record<string, string> = { boss_battle: "领主战", hard_multi: "共同决战", practice: "练习木人" };

/** 「官方原版 / 补丁 1.4.146 · boss-weapon-sets / 本地草稿」 */
export function layerLabel(layer: string | null | undefined): string {
  if (!layer) return "来源未核验";
  if (layer === "store131") return "官方原版";
  if (layer === "boss-draft") return "本地草稿";
  const match = /^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-\d+-(.+?)(?:-local)?\.zip$/.exec(layer);
  return match ? `补丁 ${match[2]} · ${match[3]}` : layer;
}

export function layerClass(layer: string | null | undefined): string {
  if (!layer) return "src-unknown";
  if (layer === "store131") return "src-official";
  if (layer === "boss-draft") return "src-draft";
  return "src-patch";
}

/** Folded technical detail of one provenance record (tooltip text). */
export function citationTip(c: BossCitation | null | undefined): string {
  if (!c) return "技术细节：没有来源记录";
  const parts = [`技术细节：${c.logical}${c.leaf_path ? " · 叶 " + c.leaf_path.join("/") : ""}`];
  if (c.scope === "leaf") parts.push(`整条叶子最后一次语义变化：${c.layer ?? "—"}（不是单格首次引入层）`);
  else if (c.scope === "table") parts.push("叶子变化层未核验（只知道整表载入层）");
  else if (c.layer) parts.push(`资源层：${c.layer}`);
  if (c.table_layer) parts.push(`整表载入层：${c.table_layer}`);
  if (c.note) parts.push(c.note);
  return parts.join("\n");
}

export function present(value: string | null | undefined): boolean {
  return value !== undefined && value !== null && value !== "" && value !== "(None)";
}

export function shortName(name: string): string {
  return name.replace(/::[^:]+::/g, "").trim();
}

/** One overview card: a quest group (five tiers of a lord battle, one shared battle, a practice folder …). */
export interface GroupCard {
  key: string;
  group: BossGroup;
  items: BossListItem[];
  mode: BossMode;
  name: string;
  elements: string[];
  levels: [number, number];
  layers: string[];
  official: boolean;
  fiveTier: boolean;
  entry: BossListItem;
}

export function fiveTier(items: BossListItem[]): boolean {
  return items.length === 5 && items[0].kind === "boss_battle"
    && items.map((i) => i.path[i.path.length - 1]).sort().join(",") === "1,2,3,4,5";
}

export function groupCards(list: BossList): GroupCard[] {
  const bySelector = new Map(list.items.map((item) => [item.selector, item]));
  return list.groups.map((group) => {
    const items = group.quests.map((q) => bySelector.get(q)!).filter(Boolean);
    const levels = items.map((i) => Number(i.level)).filter((n) => !Number.isNaN(n));
    const elements = [...new Set(items.map((i) => questElement(i.recommendedElement)).filter(Boolean) as string[])];
    const layers = [...new Set(items.map((i) => i.source.layer ?? ""))];
    const entry = items.find((i) => i.bothBoss) ?? items.find((i) => !i.hidden) ?? items[0];
    return {
      key: `${group.kind}:${group.group}`, group, items, mode: group.mode, name: entry?.name || group.name,
      elements: ELEMENT_ORDER.filter((e) => elements.includes(e)),
      levels: [Math.min(...levels), Math.max(...levels)] as [number, number],
      layers, official: layers.every((l) => l === "store131"), fiveTier: fiveTier(items), entry,
    };
  });
}

export function levelText(levels: [number, number]): string {
  if (!Number.isFinite(levels[0])) return "Lv —";
  return levels[0] === levels[1] ? `Lv${levels[0]}` : `Lv${levels[0]}–${levels[1]}`;
}

/** Shared, page-lifetime cache of the boss list (the base view does not change while the editor runs). */
export function useBossList(): { list: BossList | null; error: string | null } {
  const [list, setList] = useState<BossList | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { boss.list().then(setList, (e: Error) => setError(e.message)); }, []);
  return { list, error };
}

/** Boss draft summaries, refreshed after every boss draft write. */
export function useBossDrafts(): BossDraftSummary[] | null {
  const [drafts, setDrafts] = useState<BossDraftSummary[] | null>(null);
  useEffect(() => {
    const load = () => boss.drafts().then((r) => setDrafts(r.drafts), () => setDrafts([]));
    load();
    return onDraftChange((key) => { if (key === BOSS_ANY) load(); });
  }, []);
  return drafts;
}

/** Rule ids → plain names shown next to five-state results. */
export const RULE_LABEL: Record<string, string> = {
  "boss.inputs": "请求与重放",
  "boss.multiwave-field": "多波场地（c7/c8）",
  "boss.terrain-layers": "地形每层：边界 / 站位 / 9 复活位",
  "boss.concurrent-positions": "同屏 boss 站位",
  "boss.enemy-level": "敌人等级档",
  "boss.element-preload": "改属性的召唤物预载（C8016）",
  "boss.choice-folder": "选门（folder 层）",
  "boss.both-route": "BothBoss 路由",
  "boss.custom-time": "自制内容开放时间",
  "delivery.reward-keys": "奖励键（客户端 / 服务端）",
  "boss.shop-sync": "商店三处同步",
  "art.atlas-budget": "三人房图集预算",
  "boss.visible-prerequisites": "共同决战无前置",
  "boss.unique-ids": "新 ID 撞号",
  "boss.trial-link": "试炼击破条链接",
  "capability.unknown": "客户端能力",
};

export function preloadState(checks: RuleResult[]): "none" | "pending" | "acknowledged" | "blocked-known" {
  const preload = checks.find((c) => c.rule === "boss.element-preload");
  if (!preload) {
    const summary = checks.find((c) => c.rule === "boss.inputs");
    return summary && /C8016 黑名单/.test(summary.message) ? "blocked-known" : "none";
  }
  if (preload.status === "问题") return "blocked-known";
  if (preload.status === "待验证") return preload.blocking ? "pending" : "acknowledged";
  return "none";
}
