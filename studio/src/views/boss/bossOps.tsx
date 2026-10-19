// Shared plumbing of the phase-2 BOSS工坊 tabs: one operation → live preview → 写入草稿,
// plus small read helpers (section loading keyed to the draft revision, CSV cells).
import { useEffect, useState } from "preact/hooks";
import { Changeset } from "../../api";
import { AnyBossRequest, boss, SectionResponse } from "../../bossApi";
import { href } from "../../router";
import { Notice } from "../common";
import { PreviewState, useLivePreview } from "./BossParams";

/** Draft revision key: section reads are cached per (quest, revision). */
export function revisionKey(changeset: Changeset | null | undefined): string {
  return changeset ? `${changeset.revision}-${changeset.updatedAt}` : "base";
}

type SectionName = "terrain" | "shops" | "weapons" | "behavior" | "timeline";

/** One read-only section of the current candidate (base view + this quest's draft). */
export function useSection<T>(quest: string, name: SectionName, rev: string, enabled = true):
  { data: T | null; error: string | null; loading: boolean } {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: enabled });
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    boss.section<T>(quest, name, rev).then(
      (r: SectionResponse<T>) => { if (live) setState({ data: r.data, error: null, loading: false }); },
      (e: Error) => { if (live) setState({ data: null, error: e.message, loading: false }); });
    return () => { live = false; };
  }, [quest, name, rev, enabled]);
  return state;
}

export interface BossOp {
  request: AnyBossRequest | null;
  key: string | null;
  fresh: boolean;
  ok: boolean;
  canWrite: boolean;
  writing: boolean;
  written: boolean;
  checks: PreviewState["checks"];
  preview: ReturnType<typeof useLivePreview>["preview"];
  runNow: () => void;
  write: () => Promise<void>;
  message: { kind: "info" | "error"; text: string; link?: string } | null;
  clearMessage: () => void;
}

/** Live preview (debounced) + write of one boss operation against this quest's draft. */
export function useBossOp(questId: string, request: AnyBossRequest | null, problems: string[],
  onPreview: (state: PreviewState) => void, onWritten?: () => void): BossOp {
  const live = useLivePreview(questId, request, problems, onPreview);
  const [writing, setWriting] = useState(false);
  const [writtenFor, setWrittenFor] = useState<string | null>(null);
  const [message, setMessage] = useState<BossOp["message"]>(null);
  const key = request ? JSON.stringify(request) : null;
  const fresh = !!(live.preview && key && live.previewedFor === key);
  const ok = fresh && !!live.preview?.ok;
  const canWrite = ok && !writing && writtenFor !== key && problems.length === 0;
  const write = async () => {
    if (!canWrite || !request) return;
    setWriting(true);
    setMessage(null);
    try {
      const result = await boss.apply(questId, request);
      setWrittenFor(key);
      setMessage({
        kind: "info", text: `已写入草稿（${result.status.label}）。到「本次修改」保存后才能生成。`,
        link: href({ work: "content", shop: "boss", quest: result.questId, tab: "changes" }),
      });
      onWritten?.();
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setWriting(false);
    }
  };
  return {
    request, key, fresh, ok, canWrite, writing, written: !!key && writtenFor === key,
    checks: live.preview?.checks ?? null, preview: live.preview, runNow: live.runNow, write, message,
    clearMessage: () => setMessage(null),
  };
}

/** 立即检查 / 写入草稿 / 放弃 + status text + folded technical detail of the candidate. */
export function OpActions({ op, problems, onReset, idle = "还没有改动", writeLabel = "写入草稿" }: {
  op: BossOp; problems: string[]; onReset: () => void; idle?: string; writeLabel?: string;
}) {
  const status = !op.request ? idle : op.written ? "已写入，正在重新读取草稿……" : problems.length ? "先改正上面的输入"
    : !op.fresh ? "预检中……" : op.ok ? "预检通过，可以写入" : "有阻断项（见右侧检查）";
  return (
    <>
      {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
      <div class="save-row">
        <button type="button" disabled={!op.request || problems.length > 0} onClick={op.runNow}>立即检查</button>
        <button type="button" class="primary" disabled={!op.canWrite} onClick={op.write}
          title={!op.request ? idle : !op.fresh ? "等预检跑完" : !op.ok ? "有阻断项，不能写入" : ""}>
          {op.writing ? "写入中……" : writeLabel}
        </button>
        <button type="button" class="ghost" disabled={!op.request} onClick={() => { op.clearMessage(); onReset(); }}>放弃改动</button>
        <span class="small muted">{status}</span>
      </div>
      {op.message ? (
        <Notice kind={op.message.kind}>{op.message.text}{op.message.link ? <> <a href={op.message.link}>打开「本次修改」→</a></> : null}</Notice>
      ) : null}
      {op.fresh && op.preview?.changes?.length ? (
        <details class="tech">
          <summary>技术细节：这次会改 {op.preview.changes.length} 处{op.preview.serverTargets?.length ? `、${op.preview.serverTargets.length} 份服务端文件` : ""}</summary>
          <ul class="small mono">
            {op.preview.changes.map((c) => <li>{c.table}{c.path.length ? " · " + c.path.join("/") : ""}{c.old === null ? "（新增）" : ""}</li>)}
            {op.preview.serverTargets?.map((t) => <li>server · {t}</li>)}
          </ul>
          <p class="small muted">请求：<span class="mono">{op.key}</span></p>
        </details>
      ) : null}
    </>
  );
}

/** Minimal CSV row parser (quoted cells allowed) for previewed table values. */
export function csvRow(text: string): string[] {
  const out: string[] = [];
  let cur = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { out.push(cur); cur = ""; }
    else if (ch === "\n") break;
    else cur += ch;
  }
  out.push(cur);
  return out;
}

export const cellOf = (row: string[] | undefined | null, i: number) => (row && row[i] !== undefined ? row[i] : "");

/** Rule messages that name a crash code / placement problem (shown inline next to the edit). */
export function codeHits(checks: PreviewState["checks"], pattern: RegExp): string[] {
  return (checks ?? []).filter((c) => pattern.test(c.message)).map((c) => c.message);
}
