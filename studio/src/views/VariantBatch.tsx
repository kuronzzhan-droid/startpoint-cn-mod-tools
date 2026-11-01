import { useState } from "preact/hooks";
import { batch, BatchPreview, BatchWritten, VariantTarget } from "../batchApi";
import { drafts } from "../api";
import { VariantId } from "./VariantId";
import { Notice } from "./common";
import { BatchDone, BatchReview } from "./BatchReview";
import { duplicateTarget, startingId } from "../batchReviewState";

const ZONES = [["skill", "技能 · 乘区7"], ["power_flip", "强化弹射 · 乘区5"], ["direct", "直接攻击 · 乘区6"],
  ["ability", "能力 · 乘区8"], ["all", "全伤害 · 乘区9"]];

export function VariantBatch({ characterId }: { characterId: string }) {
  const [rule, setRule] = useState("zone");
  const [targets, setTargets] = useState<VariantTarget[]>([{ to: "", zone: "direct" }]);
  const [preview, setPreview] = useState<BatchPreview | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [done, setDone] = useState<BatchWritten | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const reset = () => { setPreview(null); setSelected([]); setDone(null); setError(""); };
  const change = (i: number, value: Partial<VariantTarget>) => { setTargets(targets.map((t, n) => n === i ? { ...t, ...value } : t)); reset(); };
  const run = async (action: "ids" | "preview" | "apply") => {
    setBusy(true); setError("");
    try {
      if (action === "ids") {
        const next: VariantTarget[] = []; let near = startingId(targets);
        for (const target of targets) {
          const r = await batch.idNext(characterId, near);
          next.push({ ...target, to: r.id }); near = String(Number(r.id) + 1);
        }
        setTargets(next); reset();
      } else if (action === "preview") {
        setPreview(null); setSelected([]); setDone(null);
        setPreview(await batch.variants({ from: characterId, rule, targets }));
      } else if (preview && selected.length) {
        setDone(await batch.apply("variants", { from: characterId, rule, targets }, preview.review, selected));
        setPreview(null); setSelected([]);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return <section class="boss-block"><h2>复制为变体</h2>
    <p>基于当前只读视图母本 {characterId}，每个目标独立克隆 ID、技能键、能力键和草稿。母本尚未写入视图的草稿不参与复制。</p>
    <fieldset disabled={busy}><label>规则 <select value={rule} onChange={e => { setRule(e.currentTarget.value); reset(); }}>
      <option value="zone">乘区复制：伤害加成换到目标类型，ATK 不变</option><option value="element">换属性复制：抗性降低一起换</option>
    </select></label>
    {rule === "element" ? <Notice kind="warn">跨属性克隆暂不可写：角色属性、技能 DSL 伤害与抗性降低、能力条件、音效和玛纳材料未完成联动验证，保留现有拦截。</Notice>
      : <Notice>支持确定等价的伤害加成，自身目标扩为全队并保留属性限定；攻击力词条保持原样。固有条件不等价、技能外部程序或未同步文案会列为「需人工」。可保存含需人工条目的克隆草稿；文案待办可在文案页同步，未知规则仍阻断交付。全伤害版的技能限时加成保留母本类型。</Notice>}
    {targets.map((target, i) => <div class="param-block" key={i}>
      <label class="param-field">目标 {i + 1} {rule === "zone" ? <select value={target.zone} onChange={e => change(i, { zone: e.currentTarget.value })}>
        {ZONES.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select>
        : <select value={target.element ?? 0} onChange={e => change(i, { element: Number(e.currentTarget.value) })}>
          {["火", "水", "雷", "风", "光", "暗"].map((name, n) => <option key={n} value={n}>{name}</option>)}</select>}</label>
      <VariantId from={characterId} value={target.to} duplicate={duplicateTarget(targets, target.to)} onChange={to => change(i, { to })} />
      <button type="button" disabled={targets.length === 1} onClick={() => { setTargets(targets.filter((_, n) => n !== i)); reset(); }}>移除此目标</button>
    </div>)}
    <div class="save-row"><button type="button" disabled={targets.length >= 20} onClick={() => { setTargets([...targets, { to: "", zone: "skill" }]); reset(); }}>添加目标</button>
      <button type="button" onClick={() => run("ids")}>为目标列表查询空闲 ID</button>
      <button type="button" disabled={targets.some(t => !t.to) || new Set(targets.map(t => t.to)).size !== targets.length} onClick={() => run("preview")}>预览所有变体差异</button></div>
    {preview && <BatchReview value={preview} selected={selected} onSelect={setSelected} />}
    {preview && <button class="primary" type="button" disabled={rule === "element" || !selected.length || !drafts.hasToken()} onClick={() => run("apply")}>创建勾选的 {selected.length} 份克隆草稿</button>}
    </fieldset>{busy && <p>正在检查母本与目标，请稍候……</p>}{error && <Notice kind="error">{error}</Notice>}<BatchDone result={done} />
  </section>;
}
