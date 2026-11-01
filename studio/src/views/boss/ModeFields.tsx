import { Json } from "../../modeApi";

const LABELS: Record<string, string> = {
  rounds: "轮次", bosses: "首领配置", affix_params: "词缀参数", variants: "变体阵容", budget: "贴图预算",
  hp_e8: "基础血量（亿，另乘副本 HP 修正）", waves: "波次", alias: "首领别名", quest: "副本 ID", name: "名称",
  round: "所属轮次", hp_mult: "HP 修正", atk_mult: "攻击修正", tp_target: "眩晕目标值",
  tp_scale: "眩晕倍率", affixes: "每波词缀", entry_affixes: "入场词缀", signature: "固有词缀",
  enemy_states: "敌方状态槽", mother: "母本", position: "站位", element: "属性原始枚举",
  group_kind: "出场方式（1 顺序 / 0 同屏）", fever_cap: "Fever 上限",
  stamina: "体力", attack_divisor: "攻击分母",
};
const FIXED = new Set(["mother", "from", "out", "src", "frames", "quest", "alias"]);
const AFFIX_LISTS = new Set(["affixes", "entry_affixes", "signature"]);

export function ModeFields({ value, path = [], change }: {
  value: Json; path?: (string | number)[]; change: (path: (string | number)[], value: Json) => void;
}) {
  const key = String(path.at(-1) ?? "");
  const label = LABELS[key] ? `${LABELS[key]} · ${key}` : key;
  const fixed = path.some(p => FIXED.has(String(p)));
  if (typeof value === "number" && !fixed) return <label class="mode-number">{label}
    <input type="number" step="any" value={value} onInput={e => {
      const input = e.currentTarget;
      if (input.value !== "" && Number.isFinite(input.valueAsNumber)) change(path, input.valueAsNumber);
      else input.value = String(value);
    }} /></label>;
  if (Array.isArray(value) && AFFIX_LISTS.has(key)) return <label class="mode-affixes">{label}
    <input value={value.join(", ")} placeholder="词缀原键名，以逗号分隔" onInput={e =>
      change(path, e.currentTarget.value.split(",").map(v => v.trim()).filter(Boolean))} /></label>;
  if (value !== null && typeof value === "object") return <details class="mode-fields" open={path.length <= 1}>
    <summary>{label || "结构"} <span class="muted">{Object.keys(value).length} 项</span></summary>
    {Object.entries(value).map(([k, v]) => <ModeFields key={k} value={v}
      path={[...path, Array.isArray(value) ? Number(k) : k]} change={change} />)}
  </details>;
  return <p class="small mode-value"><span>{label}</span> <code>{String(value ?? "null")}</code></p>;
}
