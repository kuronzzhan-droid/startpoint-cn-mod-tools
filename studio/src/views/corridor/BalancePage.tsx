import { useEffect, useState } from "preact/hooks";
import { corridor, Json, RuleField } from "../../corridorApi";
import { Notice } from "../common";
import { Num, Tag, useCorridor } from "./widgets";

const ORDER = ["economy", "shop", "rewards", "map", "difficulty"];

function pct(ws: number[]) {
  const sum = ws.reduce((a, b) => a + b, 0) || 1;
  return ws.map((w) => (Math.round((w / sum) * 1000) / 10).toString() + "%").join(" / ");
}

function FieldEditor({ field, onSet }: { field: RuleField; onSet: (value: Json) => void }) {
  const v = field.value;
  const [text, setText] = useState(JSON.stringify(v));
  useEffect(() => setText(JSON.stringify(v)), [JSON.stringify(v)]);
  switch (field.type) {
    case "int":
      return <Num value={v as number} min={field.min} max={field.max} step={1} onChange={(n) => onSet(Math.round(n))} />;
    case "number":
      return <Num value={v as number} min={field.min} max={field.max} onChange={onSet} />;
    case "bool":
      return <input type="checkbox" checked={!!v} onChange={(e) => onSet((e.currentTarget as HTMLInputElement).checked)} />;
    case "enum":
      return <select value={String(v)} onChange={(e) => onSet((e.currentTarget as HTMLSelectElement).value)}>
        {(field.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}</select>;
    case "range": {
      const r = (v as number[]) ?? [0, 0];
      return <span><Num value={r[0]} step={1} onChange={(n) => onSet([Math.round(n), r[1]])} /> – <Num value={r[1]} step={1} onChange={(n) => onSet([r[0], Math.round(n)])} /></span>;
    }
    case "weights4": {
      const w = (v as number[]) ?? [0, 0, 0, 0];
      return <span>{w.map((x, i) => <Num key={i} value={x} min={0} onChange={(n) => onSet(w.map((y, j) => (j === i ? n : y)))} />)}
        <span class="muted small"> {pct(w)}</span></span>;
    }
    case "int_list":
      return <span class="cor-toolbar"><input type="text" value={((v as number[]) ?? []).join(",")} onChange={(e) =>
        onSet((e.currentTarget as HTMLInputElement).value.split(/[,，\s]+/).filter(Boolean).map(Number))} /></span>;
    default:
      return <span class="cor-toolbar"><input type="text" style="min-width:260px" value={text} onInput={(e) => setText((e.currentTarget as HTMLInputElement).value)} />
        <button onClick={() => { try { onSet(JSON.parse(text)); } catch { window.alert("不是合法 JSON"); } }}>保存</button></span>;
  }
}

function TierBands({ field, onSet }: { field: RuleField; onSet: (value: Json) => void }) {
  const bands = (field.value as { floors: number[]; weights: number[] }[]) ?? [];
  const set = (i: number, patch: Partial<{ floors: number[]; weights: number[] }>) =>
    onSet(bands.map((b, j) => (j === i ? { ...b, ...patch } : b)) as unknown as Json);
  return (
    <table class="cor-table small">
      <thead><tr><th>楼层</th>{(field.labels ?? []).map((l) => <th key={l}>{l}</th>)}<th>概率</th></tr></thead>
      <tbody>
        {bands.map((b, i) => (
          <tr key={i}>
            <td><Num value={b.floors[0]} step={1} onChange={(n) => set(i, { floors: [Math.round(n), b.floors[1]] })} /> –
              <Num value={b.floors[1]} step={1} onChange={(n) => set(i, { floors: [b.floors[0], Math.round(n)] })} /></td>
            {b.weights.map((w, j) => <td key={j}><Num value={w} min={0} onChange={(n) => set(i, { weights: b.weights.map((x, k) => (k === j ? n : x)) })} /></td>)}
            <td class="muted">{pct(b.weights)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function BalancePage() {
  const { run, tick, setError } = useCorridor();
  const [data, setData] = useState<{ fields: RuleField[]; groups: Record<string, string>; rules: Json } | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  useEffect(() => { corridor.rules().then(setData, (e: Error) => setError(e.message)); }, [tick]);
  if (!data) return <div class="loading">读取规则…</div>;
  const set = (f: RuleField, value: Json) => run([{ op: "rules.set", path: f.path, value }], f.label);
  const profile = data.fields.find((f) => f.path === "/difficulty/active_profile")?.value;
  return (
    <div class="cor">
      {profile === "test" ? <Notice kind="warn">当前生效的是试验难度档 test（敌人 HP/ATK 按测试倍率），只适合隔离试验服。正式档的三幕目标曲线在下方「难度」里，
        公式 D=√(hp×atk)、hp=D^p、atk=D^(2−p)，相对所选原生遭遇，未标定实战耗时。</Notice> : null}
      {ORDER.map((group) => (
        <div key={group} class="cor-card">
          <h3>{data.groups[group]}</h3>
          <div class="cor-fields">
            {data.fields.filter((f) => f.group === group && f.type !== "tier_bands" && (f.present || f.optional)).map((f) => (
              <div key={f.path} class="cor-field" title={f.hint ?? f.path}>
                <span class="label">{f.label}{f.hint ? <Tag kind="info" title={f.hint}>?</Tag> : null}</span>
                <FieldEditor field={f} onSet={(value) => set(f, value)} />
              </div>
            ))}
          </div>
          {data.fields.filter((f) => f.group === group && f.type === "tier_bands").map((f) => (
            <div key={f.path}><h4>{f.label}</h4><TierBands field={f} onSet={(value) => set(f, value)} /></div>
          ))}
        </div>
      ))}
      <div class="cor-card">
        <h3>只读字段</h3>
        <p class="small muted">协议/宿主（700110/1）/data_dir/rules_revision/三幕 45 层结构/v3 固定的三选一与精英三轮/旧 enemy_scale/别名表/调试开关不在这里编辑：
          它们由服务端硬性校验或属于部署环境。data_dir 发布时由试验服映射。</p>
        <button onClick={() => setShowRaw(!showRaw)}>{showRaw ? "收起" : "查看"}完整 rogue_corridor_v1.json</button>
        {showRaw ? <pre class="cor-pre">{JSON.stringify(data.rules, null, 2)}</pre> : null}
      </div>
    </div>
  );
}
