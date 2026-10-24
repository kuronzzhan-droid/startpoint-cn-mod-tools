import { useEffect, useRef, useState } from "preact/hooks";
import { ability } from "../api";
import { AbilityGlossary, enumEntries, FieldRule, GlossaryEntry, matches, numericMeaning } from "../abilityGlossary";
import "../glossary.css";

export function useGlossary(enabled = true) {
  const [data, setData] = useState<AbilityGlossary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    ability.glossary().then((g) => { if (active) setData(g); }, (e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [enabled]);
  return { data, error };
}

function EntryName({ entry }: { entry: GlossaryEntry }) {
  const title = [entry.officialKey, entry.officialTemplate,
    ...Object.entries(entry.officialArguments ?? {}).map(([slot, binding]) =>
      `${slot} = ${binding.text} (${binding.sources.map((s) => s.key ?? s.enumToken ?? s.text).join(" / ")})`),
    ...entry.evidence].filter(Boolean).join("\n");
  return <span title={title}>
    <span>{entry.official || entry.cn || entry.en}</span>
    {entry.official && entry.cn && entry.cn !== entry.official ? <small class="muted"> · 直译：{entry.cn}</small> : null}
    {entry.mappingStatus === "guess" ? <small class="warn-text"> · 名称推测</small> : null}
  </span>;
}

export function CellMeaning({ glossary, rule, value, row }: {
  glossary: AbilityGlossary | null; rule?: FieldRule; value: string; row: string[];
}) {
  if (!glossary || !rule || !value.trim() || value === "(None)") return null;
  if (rule.enum) return <span class="cell-meaning">
    {enumEntries(glossary, rule, value).map(({ value: v, entry }) => entry
      ? <span class="decoded-term"><EntryName entry={entry} /></span>
      : <span class="error-text">未知值 {v}</span>)}
  </span>;
  const text = numericMeaning(glossary, rule, value, row);
  return text ? <span class="cell-meaning muted" title={glossary.formats[rule.format!]?.note}>{text}</span> : null;
}

export function EnumPicker({ glossary, group, value, onPick, onClose }: {
  glossary: AbilityGlossary; group: string; value: string; onPick: (value: string) => void; onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const search = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const options = glossary.groups[group];
  const filtered = options.values.filter((e) => matches(e, query));
  useEffect(() => search.current?.focus(), []);
  useEffect(() => setCursor(0), [query]);
  useEffect(() => { list.current?.querySelector(".on")?.scrollIntoView({ block: "nearest" }); }, [cursor]);
  const onNavigate = (e: KeyboardEvent) => {
    if (e.isComposing) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.max(0, Math.min(filtered.length - 1, c + 1))); }
    if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    if (e.key === "Enter" && filtered[cursor]) { e.preventDefault(); onPick(filtered[cursor].value); }
  };
  return <div class="modal-backdrop" onClick={(e) => { if (e.currentTarget === e.target) onClose(); }}>
    <div class="modal enum-picker" role="dialog" aria-modal="true" aria-label={`按名选择：${options.label}`}
      onKeyDown={(e) => {
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); }
      }}>
      <header><h3>{options.label} · 按名选择</h3><span class="spacer" /><button class="ghost" onClick={onClose}>Esc</button></header>
      <input ref={search} class="search" type="search" aria-label="筛选枚举值" placeholder="数字 / 官方词 / 直译 / 英文构造名"
        value={query} onInput={(e) => setQuery(e.currentTarget.value)} onKeyDown={onNavigate} />
      <p class="small muted">当前值 {value || "（空）"} · {filtered.length} 项 · 点击或 Enter 选入</p>
      <ul class="picker-list" ref={list} role="listbox" aria-label={options.label} tabIndex={0} onKeyDown={onNavigate}>
        {filtered.map((entry, i) => <li role="option" class={cursor === i ? "on" : ""} aria-selected={value === entry.value}
          onMouseEnter={() => setCursor(i)} onClick={() => onPick(entry.value)}>
          <span class="mono kind">{entry.value}</span>
          <span class="kind-name"><EntryName entry={entry} /><small class="muted enum-en">{entry.en}</small></span>
          <span class="small muted">使用 {entry.uses}</span>
        </li>)}
      </ul>
      {!filtered.length ? <p class="muted small">没有匹配的类型</p> : null}
      <p class="small muted">{glossary.note}</p>
    </div>
  </div>;
}

export function TypeLookup() {
  const { data, error } = useGlossary();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.focus(), []);
  const hits = data ? Object.entries(data.groups).filter(([id]) => !group || id === group)
    .flatMap(([id, g]) => g.values.filter((e) => matches(e, query)).map((entry) => ({ id, label: g.label, entry }))) : [];
  return <div class="type-lookup">
    <input ref={input} class="search" type="search" aria-label="查类型" placeholder="官方中文 / 直译 / 英文 / 数字"
      value={query} onInput={(e) => setQuery(e.currentTarget.value)} />
    <label class="small">组 / 区块 <select value={group} onChange={(e) => setGroup(e.currentTarget.value)}>
      <option value="">全部</option>
      {data && Object.entries(data.groups).map(([id, g]) => <option value={id}>{g.label}</option>)}
    </select></label>
    {error ? <p class="error-text">词汇表读取失败：{error}</p> : !data ? <p class="muted small">正在读取词汇表……</p> : <>
      <p class="small muted">匹配 {hits.length} 项{hits.length > 150 ? "，显示前 150 项，请缩小查询范围" : ""}。{data.note}</p>
      <ul class="hits">
        {hits.slice(0, 150).map(({ id, label, entry }) => <li key={`${id}:${entry.value}`}>
          <div class="small muted">{label} · 值 <span class="mono">{entry.value}</span> · 使用 {entry.uses}</div>
          <p><EntryName entry={entry} /></p>
          <span class="mono small muted">{entry.en}</span>
        </li>)}
      </ul>
    </>}
  </div>;
}
