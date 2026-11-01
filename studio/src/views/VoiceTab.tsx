import { useEffect, useRef, useState } from "preact/hooks";
import { api, drafts, fileToBase64, onDraftChange, VoiceLine, VoiceLines } from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";
import { SpeechAdd } from "./SpeechAdd";

const KIND: Record<string, string> = { "0": "主页", "1": "觉醒", "2": "入队" };
const CONSTRAINT: Record<string, string> = { "2": "两态", "0": "未进化", "1": "进化" };

export function VoiceTab({ characterId }: { characterId: string }) {
  const [data, setData] = useState<VoiceLines | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = () => drafts.voiceLines(characterId).then((value) => { setData(value); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => {
    setData(null);
    reload();
    return onDraftChange((cid) => { if (cid === characterId) reload(); });
  }, [characterId]);

  if (error && !data) return <Notice kind="error">语音读取失败：{error}</Notice>;
  if (!data) return <div class="loading">正在读取台词与语音……</div>;
  return (
    <div class="voice">
      <p class="hint">
        {data.note} 上传 WAV / MP3 / 其它 ffmpeg 能读的音频，转成游戏规格 {data.format}，响度按类别归一到官方中位
        （主页 −14、战斗短句 −12.8、技能 −13.1 LUFS），并用 wf_assets.mp3_encode 做存储态校验（VBR 会被拒绝）。
      </p>
      <SpeechAdd key={characterId} cid={characterId} />
      {error ? <Notice kind="error">{error}</Notice> : null}
      <ChecksList checks={data.checks ?? []} />
      {data.speechChangeId ? <button class="small-btn" onClick={() => drafts.revert(characterId, data.speechChangeId!).catch((e: Error) => setError(e.message))}>撤销本次全部新增台词</button> : null}
      <table class="voice-table">
        <thead>
          <tr><th>台词</th><th>A 原版</th><th>B 新版（草稿）</th><th>替换</th></tr>
        </thead>
        <tbody>
          {data.lines.map((line) => <VoiceRow line={line} characterId={characterId} />)}
        </tbody>
      </table>
    </div>
  );
}

function VoiceRow({ line, characterId }: { line: VoiceLine; characterId: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const a = useRef<HTMLAudioElement>(null);
  const b = useRef<HTMLAudioElement>(null);
  const draft = line.draft;
  const upload = async (file: File | undefined) => {
    if (!file || !line.voice) return;
    setBusy(true);
    setErr(null);
    try {
      await drafts.saveVoice(characterId, { voice: line.voice, audio: await fileToBase64(file), filename: file.name });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const playAB = () => {
    const first = a.current;
    const second = b.current;
    if (!first || !second) return;
    second.pause();
    first.currentTime = 0;
    first.onended = () => { second.currentTime = 0; second.play(); first.onended = null; };
    first.play();
  };
  return (
    <tr class={draft ? "has-draft" : ""} data-voice={line.voice ?? ""}>
      <td class="voice-line">
        <div><strong>{line.label}</strong> <span class="mono small muted">{line.voice ?? "(None)"}</span>
          {line.speechRow ? <span class="tag">speech 第 {line.speechRow} 行 · {KIND[line.kind] ?? line.kind}
            {line.kind === "0" ? ` · ${CONSTRAINT[line.constraint ?? ""] ?? "条件待核实"}` : ""}
            {line.kind === "1" ? ` · evo_level=${line.evoLevel}` : ""}</span> : null}</div>
        {line.subtitle ? <div class="speech-text small">{line.subtitle}</div> : null}
      </td>
      <td>
        {line.voice && line.present ? (
          <>
            <audio ref={a} controls preload="none" src={api.assetUrl(line.path!)} />
            <div class="small muted">{line.durationSeconds ?? "—"}s</div>
          </>
        ) : <span class="muted small">{line.voice ? "缺文件" : "字幕无声"}</span>}
      </td>
      <td>
        {draft ? (
          <>
            <audio ref={b} controls preload="none" src={drafts.fileUrl(characterId, draft.file, draft.id)} />
            <div class="small">{draft.durationSeconds}s · 源 {draft.sourceName}</div>
            <ChecksList checks={draft.checks} />
          </>
        ) : <span class="muted small">—</span>}
      </td>
      <td class="nowrap">
        {line.voice ? (
          <>
            <label class="upload-btn small">{busy ? "转码中……" : draft ? "重新上传" : "上传音频"}
              <input type="file" accept="audio/*,.wav,.mp3,.ogg,.flac,.m4a" disabled={busy}
                onChange={(e) => upload((e.target as HTMLInputElement).files?.[0])} />
            </label>
            {draft && line.present ? <button class="small-btn" onClick={playAB}>A→B 连播</button> : null}
            {draft ? <button class="small-btn ghost" onClick={() => drafts.revert(characterId, draft.id).catch((e: Error) => setErr(e.message))}>撤销</button> : null}
            {err ? <div class="error-text small">{err}</div> : null}
          </>
        ) : null}
      </td>
    </tr>
  );
}
