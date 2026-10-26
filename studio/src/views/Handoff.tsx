// 交接单: the author's notes, the files the draft really holds, and what is not in the game yet —
// three separate columns, exported as Markdown for outside artists.
import { useEffect, useState } from "preact/hooks";
import { drafts, onDraftChange } from "../api";
import { craft, HandoffNotes, HandoffSheet } from "../craftApi";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import "./craft.css";

type Editable = Omit<HandoffNotes, "updatedAt">;
const EMPTY: Editable = { title: "", author: "", summary: "", actions: {}, notes: "" };

export function Handoff({ characterId }: { characterId: string }) {
  const [doc, setDoc] = useState<HandoffSheet | null>(null);
  const [notes, setNotes] = useState<Editable>(EMPTY);
  const [newAction, setNewAction] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => onDraftChange((cid) => { if (cid === characterId) setRefresh((n) => n + 1); }), [characterId]);
  useEffect(() => {
    craft.handoff(characterId).then((d) => {
      setDoc(d);
      const { updatedAt: _, ...rest } = d.notes;
      setNotes({ ...EMPTY, ...rest });
    }, (e: Error) => setError(e.message));
  }, [characterId, refresh]);

  const set = (key: keyof Editable) => (e: Event) => setNotes({ ...notes, [key]: (e.target as HTMLInputElement).value });
  const setAction = (name: string, patch: Partial<Editable["actions"][string]>) =>
    setNotes({ ...notes, actions: { ...notes.actions, [name]: { purpose: "", includesCompanion: false, note: "", ...(notes.actions[name] as Partial<Editable["actions"][string]> | undefined), ...patch } } });
  const save = async () => {
    setBusy(true); setMessage(null); setError(null);
    try {
      await craft.saveNotes(characterId, notes);
      setMessage("说明已保存");
      setRefresh((n) => n + 1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const actionNames = Array.from(new Set([...Object.keys(notes.actions), ...(doc?.actions.map((a) => a.action) ?? [])]));

  if (error && !doc) return <Notice kind="error">交接单读取失败：{error}</Notice>;
  if (!doc) return <div class="loading">正在整理交接单……</div>;
  return (
    <div class="handoff">
      <p class="hint">交稿时把三件事分开：作者说了什么、草稿里真有哪些文件、还有哪些没进游戏。说明只存在草稿目录里，不影响生成。
        <InfoTip text={"「真实文件」只列草稿里实际存着的文件和逐帧源图，不按说明推断。\n「还没接入游戏」= 要等生成才编进游戏文件的部分、未保存的草稿、说明里写了但草稿里没有的动作、说明和导入标记对不上的地方。"} /></p>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {message ? <Notice kind="info">{message}</Notice> : null}
      <section>
        <h3>一、作者说明</h3>
        <div class="param-fields compact">
          <label class="param-field"><span>标题</span><input value={notes.title} maxLength={120} placeholder={doc.name ?? doc.code} onInput={set("title")} /></label>
          <label class="param-field"><span>作者 / 画师</span><input value={notes.author} maxLength={120} onInput={set("author")} /></label>
        </div>
        <label class="param-field wide"><span>这一套是什么</span><textarea rows={3} value={notes.summary} onInput={set("summary")} /></label>
        <table class="data">
          <thead><tr><th>动作</th><th>用途</th><th>带召唤物</th><th>草稿里</th><th>备注</th></tr></thead>
          <tbody>
            {actionNames.map((name) => {
              const row = doc.actions.find((a) => a.action === name);
              const note = notes.actions[name] ?? { purpose: row?.purpose ?? "", includesCompanion: row?.includesCompanion ?? false, note: "" };
              return (
                <tr>
                  <td>{row?.label ?? name} <span class="mono small muted">{name}</span></td>
                  <td><input value={note.purpose} maxLength={200} onInput={(e) => setAction(name, { purpose: (e.target as HTMLInputElement).value })} /></td>
                  <td><input type="checkbox" checked={note.includesCompanion} onChange={(e) => setAction(name, { includesCompanion: (e.target as HTMLInputElement).checked })} /></td>
                  <td class="small">{row?.inDraft ? `${row.frames} 帧` : <span class="muted">没有</span>}</td>
                  <td><input value={note.note} maxLength={1000} onInput={(e) => setAction(name, { note: (e.target as HTMLInputElement).value })} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div class="toolbar">
          <input class="mono" placeholder="动作名，例如 skill_ready" value={newAction} onInput={(e) => setNewAction((e.target as HTMLInputElement).value.trim())} />
          <button disabled={!/^[a-z_]+$/.test(newAction)} onClick={() => { setAction(newAction, {}); setNewAction(""); }}>加一个动作说明</button>
        </div>
        <label class="param-field wide"><span>其它注意事项</span><textarea rows={3} value={notes.notes} onInput={set("notes")} /></label>
        <div class="save-row">
          <button class="primary" onClick={save} disabled={busy || !drafts.hasToken()}>{busy ? "保存中……" : "保存说明"}</button>
          <a class="button" href={craft.handoffMarkdownUrl(characterId)} download={`交接单-${doc.code}.md`}>导出 Markdown</a>
          {doc.notes.updatedAt ? <span class="small muted">说明更新于 {doc.notes.updatedAt}</span> : null}
        </div>
      </section>
      <section>
        <h3>二、草稿里的真实文件 <span class="small muted">{doc.status.label}</span></h3>
        {!doc.files.length && !doc.frames.length ? <p class="muted small">草稿里没有文件。</p> : (
          <table class="data">
            <thead><tr><th>文件</th><th>大小 / 尺寸</th><th>SHA-256</th><th>来自改动</th></tr></thead>
            <tbody>
              {doc.files.map((f) => <tr><td class="mono small">{f.logical}{f.approximate ? "（近似）" : ""}</td><td>{f.size.toLocaleString()} 字节</td>
                <td class="mono small">{f.sha256.slice(0, 16)}…</td><td class="small">{f.change}</td></tr>)}
              {doc.frames.map((f) => <tr><td class="mono small">{f.file}</td><td>{f.size.join("×")}</td>
                <td class="mono small">{(f.sha256 ?? "").slice(0, 16)}…</td><td class="small">{f.change} · 第 {f.index} 帧</td></tr>)}
            </tbody>
          </table>
        )}
      </section>
      <section>
        <h3>三、还没接入游戏的部分</h3>
        {!doc.notInGame.length ? <p class="muted small">没有：草稿里的改动都已是游戏文件，生成后即可测试。</p> : (
          <ul class="checks">{doc.notInGame.map((i) => (
            <li class={i.kind === "mismatch" || i.kind === "unsaved" ? "check-warn" : "check-info"}><span>{i.text}{i.change ? `（${i.change}）` : ""}</span></li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}
