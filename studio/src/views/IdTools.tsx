// 工具抽屉：链视图（当前视图 / 基线 → 链终点 / 额外 ZIP / 缺包）、ID 占用查询与下一空闲值、下一个资源版本，
// 以及在表单里复用的 IdField（输入即查 + 「取下一个空闲 ID」）。查询只读，不预留。
import { useEffect, useState } from "preact/hooks";
import { api, drafts, Meta, ViewList } from "../api";
import { ID_KINDS, IdCheck, IdKind, IdNext, ownersText, StoreExport, studio, VersionNext } from "../studioApi";
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

/** 导出当前视图为 store（POST /api/studio/views/export-store）；目标目录须不存在，从不覆盖。 */
function ExportStore({ view }: { view: string | null }) {
  const [out, setOut] = useState("");
  const [copy, setCopy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<StoreExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await studio.exportStore(out.trim(), copy)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div class="tool-export">
      <h4>导出为 store <InfoTip text="只导出编辑台当前加载的视图。默认对未覆盖文件建硬链接（要求同盘），ZIP 覆盖成员写新文件；跨盘或构建器会原地改文件时勾选「复制」。完成标志是最后写入的 viewstore.json。" /></h4>
      <div class="tool-row">
        <input class="mono" value={out} placeholder="<资料根>/outputs/work/<主题>/viewstore（必须不存在）" onInput={(e) => setOut((e.target as HTMLInputElement).value)} />
        <label class="check"><input type="checkbox" checked={copy} onChange={(e) => setCopy((e.target as HTMLInputElement).checked)} />复制（不用硬链接）</label>
        <button type="button" class="primary" disabled={busy || !out.trim() || !drafts.hasToken()} onClick={run}>{busy ? "导出中……" : `导出 ${view ?? "当前视图"}`}</button>
      </div>
      {error ? <p class="small error-text">导出失败：{error}</p> : null}
      {result ? (
        <Notice>已导出 {result.view ?? "当前视图"} @ {result.version}：构建器 store = <span class="mono">{result.store ?? "（见 viewstore.json）"}</span>
          <details class="tech"><summary>技术细节</summary><pre class="cmd">{JSON.stringify(result, null, 2)}</pre></details></Notice>
      ) : null}
    </div>
  );
}

/** 链视图: /api/meta summary + /api/studio/views (switching a view needs a restart with --view). */
function ChainView({ meta }: { meta: Meta | null }) {
  const [views, setViews] = useState<ViewList | null>(null);
  const [viewsError, setViewsError] = useState<string | null>(null);
  const [pick, setPick] = useState("");
  useEffect(() => { studio.views().then((v) => { setViews(v); setPick(v.current ?? v.views[0] ?? ""); }, (e: Error) => setViewsError(e.message)); }, []);
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
      <h4>切换视图</h4>
      {viewsError ? <p class="small error-text">视图列表读取失败：{viewsError}</p> : !views ? <p class="small muted">正在读取视图列表……</p> : (
        <>
          <div class="segmented" role="radiogroup" aria-label="命名视图">
            {views.views.map((v) => (
              <button type="button" role="radio" aria-checked={pick === v} class={pick === v ? "on" : ""} onClick={() => setPick(v)}>
                {v}{v === views.current ? <span class="count">当前</span> : null}</button>
            ))}
          </div>
          {!views.views.length ? <p class="small muted">本机配置没有命名视图（profiles/local.json 的 views）。</p> : null}
          {pick && pick !== views.current ? (
            <>
              <p class="small warn-text">编辑台不能运行时切换视图（所有读取与生成都绑定启动时的完整视图）。关掉编辑台，用下面的命令重启：</p>
              <pre class="cmd">python -m wf.studio --view {pick}</pre>
            </>
          ) : <p class="small muted">{views.current ? `正在使用 ${views.current}。` : "当前不是命名视图（旧 view 配置或本机默认链）。"}</p>}
        </>
      )}
      <ExportStore view={views?.current ?? s.view ?? null} />
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
