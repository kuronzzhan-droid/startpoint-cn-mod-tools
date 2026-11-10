import { useEffect, useState } from "preact/hooks";
import { corridor, DeployEntry, DiffResult, ReleaseSummary, short, TrialPlan, TrialStatus } from "../../corridorApi";
import { Notice } from "../common";
import { FindingList, Modal, Tag, useCorridor } from "./widgets";

function Impact({ diff }: { diff: DiffResult }) {
  const b = diff.impact.before as Record<string, any>;
  const a = diff.impact.after as Record<string, any>;
  const rows: [string, string, string][] = [];
  (a.acts ?? []).forEach((act: Record<string, any>, i: number) => {
    const old = (b.acts ?? [])[i] ?? {};
    rows.push([`第${act.act}幕遭遇数 / 段尾首领`, `${old.size} / ${old.boss}`, `${act.size} / ${act.boss}`]);
  });
  for (const [k, label] of [["characters_by_tier", "入池角色 T1/T2/T3/T4"], ["starter_by_element", "开局可用角色（火水雷风光暗）"],
    ["relics_by_rarity", "遗物 普通/稀有/首领"]] as const) {
    if (a[k]) rows.push([label, Object.values(b[k] ?? {}).join(" / "), Object.values(a[k]).join(" / ")]);
  }
  rows.push(["事件数", String(b.events), String(a.events)]);
  return (
    <table class="cor-table small">
      <thead><tr><th>影响</th><th>之前</th><th>之后</th></tr></thead>
      <tbody>{rows.map(([l, x, y]) => <tr key={l} class={x === y ? "dim" : ""}><td>{l}</td><td>{x}</td><td>{x === y ? y : <b>{y}</b>}</td></tr>)}</tbody>
    </table>
  );
}

function DiffView({ against, setAgainst, releases }: { against: string; setAgainst: (v: string) => void; releases: ReleaseSummary[] }) {
  const { tick, setError } = useCorridor();
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [pointers, setPointers] = useState(false);
  useEffect(() => { corridor.diff(against).then(setDiff, (e: Error) => setError(e.message)); }, [against, tick]);
  const areas = diff ? [...new Set(diff.readable.map((l) => l.area))] : [];
  return (
    <div class="cor-card">
      <h3>改动预览
        <select value={against} onChange={(e) => setAgainst((e.currentTarget as HTMLSelectElement).value)}>
          <option value="base">对比导入基线</option>
          <option value="trial">对比试验服当前内容</option>
          {releases.map((r) => <option key={r.id} value={"release:" + r.content_version}>对比发布包 {r.id}</option>)}
        </select>
      </h3>
      {!diff ? <div class="loading">计算差异…</div> : (
        <>
          <div class="muted small">基准：{diff.label} · {diff.readable.length} 条可读改动 · {diff.pointer_count} 个 JSON 指针 · {diff.files.length} 个文件变化</div>
          {diff.readable.length ? (
            <ul class="cor-diff">{areas.map((area) => diff.readable.filter((l) => l.area === area).map((l, i) => (
              <li key={area + i}><span class="area">{area}</span>{l.text}</li>)))}</ul>
          ) : <div class="muted">没有改动。</div>}
          {diff.files.length ? (
            <table class="cor-table small">
              <thead><tr><th>文件</th><th>之前</th><th>之后</th><th>服务端读取</th></tr></thead>
              <tbody>{diff.files.map((f) => (
                <tr key={f.name}><td class="mono">{f.name}</td><td class="mono">{short(f.before)}</td><td class="mono">{short(f.after)}</td>
                  <td>{f.server_reads ? "是" : <Tag kind="warn" title="locales 编进客户端；tier_overrides 给数据线生成器；policy 服务端未接入">否</Tag>}</td></tr>))}</tbody>
            </table>
          ) : null}
          <h4>游戏影响</h4>
          <Impact diff={diff} />
          <button class="ghost" onClick={() => setPointers(!pointers)}>{pointers ? "收起" : "展开"} JSON 指针差异</button>
          {pointers ? <pre class="cor-pre">{diff.pointers.map((p) => `${p.op} ${p.path}${"before" in p ? "  " + JSON.stringify(p.before) : ""}${"after" in p ? " → " + JSON.stringify(p.after) : ""}`).join("\n")}</pre> : null}
        </>
      )}
    </div>
  );
}

function ApplyDialog({ release, rollback, onClose, onDone }: { release: ReleaseSummary; rollback: boolean; onClose: () => void; onDone: (msg: string) => void }) {
  const [plan, setPlan] = useState<TrialPlan | null>(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { corridor.plan(release.content_version).then(setPlan, (e: Error) => setErr(e.message)); }, [release.content_version]);
  const m = (plan?.manifest ?? {}) as Record<string, any>;
  return (
    <Modal onClose={onClose}>
      <h2>{rollback ? "回滚试验服到此版本" : "应用到试验服"}</h2>
      {err ? <Notice kind="error"><div style="white-space:pre-wrap">{err}</div></Notice> : null}
      {!plan ? <div class="loading">检查目标与进行中的局…</div> : (
        <>
          <dl class="cor-kv">
            <dt>目标</dt><dd>隔离试验服（trialctl 管理，端口 {plan.ports?.join("/")}）</dd>
            <dt>试验服当前</dt><dd class="mono">{plan.active.label}</dd>
            <dt>将切换到</dt><dd class="mono">{short(release.content_version)}（工作区 r{m.workspace_revision}）</dd>
            <dt>说明</dt><dd>{m.message || "—"}</dd>
            <dt>宿主活动</dt><dd>{m.host ? `${m.host.event_id}/${m.host.folder_id}` : "?"}</dd>
            <dt>难度档</dt><dd>{m.active_profile === "test" ? <Tag kind="warn">test（试验倍率）</Tag> : m.active_profile}</dd>
            <dt>校验</dt><dd>阻断 {m.validation_summary?.blockers} · 警告 {m.validation_summary?.warnings}</dd>
            <dt>做法</dt><dd>发布包落到试验服 assets/rogue-content/ → Node 预检 → trialctl 停服 → 替换配置与叠加层 → trialctl 启动 → 日志健康检查；失败自动恢复原文件。</dd>
          </dl>
          {plan.guard.length ? <Notice kind="error">{plan.guard.join("；")}</Notice> : null}
          {plan.open_runs.length ? (
            <Notice kind={plan.blocked ? "error" : "warn"}>
              <b>进行中的局 {plan.open_runs.length}</b>（服务端没有内容版本锁）
              {plan.open_runs.map((r, i) => (
                <div key={i} class="small">{r.run_id ?? "?"} 第 {r.floor ?? "?"} 层：{r.breaking.length ? <span class="error-text">{r.breaking.join("；")}</span> : r.notes.join("；")}</div>
              ))}
              {plan.blocked ? <div>这些局会被破坏，拒绝应用：请先在游戏里放弃/结束它们，或在确认没人测试时手动 trialctl reset-db。</div> : (
                <label><input type="checkbox" checked={ack} onChange={(e) => setAck((e.currentTarget as HTMLInputElement).checked)} />
                  {" "}我知道这些局重启后会按新内容继续</label>
              )}
            </Notice>
          ) : <div class="small muted">没有进行中的局。</div>}
          <div class="cor-toolbar" style="margin-top:12px">
            <button class="primary" disabled={busy || plan.blocked || (plan.needs_ack && !ack)} onClick={async () => {
              setBusy(true); setErr(null);
              try {
                const r = await corridor.apply(release.content_version, plan.active.label, ack, rollback);
                const h = r.health as Record<string, any> | undefined;
                onDone(`${rollback ? "回滚" : "应用"}完成：试验服已切换到 ${short(release.content_version)}` +
                  (h?.loaded ? `（重启后加载 遗物 ${h.loaded.relics} / 事件 ${h.loaded.events} / 角色 ${h.loaded.characters}）` : ""));
              } catch (e) {
                setErr((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}>{busy ? "进行中（停服/启动约需几十秒）…" : "确认" + (rollback ? "回滚" : "应用")}</button>
            <button onClick={onClose} disabled={busy}>取消</button>
          </div>
        </>
      )}
    </Modal>
  );
}

function TrialPanel({ reload, onNote }: { reload: number; onNote: (m: string) => void }) {
  const { setError } = useCorridor();
  const [trial, setTrial] = useState<TrialStatus | null>(null);
  const [deploys, setDeploys] = useState<DeployEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const load = () => {
    corridor.trial().then(setTrial, (e: Error) => setError(e.message));
    corridor.deploys().then((d) => setDeploys(d.deploys), () => setDeploys([]));
  };
  useEffect(load, [reload]);
  const act = async (fn: () => Promise<unknown>, msg: string) => {
    setBusy(true);
    try { await fn(); onNote(msg); } catch (e) { setError((e as Error).message); } finally { setBusy(false); load(); }
  };
  const s = trial?.status;
  return (
    <div class={"cor-card" + (busy ? " cor-busy" : "")}>
      <h3>隔离试验服
        {s ? <Tag kind={s.running ? "ok" : s.state === "inconsistent" ? "bad" : ""}>{s.running ? "运行中" : s.state === "inconsistent" ? "状态不一致" : "已停止"}</Tag> : null}
        <button class="ghost" onClick={load}>刷新</button></h3>
      {!trial ? <div class="loading">读取 trialctl status…</div> : (
        <>
          {s?.guard.length ? <Notice kind="error">{s.guard.join("；")}</Notice> : null}
          <dl class="cor-kv">
            <dt>端口</dt><dd>{s?.ports?.join(" / ") ?? "?"}　监听：{JSON.stringify(s?.listeners ?? {})}</dd>
            <dt>当前内容</dt><dd class="mono">{trial.active.label} {trial.active.note ? <span class="muted">{trial.active.note}</span> : null}</dd>
            <dt>进行中的局</dt><dd>{trial.open_runs.length ? trial.open_runs.map((r) => `${r.run_id}（第${r.floor ?? "?"}层）`).join("、") : "无"}</dd>
          </dl>
          <div class="cor-toolbar" style="margin-top:8px">
            <button disabled={!!s?.running} onClick={() => act(() => corridor.start(), "已启动试验服")}>启动</button>
            <button disabled={!s?.running} onClick={() => act(() => corridor.stop(), "已停止试验服")}>停止</button>
            <button disabled={trial.active.kind === "proto-install"} title="把试验服的配置与叠加层换回 proto-server/src 的原始安装（data_dir 指回共享 data 目录）"
              onClick={() => window.confirm("恢复 proto-server 原始安装的回廊配置？（运行中会受控重启）") &&
                act(() => corridor.restoreOriginal(trial.active.label), "已恢复 proto 原始安装")}>恢复原始安装</button>
          </div>
          <h4>部署记录</h4>
          <table class="cor-table small">
            <thead><tr><th>时间</th><th>动作</th><th>从 → 到</th><th>结果</th></tr></thead>
            <tbody>{deploys.slice(0, 15).map((d, i) => (
              <tr key={i}><td>{d.at}</td><td>{d.action}</td><td class="mono">{d.from ? `${d.from.replace("release:sha256:", "").slice(0, 14)} → ${(d.to ?? "").replace("release:sha256:", "").slice(0, 14)}` : ""}</td>
                <td>{d.result ?? (d.exit === 0 ? "ok" : d.exit)}{d.health && (d.health as any).ok === false ? <span class="error-text"> {String((d.health as any).reason)}</span> : null}</td></tr>))}</tbody>
          </table>
        </>
      )}
    </div>
  );
}

export function ReleasesPage() {
  const { status, revision, refresh, tick, setError } = useCorridor();
  const [releases, setReleases] = useState<ReleaseSummary[]>([]);
  const [against, setAgainst] = useState("base");
  const [message, setMessage] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ release: ReleaseSummary; rollback: boolean } | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => { corridor.releases().then((r) => setReleases(r.releases), (e: Error) => setError(e.message)); }, [tick, reload]);
  const v = status?.validation;
  return (
    <div class="cor">
      {note ? <Notice>{note}</Notice> : null}
      <DiffView against={against} setAgainst={setAgainst} releases={releases} />
      <div class="cor-card">
        <h3>校验与打包 <Tag kind={v?.blockers ? "bad" : "ok"}>阻断 {v?.blockers}</Tag><Tag kind={v?.warnings ? "warn" : ""}>警告 {v?.warnings}</Tag></h3>
        {v ? <details><summary class="small">查看全部问题</summary><FindingList findings={v.findings} /></details> : null}
        <div class="cor-toolbar" style="margin-top:8px">
          <input type="text" style="flex:1" placeholder="这次发布的说明（写进 manifest）" value={message} onInput={(e) => setMessage((e.currentTarget as HTMLInputElement).value)} />
          <button class="primary" disabled={!!v?.blockers} title={v?.blockers ? "阻断项清零后才能打包" : "编译成不可变发布包（自动快照）"} onClick={async () => {
            try {
              const r = await corridor.build(revision, message || `r${revision}`);
              setNote((r.release.reused ? "内容未变，复用已有发布包 " : "已生成发布包 ") + short(r.release.content_version));
              setReload((x) => x + 1);
              await refresh();
            } catch (e) {
              setError((e as Error).message);
            }
          }}>生成发布包</button>
        </div>
      </div>
      <div class="cor-card">
        <h3>发布包（不可变）</h3>
        <table class="cor-table small">
          <thead><tr><th>版本</th><th>时间</th><th>工作区</th><th>说明</th><th>难度档</th><th>警告</th><th></th></tr></thead>
          <tbody>{releases.map((r) => (
            <tr key={r.id}>
              <td class="mono" title={r.content_version}>{r.id}</td><td>{r.created_at}</td><td>r{r.workspace_revision}</td><td>{r.message}</td>
              <td>{r.active_profile}</td><td>{r.validation_summary?.warnings}</td>
              <td class="cor-toolbar">
                <button class="primary" onClick={() => setDialog({ release: r, rollback: false })}>应用到试验服</button>
                <button onClick={() => setDialog({ release: r, rollback: true })}>回滚到此版</button>
                <a href={`/api/corridor/export?format=runtime&version=${encodeURIComponent(r.content_version)}`} download>导出 ZIP</a>
                <a href="javascript:void 0" onClick={() => setAgainst("release:" + r.content_version)}>对比</a>
              </td>
            </tr>))}</tbody>
        </table>
        {!releases.length ? <div class="muted small">还没有发布包。</div> : null}
      </div>
      <TrialPanel reload={reload} onNote={(m) => setNote(m)} />
      {dialog ? <ApplyDialog release={dialog.release} rollback={dialog.rollback} onClose={() => setDialog(null)}
        onDone={(msg) => { setDialog(null); setNote(msg); setReload((x) => x + 1); }} /> : null}
    </div>
  );
}

