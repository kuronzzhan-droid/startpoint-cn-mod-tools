import { useEffect, useMemo, useState } from "preact/hooks";
import { api, CharacterSummary } from "../api";
import { href } from "../router";
import { Avatar, ElementBadge, OriginBadge, Rarity } from "./common";
import { useClientProfile } from "../clientProfile";
import { neededProfiles, useCharacterCompat } from "./ClientProfile";

const ORIGINS: { id: string; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "new", label: "新增 MOD" },
  { id: "modified", label: "改版官方" },
  { id: "official", label: "官方原版" },
];
const ELEMENTS = ["全部", "火", "水", "雷", "风", "光", "暗"];

function remembered(key: string, fallback: string): string {
  try {
    return sessionStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}
function remember(key: string, value: string) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* storage unavailable: ignore */
  }
}

export function CharacterList() {
  const [items, setItems] = useState<CharacterSummary[] | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(() => remembered("studio.q", ""));
  const [origin, setOrigin] = useState(() => remembered("studio.origin", "all"));
  const [element, setElement] = useState(() => remembered("studio.element", "全部"));
  const [onlyNeeds, setOnlyNeeds] = useState(() => remembered("studio.needsProfile", "") === "1");
  const profile = useClientProfile();
  const compat = useCharacterCompat();
  const fallback = profile.profiles?.defaultClientProfile;
  const needs = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const cid of Object.keys(compat.report?.characters ?? {})) {
      const list = neededProfiles(compat.report, cid, fallback);
      if (list.length) out[cid] = list;
    }
    return out;
  }, [compat.report, fallback]);
  // Name the filter after the profile those characters need (e.g. 「只看需要 v35e 的角色」).
  const needLabel = profile.label(Object.values(needs)[0]?.[0] ?? (profile.profiles?.profiles.find((p) => !p.default)?.id));

  useEffect(() => {
    api.characters().then((data) => { setItems(data.characters); setVersion(data.version); }, (e: Error) => setError(e.message));
  }, []);
  useEffect(() => remember("studio.q", query), [query]);
  useEffect(() => remember("studio.origin", origin), [origin]);
  useEffect(() => remember("studio.element", element), [element]);
  useEffect(() => remember("studio.needsProfile", onlyNeeds ? "1" : ""), [onlyNeeds]);

  const filtered = useMemo(() => {
    if (!items) return [];
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return items.filter((c) => {
      if (origin !== "all" && c.origin !== origin) return false;
      if (element !== "全部" && c.element !== element) return false;
      if (onlyNeeds && !needs[c.id]) return false;
      const hay = `${c.id} ${c.name} ${c.title} ${c.code}`.toLowerCase();
      return terms.every((t) => hay.includes(t));
    });
  }, [items, query, origin, element, onlyNeeds, needs]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: items?.length ?? 0 };
    for (const c of items ?? []) result[c.origin] = (result[c.origin] ?? 0) + 1;
    return result;
  }, [items]);

  return (
    <section class="page">
      <div class="page-head">
        <div>
          <h1>找到要修改的角色</h1>
          <p class="muted">按角色名、称号、ID 或代码名搜索。打开角色只是查看，本版不会写入任何数据。</p>
        </div>
        <a class="header-btn" href={href({ work: "content", shop: "characters", balance: true })}>平衡表导入</a>
        <a class="header-btn primary-link" href={href({ work: "content", shop: "characters", clone: true })}
          title="新 ID 的正式角色草稿：表行与资产引用来自母本">＋ 从母本克隆新角色</a>
      </div>
      <div class="search-row">
        <input
          class="search"
          type="search"
          placeholder="搜索角色名、称号、ID……"
          value={query}
          onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
          autoFocus
        />
      </div>
      <div class="filters">
        <div class="segmented" role="group" aria-label="来源">
          {ORIGINS.map((o) => (
            <button class={origin === o.id ? "on" : ""} onClick={() => setOrigin(o.id)}>
              {o.label}
              <span class="count">{counts[o.id] ?? 0}</span>
            </button>
          ))}
        </div>
        <div class="segmented" role="group" aria-label="属性">
          {ELEMENTS.map((e) => (
            <button class={element === e ? "on" : ""} onClick={() => setElement(e)}>
              {e}
            </button>
          ))}
        </div>
        <label class="profile-filter" title={compat.report
          ? `依据全角色兼容报告 ${compat.report.source}（资源版本 ${compat.report.tip}，离线静态结果）：默认客户端 ${profile.label(fallback)} 缺能力的角色。草稿里的改动以「生成」时的检查为准。`
          : compat.error ?? "正在读取全角色兼容报告……"}>
          <input type="checkbox" checked={onlyNeeds} disabled={!compat.report}
            onChange={(e) => setOnlyNeeds((e.target as HTMLInputElement).checked)} />
          只看需要 {needLabel} 的角色 <span class="count">{Object.keys(needs).length}</span>
        </label>
      </div>
      {onlyNeeds && compat.report ? (
        <p class="small muted">按全角色兼容报告（资源版本 {compat.report.tip}）：这些角色在 {profile.label(fallback)} 上缺客户端能力，只能发给装了 {needLabel} 的玩家。
          {version && version !== compat.report.tip ? <span class="warn-text"> 当前视图是 {version}，报告之后新增或改过的角色以「生成」时的检查为准。</span> : null}</p>
      ) : null}
      {compat.error ? <p class="small error-text">全角色兼容报告读取失败：{compat.error}</p> : null}
      {error ? <div class="notice error">角色列表读取失败：{error}</div> : null}
      {!items && !error ? <div class="loading">正在读取角色列表……</div> : null}
      {items ? (
        <>
          <div class="result-count muted">共 {filtered.length} 个角色</div>
          <ul class="char-grid">
            {filtered.slice(0, 400).map((c) => (
              <li>
                <a class="char-card" href={href({ work: "content", shop: "characters", id: c.id })}>
                  <Avatar id={c.id} element={c.element} />
                  <div class="char-main">
                    <div class="char-name">
                      <ElementBadge element={c.element} />
                      {c.name}
                      <Rarity value={c.rarity} />
                    </div>
                    <div class="char-title muted">{c.title || "（无称号）"}</div>
                  </div>
                  <div class="char-side">
                    <OriginBadge origin={c.origin} />
                    {needs[c.id] ? (
                      <span class={"cap-chip " + (profile.selected && needs[c.id].includes(profile.selected) ? "needs" : "miss")}
                        title={`${profile.label(fallback)} 缺：` + (compat.report?.characters[c.id]?.profiles[fallback ?? ""]?.missing ?? []).map((m) => m.title).join("、")}>
                        需要 {profile.label(needs[c.id][0])}
                      </span>
                    ) : null}
                    <span class="char-id">{c.id}</span>
                  </div>
                </a>
              </li>
            ))}
          </ul>
          {filtered.length > 400 ? <p class="muted">只显示前 400 个结果，请继续输入以缩小范围。</p> : null}
        </>
      ) : null}
    </section>
  );
}
