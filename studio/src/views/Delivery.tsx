import { useEffect, useRef, useState } from "preact/hooks";
import { BuildJob, BuildResult, deliveries, DeliveryApi, DeliveryDetail, DeliverySummary, DraftView, onDraftChange } from "../api";
import { Notice } from "./common";
import { RuleChips, ruleCounts, RuleList } from "./rules";
import { useClientProfile } from "../clientProfile";
import { MissingCapabilities, ProfileBadge } from "./ClientProfile";
import { DeviceBadge, DevicePanel, sameDraft, useDeviceEntry } from "./DeviceResult";
import { BundleCheckPanel, ClientExtensionsPanel, IconAlphaPanel, KeyDiffPanel, RehearsalPanel, ApplyPanel, OverlayPanel } from "./DeliveryGuards";

function size(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

/** Latest delivery for a character or boss draft (refreshed after any draft write or build). */
export function useDeliveries(cid: string, api: DeliveryApi = deliveries): {
  list: DeliverySummary[] | null; currentRevision: number | null; reload: () => void;
} {
  const [list, setList] = useState<DeliverySummary[] | null>(null);
  const [currentRevision, setRevision] = useState<number | null>(null);
  const reload = () => {
    if (!cid) { setList([]); return Promise.resolve(); }
    return api.list(cid).then((r) => { setList(r.deliveries); setRevision(r.currentRevision ?? null); }, () => setList([]));
  };
  useEffect(() => {
    setList(null);
    reload();
    return onDraftChange((changed) => { if (changed === api.key(cid)) reload(); });
  }, [cid, api]);
  return { list, currentRevision, reload };
}

export function DeliveryPanel({ characterId, mode, view, onMode, api = deliveries, initialPick = null }: {
  characterId: string; mode: "generate" | "export"; view: DraftView; onMode: (m: "generate" | "export") => void;
  api?: DeliveryApi; initialPick?: string | null;
}) {
  const [picked, setPicked] = useState<string | null>(initialPick);
  useEffect(() => { if (initialPick) setPicked(initialPick); }, [initialPick]);
  return (
    <section class="delivery-panel">
      <nav class="segmented" aria-label="生成或导出">
        <button class={mode === "generate" ? "on" : ""} onClick={() => onMode("generate")}>生成</button>
        <button class={mode === "export" ? "on" : ""} onClick={() => onMode("export")}>导出</button>
      </nav>
      {mode === "generate" ? (
        <GenerateForm characterId={characterId} view={view} api={api} onBuilt={(name) => { setPicked(name); onMode("export"); }} />
      ) : (
        <ExportView characterId={characterId} picked={picked} onPick={setPicked} revision={view.changeset?.revision ?? null} changeset={view.changeset} api={api} />
      )}
    </section>
  );
}

const STAGE_STATE: Record<string, string> = { waiting: "等待", running: "进行中", done: "完成", failed: "失败", cancelled: "已取消" };

function GenerateForm({ characterId, view, onBuilt, api }: {
  characterId: string; view: DraftView; onBuilt: (name: string) => void; api: DeliveryApi;
}) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [provides, setProvides] = useState("");
  const [note, setNote] = useState("");
  const [job, setJob] = useState<BuildJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const poll = useRef<number | undefined>(undefined);

  useEffect(() => {
    api.defaults().then((d) => { setFrom(d.from); setTo(d.to); setNote(d.note); }, (e: Error) => setError(e.message));
    // Resume a build that is still running (page reloaded or tab switched).
    api.list(characterId).then((r) => {
      const running = r.jobs?.find((j) => j.state === "running");
      if (running) follow(running);
    }, () => undefined);
    return () => window.clearTimeout(poll.current);
  }, [characterId]);

  const follow = (current: BuildJob) => {
    setJob(current);
    window.clearTimeout(poll.current);
    if (current.state !== "running") {
      setCancelling(false);
      api.finished(characterId);
      return;
    }
    poll.current = window.setTimeout(() => {
      api.job(current.name).then(follow, (e: Error) => { setError(e.message); setJob(null); });
    }, 700);
  };

  const profile = useClientProfile();
  const custom = provides.trim();
  const base = view.changeset?.baseView;
  const mismatch = !!base && !!from && base !== from;
  const busy = job?.state === "running";
  const build = async () => {
    setError(null);
    setJob(null);
    try {
      // The selected profile always travels with the request; a typed evidence file replaces it (never both).
      follow(await api.start(characterId, { from, to, ...(custom ? { provides: custom }
        : profile.selected ? { clientProfile: profile.selected } : {}) }));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const cancel = async () => {
    setCancelling(true);
    try { await api.cancel(characterId); } catch (e) { setError((e as Error).message); setCancelling(false); }
  };
  const result = job && job.state !== "running" ? job.result : null;

  return (
    <div class="generate-form">
      <p class="small muted">
        把已保存的草稿打成本地测试补丁：编译草稿 → 分包与清单（每包 ≤5 MiB）→ 兼容检查（按目标客户端的能力证据）→ 交付检查。
        全部写到 <span class="mono">work/studio-deliveries/</span> 新目录，不改测试服、不改草稿。{note}
        <InfoTip text="技术细节：内容寻址变更集 + wf deliver（两种 manifest、requires 推导、prepush）+ wf check + compat。" />
      </p>
      <form class="version-row" onSubmit={(e) => { e.preventDefault(); if (!busy) build(); }}>
        <label>来源版本 <input class="mono" value={from} onInput={(e) => setFrom((e.target as HTMLInputElement).value)} size={9} /></label>
        <span aria-hidden="true">→</span>
        <label>目标版本 <input class="mono" value={to} onInput={(e) => setTo((e.target as HTMLInputElement).value)} size={9} /></label>
        <button type="submit" class="primary" disabled={busy || !from || !to || (!custom && !profile.selected && !profile.error)}>{busy ? `生成中…… ${Math.round(job?.seconds ?? 0)}s` : "生成本地交付"}</button>
        {busy ? <button type="button" onClick={cancel} disabled={cancelling}>{cancelling ? "取消中……" : "取消"}</button> : null}
      </form>
      <div class="profile-line">
        <span class="small">兼容检查按目标客户端</span>
        {custom ? <span class="profile-badge none">自定义能力清单</span> : <ProfileBadge id={profile.selected} title={profile.info?.description} />}
        <span class="small muted">{custom ? "（已填自定义清单，不按页面顶部的目标客户端检查）"
          : profile.error ? `客户端档案读取失败（${profile.error}），生成时由后端用默认档案`
          : `${profile.info?.packageName ?? ""}${profile.info?.versionCode ? " · versionCode " + profile.info.versionCode : ""} · 在页面顶部「目标客户端」切换`}</span>
      </div>
      <details>
        <summary>高级：改用自定义能力清单（wf apk provides 的输出；填了就不按目标客户端检查）</summary>
        <input class="mono wide-input" placeholder="例如 work/…/my-provides.json 的绝对路径" value={provides}
          onInput={(e) => setProvides((e.target as HTMLInputElement).value)} />
      </details>
      {mismatch ? <Notice kind="warn">草稿基于视图 {base}，来源版本填的是 {from}：生成会拒绝（草稿必须在来源视图上制作）。</Notice> : null}
      {view.status.state !== "saved" ? <Notice kind="warn">草稿有未保存的修订，请先保存。</Notice> : null}
      {busy && job ? <p class="small muted">正在按 {job.clientProfile ? <ProfileBadge id={job.clientProfile} /> : "自定义能力清单"} 检查。</p> : null}
      {job ? (
        <ol class="build-stages" aria-label="生成进度">
          {job.stages.map((s) => (
            <li class={"stage-" + s.state}><span class="stage-dot" aria-hidden="true" />{s.label}<span class="small muted"> · {STAGE_STATE[s.state] ?? s.state}</span></li>
          ))}
        </ol>
      ) : null}
      {cancelling && busy ? <p class="small muted">当前阶段结束后停止，半成品目录会删除。</p> : null}
      {error ? <Notice kind="error">生成请求失败：{error}</Notice> : null}
      {job?.state === "cancelled" ? <Notice>已取消生成。</Notice> : null}
      {result && job?.state !== "cancelled" ? <BuildResultCard result={result} onOpen={() => onBuilt(result.name)} /> : null}
    </div>
  );
}

export function InfoTip({ text }: { text: string }) {
  return <span class="info-tip" title={text} aria-label={text} tabIndex={0}>ⓘ</span>;
}

function BuildResultCard({ result, onOpen }: { result: BuildResult; onOpen: () => void }) {
  // compat is the status string; the per-item compat results are compatChecks.
  const compat = result.compatChecks ?? (Array.isArray(result.compat) ? result.compat : []);
  const checks = [...(result.checks ?? []), ...compat];
  return (
    <div class={"build-result " + (result.ok ? "ok" : "bad")}>
      <header>
        <strong>{result.ok ? "生成完成" : "生成失败"}</strong>
        <span class="mono small">{result.from} → {result.to}</span>
        <span class="small">目标客户端 <ProfileBadge id={result.clientProfile} title={result.clientProfile ? undefined : "这次生成用的是自定义能力清单或没有客户端证据"} /></span>
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
      {typeof result.compat === "string" ? <p class="small">兼容检查（客户端能力）：{result.compat}</p> : null}
      <MissingCapabilities checks={compat} profile={result.clientProfile} />
      {result.draftChecks?.length ? <p class="small">草稿规则（编译时重放）：<RuleChips counts={ruleCounts(result.draftChecks)} /></p> : null}
      <p class="small muted">实测：{result.deviceValidation}。检查通过只代表文件与静态能力证据，不代表真机生效。</p>
    </div>
  );
}

function ExportView({ characterId, picked, onPick, revision, changeset, api }: {
  characterId: string; picked: string | null; onPick: (name: string) => void; revision: number | null; api: DeliveryApi;
  changeset?: DraftView["changeset"];
}) {
  const { list } = useDeliveries(characterId, api);
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
              {d.draftRevision != null && revision != null && d.draftRevision !== revision ? <span class="tag">旧修订 {d.draftRevision}</span>
                : d.draftRevision != null && changeset && !sameDraft(d, changeset) ? <span class="tag" title="草稿删掉重建过，修订号相同但不是同一份草稿">旧草稿</span> : null}
              {d.device ? <span title={`实测 ${d.device.testedAt ?? ""}`}><DeviceBadge status={d.device.status}
                stale={!!d.device.stale} /></span> : null}
            </button>
          </li>
        ))}
      </ul>
      {picked ? <DeliveryDetailView name={picked} api={api} characterId={characterId} /> : null}
    </div>
  );
}

function DeliveryDetailView({ name, api, characterId }: { name: string; api: DeliveryApi; characterId: string }) {
  const [detail, setDetail] = useState<DeliveryDetail | null>(null);
  const [device, setDevice] = useDeviceEntry(detail?.deviceResult);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    setDetail(null);
    api.detail(name).then(setDetail, (e: Error) => setError(e.message));
  }, [name, api]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!detail) return <div class="loading small">正在读取交付……</div>;
  const report = detail.report ?? detail.error;
  const req = detail.requires?.requires ?? {};
  const file = (path: string) => api.fileUrl(name, path);
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
      <div class="profile-line"><span class="small">兼容检查按目标客户端</span> <ProfileBadge id={report?.clientProfile} /></div>
      <MissingCapabilities checks={detail.compat ?? []} profile={report?.clientProfile} />
      <div class="status-strip compact">
        <div><span class="label">保存状态</span><span class="value">草稿修订 {report?.draftRevision ?? "—"}</span></div>
        <div><span class="label">检查结果</span><span class="value"><RuleChips counts={ruleCounts([...(detail.check ?? []), ...(detail.compat ?? [])])} /></span></div>
        <div><span class="label">实测情况</span><span class="value">
          {device?.result ? <><DeviceBadge status={device.result.status} stale={device.stale} /> <span class="small muted">{device.result.testedAt}</span></>
            : <span class="state-none">未执行</span>}</span></div>
      </div>
      <DevicePanel name={name} cid={characterId} entry={device} api={api} onChange={setDevice} />

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

      <BundleCheckPanel check={detail.bundleCheck} />
      <KeyDiffPanel diff={detail.keyDiff}
        mdUrl={detail.files.some((f) => f.path === "delivery/key-diff.md") ? file("delivery/key-diff.md") : null} />
      <IconAlphaPanel result={detail.iconAlpha} />
      <ClientExtensionsPanel result={detail.clientExtensions} />
      <RehearsalPanel name={name} initial={detail.rehearsal} rehearse={api.rehearse} fileUrl={file} />
      <ApplyPanel name={name} api={api} />
      <OverlayPanel name={name} api={api} available={detail.overlayAvailable} reason={detail.overlayReason} fileUrl={file} />

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
