import { useEffect, useState } from "preact/hooks";
import { DraftView } from "../../api";
import { Floor, Json, Mode, ModePreview, ModeRead, modeDeliveries, modes } from "../../modeApi";
import { href } from "../../router";
import { Notice } from "../common";
import { DeliveryPanel } from "../Delivery";
import { useWorkshopAction } from "../workshopKit";
import { ModeFields } from "./ModeFields";
import "./modes.css";

const SECTIONS = ["rounds", "bosses", "affix_params", "variants", "budget"];
export function ModeWorkshop({ mode }: { mode: Mode }) {
  const [read, setRead] = useState<ModeRead | null>(null);
  const [payload, setPayload] = useState<Json>(null);
  const [preview, setPreview] = useState<ModePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seedText, setSeedText] = useState("0");
  const [delivery, setDelivery] = useState<"generate" | "export">("generate");
  const [tab, setTab] = useState<"edit" | "delivery">("edit");
  const action = useWorkshopAction();
  useEffect(() => {
    let alive = true;
    setRead(null); setError(null); setPreview(null); setTab("edit");
    modes.read(mode).then(data => {
      if (!alive) return;
      setRead(data); setPayload(data.payload); setPreview(data.preview ?? null);
      if (mode === "rogue") setSeedText(String((data.payload as { seed: number }).seed));
    }, e => alive && setError(e.message));
    return () => { alive = false; };
  }, [mode]);
  const change = (path: (string | number)[], value: Json) => {
    const next = structuredClone(payload) as any;
    let parent = next;
    for (const part of path.slice(0, -1)) parent = parent[part];
    parent[path.at(-1)!] = value;
    setPayload(next); setPreview(null);
  };
  const dirty = JSON.stringify(payload) !== JSON.stringify(read?.draft?.payload);
  const seedValid = mode !== "rogue" || (seedText.trim() !== "" && Number.isInteger(Number(seedText))
    && Number(seedText) >= 0 && Number(seedText) <= 4294967295);
  const saved = !!read?.draft && !dirty && seedValid && read.draft.baseView === read.version;
  const allowed = saved && !!preview?.canGenerate;
  const view: DraftView = { characterId: mode, changeset: read?.draft ?? null,
    status: { state: saved ? "saved" : "dirty", label: saved ? "已保存" : "尚未保存", changes: 1 }, actions: [] };
  const submit = (save: boolean) => action.run(async () => {
    if (!seedValid) throw new Error("种子必须是 0–4294967295 的整数");
    const result = save ? await modes.save(mode, payload, read?.draft?.revision ?? 0) : await modes.preview(mode, payload);
    setPreview(result);
    if (result.draft && read) setRead({ ...read, draft: result.draft });
    if (save) await modeDeliveries.finished(mode);
  });
  return <section class="page mode-workshop">
    <a class="back" href={href({ work: "content", shop: "boss" })}>← BOSS 工坊</a>
    <h1>{mode === "five" ? "五重决战 · 结构" : "深渊连战"}</h1>
    <p class="muted">当前视图 {read?.version ?? "读取中"} · 草稿独立保存 · 设备实测未执行</p>
    <nav class="segmented">
      <button class={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>{mode === "five" ? "结构" : "赛季与重抽"}</button>
      <button class={tab === "delivery" ? "on" : ""} onClick={() => setTab("delivery")}>交付</button>
    </nav>
    {error || action.error ? <Notice kind="error">{error || action.error}</Notice> : null}
    {!read && !error ? <p class="loading">正在读取当前视图并核对构建输入……</p> : null}
    {read ? <>
      <div hidden={tab !== "edit"}>
        {read.current ? <details open><summary>当前赛季内容 · 活动 {read.current.event} · {read.current.rounds} 轮</summary>
          <p>{read.current.seasonNote}</p><p class="small mono">内容指纹：{read.current.fingerprint}</p>
          <FloorTable rows={read.current.rows} />
          <details><summary>活动原始行</summary><pre>{JSON.stringify(read.current.eventRow, null, 2)}</pre></details>
        </details> : null}
        <fieldset disabled={action.busy} class="mode-editor">
          {mode === "five" ? SECTIONS.map(key => <ModeFields key={key} value={(payload as Record<string, Json>)[key]}
            path={[key]} change={change} />) : <div class="version-row">
            <label>随机种子 <input type="number" min="0" max="4294967295" step="1" value={seedText}
              onInput={e => {
                const text = e.currentTarget.value; setSeedText(text); setPreview(null);
                if (text.trim() !== "" && Number.isInteger(Number(text)) && Number(text) >= 0 && Number(text) <= 4294967295)
                  change(["seed"], Number(text));
              }} /></label>
            <button onClick={() => { const seed = crypto.getRandomValues(new Uint32Array(1))[0];
              setSeedText(String(seed)); change(["seed"], seed); }}>随机种子</button>
            {!seedValid ? <Notice kind="warn">种子必须是 0–4294967295 的整数</Notice> : null}
          </div>}
          <div class="version-row">
            <button disabled={!seedValid} onClick={() => submit(false)}>只读预览与校验</button>
            <button class="primary" disabled={!preview?.ok || !seedValid} onClick={() => submit(true)}>保存独立草稿</button>
            <span class="small muted">{saved ? `已保存 · 修订 ${read.draft?.revision}` : "尚有未保存内容"}</span>
          </div>
        </fieldset>
        {action.busy ? <p class="loading">构建器正在计算与校验，尚未写入游戏数据……</p> : null}
        {preview ? <Preview result={preview} /> : <p class="muted">修改后请重新预览，再保存。</p>}
        {(preview?.manualSteps ?? read.current?.manualSteps)?.map(step => <details>
          <summary>手工步骤：{step.title}</summary><pre>{step.command}</pre>
        </details>)}
      </div>
      {tab === "delivery" ? <>
        {!allowed ? <Notice kind="warn">{preview?.blockers?.join("；") || "请先预览通过并保存当前草稿，才可生成交付。"}</Notice> : null}
        <fieldset disabled={delivery === "generate" && !allowed} class="mode-editor">
          <DeliveryPanel characterId={mode} view={view} mode={delivery} onMode={setDelivery} api={modeDeliveries} />
        </fieldset>
        {!allowed && delivery === "generate" ? <button onClick={() => setDelivery("export")}>查看已有交付</button> : null}
      </> : null}
    </> : null}
  </section>;
}

function FloorTable({ rows }: { rows: Floor[] }) {
  return <div class="mode-table"><table><thead><tr><th>轮次</th><th>楼层 / 场地</th><th>Boss 属性</th><th>敌等级</th><th>场地效果</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.key}><td>{row.round === "0" ? "无尽" : row.round}</td>
      <td>{row.name}<br /><code>{row.field}</code>{row.bosses?.length ? <details><summary>首领代号</summary>{row.bosses.map(boss => <div><code>{boss}</code></div>)}</details> : null}</td><td>{row.element}（原始枚举）</td><td>{row.level}</td>
      <td>{row.description}<details><summary>效果原键与数值</summary>{row.effects.map(e => <div>{e.kind}: {e.strength || "—"}</div>)}</details></td></tr>)}</tbody></table></div>;
}

function Preview({ result }: { result: ModePreview }) {
  return <section>
    <h2>预览结果</h2>
    <p>{result.ok ? "构建与引用检查已完成" : "存在构建问题"} · {result.canGenerate ? "可保存后生成" : "生成已阻断"}</p>
    {result.blockers.map(message => <Notice kind="warn">{message}</Notice>)}
    {result.audit ? <details open={!result.audit.aligned}><summary>spec 与当前链尾：{result.audit.differences.length} 处差异</summary>
      <p>{result.audit.note}</p><ul>{result.audit.differences.map(d => <li><code>{d.logical} {d.path}</code></li>)}</ul>
      {result.audit.quests ? <table><thead><tr><th>副本</th><th>当前 Boss HP 修正</th><th>spec 修正</th><th>状态槽</th></tr></thead>
        <tbody>{result.audit.quests.map(q => <tr><td>{q.quest}</td><td>{q.currentBossHpMultiplier}</td><td>{q.specBossHpMultiplier}</td><td>{q.statesMatch ? "一致" : "不同"}</td></tr>)}</tbody></table> : null}
    </details> : null}
    {result.diff ? <details open><summary>草稿与仓库 spec 差异（{result.diff.length}）</summary>
      {result.diff.length ? result.diff.map(d => <p><code>{d.path}</code>：{JSON.stringify(d.before)} → {JSON.stringify(d.after)}</p>) : <p>没有修改。</p>}
    </details> : null}
    {result.report?.budget ? <details open><summary>敌方静态贴图预算下界</summary>
      <p>仅计算敌方 layer0；出战队伍、协力召唤与运行时图集待验证。</p>
      <table><thead><tr><th>副本</th><th>Mpx</th><th>贴图数</th><th>静态估算</th></tr></thead>
      <tbody>{Object.entries(result.report.budget).map(([id, b]) => <tr><td>{id}</td><td>{b.mpx}</td><td>{b.sheets}</td><td>{b.verdict === "PASS" ? "静态下界未超限" : b.verdict}</td></tr>)}</tbody></table></details> : null}
    {result.report?.element_variants_in_apk?.map(name => <Notice kind="warn">待验证（假定在 APK，未核验）：{name}</Notice>)}
    {result.warnings?.map(warning => <Notice kind="warn">{warning}</Notice>)}
    {result.rows ? <FloorTable rows={result.rows} /> : null}
    {result.checks ? <p>rogue_validate 引用门禁：{result.checks.filter(c => c.ok).length}/{result.checks.length} 关通过。</p> : null}
    {result.log ? <details><summary>构建器详细记录</summary><pre>{result.log}</pre></details> : null}
  </section>;
}
