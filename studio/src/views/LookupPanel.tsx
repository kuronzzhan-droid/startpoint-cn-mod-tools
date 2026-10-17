import { useEffect, useRef, useState } from "preact/hooks";
import { api, LookupHit } from "../api";
import { href } from "../router";

export function LookupPanel({ onClose, context }: { onClose: () => void; context?: string }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<{ total: number; count: number; results: LookupHit[]; note: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setResult(null);
      return;
    }
    setBusy(true);
    const timer = setTimeout(() => {
      api.lookup(text).then((data) => { setResult(data); setError(null); }, (e: Error) => setError(e.message))
        .finally(() => setBusy(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <aside class="lookup" aria-label="词条速查">
      <header>
        <h2>词条速查</h2>
        <button class="ghost" onClick={onClose} aria-label="收起">收起</button>
      </header>
      <p class="muted small">
        {context ? <>正在查看角色 {context}；速查只读，不会替换当前对象。</> : <>独立查询：只提供查阅。</>}
      </p>
      <input ref={input} class="search" type="search" placeholder="效果关键词、角色名或词条键，空格分隔"
        value={query} onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
      <div class="chips">
        {["攻击力", "技能伤害", "技能槽", "直接攻击", "强化弹射", "Fever"].map((k) => (
          <button class="chip" onClick={() => setQuery(k)}>{k}</button>
        ))}
      </div>
      {error ? <p class="error-text">{error}</p> : null}
      {busy ? <p class="muted small">检索中……</p> : null}
      {result ? (
        <>
          <p class="muted small">
            在 {result.total} 条能力/队长技数据行中命中 {result.count} 条{result.count > result.results.length ? `，显示前 ${result.results.length} 条` : ""}。{result.note}
          </p>
          <ul class="hits">
            {result.results.map((hit) => (
              <li>
                <a href={href({ work: "content", shop: "characters", id: hit.characterId,
                  tab: hit.slot === "队长技" || /能力 [123]$/.test(hit.slot) ? "board1" : "board2" })}>
                  <strong>{hit.characterName}</strong>
                  <span class="muted small"> {hit.characterTitle} · {hit.slot} · 行 {hit.row}</span>
                </a>
                <p>{hit.description}</p>
              </li>
            ))}
          </ul>
        </>
      ) : !query ? (
        <p class="muted small">输入关键词开始检索。结果只代表当前视图里的数据用法，不是推荐数值，也不代表已验证。</p>
      ) : null}
    </aside>
  );
}
