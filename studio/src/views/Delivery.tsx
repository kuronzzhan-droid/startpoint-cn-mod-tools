import { useEffect, useState } from "preact/hooks";
import { BuildResult, deliveries, DeliveryDetail, DeliverySummary, DraftView, onDraftChange } from "../api";
import { Notice } from "./common";
import { RuleChips, ruleCounts, RuleList } from "./rules";

function size(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

/** Latest delivery for a character (refreshed after any draft write or build). */
export function useDeliveries(cid: string): { list: DeliverySummary[] | null; reload: () => void } {
  const [list, setList] = useState<DeliverySummary[] | null>(null);
  const reload = () => deliveries.list(cid).then((r) => setList(r.deliveries), () => setList([]));
  useEffect(() => {
    setList(null);
    reload();
    return onDraftChange((changed) => { if (changed === cid) reload(); });
  }, [cid]);
  return { list, reload };
}

export function DeliveryPanel({ characterId, mode, view, onMode }: {
  characterId: string; mode: "generate" | "export"; view: DraftView; onMode: (m: "generate" | "export") => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <section class="delivery-panel">
      <nav class="segmented" aria-label="生成或导出">
        <button class={mode === "generate" ? "on" : ""} onClick={() => onMode("generate")}>生成</button>
        <button class={mode === "export" ? "on" : ""} onClick={() => onMode("export")}>导出</button>
      </nav>
      {mode === "generate" ? (
        <GenerateForm characterId={characterId} view={view} onBuilt={(name) => { setPicked(name); onMode("export"); }} />
      ) : (
        <ExportView characterId={characterId} picked={picked} onPick={setPicked} revision={view.changeset?.revision ?? null} />
      )}
    </section>
  );
}

function GenerateForm({ characterId, view, onBuilt }: { characterId: string; view: DraftView; onBuilt: (name: string) => void }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [provides, setProvides] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<BuildResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    deliveries.defaults().then((d) => { setFrom(d.from); setTo(d.to); setNote(d.note); }, (e: Error) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - start) / 1000)), 500);
    return () => clearInterval(timer);
  }, [busy]);

  const base = view.changeset?.baseView;
  const mismatch = !!base && !!from && base !== from;
  const build = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await deliveries.build(characterId, { from, to, ...(provides.trim() ? { provides: provides.trim() } : {}) });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div class="generate-form">
      <p class="small muted">
        把已保存的草稿编译成内容寻址变更集，再跑现有 <span class="mono">wf deliver</span>（≤5 MiB 分包、两种 manifest、requires 推导、prepush）、
        <span class="mono">wf check</span>，给了 provides 时再跑兼容检查。全部写到 <span class="mono">work/studio-deliveries/</span> 新目录；
        不改 store、补丁链、测试服或草稿。{note}
      </p>
      <form class="version-row" onSubmit={(e) => { e.preventDefault(); if (!busy) build(); }}>
        <label>来源版本 <input class="mono" value={from} onInput={(e) => setFrom((e.target as HTMLInputElement).value)} size={9} /></label>
        <span aria-hidden="true">→</span>
        <label>目标版本 <input class="mono" value={to} onInput={(e) => setTo((e.target as HTMLInputElement).value)} size={9} /></label>
        <button type="submit" class="primary" disabled={busy || !from || !to}>{busy ? `生成中…… ${elapsed}s` : "生成本地交付"}</button>
      </form>
      <details>
        <summary>可选：目标客户端 provides.json（不填则兼容检查「未执行」）</summary>
        <input class="mono wide-input" placeholder="例如 work/…/v34-provides.json 的绝对路径" value={provides}
          onInput={(e) => setProvides((e.target as HTMLInputElement).value)} />
      </details>
      {mismatch ? <Notice kind="warn">草稿基于视图 {base}，来源版本填的是 {from}：生成会拒绝（草稿必须在来源视图上制作）。</Notice> : null}
      {view.status.state !== "saved" ? <Notice kind="warn">草稿有未保存的修订，请先保存。</Notice> : null}
      {busy ? <p class="small muted">正在锁定来源视图、编译草稿并运行 deliver / check（139985 一条词条约 30 秒）……</p> : null}
      {error ? <Notice kind="error">生成请求失败：{error}</Notice> : null}
      {result ? <BuildResultCard result={result} onOpen={() => onBuilt(result.name)} /> : null}
    </div>
  );
}

function BuildResultCard({ result, onOpen }: { result: BuildResult; onOpen: () => void }) {
  const checks = [...(result.checks ?? []), ...(result.compat ?? [])];
  return (
    <div class={"build-result " + (result.ok ? "ok" : "bad")}>
      <header>
        <strong>{result.ok ? "生成完成" : "生成失败"}</strong>
        <span class="mono small">{result.from} → {result.to}</span>
        {result.seconds !== undefined ? <span class="small muted">{result.seconds}s</span> : null}
        {checks.length ? <RuleChips counts={ruleCounts(checks)} /> : null}
        <span class="spacer" />
        <button onClick={onOpen}>查看导出 →</button>
      </header>
      {result.error ? <p class="error-text">{result.error}</p> : null}
      {result.prepush ? (
        <p class="small">prepush：{result.prepush.status}（exit {result.prepush.exit_code}）
          {result.prepush.limitations?.length ? <span class="muted"> · {result.prepush.limitations.join("；")}</span> : null}</p>
      ) : null}
      <p class="small muted">实测：{result.deviceValidation}。检查通过只代表文件与静态能力证据，不代表真机生效。</p>
    </div>
  );
}

function ExportView({ characterId, picked, onPick, revision }: {
  characterId: string; picked: string | null; onPick: (name: string) => void; revision: number | null;
}) {
  const { list } = useDeliveries(characterId);
  useEffect(() => {
    if (!picked && list && list.length) onPick(list[0].name);
  }, [list]);
  if (!list) return <div class="loading small">正在读取交付目录……</div>;
  if (!list.length) return <Notice>还没有生成过交付。先点「生成」。</Notice>;
  return (
    <div class="export-view">
      <ul class="delivery-list" role="listbox" aria-label="已生成的交付">
        {list.map((d) => (
          <li role="option" aria-selected={d.name === picked} class={d.name === picked ? "on" : ""}>
            <button class="ghost" onClick={() => onPick(d.name)}>
              <span class={d.ok ? "state-ok" : "error-text"}>{d.ok ? "完成" : "失败"}</span>
              <span class="mono small">{d.from} → {d.to}</span>
              <span class="small muted">{d.name.slice(-15)}</span>
              {d.draftRevision != null && revision != null && d.draftRevision !== revision ? <span class="tag">旧修订 {d.draftRevision}</span> : null}
            </button>
          </li>
        ))}
      </ul>
      {picked ? <DeliveryDetailView name={picked} /> : null}
    </div>
  );
}

function DeliveryDetailView({ name }: { name: string }) {
  const [detail, setDetail] = useState<DeliveryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    setDetail(null);
    deliveries.detail(name).then(setDetail, (e: Error) => setError(e.message));
  }, [name]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!detail) return <div class="loading small">正在读取交付……</div>;
  const report = detail.report ?? detail.error;
  const req = detail.requires?.requires ?? {};
  const file = (path: string) => deliveries.fileUrl(name, path);
  const main = detail.files.filter((f) => !f.path.startsWith("delivery/validation/") && !f.path.startsWith("delivery/patches/"));
  return (
    <div class="delivery-detail">
      <div class="folder-row">
        <span class="small muted">交付目录</span>
        <span class="mono small path">{detail.path}</span>
        <button class="small-btn" onClick={() => navigator.clipboard?.writeText(detail.path).then(() => setCopied(true))}>
          {copied ? "已复制" : "复制路径"}
        </button>
      </div>
      {report && !report.ok ? <Notice kind="error">生成失败：{report.error ?? "检查或 prepush 未通过，见下方结果"}</Notice> : null}
      <div class="status-strip compact">
        <div><span class="label">保存状态</span><span class="value">草稿修订 {report?.draftRevision ?? "—"}</span></div>
        <div><span class="label">检查结果</span><span class="value"><RuleChips counts={ruleCounts([...(detail.check ?? []), ...(detail.compat ?? [])])} /></span></div>
        <div><span class="label">实测情况</span><span class="value state-none">未记录（{detail.deviceValidation}）</span></div>
      </div>

      <h4>ZIP（{detail.archives.length}）</h4>
      <table class="files">
        <thead><tr><th>文件</th><th>大小</th><th>成员</th><th>SHA-256</th></tr></thead>
        <tbody>
          {detail.archives.map((a) => (
            <tr>
              <td class="mono small"><a href={file("delivery/" + a.name)} download={a.name}>{a.name}</a></td>
              <td class="nowrap">{size(a.size)}</td>
              <td>{a.members}</td>
              <td class="mono small" title={a.sha256}>{a.sha256?.slice(0, 12)}…</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>清单成员（{detail.members.length}）{detail.serverChanges.length ? ` · 服务端镜像 ${detail.serverChanges.length}` : ""}</h4>
      <table class="files">
        <thead><tr><th>逻辑路径</th><th>根</th><th>原 → 新</th></tr></thead>
        <tbody>
          {detail.members.map((m) => (
            <tr>
              <td class="mono small">{m.logical}</td>
              <td>{m.root}</td>
              <td class="mono small">{m.before ? m.before.slice(0, 10) : "（新）"} → {m.sha256.slice(0, 10)}</td>
            </tr>
          ))}
          {detail.serverChanges.map((s) => (
            <tr><td class="mono small">{s.target}</td><td>server</td><td class="mono small">→ {s.sha256.slice(0, 10)}</td></tr>
          ))}
        </tbody>
      </table>

      <h4>requires.json</h4>
      {detail.requires ? (
        <div class="requires small">
          <div>客户端能力：{(req.clientCapabilities ?? []).map((c: string) => <span class="tag mono">{c}</span>)}{!(req.clientCapabilities ?? []).length ? "无" : null}</div>
          <div>客户端补丁：{(req.clientPatches ?? []).map((c: string) => <span class="tag mono">{c}</span>)}{!(req.clientPatches ?? []).length ? "无" : null}</div>
          <div>服务端功能：{(req.serverFeatures ?? []).map((c: string) => <span class="tag mono">{c}</span>)}{!(req.serverFeatures ?? []).length ? "无" : null}
            · 解析：{req.capabilityResolution ?? "—"}</div>
          <a href={file("delivery/requires.json")} target="_blank" rel="noreferrer">打开原文</a>
        </div>
      ) : <p class="small muted">没有 requires.json（生成未完成）。</p>}

      {detail.check ? <RuleList checks={detail.check} title="wf check（交付清单）" /> : <p class="small muted">没有 check.json。</p>}
      {detail.compat ? <RuleList checks={detail.compat} title="兼容检查（provides）" /> : null}

      <details>
        <summary>全部文件（{detail.files.length}，不含 inputs/blobs）</summary>
        <ul class="file-list small">
          {main.concat(detail.files.filter((f) => !main.includes(f))).map((f) => (
            <li><a class="mono" href={file(f.path)} target="_blank" rel="noreferrer"
              {...(f.path.endsWith(".zip") ? { download: f.path.split("/").pop() } : {})}>{f.path}</a> <span class="muted">{size(f.size)}</span></li>
          ))}
        </ul>
      </details>
    </div>
  );
}
