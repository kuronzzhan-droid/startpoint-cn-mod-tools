import { ComponentChildren } from "preact";
import { Origin } from "../api";

const ELEMENT_CLASS: Record<string, string> = {
  火: "el-fire", 水: "el-water", 雷: "el-thunder", 风: "el-wind", 光: "el-light", 暗: "el-dark",
};

export function ElementBadge({ element }: { element: string }) {
  return <span class={"el-badge " + (ELEMENT_CLASS[element] ?? "el-none")} title={element + "属性"}>{element}</span>;
}

const ORIGIN_LABEL: Record<Origin, string> = {
  new: "新增 MOD", modified: "改版官方", official: "官方原版", unknown: "来源未知",
};

export function OriginBadge({ origin }: { origin: Origin }) {
  return (
    <span class={"origin origin-" + origin}
      title="与官方 CDN 基线比对角色/能力/队长技/技能行得出；未比对立绘、像素等资源">
      {ORIGIN_LABEL[origin]}
    </span>
  );
}

export function Rarity({ value }: { value: number | string | null }) {
  if (typeof value !== "number") return null;
  return <span class="rarity" title={`${value} 星`}>{"★".repeat(value)}</span>;
}

/** Codex 状态语言：保存状态 / 检查结果（五态）/ 实测情况，未接入的项如实显示。 */
export function StatusStrip() {
  return (
    <div class="status-strip" aria-label="状态">
      <div>
        <span class="label">保存状态</span>
        <span class="value">只读查看 · 无修改</span>
      </div>
      <div>
        <span class="label">检查结果</span>
        <span class="value state-none" title="规则条目尚未接入；未执行不等于通过">未执行</span>
      </div>
      <div>
        <span class="label">实测情况</span>
        <span class="value state-none">未记录</span>
      </div>
    </div>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "warn" | "error"; children: ComponentChildren }) {
  return <div class={"notice " + kind}>{children}</div>;
}
