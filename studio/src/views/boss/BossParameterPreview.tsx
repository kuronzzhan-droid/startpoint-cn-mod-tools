import { BossPreview } from "../../bossApi";

const TARGETS = { zako: "杂兵", funnel: "浮游", boss: "首领" };

export function BossParameterPreview({ preview }: { preview: BossPreview | null }) {
  const changes = preview?.parameterChanges ?? [];
  if (!changes.length) return null;
  return (
    <div class="table-scroll">
      <p class="small">草稿数值预览（按操作顺序；显示表内实际系数）</p>
      <table class="boss-table">
        <thead><tr><th>副本 / 属性</th><th>操作</th><th>对象</th><th>改前</th><th>改后</th></tr></thead>
        <tbody>{changes.flatMap((change) => change.values.map((value) => (
          <tr>
            <td>{change.quest} · {change.stat === "hp" ? "HP" : "攻击"}</td>
            <td>{change.mode === "scale" ? `当前值乘以 ${change.input}` : `绝对设为 ${change.input}`}
              {change.deprecated ? "（旧字段已弃用）" : ""}</td>
            <td>{TARGETS[value.target]}</td><td>{value.before}</td><td>{value.after}</td>
          </tr>
        )))}</tbody>
      </table>
      {changes.some((change) => change.mode === "scale") ? (
        <p class="small">缩放按当前草稿数值相乘；同一草稿再次写入会再乘一次。预览和保存重放不会追加操作。</p>
      ) : null}
    </div>
  );
}
