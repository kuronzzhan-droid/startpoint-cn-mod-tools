import { ComponentChildren } from "preact";
import { useEffect, useState } from "preact/hooks";
import { DeliveryApi, deliveries, DraftChange, DraftCheck, drafts, DraftView, onDraftChange } from "../api";
import { Notice } from "./common";
import { DeliveryPanel } from "./Delivery";

/** One draft namespace behind 「本次修改」: a character draft, or a boss draft (own API, own listener key). */
export interface DraftSubject {
  /** API id of the draft (character id, or boss quest selector). */
  id: string;
  /** Listener key used by onDraftChange (characters: the id itself). */
  key: string;
  get: () => Promise<DraftView>;
  save: () => Promise<unknown>;
  revert: (change: string) => Promise<unknown>;
  deliveries: DeliveryApi;
}

export function characterSubject(cid: string): DraftSubject {
  return {
    id: cid, key: cid, deliveries,
    get: () => drafts.get(cid), save: () => drafts.save(cid), revert: (change) => drafts.revert(cid, change),
  };
}

/** Draft state of one character, refreshed whenever any editor writes. */
export function useDraft(cid: string): { view: DraftView | null; error: string | null; reload: () => void } {
  return useDraftOf(characterSubject(cid));
}

export function useDraftOf(subject: DraftSubject): { view: DraftView | null; error: string | null; reload: () => void } {
  const [view, setView] = useState<DraftView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = () => subject.get().then((v) => { setView(v); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => {
    setView(null);
    reload();
    return onDraftChange((changed) => { if (changed === subject.key) reload(); });
  }, [subject.key]);
  return { view, error, reload };
}

const LEVEL_LABEL: Record<string, string> = { error: "错误", warn: "注意", info: "说明" };

export function ChecksList({ checks, empty }: { checks: DraftCheck[]; empty?: string }) {
  if (!checks.length) return empty ? <p class="muted small">{empty}</p> : null;
  return (
    <ul class="checks">
      {checks.map((c) => (
        <li class={"check-" + c.level} title={c.code}>
          <span class="check-level">{LEVEL_LABEL[c.level]}</span>
          <span>{c.message}</span>
        </li>
      ))}
    </ul>
  );
}

const KIND_LABEL: Record<string, string> = { portrait: "立绘 / UI", pixel_action: "像素动作", pixel_family: "像素整族", voice_line: "语音", ability_edit: "词条" };

function size(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

/** 「本次修改」：草稿里的全部改动，逐项撤销；保存 / 生成 / 导出接通，应用 / 发布不开放。
 * Boss drafts pass their own `subject`, `renderChange`, `emptyText` and `techNote`. */
export function ChangesPanel({ characterId, scratch, subject, renderChange, emptyText, techNote, openDelivery }: {
  characterId: string; scratch?: boolean; subject?: DraftSubject;
  /** Open 「导出」 on this delivery (link from the 实测 cell of the status bar). */
  openDelivery?: string | null;
  renderChange?: (change: DraftChange, actions: { busy: boolean; onRevert: () => void }) => ComponentChildren;
  emptyText?: ComponentChildren; techNote?: ComponentChildren;
}) {
  const target = subject ?? characterSubject(characterId);
  const { view, error } = useDraftOf(target);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [panel, setPanel] = useState<"generate" | "export" | null>(openDelivery ? "export" : null);
  useEffect(() => { if (openDelivery) setPanel("export"); }, [openDelivery]);

  if (error) return <Notice kind="error">草稿读取失败：{error}</Notice>;
  if (!view) return <div class="loading">正在读取草稿……</div>;
  const changes = view.changeset?.changes ?? [];
  const saved = view.status.state === "saved";

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

  const disabledReason = (id: string): string | null => {
    if (id === "save") return changes.length ? null : "没有草稿改动";
    if (id === "generate") return !changes.length ? "没有草稿改动" : !saved ? "先保存草稿（生成只认已保存的修订）" : null;
    return null;
  };

  return (
    <div class="changes">
      <div class="action-bar" role="toolbar" aria-label="五个动作">
        {view.actions.map((a) => {
          const reason = a.enabled ? disabledReason(a.id) : null;
          const on = (a.id === "generate" || a.id === "export") && panel === a.id;
          return (
            <div class={"action" + (a.enabled ? "" : " off") + (on ? " on" : "")}>
              <button class={a.id === "save" || a.id === "generate" ? "primary" : ""} title={reason ?? a.note}
                disabled={!a.enabled || busy !== null || !!reason}
                onClick={() => {
                  if (a.id === "save") run("save", () => target.save(), subject ? "已保存：草稿通过 schema 校验，并按当前视图重放复核了检查。" : "已保存：整份草稿通过 schema 校验，文件哈希逐个复核一致。");
                  else if (a.id === "generate" || a.id === "export") setPanel(panel === a.id ? null : a.id);
                }}>
                {busy === "save" && a.id === "save" ? "保存中……" : a.label}
              </button>
              <span class="small muted">{reason && a.enabled ? reason : a.note}</span>
            </div>
          );
        })}
      </div>
      {!drafts.hasToken() ? (
        <Notice kind="warn">页面里没有写入令牌（不是由 python -m wf.studio 提供的页面），所有写入都会被拒绝。</Notice>
      ) : null}
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {panel ? <DeliveryPanel characterId={target.id} mode={panel} view={view} onMode={setPanel} api={target.deliveries}
        initialPick={openDelivery ?? null} /> : null}
      <p class="hint">
        草稿只记录「要把什么换成什么」，不改游戏数据、测试服或补丁链；「生成」只在本机写一个交付目录。
        {view.changeset ? ` 基于资源版本 ${view.changeset.baseView}，第 ${view.changeset.revision} 次修改。` : ""}
      </p>
      <details class="tech">
        <summary>技术细节</summary>
        {techNote ?? (
          <p class="small">草稿目录 <span class="mono">work/studio-drafts/{characterId}/</span>：文件 + changeset.json（结构见
            <span class="mono"> schemas/studio-draft.schema.json</span>；agent 可用 <span class="mono">python -m wf.studio.draft</span> 走同一套操作）。
            生成写 <span class="mono">work/studio-deliveries/</span>。</p>
        )}
      </details>
      {!changes.length ? (
        <Notice>{emptyText ?? (scratch
          ? "还没有改动。草稿角色只做像素：在「像素」里换色、生成动作、画板，或整族导入现成的小人。"
          : "还没有改动。可以在「能力」「技能」「文案」改词条和文字，或在「立绘」「像素」「语音」里替换资源。")}</Notice>
      ) : (
        <ol class="change-list">
          {changes.map((change) => {
            const onRevert = () => {
              if (change.kind === "boss" || change.kind === "weapon") {
                if (!confirm(`撤销「${change.title}」？这份${change.kind === "weapon" ? "武器" : "副本"}草稿里的全部操作（共 ${(change.params.requests ?? []).length} 步）会一起删除。`)) return;
              } else if (!confirm(`撤销「${change.title}」？草稿里这一项${change.kind === "ability_edit" ? "的全部词条操作" : "的文件"}会被删除${change.kind === "ability_edit" ? "" : "（上传的源文件保留）"}。`)) return;
              run(change.id, () => target.revert(change.id), `已撤销：${change.title}`);
            };
            return renderChange ? renderChange(change, { busy: busy === change.id, onRevert })
              : <ChangeItem change={change} characterId={characterId} busy={busy === change.id} onRevert={onRevert} />;
          })}
        </ol>
      )}
    </div>
  );
}

const OP_TEXT: Record<string, string> = { set_cells: "改格", insert_row: "插入行", delete_row: "删除行", move_row: "移动行", attach_key: "挂键" };

function AbilityOps({ change }: { change: DraftChange }) {
  const requests: any[] = change.params.requests ?? [];
  const ops = requests.flatMap((r) => r.operations ?? []);
  const texts = requests.filter((r) => r.text).length;
  return (
    <ol class="ability-ops small">
      {ops.map((op: any) => (
        <li>
          <span class="tag">{OP_TEXT[op.op] ?? op.op}</span>{" "}
          <span class="mono">{op.table}/{op.key}{op.level ? "#" + op.level : ""}</span>
          {op.row !== undefined ? ` 行${op.row + 1}` : ""}{op.to_row !== undefined ? ` → 行${op.to_row + 1}` : ""}
          {op.shared_ok ? <span class="tag">shared_ok</span> : null}
          {op.op === "set_cells" ? (
            <span class="mono"> {op.cells.map((c: any) => `${c.column}: ${c.old === "" ? "（空）" : c.old} → ${c.new === "" ? "（空）" : c.new}`).join("；")}</span>
          ) : null}
        </li>
      ))}
      {texts ? <li>另有 {texts} 个文本段请求</li> : null}
    </ol>
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
      {change.kind === "ability_edit" ? <AbilityOps change={change} /> : null}
      <ChecksList checks={change.checks} />
      {change.kind === "ability_edit" ? null : <details>
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
      </details>}
    </li>
  );
}
