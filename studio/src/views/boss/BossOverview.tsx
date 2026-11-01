import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { BossDraftSummary, BossListItem, BossMode } from "../../bossApi";
import { href } from "../../router";
import { ElementBadge, Notice } from "../common";
import {
  citationTip, ELEMENT_ORDER, GroupCard, groupCards, layerClass, layerLabel, levelText, MODE_LABEL, MODE_ORDER,
  questElement, useBossDrafts, useBossList,
} from "./bossModel";

function remembered(key: string, fallback: string): string {
  try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function remember(key: string, value: string) {
  try { sessionStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

const ORIGINS = [{ id: "all", label: "全部来源" }, { id: "mod", label: "MOD 新增 / 改动" }, { id: "official", label: "官方原版" }];

const questLink = (selector: string, tab?: string) => href({ work: "content", shop: "boss", quest: selector, tab });

/** 方向键在卡片之间移动焦点（网格按阅读顺序）。 */
function moveFocus(event: KeyboardEvent) {
  const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
  if (!(event.key in keys)) return;
  const cards = [...document.querySelectorAll<HTMLAnchorElement>(".boss-overview a.boss-card")];
  const index = cards.indexOf(document.activeElement as HTMLAnchorElement);
  if (index < 0) return;
  event.preventDefault();
  cards[Math.max(0, Math.min(cards.length - 1, index + keys[event.key]))]?.focus();
}

export function BossOverview() {
  const { list, error } = useBossList();
  const drafts = useBossDrafts();
  const [query, setQuery] = useState(() => remembered("boss.q", ""));
  const [mode, setMode] = useState(() => remembered("boss.mode", "all"));
  const [element, setElement] = useState(() => remembered("boss.element", "全部"));
  const [origin, setOrigin] = useState(() => remembered("boss.origin", "all"));
  const [onlyDrafts, setOnlyDrafts] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => remember("boss.q", query), [query]);
  useEffect(() => remember("boss.mode", mode), [mode]);
  useEffect(() => remember("boss.element", element), [element]);
  useEffect(() => remember("boss.origin", origin), [origin]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = (event.target as HTMLElement)?.closest?.("input, textarea, select");
      if (event.key === "/" && !typing) { event.preventDefault(); search.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const cards = useMemo(() => (list ? groupCards(list) : []), [list]);
  const draftIds = useMemo(() => new Set((drafts ?? []).map((d) => d.characterId)), [drafts]);
  const hasDraft = (card: GroupCard) => card.items.some((i) => draftIds.has(i.selector) || draftIds.has(i.id));

  const filtered = useMemo(() => {
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return cards.filter((card) => {
      if (mode !== "all" && card.mode !== mode) return false;
      if (element !== "全部" && !card.elements.includes(element)) return false;
      if (origin === "official" && !card.official) return false;
      if (origin === "mod" && card.official) return false;
      if (onlyDrafts && !hasDraft(card)) return false;
      const hay = [card.name, card.group.group, ...card.items.flatMap((i) => [i.name, i.id, i.selector, i.fieldData])]
        .join(" ").toLowerCase();
      return terms.every((t) => hay.includes(t));
    });
  }, [cards, query, mode, element, origin, onlyDrafts, draftIds]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: cards.length };
    for (const card of cards) result[card.mode] = (result[card.mode] ?? 0) + 1;
    return result;
  }, [cards]);

  const known = new Set(list?.items.flatMap((i) => [i.selector, i.id]) ?? []);
  const newDrafts = (drafts ?? []).filter((d) => !known.has(d.characterId));
  const rules = Object.fromEntries((list?.modes ?? []).map((m) => [m.id, m.rule]));

  return (
    <section class="page boss-overview">
      <div class="page-head">
        <div>
          <h1>BOSS工坊</h1>
          <p class="muted">按模式找到副本。打开只是查看；改等级、倍率、属性、BGM、场景会写进本地草稿，生成后才是测试补丁。</p>
        </div>
        <a class="header-btn primary-link" href={href({ work: "content", shop: "boss", wizard: true })}>＋ 新建共同决战</a>
      </div>
      <div class="search-row">
        <a class="header-btn" href={questLink("five-structure")}>五重决战 · 结构</a>
        <a class="header-btn" href={questLink("rogue")}>深渊连战</a>
        <input ref={search} class="search" type="search" value={query} autoFocus
          placeholder="搜索 boss 名、quest ID、场景" title="按 / 聚焦；回车打开第一个结果；↓ 进入卡片，方向键移动"
          onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && filtered[0]) location.hash = questLink(filtered[0].entry.selector);
            if (e.key === "ArrowDown") { e.preventDefault(); document.querySelector<HTMLAnchorElement>(".boss-overview a.boss-card")?.focus(); }
          }} />
      </div>
      <div class="filters">
        <div class="segmented" role="group" aria-label="模式">
          <button class={mode === "all" ? "on" : ""} aria-pressed={mode === "all"} onClick={() => setMode("all")}>全部<span class="count">{counts.all ?? 0}</span></button>
          {MODE_ORDER.filter((m) => counts[m]).map((m) => (
            <button class={mode === m ? "on" : ""} aria-pressed={mode === m} title={rules[m]} onClick={() => setMode(m)}>
              {MODE_LABEL[m]}<span class="count">{counts[m]}</span>
            </button>
          ))}
        </div>
        <div class="segmented" role="group" aria-label="属性">
          {["全部", ...ELEMENT_ORDER].map((e) => (
            <button class={element === e ? "on" : ""} aria-pressed={element === e} onClick={() => setElement(e)}>{e}</button>
          ))}
        </div>
        <div class="segmented" role="group" aria-label="来源">
          {ORIGINS.map((o) => (
            <button class={origin === o.id ? "on" : ""} aria-pressed={origin === o.id} onClick={() => setOrigin(o.id)}>{o.label}</button>
          ))}
        </div>
        <label class="check"><input type="checkbox" checked={onlyDrafts} onChange={(e) => setOnlyDrafts((e.target as HTMLInputElement).checked)} />只看有草稿</label>
      </div>
      {error ? <Notice kind="error">副本列表读取失败：{error}</Notice> : null}
      {!list && !error ? <div class="loading">正在读取副本列表……</div> : null}

      {newDrafts.length && (mode === "all" || mode === "shared") ? (
        <section class="boss-section">
          <h2>新建中的共同决战 <span class="count">{newDrafts.length}</span></h2>
          <p class="small muted">只在本地草稿里，还没进任何补丁；生成交付后也不会自动上测试服。</p>
          <ul class="boss-grid" onKeyDown={moveFocus}>
            {newDrafts.map((d) => <li><NewDraftCard draft={d} /></li>)}
          </ul>
        </section>
      ) : null}

      {list ? (
        <>
          <div class="result-count muted">
            共 {filtered.length} 组副本（{filtered.reduce((n, c) => n + c.items.length, 0)} 个难度）
            <span class="small"> · 视图 {list.version} 的客户端表；不代表服务端已开放</span>
          </div>
          {MODE_ORDER.map((m) => {
            const section = filtered.filter((c) => c.mode === m);
            if (!section.length) return null;
            return (
              <section class="boss-section">
                <h2 title={rules[m]}>{MODE_LABEL[m]} <span class="count">{section.length}</span></h2>
                {m === "five" ? <p class="small muted">五重入口只是路由（BothBoss），只读；真正的战斗是它指向的隐藏关。</p> : null}
                {m === "main_lord" ? <p class="small muted">补讨伐的主线 boss，每个 5 档；可以按档改，也可以五档一起改。</p> : null}
                <ul class="boss-grid" onKeyDown={moveFocus}>
                  {section.map((card) => <li><BossCardView card={card} draft={hasDraft(card)} /></li>)}
                </ul>
              </section>
            );
          })}
          {!filtered.length ? <Notice>没有匹配的副本。换个关键词，或把筛选切回「全部」。</Notice> : null}
          <p class="small muted">深渊连战、练习关之外的活动副本不在本期读模型里。</p>
        </>
      ) : null}
    </section>
  );
}

function BossCardView({ card, draft }: { card: GroupCard; draft: boolean }) {
  const hiddenCount = card.items.filter((i) => i.hidden).length;
  const layer = card.layers.length === 1 ? card.layers[0] : card.layers.find((l) => l !== "store131") ?? card.layers[0];
  const size = card.mode === "five"
    ? `入口只读 · 隐藏关 ${hiddenCount}`
    : card.fiveTier ? "5 档" : card.items.length > 1 ? `${card.items.length} 个难度` : "1 关";
  return (
    <a class={"boss-card" + (card.mode === "five" ? " readonly" : "")} href={questLink(card.entry.selector)}
      title={`${card.name}（${card.group.kind} ${card.group.group}）`}>
      <span class="boss-els">
        {card.elements.length ? card.elements.map((e) => <ElementBadge element={e} />) : <ElementBadge element="—" />}
      </span>
      <span class="boss-card-main">
        <span class="boss-card-name">{card.name}</span>
        <span class="small muted">{size} · {levelText(card.levels)}</span>
      </span>
      <span class="boss-card-side">
        <span class={"src-pill " + layerClass(layer)} title={citationTip(card.entry.source)}>
          {layerLabel(layer)}{card.layers.length > 1 ? ` 等 ${card.layers.length} 个来源` : ""}
        </span>
        <span class="char-id">{card.group.kind === "practice" ? "练习 " : ""}{card.group.group}</span>
        {draft ? <span class="pill pendingpill">有草稿</span> : null}
      </span>
    </a>
  );
}

function NewDraftCard({ draft }: { draft: BossDraftSummary }) {
  return (
    <a class="boss-card draft" href={questLink(draft.characterId)}>
      <span class="boss-els"><ElementBadge element="新" /></span>
      <span class="boss-card-main">
        <span class="boss-card-name">{draft.created?.name ?? "（未命名）"}</span>
        <span class="small muted">模板来源 {draft.created?.sourceQuest ?? "—"}</span>
      </span>
      <span class="boss-card-side">
        <span class={"src-pill src-draft"}>本地草稿</span>
        <span class="char-id">quest {draft.characterId}</span>
        <span class={"pill " + (draft.status.state === "saved" ? "draftable" : "warnpill")}>{draft.status.label}</span>
      </span>
    </a>
  );
}

export function elementOf(item: BossListItem): string {
  return questElement(item.recommendedElement) ?? "—";
}

export type { BossMode };
