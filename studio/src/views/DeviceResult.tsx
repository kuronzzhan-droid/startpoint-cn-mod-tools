import { useEffect, useState } from "preact/hooks";
import {
  DEVICE_STATUSES, DeliveryApi, DeliverySummary, DeviceCheck, DeviceEntry, DeviceResult, DeviceStatus, DeviceWrite,
  drafts, screenshotUrl,
} from "../api";
import { Notice } from "./common";
import "./device.css";

const STATUS_CLASS: Record<string, string> = {
  通过: "dev-pass", 失败: "dev-fail", 未执行: "dev-none", 作废: "dev-void", 无效: "dev-fail",
};

export function DeviceBadge({ status, stale }: { status: string; stale?: boolean }) {
  return <span class={"dev-badge " + (stale ? "dev-stale" : STATUS_CLASS[status] ?? "dev-none")}>{stale ? "实测已过期" : status}</span>;
}

/** Date part of an ISO-ish timestamp, for the strip (full value goes in the title). */
export function shortDate(value?: string): string {
  if (!value) return "";
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
  return m ? `${m[2]}-${m[3]}${m[4] ? " " + m[4] + ":" + m[5] : ""}` : value;
}

/** The delivery built from exactly this saved draft (same revision and, when known, same draft creation time). */
export function sameDraft(d: { draftRevision: number | null; draftCreatedAt?: string | null }, changeset: { revision: number; createdAt: string } | null | undefined): boolean {
  if (!changeset || d.draftRevision !== changeset.revision) return false;
  return !d.draftCreatedAt || !changeset.createdAt || d.draftCreatedAt === changeset.createdAt;
}

export interface DeviceCell {
  status: string;
  stale: boolean;
  delivery: string | null;
  testedAt?: string;
  title: string;
}

/**
 * 「实测」 cell of the three-status bar: the device result of the delivery built from the current
 * draft revision; otherwise the newest result of an older revision, shown as 实测已过期.
 */
export function deviceCell(list: DeliverySummary[] | null, revision: number | null | undefined): DeviceCell {
  const tested = (list ?? []).filter((d) => d.device && d.device.status);
  const newest = (items: DeliverySummary[]) =>
    [...items].sort((a, b) => (b.device?.testedAt ?? "").localeCompare(a.device?.testedAt ?? ""))[0];
  // The backend marks a result stale when the draft's revision (or creation time) no longer matches the delivery.
  const current = newest(tested.filter((d) => !d.device!.stale && (revision == null || d.draftRevision === revision)));
  if (current?.device) {
    return { status: current.device.status, stale: false, delivery: current.name, testedAt: current.device.testedAt,
      title: `交付 ${current.name} · 草稿修订 ${current.draftRevision} · 实测 ${current.device.testedAt ?? "—"}` +
        (current.device.tester ? ` · ${current.device.tester}` : "") };
  }
  const older = newest(tested);
  if (older?.device) {
    return { status: older.device.status, stale: true, delivery: older.name, testedAt: older.device.testedAt,
      title: `最近一次实测针对修订 ${older.draftRevision ?? "—"} 的交付 ${older.name}（${older.device.status}），草稿已改到修订 ${revision ?? "—"}；需要重新生成并实测` };
  }
  return { status: "未执行", stale: false, delivery: null,
    title: list && list.length ? "这些交付还没有记录实测（在「导出」的交付详情里记录）" : "还没有生成交付" };
}

export function DeviceCellValue({ cell, link }: { cell: DeviceCell; link?: (name: string) => string }) {
  const badge = <DeviceBadge status={cell.status} stale={cell.stale} />;
  return (
    <span class="value" title={cell.title}>
      {cell.delivery && link ? <a href={link(cell.delivery)}>{badge}</a> : badge}
      {cell.testedAt ? <span class="small muted"> {shortDate(cell.testedAt)}</span> : null}
      {cell.stale ? <span class="small muted"> · 上次 {cell.status}</span> : null}
      {cell.delivery && link ? <> <a class="small" href={link(cell.delivery)}>查看</a></> : null}
    </span>
  );
}

// ---------------------------------------------------------------------------
// 交付详情里的完整实测记录 + 记录 / 更新 / 导入

export function DevicePanel({ name, cid, entry, api, onChange }: {
  name: string; cid: string; entry: DeviceEntry | null | undefined; api: DeliveryApi; onChange: (entry: DeviceEntry) => void;
}) {
  const [mode, setMode] = useState<"view" | "edit" | "import">("view");
  const result = entry?.result ?? null;
  const writable = drafts.hasToken();
  return (
    <section class="device-panel" aria-label="实测记录">
      <header class="device-head">
        <h4>实测记录</h4>
        {result ? <><DeviceBadge status={result.status} /><span class="tag">{result.testType ?? "未分类"}</span></> : entry ? <DeviceBadge status="无效" /> : <DeviceBadge status="未执行" />}
        {entry?.stale ? <DeviceBadge status="" stale /> : null}
        <span class="spacer" />
        {mode === "view" ? (
          <>
            <button class="small-btn" disabled={!writable} onClick={() => setMode("edit")}>{result ? "更新实测" : "记录实测"}</button>
            <button class="small-btn" disabled={!writable} onClick={() => setMode("import")}>导入 device-result.json</button>
          </>
        ) : <button class="small-btn" onClick={() => setMode("view")}>取消</button>}
      </header>
      {!writable ? <p class="small muted">页面没有写入令牌，只能查看。</p> : null}
      {mode === "edit" ? (
        <DeviceForm initial={result} onSubmit={async (body) => {
          const r = await api.writeDevice(cid, name, body);
          onChange(r.deviceResult);
          setMode("view");
        }} />
      ) : mode === "import" ? (
        <ImportForm onSubmit={async (path, loose) => {
          const r = await api.importDevice(cid, name, path, loose);
          onChange(r.deviceResult);
          setMode("view");
        }} />
      ) : entry ? <DeviceView entry={entry} /> : (
        <p class="small muted">这份交付还没有实测记录。装机测试后点「记录实测」，或导入已有的 device-result.json。
          记录写在交付目录的 <span class="mono">device-result.json</span>；agent 可用
          <span class="mono"> python -m wf.studio.draft device-result</span>。</p>
      )}
    </section>
  );
}

function DeviceView({ entry }: { entry: DeviceEntry }) {
  const r = entry.result;
  if (!r) return <Notice kind="error">device-result.json 读不了：{entry.errors.join("；")}</Notice>;
  const shots = new Map(entry.screenshots.map((s) => [s.path, s]));
  const d = r.device ?? {};
  return (
    <div class="device-view">
      {entry.stale ? (
        <Notice kind="warn">实测已过期：这份交付由草稿修订 {r.delivery.draftRevision ?? "—"} 生成，之后草稿改过或删掉重建（现在修订 {entry.currentRevision ?? "—"}）。
          重新生成并装机后再记录。</Notice>
      ) : null}
      {entry.bindingMismatch ? <Notice kind="error">记录里的交付绑定（{r.delivery.name}）与这个目录不一致：文件可能是从别处复制来的。</Notice> : null}
      {entry.errors.length ? <Notice kind="warn">记录有 {entry.errors.length} 处不符合 schema：{entry.errors.slice(0, 3).join("；")}</Notice> : null}
      {entry.legacy ? <p class="small muted">旧版手写记录（wf-device-result/1），按新结构显示，原文件没改；「更新实测」会写成新版并保留旧文件。</p> : null}
      {r.importedFrom ? (
        <p class="small muted">导入自 <span class="mono">{r.importedFrom.path}</span>（{r.importedFrom.schema}，
          {r.importedFrom.archivesMatch === true ? "ZIP 与本交付一致" : "来源没有清单，未核对 ZIP"}）</p>
      ) : null}
      {r.reason ? <p class="small"><span class="label">原因</span> {r.reason}</p> : null}
      <dl class="device-facts">
        <dt>实测时间</dt><dd>{r.testedAt}{r.tester ? ` · ${r.tester}` : ""}<span class="muted small">{r.recordedAt ? `（记录于 ${r.recordedAt}）` : ""}</span></dd>
        <dt>设备</dt><dd>{[d.id, d.label].filter(Boolean).join(" · ") || "—"}{d.emulator ? <span class="tag">模拟器</span> : null}
          {d.package ? <span class="tag mono">{d.package}</span> : null}</dd>
        {d.apk || d.apkSha256 ? <><dt>APK</dt><dd class="mono small">{d.apk}{d.apkSha256 ? ` · ${d.apkSha256.slice(0, 12)}…` : ""}</dd></> : null}
        {r.server ? <><dt>服务端</dt><dd>{r.server}</dd></> : null}
        <dt>客户端资源</dt><dd class="mono">{r.client?.versionBefore || "—"} → {r.client?.versionAfter || "—"}
          {r.client?.profile ? <span class="small muted"> · 档案 {r.client.profile}</span> : null}</dd>
        <dt>装入的链边</dt><dd>{(r.chainEdges ?? []).length ? r.chainEdges!.map((e) => <span class="tag mono" title={e.note}>{e.version}</span>) : "—"}</dd>
        <dt>交付</dt><dd class="mono small">{r.delivery.from} → {r.delivery.to} · 草稿修订 {r.delivery.draftRevision ?? "—"}</dd>
        {r.restore ? <><dt>恢复</dt><dd>{r.restore.method || "—"}{(r.restore.edges ?? []).map((v) => <span class="tag mono">{v}</span>)}
          {r.restore.verified != null ? <span class={r.restore.verified ? "dev-ok-text" : "warn-text"}> · {r.restore.verified ? "已核对" : "未核对"}</span> : null}
          {r.restore.notes ? <div class="small muted">{r.restore.notes}</div> : null}</dd></> : null}
        {r.errorCodes?.length || r.errorScan ? <><dt>错误码</dt><dd>{(r.errorCodes ?? []).map((c) => <span class="tag mono">{c}</span>)}
          {!(r.errorCodes ?? []).length ? "无" : null}{r.errorScan ? <div class="small muted">{r.errorScan}</div> : null}</dd></> : null}
      </dl>
      <h5>检查项（{r.checks.length}）</h5>
      {r.checks.length ? (
        <table class="files device-checks">
          <thead><tr><th>项</th><th>预期</th><th>实际</th><th>结论</th><th>截图</th></tr></thead>
          <tbody>
            {r.checks.map((c) => (
              <tr>
                <td>{c.item}</td><td>{c.expected}</td><td>{c.observed}</td>
                <td>{c.status ? <DeviceBadge status={c.status} /> : "—"}</td>
                <td>{c.screenshot ? <Shot shot={shots.get(c.screenshot) ?? { path: c.screenshot, name: c.screenshot, allowed: false, exists: false }} small /> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p class="small muted">没有逐项检查。</p>}
      {entry.screenshots.length ? (
        <>
          <h5>截图（{entry.screenshots.length}）</h5>
          <div class="shot-grid">{entry.screenshots.map((s) => <Shot shot={s} />)}</div>
        </>
      ) : null}
      {r.notes ? <><h5>备注</h5><p class="device-notes">{r.notes}</p></> : null}
      {entry.history ? <p class="small muted">之前的 {entry.history} 版记录在交付目录 device-results/ 下。</p> : null}
    </div>
  );
}

function Shot({ shot, small }: { shot: DeviceEntry["screenshots"][number]; small?: boolean }) {
  if (!shot.allowed || !shot.exists) {
    return <span class="shot-missing small" title={shot.path}>{shot.name}<br />
      <span class="muted">{!shot.allowed ? "不在截图白名单目录（profiles 的 paths.studio_screenshots）" : "文件不存在"}</span></span>;
  }
  const url = screenshotUrl(shot.path);
  return (
    <a class={"shot" + (small ? " small" : "")} href={url} target="_blank" rel="noreferrer" title={shot.path}>
      <img src={url} alt={shot.name} loading="lazy" decoding="async" />
      {small ? null : <span class="small mono">{shot.name}</span>}
    </a>
  );
}

// ---------------------------------------------------------------------------

function localNow(): string {
  const t = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}T${pad(t.getHours())}:${pad(t.getMinutes())}`;
}

const lines = (text: string) => text.split(/\r?\n/).map((v) => v.trim()).filter(Boolean);
const words = (text: string) => text.split(/[,，\s]+/).map((v) => v.trim()).filter(Boolean);
const EMPTY_CHECK: DeviceCheck = { item: "", expected: "", observed: "" };

function DeviceForm({ initial, onSubmit }: { initial: DeviceResult | null; onSubmit: (body: DeviceWrite) => Promise<void> }) {
  const [testType, setTestType] = useState<"" | "单机" | "三开联机">(initial?.testType ?? "");
  const [status, setStatus] = useState<DeviceStatus>(initial?.status ?? "通过");
  const [testedAt, setTestedAt] = useState(initial?.testedAt ?? localNow());
  const [tester, setTester] = useState(initial?.tester ?? "");
  const [device, setDevice] = useState({ id: "", label: "", package: "", apk: "", apkSha256: "", ...initial?.device });
  const [emulator, setEmulator] = useState(initial?.device?.emulator ?? true);
  const [server, setServer] = useState(initial?.server ?? "");
  const [client, setClient] = useState({ versionBefore: "", versionAfter: "", profile: "", ...initial?.client });
  const [edges, setEdges] = useState((initial?.chainEdges ?? []).map((e) => e.version).join(", "));
  const [checks, setChecks] = useState<DeviceCheck[]>(initial?.checks?.length ? initial.checks.map((c) => ({ ...c })) : [{ ...EMPTY_CHECK }]);
  const [shots, setShots] = useState((initial?.screenshots ?? []).join("\n"));
  const [codes, setCodes] = useState((initial?.errorCodes ?? []).join(", "));
  const [errorScan, setErrorScan] = useState(initial?.errorScan ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [reason, setReason] = useState(initial?.reason ?? "");
  const [restore, setRestore] = useState({ method: "", notes: "", ...initial?.restore, edges: (initial?.restore?.edges ?? []).join(", ") });
  const [restoreVerified, setRestoreVerified] = useState(initial?.restore?.verified ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setCheck = (i: number, patch: Partial<DeviceCheck>) => setChecks(checks.map((c, n) => (n === i ? { ...c, ...patch } : c)));
  const trimmed = (o: Record<string, string | undefined>) =>
    Object.fromEntries(Object.entries(o).map(([k, v]) => [k, (v ?? "").trim()]).filter(([, v]) => v));

  const submit = async () => {
    setError(null);
    const body: DeviceWrite = {
      status, ...(testType ? { testType } : {}), testedAt: testedAt.trim(),
      checks: checks.filter((c) => c.item.trim()).map((c) => ({
        item: c.item.trim(), ...trimmed({ expected: c.expected, observed: c.observed, screenshot: c.screenshot }),
        ...(c.status ? { status: c.status } : {}) })),
      device: { ...trimmed({ id: device.id, label: device.label, package: device.package, apk: device.apk,
        apkSha256: device.apkSha256?.toLowerCase() }), emulator },
      client: trimmed(client),
      chainEdges: words(edges).map((version) => ({ version, ...(initial?.chainEdges?.find((e) => e.version === version)?.note
        ? { note: initial!.chainEdges!.find((e) => e.version === version)!.note } : {}) })),
      screenshots: lines(shots),
      errorCodes: words(codes),
      ...trimmed({ tester, server, errorScan, notes, reason }),
    };
    if (restore.method.trim() || restore.edges.trim() || (restore.notes ?? "").trim()) {
      body.restore = { ...trimmed({ method: restore.method, notes: restore.notes }), edges: words(restore.edges), verified: restoreVerified };
    }
    if (initial?.extra) body.extra = initial.extra;
    setBusy(true);
    try { await onSubmit(body); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const input = (value: string, set: (v: string) => void, attrs: Record<string, unknown> = {}) =>
    <input class="text-input" value={value} onInput={(e) => set((e.target as HTMLInputElement).value)} {...attrs} />;

  return (
    <form class="device-form" onSubmit={(e) => { e.preventDefault(); if (!busy) submit(); }}>
      <div class="device-grid">
        <label>实测类型<select value={testType} onChange={(e) => setTestType(e.currentTarget.value as typeof testType)}><option value="">未分类</option><option>单机</option><option>三开联机</option></select></label>
        <label>结论<select value={status} onChange={(e) => setStatus((e.target as HTMLSelectElement).value as DeviceStatus)}>
          {DEVICE_STATUSES.map((s) => <option value={s}>{s}</option>)}</select></label>
        <label>实测时间{input(testedAt, setTestedAt, { placeholder: "2026-10-19T18:55" })}</label>
        <label>测试人{input(tester, setTester)}</label>
        <label>设备 / 模拟器 ID{input(device.id ?? "", (v) => setDevice({ ...device, id: v }), { placeholder: "MuMu-1 / adb 序列号" })}</label>
        <label>设备说明{input(device.label ?? "", (v) => setDevice({ ...device, label: v }))}</label>
        <label class="check"><input type="checkbox" checked={emulator} onChange={(e) => setEmulator((e.target as HTMLInputElement).checked)} />模拟器</label>
        <label>包名{input(device.package ?? "", (v) => setDevice({ ...device, package: v }), { placeholder: "com.leiting.wf" })}</label>
        <label>APK{input(device.apk ?? "", (v) => setDevice({ ...device, apk: v }))}</label>
        <label>APK SHA-256{input(device.apkSha256 ?? "", (v) => setDevice({ ...device, apkSha256: v }), { class: "text-input mono" })}</label>
        <label>服务端{input(server, setServer)}</label>
        <label>更新前客户端版本{input(client.versionBefore ?? "", (v) => setClient({ ...client, versionBefore: v }), { placeholder: "1.4.251" })}</label>
        <label>更新后客户端版本{input(client.versionAfter ?? "", (v) => setClient({ ...client, versionAfter: v }), { placeholder: "1.4.252" })}</label>
        <label>客户端档案{input(client.profile ?? "", (v) => setClient({ ...client, profile: v }))}</label>
        <label>装入的链边（逗号分隔）{input(edges, setEdges, { placeholder: "1.4.252, 1.4.253" })}</label>
      </div>
      {status === "作废" || status === "未执行" ? <label class="block">原因{input(reason, setReason)}</label> : null}
      <h5>检查项</h5>
      <div class="device-check-wrap"><table class="files device-check-form">
        <thead><tr><th>项</th><th>预期</th><th>实际</th><th>结论</th><th>截图路径</th><th /></tr></thead>
        <tbody>
          {checks.map((c, i) => (
            <tr>
              <td>{input(c.item, (v) => setCheck(i, { item: v }), { "aria-label": `检查项 ${i + 1}` })}</td>
              <td>{input(c.expected ?? "", (v) => setCheck(i, { expected: v }))}</td>
              <td>{input(c.observed ?? "", (v) => setCheck(i, { observed: v }))}</td>
              <td><select value={c.status ?? ""} onChange={(e) => setCheck(i, { status: ((e.target as HTMLSelectElement).value || undefined) as DeviceCheck["status"] })}>
                <option value="">—</option><option>通过</option><option>失败</option><option>未执行</option></select></td>
              <td>{input(c.screenshot ?? "", (v) => setCheck(i, { screenshot: v }), { class: "text-input mono" })}</td>
              <td><button type="button" class="small-btn" onClick={() => setChecks(checks.filter((_, n) => n !== i))} aria-label="删除这一项">删除</button></td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <button type="button" class="small-btn" onClick={() => setChecks([...checks, { ...EMPTY_CHECK }])}>加一项</button>
      <div class="device-grid wide">
        <label>截图（每行一个绝对路径）<textarea class="text-input mono" rows={3} value={shots} onInput={(e) => setShots((e.target as HTMLTextAreaElement).value)} /></label>
        <label>错误码（逗号分隔）{input(codes, setCodes)}<span class="small muted">日志扫描说明</span>{input(errorScan, setErrorScan)}</label>
        <label>恢复方式{input(restore.method ?? "", (v) => setRestore({ ...restore, method: v }), { placeholder: "恢复边 / 备份还原 / 未恢复" })}
          <span class="small muted">恢复边（逗号分隔）</span>{input(restore.edges, (v) => setRestore({ ...restore, edges: v }))}
          <span class="small muted">恢复说明</span>{input(restore.notes ?? "", (v) => setRestore({ ...restore, notes: v }))}
          <span class="check"><input type="checkbox" checked={restoreVerified} onChange={(e) => setRestoreVerified((e.target as HTMLInputElement).checked)} />已核对恢复结果</span></label>
        <label>备注<textarea class="text-input" rows={4} value={notes} onInput={(e) => setNotes((e.target as HTMLTextAreaElement).value)} /></label>
      </div>
      {error ? <Notice kind="error">写入失败：{error}</Notice> : null}
      <div class="toolbar">
        <button type="submit" class="primary" disabled={busy || !testedAt.trim()}>{busy ? "写入中……" : "写入实测记录"}</button>
        <span class="small muted">只写这个交付目录的 device-result.json（旧版本移到 device-results/）；交付绑定（修订、ZIP 摘要）由编辑台填写。</span>
      </div>
    </form>
  );
}

function ImportForm({ onSubmit }: { onSubmit: (path: string, allowUnverified: boolean) => Promise<void> }) {
  const [path, setPath] = useState("");
  const [loose, setLoose] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <form class="device-form" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true); setError(null);
      try { await onSubmit(path.trim(), loose); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
    }}>
      <p class="small muted">填别处交付目录里的 device-result.json（或那个交付目录）的绝对路径，例如另一个 worktree 的
        <span class="mono"> work/studio-deliveries/&lt;交付名&gt;/device-result.json</span>。
        来源交付的 ZIP 摘要必须与本交付一致；旧版 wf-device-result/1 会转换成新结构。</p>
      <input class="text-input mono" value={path} placeholder="…/studio-deliveries/<交付名>/device-result.json"
        onInput={(e) => setPath((e.target as HTMLInputElement).value)} aria-label="来源路径" />
      <label class="check small"><input type="checkbox" checked={loose} onChange={(e) => setLoose((e.target as HTMLInputElement).checked)} />
        来源没有交付清单时也导入（不核对 ZIP）</label>
      {error ? <Notice kind="error">导入失败：{error}</Notice> : null}
      <div class="toolbar"><button type="submit" class="primary" disabled={busy || !path.trim()}>{busy ? "导入中……" : "导入"}</button></div>
    </form>
  );
}

/** Keep a detail's device entry in sync after a write (and with other tabs' writes). */
export function useDeviceEntry(initial: DeviceEntry | null | undefined) {
  const [entry, setEntry] = useState(initial ?? null);
  useEffect(() => setEntry(initial ?? null), [initial]);
  return [entry, setEntry] as const;
}
