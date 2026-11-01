import { useState } from "preact/hooks";
import { drafts } from "../api";
import { Notice } from "./common";

export function SpeechAdd({ cid }: { cid: string }) {
  const [kind, setKind] = useState("0");
  const [constraint, setConstraint] = useState("2");
  const [evo, setEvo] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [voice, setVoice] = useState("(None)");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const add = async (e: Event) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await drafts.addSpeech(cid, [[kind, constraint, evo, subtitle, voice]]);
      setSubtitle("");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return <details class="ability"><summary>新增台词</summary>
    <form onSubmit={add}>
      <div class="toolbar">
        <label>类型<select value={kind} onChange={(e) => {
          const selected = e.currentTarget.value;
          setKind(selected); setConstraint(selected === "0" ? "2" : ""); setEvo(selected === "1" ? "1" : "");
        }}>
          <option value="0">主页</option><option value="1">觉醒</option><option value="2">入队</option>
        </select></label>
        <label>显示条件<select value={constraint} disabled={kind !== "0"} onChange={(e) => setConstraint(e.currentTarget.value)}>
          {kind !== "0" ? <option value="">不适用</option> : null}
          <option value="2">两态均可见</option><option value="0">未进化</option><option value="1">进化</option>
        </select></label>
        <label>evo_level<input value={evo} inputMode="numeric" pattern="[0-9]+" required={kind === "1"} disabled={kind !== "1"} onInput={(e) => setEvo(e.currentTarget.value)} /></label>
        <label>语音相对路径<input value={voice} required placeholder="home/home_2 或 (None)" onInput={(e) => setVoice(e.currentTarget.value)} /></label>
      </div>
      <label class="block">字幕（支持换行）<textarea value={subtitle} required maxLength={8000} onInput={(e) => setSubtitle(e.currentTarget.value)} /></label>
      <p class="hint">主页须覆盖未进化和进化两态，并须有入队及 evo_level=1 的觉醒台词。路径不带 .mp3；新路径登记后在列表上传音频，(None) 为无声字幕。</p>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <button class="primary" disabled={busy || !drafts.hasToken()}>{busy ? "写入中……" : "追加到草稿"}</button>
    </form>
  </details>;
}
