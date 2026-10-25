// 工具抽屉：链视图（当前视图 / 基线 → 链终点 / 额外 ZIP / 缺包）、ID 占用查询与下一空闲值、下一个资源版本，
// 以及在表单里复用的 IdField（输入即查 + 「取下一个空闲 ID」）。查询只读，不预留。
import { useEffect, useState } from "preact/hooks";
import { api, Meta } from "../api";
import { ID_KINDS, IdCheck, IdKind, IdNext, ownersText, studio, VersionNext } from "../studioApi";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";

/** Live availability of one ID (debounced); stale answers are dropped. */
export function useIdCheck(kind: IdKind, id: string): { result: IdCheck | null; error: string | null; busy: boolean } {
  const [state, setState] = useState<{ result: IdCheck | null; error: string | null; busy: boolean }>({ result: null, error: null, busy: false });
  useEffect(() => {
    const value = id.trim();
    if (!value) { setState({ result: null, error: null, busy: false }); return; }
    let live = true;
    setState((s) => ({ ...s, busy: true }));
    const timer = window.setTimeout(() => {
      studio.idCheck(kind, value).then(
        (r) => { if (live) setState({ result: r, error: null, busy: false }); },
        (e: Error) => { if (live) setState({ result: null, error: e.message, busy: false }); });
    }, 300);
    return () => { live = false; window.clearTimeout(timer); };
  }, [kind, id]);
  return state;
}

/** ID input with live ids/check and 「取下一个空闲 ID」 (ids/next from the typed value, or the tool's default start). */
export function IdField({ kind, label, value, onChange, placeholder, onAvailability }: {
  kind: IdKind; label: string; value: string; onChange: (v: string) => void; placeholder?: string;
  /** Reports true / false / null (unknown) so the caller can block writing on a taken ID. */
  onAvailability?: (available: boolean | null) => void;
}) {
  const check = useIdCheck(kind, value);
  const [nextBusy, setNextBusy] = useState(false);
  const [nextError, setNextError] = useState<string | null>(null);
  const fresh = check.result && check.result.id === value.trim() ? check.result : null;
  useEffect(() => { onAvailability?.(check.busy || !fresh ? null : fresh.available); }, [fresh?.available, fresh?.id, check.busy]);
  const takeNext = async () => {
    setNextBusy(true); setNextError(null);
    try { const r: IdNext = await studio.idNext(kind, value.trim() || undefined); onChange(r.id); }
    catch (e) { setNextError((e as Error).message); }
    finally { setNextBusy(false); }
  };
  return (
    <label class="param-field id-field"><span>{label}</span>
      <span class="id-input">
        <input class="mono" value={value} placeholder={placeholder} onInput={(e) => onChange((e.target as HTMLInputElement).value.trim())} />
        <button type="button" onClick={takeNext} disabled={nextBusy} title="从输入值（含）向上找第一个当前视图、服务端镜像和全部草稿都没占用的值">
          {nextBusy ? "查询中……" : "取下一个空闲 ID"}</button>
      </span>
      <span class="small">
        {check.busy ? <span class="muted">查询占用……</span>
          : check.error ? <span class="error-text">{check.error}</span>
          : fresh ? (fresh.available
            ? <span class="state-ok">空闲{fresh.serverChecked ? "" : "（未查服务端镜像）"}</span>
            : <span class="error-text">已占用：{ownersText(fresh.owners)}</span>)
          : <span class="muted">输入后自动查询占用</span>}
        {fresh?.segment ? <span class="muted"> · 玛纳节点段 {fresh.segment.start}–{fresh.segment.end}</span> : null}
        {nextError ? <span class="error-text"> · {nextError}</span> : null}
      </span>
    </label>
  );
}

/** 链视图 summary from /api/meta (switching and store export are launch-time / CLI only). */
function ChainView({ meta }: { meta: Meta | null }) {
  if (!meta) return <p class="small muted">正在读取视图……</p>;
  const s = meta.source;
  const view = s.view ?? "（未命名：旧 view 配置或本机默认链）";
  return (
    <section class="tool-block">
      <h3>链视图</h3>
      <dl class="kv">
        <dt>当前视图</dt><dd class="mono">{view}</dd>
        <dt>基线 → 链终点</dt><dd class="mono">{s.baseVersion ?? "1.4.131"} → {String(s.tip)}</dd>
        <dt>叠加后版本</dt><dd class="mono">{s.version}</dd>
        <dt>补丁 ZIP</dt><dd>{s.zipCount} 个（{s.memberCount} 个成员）{s.chain ? <span class="small muted mono"> · 清单 {s.chain.manifest}</span> : null}</dd>
        <dt>额外 ZIP</dt><dd>{s.extraZips.length ? <ul class="small mono">{s.extraZips.map((z) => <li>{z}</li>)}</ul> : "无"}</dd>
      </dl>
      {s.chain?.missing.length ? (
        <Notice kind="error">补丁链缺 {s.chain.missing.length} 个 ZIP，视图不完整：
          <ul class="small mono">{s.chain.missing.map((m) => <li>{m.version} · {m.name}</li>)}</ul></Notice>
      ) : null}
      <p class="small muted">切换视图要重启编辑台（启动时选定，所有读取与生成都用同一个完整视图）：</p>
      <pre class="cmd">python -m wf.studio --view test175{"\n"}python -m wf.studio --view local{"\n"}python -m wf.studio --view prod</pre>
      <p class="small muted">导出为 store（给现有构建器；目标目录须不存在，跨盘用 --copy）：</p>
      <pre class="cmd">python -m wf.studio.draft --view {s.view ?? "<视图名>"} export-store --out D:/WF/outputs/work/&lt;主题&gt;/viewstore</pre>
      <p class="small muted">视图名、store、manifest 与 ZIP 目录在 <span class="mono">profiles/local.json</span> 的 <span class="mono">views</span> 里配置；HTTP 目前不提供视图列表、切换和导出。</p>
    </section>
  );
}

function IdLookup() {
  const [kind, setKind] = useState<IdKind>("character");
  const [id, setId] = useState("");
  const check = useIdCheck(kind, id);
  const [next, setNext] = useState<IdNext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setNext(null); }, [kind]);
  const runNext = async () => {
    setBusy(true); setError(null);
    try { setNext(await studio.idNext(kind, id || undefined)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <section class="tool-block">
      <h3>ID 查询 <InfoTip text="查当前视图、启动时 --server-dir 的服务端镜像、全部角色 / BOSS / 武器草稿。结果只是证据，不预留；正式写入时会再查一次碰撞。" /></h3>
      <div class="tool-row">
        <select value={kind} aria-label="ID 类型" onChange={(e) => setKind((e.target as HTMLSelectElement).value as IdKind)}>
          {ID_KINDS.map((k) => <option value={k.id}>{k.label}</option>)}
        </select>
        <input class="mono" value={id} placeholder={kind === "string_id" ? "例如 studio_1" : "ID"} onInput={(e) => setId((e.target as HTMLInputElement).value.trim())} />
        <button type="button" onClick={runNext} disabled={busy}>{busy ? "查询中……" : id ? "从这里找下一个空闲" : "找下一个空闲"}</button>
      </div>
      {check.error ? <p class="small error-text">{check.error}</p> : check.result ? (
        <p class="small">{check.result.id}：{check.result.available ? <span class="state-ok">空闲</span> : <span class="error-text">已占用</span>}
          {check.result.owners.length ? <span class="muted"> · {ownersText(check.result.owners)}</span> : null}
          {!check.result.serverChecked ? <span class="warn-text"> · 未查服务端镜像（启动时没给 --server-dir）</span> : null}
          <span class="muted"> · 视图 {check.result.viewVersion}</span></p>
      ) : null}
      {error ? <p class="small error-text">{error}</p> : null}
      {next ? (
        <div class="small">
          <p>下一个空闲：<strong class="mono">{next.id}</strong>{next.segment ? <span class="muted"> · 节点段 {next.segment.start}–{next.segment.end}</span> : null}
            {" "}<button type="button" class="link" onClick={() => setId(next.id)}>填入</button></p>
          {next.skipped.length ? (
            <details><summary>跳过 {next.skipped.length} 个已占用值</summary>
              <ul class="mono">{next.skipped.slice(0, 50).map((s) => <li>{s.id} · {ownersText(s.owners)}</li>)}</ul></details>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function VersionLookup({ meta }: { meta: Meta | null }) {
  const [view, setView] = useState("");
  const [result, setResult] = useState<VersionNext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true); setError(null);
    try { setResult(await studio.versionNext(view || undefined)); } catch (e) { setResult(null); setError((e as Error).message); } finally { setBusy(false); }
  };
  useEffect(() => { run(); }, []);
  return (
    <section class="tool-block">
      <h3>下一个资源版本 <InfoTip text="从所选视图叠加后的版本加一，跳过 release-contracts/version-reservations.json 登记的版本和清单里已声明的更晚版本。只是建议，不会登记预留。" /></h3>
      <div class="tool-row">
        <input value={view} placeholder={`视图名（留空 = 当前 ${meta?.source.view ?? "视图"}）`} onInput={(e) => setView((e.target as HTMLInputElement).value.trim())}
          onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
        <button type="button" onClick={run} disabled={busy}>{busy ? "查询中……" : "查询"}</button>
      </div>
      {error ? <p class="small error-text">{error}</p> : null}
      {result ? (
        <div class="small">
          <p>视图 <span class="mono">{result.view ?? "当前"}</span>：当前 <span class="mono">{result.current}</span> → 下一个 <strong class="mono">{result.next}</strong></p>
          {result.skipped.length ? <ul class="mono">{result.skipped.map((s) => <li>跳过 {s.version}{s.source === "manifest" ? ` · 清单已声明${s.location ? `（${s.location}）` : ""}` : s.purpose ? ` · ${s.purpose}${s.owner ? ` / ${s.owner}` : ""}` : ""}</li>)}</ul> : null}
          <p class="muted">登记文件：<span class="mono">{result.reservationsFile ?? "（无）"}</span></p>
        </div>
      ) : null}
    </section>
  );
}

/** Drawer body of the header 「工具」 button. */
export function ToolsPanel() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => { api.meta().then(setMeta, () => setMeta(null)); }, []);
  return (
    <div class="tools-panel">
      <ChainView meta={meta} />
      <IdLookup />
      <VersionLookup meta={meta} />
    </div>
  );
}
