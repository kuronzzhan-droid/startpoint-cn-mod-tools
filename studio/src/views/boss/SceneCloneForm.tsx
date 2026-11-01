import { useState } from "preact/hooks";
import { SceneSpec } from "../../sceneApi";

export function SceneCloneForm({ disabled, onClone }: { disabled: boolean; onClone: (name: string) => void }) {
  const [name, setName] = useState("");
  return <details class="scene-clone">
    <summary>从当前规格新建活动 · 活动、五档、商店、掉落一起建</summary>
    <p class="small muted">以当前规格为母本，自动分配新活动编号与专属资源命名空间。生成候选后展示编译校验结果，再保存草稿。编号尚未预留，保存与出包时会重新核验。</p>
    <div class="version-row">
      <label>新活动名称 <input value={name} maxLength={80} placeholder="输入新活动名称" disabled={disabled}
        onInput={e => setName(e.currentTarget.value)} /></label>
      <button disabled={disabled || !name.trim()} onClick={() => onClone(name.trim())}>生成新活动规格候选</button>
    </div>
  </details>;
}

export function SceneCreationSummary({ spec }: { spec: SceneSpec }) {
  if (!spec.creation) return null;
  if (typeof spec.creation !== "object" || typeof spec.creation.sourceEvent !== "string" || !spec.event
    || typeof spec.event.id !== "string" || typeof spec.id !== "string" || typeof spec.name !== "string"
    || !Array.isArray(spec.creation.tableTargets) || !Array.isArray(spec.creation.resourceTargets)
    || !Array.isArray(spec.shops) || !Array.isArray(spec.drops) || !Array.isArray(spec.tiers)
    || spec.tiers.some(tier => !tier || typeof tier.id !== "string" || typeof tier.quest !== "string"
      || (tier.sourceQuest !== undefined && typeof tier.sourceQuest !== "string")))
    return <p class="error-text">新活动候选信息不完整，请先运行规格校验并修正 JSON。</p>;
  return <details open class="scene-clone">
    <summary>新活动候选：{spec.event.id} · {spec.name}</summary>
    <p class="small">母本活动 {spec.creation.sourceEvent} → 新活动 {spec.event.id} · 规格标识 <code>{spec.id}</code></p>
    <p class="small muted">活动、五档、商店与掉落一并创建；美术和 BGM 沿用当前视图。候选编号未预留，保存草稿和生成交付都会复核冲突。</p>
    <ul>{spec.tiers.map(tier => <li key={tier.id}>第 {tier.id} 档：<code>{tier.sourceQuest ?? "未指定母本"}</code> → <code>{tier.quest}</code></li>)}</ul>
    <p class="small">{spec.shops.length} 组商店 · {spec.drops.length} 组掉落 · {spec.creation.tableTargets.length} 个新表键 · {spec.creation.resourceTargets.length} 个独立资源路径</p>
    <p class="small muted">继续编辑本候选，或切换到母本槽位创建另一活动。保存会写入独立草稿槽 <code>{spec.id}</code>，不会覆盖母本或其他克隆草稿。</p>
  </details>;
}
