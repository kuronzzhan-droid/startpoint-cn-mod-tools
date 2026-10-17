import { useEffect, useState } from "preact/hooks";
import { DraftChange, DraftCheck, drafts, DraftView, onDraftChange } from "../api";
import { Notice } from "./common";

/** Draft state of one character, refreshed whenever any editor writes. */
export function useDraft(cid: string): { view: DraftView | null; error: string | null; reload: () => void } {
  const [view, setView] = useState<DraftView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = () => drafts.get(cid).then((v) => { setView(v); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => {
    setView(null);
    reload();
    return onDraftChange((changed) => { if (changed === cid) reload(); });
  }, [cid]);
  return { view, error, reload };
}

const LEVEL_LABEL: Record<string, string> = { error: "错误", warn: "注意", info: "说明" };

export function ChecksList({ checks, empty }: { checks: DraftCheck[]; empty?: string }) {
  if (!checks.length) return empty ? <p class="muted small">{empty}</p> : null;
  return (
    <ul class="checks">
      {checks.map((c) => (
        <li class={"check-" + c.level}>
          <span class="check-level">{LEVEL_LABEL[c.level]}</span>
          <span>{c.message}</span>
          <span class="mono muted small">{c.code}</span>
        </li>
      ))}
    </ul>
  );
}

const KIND_LABEL: Record<string, string> = { portrait: "立绘 / UI", pixel_action: "像素动作", voice_line: "语音" };

function size(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

/** 「本次修改」：草稿里的全部改动，逐项撤销；五个动作只有「保存」接通。 */
export function ChangesPanel({ characterId }: { characterId: string }) {
  const { view, error } = useDraft(characterId);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  if (error) return <Notice kind="error">草稿读取失败：{error}</Notice>;
  if (!view) return <div class="loading">正在读取草稿……</div>;
  const changes = view.changeset?.changes ?? [];

  const run = async (id: string, action: () => Promise<unknown>, done: string) => {
    setBusy(id);
    setMessage(null);
    try {
      await action();
      setMessage({ kind: "info", text: done });
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div class="changes">
      <div class="action-bar" role="toolbar" aria-label="五个动作">
        {view.actions.map((a) => (
          <div class={"action" + (a.enabled ? "" : " off")}>
            <button class={a.id === "save" ? "primary" : ""} disabled={!a.enabled || busy !== null || (a.id === "save" && !changes.length)}
              onClick={() => a.id === "save" && run("save", () => drafts.save(characterId), "已保存：整份草稿通过 schema 校验，文件哈希逐个复核一致。")}>
              {busy === "save" && a.id === "save" ? "保存中……" : a.label}
            </button>
            <span class="small muted">{a.note}</span>
          </div>
        ))}
      </div>
      {!drafts.hasToken() ? (
        <Notice kind="warn">页面里没有写入令牌（不是由 python -m wf.studio 提供的页面），所有写入都会被拒绝。</Notice>
      ) : null}
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <p class="hint">
        草稿目录 <span class="mono">work/studio-drafts/{characterId}/</span>：文件 + changeset.json（结构见
        <span class="mono"> schemas/studio-draft.schema.json</span>，agent 可用 <span class="mono">python -m wf.studio.draft</span> 走同一套操作）。
        草稿不写任何游戏表、store、补丁链或服务器。{view.changeset ? ` 基于视图 ${view.changeset.baseView}，修订 ${view.changeset.revision}。` : ""}
      </p>
      {!changes.length ? (
        <Notice>这个角色还没有草稿改动。可以在「换立绘」「换像素」「换语音」里替换资源。</Notice>
      ) : (
        <ol class="change-list">
          {changes.map((change) => (
            <ChangeItem change={change} characterId={characterId} busy={busy === change.id}
              onRevert={() => {
                if (!confirm(`撤销「${change.title}」？草稿里这一项的文件会被删除（上传的源文件保留）。`)) return;
                run(change.id, () => drafts.revert(characterId, change.id), `已撤销：${change.title}`);
              }} />
          ))}
        </ol>
      )}
    </div>
  );
}

function ChangeItem({ change, characterId, busy, onRevert }: {
  change: DraftChange; characterId: string; busy: boolean; onRevert: () => void;
}) {
  const errors = change.checks.filter((c) => c.level === "error").length;
  const warns = change.checks.filter((c) => c.level === "warn").length;
  const images = change.files.filter((f) => f.draft.endsWith(".png"));
  const frames: { file: string; duration: number }[] = change.kind === "pixel_action" ? change.params.frames : [];
  return (
    <li class="change">
      <header>
        <span class="tag">{KIND_LABEL[change.kind]}</span>
        <h3>{change.title}</h3>
        <span class="muted small mono">{change.id} · {change.createdAt.replace("T", " ").slice(0, 19)}</span>
        <span class="spacer" />
        {errors ? <span class="pill bad">{errors} 错误</span> : null}
        {warns ? <span class="pill warnpill">{warns} 注意</span> : null}
        <button onClick={onRevert} disabled={busy}>{busy ? "撤销中……" : "撤销此项"}</button>
      </header>
      {images.length ? (
        <div class="change-thumbs">
          {images.map((f) => (
            <figure title={f.logical}>
              <img src={drafts.fileUrl(characterId, f.draft, f.sha256.slice(0, 8))} loading="lazy" alt="" />
              <figcaption class="small mono">{f.logical.split("/").pop()}{f.approximate ? " ≈" : ""}</figcaption>
            </figure>
          ))}
        </div>
      ) : null}
      {frames.length ? (
        <div class="change-thumbs pixel">
          {frames.map((f, i) => (
            <figure><img src={drafts.fileUrl(characterId, f.file)} alt="" /><figcaption class="small mono">#{i + 1} · {f.duration}f</figcaption></figure>
          ))}
        </div>
      ) : null}
      {change.kind === "voice_line" ? (
        <div class="ab-row">
          <span class="small muted">新语音</span>
          <audio controls preload="none" src={drafts.fileUrl(characterId, change.files[0].draft, change.files[0].sha256.slice(0, 8))} />
          <span class="small">{change.params.durationSeconds}s（原 {change.params.originalDurationSeconds ?? "—"}s）· 源文件 {change.params.sourceName}</span>
        </div>
      ) : null}
      <ChecksList checks={change.checks} />
      <details>
        <summary>替换的文件 {change.files.length} 个{change.pending.length ? ` · 待生成 ${change.pending.length} 项` : ""}</summary>
        <table class="files">
          <thead><tr><th>逻辑路径</th><th>根</th><th>大小</th><th>草稿 SHA-256</th><th>原文件</th></tr></thead>
          <tbody>
            {change.files.map((f) => (
              <tr>
                <td class="mono small">{f.logical}{f.approximate ? <span class="tag" title={f.note}>近似</span> : null}</td>
                <td>{f.root}</td>
                <td class="nowrap">{size(f.size)}</td>
                <td class="mono small" title={f.sha256}>{f.sha256.slice(0, 12)}…</td>
                <td class="small">{f.base.layer ? (f.base.layer === "store131" ? "store131 基底" : f.base.layer) : "（新文件）"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {change.pending.length ? (
          <>
            <h4>生成时还要写（草稿不写表、不打包）</h4>
            <ul class="pending">
              {change.pending.map((p) => (
                <li><span class="mono small">{p.logical}</span> — {p.reason}{p.value !== undefined ? <> → <code>{String(p.value)}</code></> : null}</li>
              ))}
            </ul>
          </>
        ) : null}
      </details>
    </li>
  );
}
