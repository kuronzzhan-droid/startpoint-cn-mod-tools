import { RuleResult } from "../api";

export function MultiplayerNote({ checks }: { checks: RuleResult[] }) {
  if (!checks.some((c) => c.category === "联机风险")) return null;
  return <p class="small muted">联机提示按文件和规则合并。官方基线也会命中；优先检查与本次改动相关的新增或变化。
    命中不证明存在故障，未命中也不代表同步安全；这些提示不参与五态判定或阻断。</p>;
}

export function MultiplayerDetails({ check: c }: { check: RuleResult }) {
  if (c.category !== "联机风险" || c.hit_count == null) return null;
  const changed = c.baseline_comparison === "candidate" && (c.new_hit_count ?? 0) > 0;
  const label = c.baseline_comparison === "unavailable" ? "基线对比不完整，新增数未知"
    : c.baseline_comparison === "baseline" ? "当前视图基线命中"
    : changed ? `相对草稿基线新增或变化 ${c.new_hit_count} 处` : "基线已有的命中，本文件无新增";
  return <div class="small">
    <p class={changed ? "warn-text" : "muted"}>{c.hit_count} 处命中 · {label}</p>
    <details class="tech">
      <summary>命中位置（前 {c.locations?.length ?? 0} 处）</summary>
      <ul class="mono">{c.locations?.map((location) => <li>{location}</li>)}</ul>
      {changed && c.new_locations?.length ? <>
        <p>新增或变化位置（前 {c.new_locations.length} 处）</p>
        <ul class="mono">{c.new_locations.map((location) => <li>{location}</li>)}</ul>
      </> : null}
      <p class="muted">按同文件同规则的构造及参数比较；位置移动不算新增，重复构造按数量比较。草稿基线是编辑前的当前视图。</p>
    </details>
  </div>;
}
