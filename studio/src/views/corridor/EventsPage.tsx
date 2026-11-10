import { useEffect, useState } from "preact/hooks";
import { corridor, EventEntry, Json, Tombstone } from "../../corridorApi";
import { Notice } from "../common";
import { EventEffectsEditor, FindingList, RequiresEditor, Tag, useCorridor } from "./widgets";

interface OptDraft { option_id: string; label: string; label_en: string; effects: Record<string, Json>[]; requires: Record<string, number> | null }
interface Draft { title: string; text: string; title_en: string; text_en: string; options: OptDraft[]; policy: Record<string, Json> }

function draftOf(e: EventEntry): Draft {
  return {
    title: e.zh.title ?? String(e.event.title ?? ""), text: e.zh.text ?? String(e.event.text ?? ""),
    title_en: e.en.title ?? "", text_en: e.en.text ?? "", policy: { ...e.policy },
    options: e.options.map((o) => ({ option_id: String(o.option_id), label: o.zh ?? String(o.option.label ?? ""), label_en: o.en ?? "",
      effects: JSON.parse(JSON.stringify(o.option.effects ?? [])), requires: (o.option.requires as Record<string, number>) ?? null })),
  };
}

export function EventsPage({ id }: { id?: string }) {
  const { run, tick, registry, setError } = useCorridor();
  const [data, setData] = useState<{ events: EventEntry[]; tombstones: Tombstone[] } | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [template, setTemplate] = useState("gold_or_leave");
  useEffect(() => { corridor.events().then(setData, (e: Error) => setError(e.message)); }, [tick]);
  const current = data?.events.find((e) => e.event.event_id === id) ?? null;
  useEffect(() => { setDraft(current ? draftOf(current) : null); }, [current ? JSON.stringify(current) : "", id]);
  if (!data || !registry) return <div class="loading">读取事件…</div>;
  const go = (eid: string) => { location.hash = `#/corridor/events/${encodeURIComponent(eid)}`; };
  const eid = current ? String(current.event.event_id) : "";
  const base = current ? draftOf(current) : null;
  const dirty = !!(draft && base && JSON.stringify(draft) !== JSON.stringify(base));
  const save = async () => {
    if (!draft || !base) return;
    const commands: Record<string, Json>[] = [];
    const ev: Record<string, Json> = { op: "event.update", event_id: eid };
    for (const k of ["title", "text", "title_en", "text_en"] as const) if (draft[k] !== base[k]) ev[k] = draft[k];
    const policy: Record<string, Json> = {};
    for (const k of new Set([...Object.keys(base.policy), ...Object.keys(draft.policy)])) {
      if (JSON.stringify(base.policy[k]) !== JSON.stringify(draft.policy[k])) policy[k] = draft.policy[k] ?? null;
    }
    if (Object.keys(policy).length) ev.policy = policy;
    if (Object.keys(ev).length > 2) commands.push(ev);
    draft.options.forEach((o, i) => {
      const b = base.options[i];
      const cmd: Record<string, Json> = { op: "event.option.update", event_id: eid, option_id: o.option_id };
      if (o.label !== b.label) cmd.label = o.label;
      if (o.label_en !== b.label_en) cmd.label_en = o.label_en;
      if (JSON.stringify(o.effects) !== JSON.stringify(b.effects)) cmd.effects = o.effects;
      if (JSON.stringify(o.requires) !== JSON.stringify(b.requires)) cmd.requires = o.requires;
      if (Object.keys(cmd).length > 3) commands.push(cmd);
    });
    if (commands.length) await run(commands, `事件 ${eid}`);
  };
  const setOpt = (i: number, patch: Partial<OptDraft>) => draft && setDraft({ ...draft, options: draft.options.map((o, j) => (j === i ? { ...o, ...patch } : o)) });
  const structural = (cmd: Record<string, Json>, label: string) => {
    if (dirty && !window.confirm("有未保存的文字/效果修改，继续会丢弃它们。继续？")) return;
    run([cmd], label);
  };
  return (
    <div class="cor-split">
      <div>
        <div class="cor-toolbar" style="margin-bottom:8px">
          <select value={template} onChange={(e) => setTemplate((e.currentTarget as HTMLSelectElement).value)}>
            {registry.templates.events.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <button class="primary" onClick={async () => {
            const r = await run([{ op: "event.create", template }], "新建事件");
            const id2 = r?.results[0]?.event_id;
            if (id2) go(String(id2));
          }}>＋ 从模板新建</button>
        </div>
        <div class="cor-list">
          {data.events.map((e) => {
            const id2 = String(e.event.event_id);
            const blocks = e.findings.filter((f) => f.severity === "block").length;
            return (
              <button key={id2} class={id2 === id ? "active" : ""} onClick={() => go(id2)}>
                <span class="id">{id2}</span><span style="flex:1">{String(e.event.title)}</span>
                <span class="muted small">{e.options.length} 项</span>
                {!e.settled.ok ? <Tag kind="bad">丢弃</Tag> : null}{blocks ? <Tag kind="bad">{blocks}</Tag> : null}
              </button>
            );
          })}
        </div>
        {data.tombstones.length ? (
          <details class="small" style="margin-top:8px"><summary>已退休 ID（{data.tombstones.length}）</summary>
            {data.tombstones.map((t) => <div key={t.id}>{t.kind} {t.id} · r{t.at_revision} · {t.reason}</div>)}</details>
        ) : null}
      </div>
      <div>
        {!current || !draft ? <Notice>从左侧选择事件，或从模板新建。选项有稳定 ID：重排后编译器重建 option.N 文本键，中英文本随选项移动。</Notice> : (
          <div class="cor-card">
            <h3>{eid} · {draft.title}
              {current.settled.ok ? <Tag kind="ok">服务端可加载</Tag> : <Tag kind="bad" title={current.settled.reason}>服务端会丢弃</Tag>}</h3>
            <div class="cor-form">
              <label>标题（中）</label><input value={draft.title} onInput={(e) => setDraft({ ...draft, title: (e.currentTarget as HTMLInputElement).value })} />
              <label>标题（英）</label><input value={draft.title_en} placeholder="待补" onInput={(e) => setDraft({ ...draft, title_en: (e.currentTarget as HTMLInputElement).value })} />
              <label>正文（中）</label><textarea value={draft.text} onInput={(e) => setDraft({ ...draft, text: (e.currentTarget as HTMLTextAreaElement).value })} />
              <label>正文（英）</label><textarea value={draft.text_en} placeholder="待补" onInput={(e) => setDraft({ ...draft, text_en: (e.currentTarget as HTMLTextAreaElement).value })} />
              <label title="服务端未接入，非默认值发布被阻断">候选策略</label>
              <div class="cor-toolbar small">
                最早幕 <select value={String(draft.policy.min_act ?? "")} onChange={(e) => {
                  const v = (e.currentTarget as HTMLSelectElement).value;
                  const policy = { ...draft.policy };
                  if (v) policy.min_act = Number(v); else delete policy.min_act;
                  setDraft({ ...draft, policy });
                }}><option value="">不限</option>{[1, 2, 3].map((a) => <option key={a} value={a}>{a}</option>)}</select>
                <input type="text" placeholder="备注" value={String(draft.policy.notes ?? "")} onInput={(e) => {
                  const v = (e.currentTarget as HTMLInputElement).value;
                  const policy = { ...draft.policy };
                  if (v) policy.notes = v; else delete policy.notes;
                  setDraft({ ...draft, policy });
                }} />
              </div>
            </div>
            {draft.options.map((o, i) => (
              <div key={o.option_id} class="cor-option">
                <div class="cor-option-head">
                  <span><b>选项 {i}</b> <span class="muted small mono" title="稳定选项 ID（编辑层）">{o.option_id.slice(0, 12)}…</span></span>
                  <span class="cor-toolbar">
                    <button disabled={i === 0} onClick={() => structural({ op: "event.option.move", event_id: eid, option_id: o.option_id, to: i - 1 }, "选项上移")}>↑</button>
                    <button disabled={i === draft.options.length - 1} onClick={() => structural({ op: "event.option.move", event_id: eid, option_id: o.option_id, to: i + 1 }, "选项下移")}>↓</button>
                    <button disabled={draft.options.length <= 1} onClick={() => window.confirm("删除这个选项？") &&
                      structural({ op: "event.option.delete", event_id: eid, option_id: o.option_id }, "删除选项")}>删除</button>
                  </span>
                </div>
                <div class="cor-form">
                  <label>选项文本（中）</label><input value={o.label} onInput={(e) => setOpt(i, { label: (e.currentTarget as HTMLInputElement).value })} />
                  <label>选项文本（英）</label><input value={o.label_en} placeholder="待补" onInput={(e) => setOpt(i, { label_en: (e.currentTarget as HTMLInputElement).value })} />
                  <label>条件</label><RequiresEditor value={o.requires} registry={registry} onChange={(requires) => setOpt(i, { requires })} />
                  <label>效果（按顺序结算）</label>
                  <EventEffectsEditor effects={o.effects} registry={registry} onChange={(effects) => setOpt(i, { effects })} />
                </div>
              </div>
            ))}
            <div class="cor-toolbar" style="margin-top:10px">
              <button class="primary" disabled={!dirty} onClick={save}>保存</button>
              <button disabled={!dirty} onClick={() => setDraft(base)}>撤销未保存</button>
              <button disabled={draft.options.length >= 6} title="服务端只接受 1..6 个选项"
                onClick={() => structural({ op: "event.option.add", event_id: eid, label: "新选项", effects: [{ type: "leave" }] }, "新增选项")}>＋ 选项</button>
              <button onClick={async () => {
                const r = await run([{ op: "event.duplicate", event_id: eid }], "复制事件");
                const id2 = r?.results[0]?.event_id;
                if (id2) go(String(id2));
              }}>复制</button>
              <button onClick={async () => {
                const reason = window.prompt(`删除并退休 ${eid}（ID 永不复用）。理由：`, "不再投放");
                if (reason === null) return;
                if (await run([{ op: "event.delete", event_id: eid, reason }], "删除事件")) location.hash = "#/corridor/events";
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
