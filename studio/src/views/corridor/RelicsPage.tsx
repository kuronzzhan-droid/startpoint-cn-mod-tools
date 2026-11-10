import { useEffect, useState } from "preact/hooks";
import { corridor, Json, RelicEntry, Tombstone } from "../../corridorApi";
import { Notice } from "../common";
import { FindingList, RelicEffectsEditor, Tag, useCorridor } from "./widgets";

interface Draft { rarity: string; name: string; desc: string; name_en: string; desc_en: string; effects: Record<string, Json>[];
  policy: Record<string, Json> }

function draftOf(r: RelicEntry): Draft {
  return { rarity: String(r.relic.rarity), name: r.zh.name ?? String(r.relic.name ?? ""), desc: r.zh.desc ?? String(r.relic.desc ?? ""),
    name_en: r.en.name ?? "", desc_en: r.en.desc ?? "", effects: JSON.parse(JSON.stringify(r.effects)), policy: { ...r.policy } };
}

export function RelicsPage({ id }: { id?: string }) {
  const { run, tick, registry, setError } = useCorridor();
  const [data, setData] = useState<{ relics: RelicEntry[]; tombstones: Tombstone[] } | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [filter, setFilter] = useState("");
  const [template, setTemplate] = useState("gold_on_pickup");
  useEffect(() => { corridor.relics().then(setData, (e: Error) => setError(e.message)); }, [tick]);
  const current = data?.relics.find((r) => r.relic.relic_id === id) ?? null;
  useEffect(() => { setDraft(current ? draftOf(current) : null); }, [current ? JSON.stringify(current) : "", id]);
  if (!data || !registry) return <div class="loading">读取遗物…</div>;
  const list = data.relics.filter((r) => !filter || JSON.stringify([r.relic.relic_id, r.relic.name, r.relic.rarity]).includes(filter));
  const go = (rid: string) => { location.hash = `#/corridor/relics/${encodeURIComponent(rid)}`; };
  const save = async () => {
    if (!current || !draft) return;
    const base = draftOf(current);
    const cmd: Record<string, Json> = { op: "relic.update", relic_id: String(current.relic.relic_id) };
    for (const k of ["rarity", "name", "desc", "name_en", "desc_en"] as const) if (draft[k] !== base[k]) cmd[k] = draft[k];
    if (JSON.stringify(draft.effects) !== JSON.stringify(base.effects)) cmd.effects = draft.effects;
    const policy: Record<string, Json> = {};
    for (const k of new Set([...Object.keys(base.policy), ...Object.keys(draft.policy)])) {
      if (JSON.stringify(base.policy[k]) !== JSON.stringify(draft.policy[k])) policy[k] = draft.policy[k] ?? null;
    }
    if (Object.keys(policy).length) cmd.policy = policy;
    if (Object.keys(cmd).length > 2) await run([cmd], `遗物 ${current.relic.relic_id}`);
  };
  const dirty = current && draft && JSON.stringify(draft) !== JSON.stringify(draftOf(current));
  const setPolicy = (key: string, value: Json) => {
    if (!draft) return;
    const policy = { ...draft.policy };
    if (value === null || value === "") delete policy[key]; else policy[key] = value;
    setDraft({ ...draft, policy });
  };
  return (
    <div class="cor-split">
      <div>
        <div class="cor-toolbar" style="margin-bottom:8px">
          <input type="search" placeholder="筛选" value={filter} onInput={(e) => setFilter((e.currentTarget as HTMLInputElement).value)} />
        </div>
        <div class="cor-toolbar" style="margin-bottom:8px">
          <select value={template} onChange={(e) => setTemplate((e.currentTarget as HTMLSelectElement).value)}>
            {registry.templates.relics.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <button class="primary" onClick={async () => {
            const r = await run([{ op: "relic.create", template }], "新建遗物");
            const rid = r?.results[0]?.relic_id;
            if (rid) go(String(rid));
          }}>＋ 从模板新建</button>
        </div>
        <div class="cor-list">
          {list.map((r) => {
            const rid = String(r.relic.relic_id);
            const blocks = r.findings.filter((f) => f.severity === "block").length;
            return (
              <button key={rid} class={rid === id ? "active" : ""} onClick={() => go(rid)}>
                <span class="id">{rid}</span>
                <span style="flex:1">{String(r.relic.name)}</span>
                <span class="muted small">{registry.rarities[String(r.relic.rarity)]}</span>
                {r.combat ? <Tag kind="warn">战斗</Tag> : null}
                {blocks ? <Tag kind="bad">{blocks}</Tag> : null}
              </button>
            );
          })}
        </div>
        {data.tombstones.length ? (
          <details class="small" style="margin-top:8px"><summary>已退休 ID（{data.tombstones.length}，永不复用）</summary>
            {data.tombstones.map((t) => <div key={t.id}>{t.id} · r{t.at_revision} · {t.reason}</div>)}</details>
        ) : null}
      </div>
      <div>
        {!current || !draft ? <Notice>从左侧选择一件遗物，或从模板新建。新 ID 由后端分配（已删除的 ID 永不复用）。</Notice> : (
          <div class="cor-card">
            <h3>{String(current.relic.relic_id)} · {draft.name}
              {current.settled.ok ? <Tag kind="ok">服务端可加载</Tag> : <Tag kind="bad">服务端会丢弃</Tag>}
              {current.combat ? <Tag kind="warn" title="runtime=client_pending">客户端效果</Tag> : null}
            </h3>
            <div class="cor-form">
              <label>稀有度</label>
              <select value={draft.rarity} onChange={(e) => setDraft({ ...draft, rarity: (e.currentTarget as HTMLSelectElement).value })}>
                {Object.entries(registry.rarities).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <label>名称（中）</label><input value={draft.name} onInput={(e) => setDraft({ ...draft, name: (e.currentTarget as HTMLInputElement).value })} />
              <label>名称（英）</label><input value={draft.name_en} placeholder="待补（空则阻断发布）"
                onInput={(e) => setDraft({ ...draft, name_en: (e.currentTarget as HTMLInputElement).value })} />
              <label>说明（中）</label><textarea value={draft.desc} onInput={(e) => setDraft({ ...draft, desc: (e.currentTarget as HTMLTextAreaElement).value })} />
              <label>说明（英）</label><textarea value={draft.desc_en} placeholder="待补（空则阻断发布）"
                onInput={(e) => setDraft({ ...draft, desc_en: (e.currentTarget as HTMLTextAreaElement).value })} />
              <label>效果</label>
              <RelicEffectsEditor effects={draft.effects} registry={registry} onChange={(effects) => setDraft({ ...draft, effects })} />
              <label>服务端结算</label>
              <div class="small">{current.settled.ok ? current.settled_text.join("；") : <span class="error-text">{current.settled.reason}</span>}
                <span class="muted">（保存后刷新）</span></div>
              <label title="服务端未接入，非默认值发布被阻断">候选策略</label>
              <div class="cor-toolbar small">
                <label><input type="checkbox" checked={draft.policy.enabled === false}
                  onChange={(e) => setPolicy("enabled", (e.currentTarget as HTMLInputElement).checked ? false : null)} /> 暂不投放</label>
                最早幕 <select value={String(draft.policy.min_act ?? "")} onChange={(e) => {
                  const v = (e.currentTarget as HTMLSelectElement).value;
                  setPolicy("min_act", v ? Number(v) : null);
                }}><option value="">不限</option>{[1, 2, 3].map((a) => <option key={a} value={a}>{a}</option>)}</select>
                <input type="text" placeholder="备注" value={String(draft.policy.notes ?? "")}
                  onInput={(e) => setPolicy("notes", (e.currentTarget as HTMLInputElement).value)} />
              </div>
            </div>
            <div class="cor-toolbar" style="margin-top:10px">
              <button class="primary" disabled={!dirty} onClick={save}>保存</button>
              <button disabled={!dirty} onClick={() => setDraft(draftOf(current))}>撤销未保存</button>
              <button onClick={async () => {
                const r = await run([{ op: "relic.duplicate", relic_id: String(current.relic.relic_id) }], "复制遗物");
                const rid = r?.results[0]?.relic_id;
                if (rid) go(String(rid));
              }}>复制</button>
              <button onClick={async () => {
                const reason = window.prompt(`删除并退休 ${current.relic.relic_id}（ID 永不复用）。理由：`, "不再投放");
                if (reason === null) return;
                const r = await run([{ op: "relic.delete", relic_id: String(current.relic.relic_id), reason }], "删除遗物");
                if (r) location.hash = "#/corridor/relics";
              }}>删除（退休）</button>
            </div>
            <h4>问题</h4>
            <FindingList findings={current.findings} />
          </div>
        )}
      </div>
    </div>
  );
}
