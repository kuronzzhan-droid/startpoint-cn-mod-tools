// 像素 › 批量预检: one folder / zip of per-frame PNGs, grouped by file name into action slots,
// checked with the single-action rules; _sp composite frames are reported, never imported.
import { useState } from "preact/hooks";
import { drafts } from "../api";
import { ActionMark, craft, PrecheckResult } from "../craftApi";
import { ChecksList } from "./Changes";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import "./craft.css";
import { readAsDataUrl } from "./workshopKit";

const b64 = async (f: Blob) => (await readAsDataUrl(f)).replace(/^data:[^,]*,/, "");

export function PixelPrecheck({ characterId }: { characterId: string }) {
  const [family, setFamily] = useState<"pixelart" | "special">("pixelart");
  const [files, setFiles] = useState<Record<string, string>>({});
  const [zip, setZip] = useState<{ name: string; data: string } | null>(null);
  const [marks, setMarks] = useState<Record<string, ActionMark>>({});
  const [result, setResult] = useState<PrecheckResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const folderProps = { webkitdirectory: "", directory: "" } as Record<string, string>;
  const ready = zip !== null || Object.keys(files).length > 0;

  const pickFolder = async (list: FileList | null) => {
    if (!list) return;
    const out: Record<string, string> = {};
    for (const f of Array.from(list)) {
      if (/\.png$/i.test(f.name)) out[(f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name] = await b64(f);
    }
    setFiles(out); setZip(null); setResult(null);
  };
  const run = async (apply: boolean) => {
    setBusy(apply ? "apply" : "check"); setMessage(null);
    try {
      const r = await craft.precheck(characterId, { family, ...(zip ? { zip: zip.data } : { files }), actions: marks, apply });
      setResult(r);
      if (apply) setMessage({ kind: "info", text: `已写入 ${r.saved.length} 个动作（单动作替换）：${r.saved.map((s) => s.action).join("、")}` });
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const mark = (action: string, patch: Partial<ActionMark>) =>
    setMarks((m) => ({ ...m, [action]: { includesCompanion: false, purpose: "", ...(m[action] as Partial<ActionMark> | undefined), ...patch } }));

  return (
    <div class="ws-import">
      <p class="hint">一次检查画师交来的一整批逐帧 PNG：按文件名归到动作槽，每个动作走单动作替换同一套规则。
        带 <code>_sp</code> 的合成帧（本体 + 特效/召唤物）只报出来，不会归进待机这类基础动作。
        <InfoTip text={"文件名：动作_帧号.png、动作-帧号.png、动作/帧号.png 或 动作.png（单帧）；例如 neutral_01.png、walk_front/03.png。\n" +
          "合成帧：neutral_sp_01.png、neutral_01_sp.png、neutral_sp/01.png。\n" +
          "停留帧数按原动作总长均分；写入后可以在「单动作替换」里逐帧调。"} /></p>
      <div class="toolbar">
        <label>像素族<select value={family} onChange={(e) => { setFamily((e.target as HTMLSelectElement).value as "pixelart" | "special"); setResult(null); }}>
          <option value="pixelart">基础动作（pixelart）</option><option value="special">特殊动作（special）</option>
        </select></label>
        <label class="upload-btn">选文件夹<input type="file" multiple {...folderProps} onChange={(e) => pickFolder((e.target as HTMLInputElement).files)} /></label>
        <label class="upload-btn">或 zip<input type="file" accept=".zip" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (f) { setZip({ name: f.name, data: await b64(f) }); setFiles({}); setResult(null); }
        }} /></label>
      </div>
      <p class="small muted">{zip ? `zip：${zip.name}` : Object.keys(files).length ? `文件夹：${Object.keys(files).length} 个 PNG` : "还没选"}</p>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <div class="save-row">
        <button onClick={() => run(false)} disabled={!ready || busy !== null || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "预检（不写草稿）"}</button>
        <button class="primary" onClick={() => run(true)} disabled={!result?.ready.length || busy !== null || !drafts.hasToken()}
          title="只写没有错误的动作，每个动作一条单动作替换">{busy === "apply" ? "写入中……" : `写入通过的 ${result?.ready.length ?? 0} 个动作`}</button>
      </div>
      {result ? (
        <section class="pixel-check">
          <h4>预检结果 · 错误 {result.counts.error} · 提示 {result.counts.warn}</h4>
          <ChecksList checks={result.checks} />
          <table class="data">
            <thead><tr><th>动作</th><th>帧</th><th>尺寸</th><th>带召唤物</th><th>用途</th><th>检查</th></tr></thead>
            <tbody>
              {result.actions.map((a) => (
                <tr class={a.ok ? "" : "row-error"}>
                  <td>{a.label ?? "（未知）"} <span class="mono small muted">{a.action}</span>
                    <InfoTip text={a.files.join("\n")} /></td>
                  <td>{a.frames}{a.durations ? <span class="small muted"> · 停留 {a.durations.join("/")}</span> : null}</td>
                  <td class="small mono">{a.sizes?.join("、") ?? "—"}</td>
                  <td><input type="checkbox" checked={marks[a.action]?.includesCompanion ?? a.includesCompanion}
                    onChange={(e) => mark(a.action, { includesCompanion: (e.target as HTMLInputElement).checked })} /></td>
                  <td><input class="small" maxLength={200} placeholder="例如 放技能时的召唤兽" value={marks[a.action]?.purpose ?? a.purpose}
                    onInput={(e) => mark(a.action, { purpose: (e.target as HTMLInputElement).value })} /></td>
                  <td><ChecksList checks={a.checks} empty={a.ok ? "通过" : ""} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p class="small muted">改了「带召唤物」或用途后再点一次预检，结果会按新标记重算；写入时标记会记进草稿改动，交接单里也会列出。</p>
          {result.composite.length ? (
            <details><summary>_sp 合成帧 {result.composite.length} 个（未导入）</summary>
              <ul class="small mono">{result.composite.map((c) => <li>{c.file} → {c.action}</li>)}</ul></details>
          ) : null}
          {result.unmatched.length ? (
            <details><summary>认不出动作的文件 {result.unmatched.length} 个</summary>
              <ul class="small mono">{result.unmatched.map((n) => <li>{n}</li>)}</ul></details>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
