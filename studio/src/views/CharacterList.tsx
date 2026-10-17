import { useEffect, useMemo, useState } from "preact/hooks";
import { api, CharacterSummary } from "../api";
import { href } from "../router";
import { Avatar, ElementBadge, OriginBadge, Rarity } from "./common";

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
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(() => remembered("studio.q", ""));
  const [origin, setOrigin] = useState(() => remembered("studio.origin", "all"));
  const [element, setElement] = useState(() => remembered("studio.element", "全部"));

  useEffect(() => {
    api.characters().then((data) => setItems(data.characters), (e: Error) => setError(e.message));
  }, []);
  useEffect(() => remember("studio.q", query), [query]);
  useEffect(() => remember("studio.origin", origin), [origin]);
  useEffect(() => remember("studio.element", element), [element]);

  const filtered = useMemo(() => {
    if (!items) return [];
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return items.filter((c) => {
      if (origin !== "all" && c.origin !== origin) return false;
      if (element !== "全部" && c.element !== element) return false;
      const hay = `${c.id} ${c.name} ${c.title} ${c.code}`.toLowerCase();
      return terms.every((t) => hay.includes(t));
    });
  }, [items, query, origin, element]);

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
      </div>
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
