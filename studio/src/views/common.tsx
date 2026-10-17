import { ComponentChildren } from "preact";
import { useState } from "preact/hooks";
import { api, DraftCheck, DraftStatus, Origin } from "../api";

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
export function StatusStrip({ draft, checks = [] }: { draft?: DraftStatus | null; checks?: DraftCheck[] }) {
  const errors = checks.filter((c) => c.level === "error").length;
  const warns = checks.filter((c) => c.level === "warn").length;
  const saveLabel = !draft || draft.state === "clean" ? "无草稿改动" : draft.label;
  const saveClass = draft?.state === "dirty" ? "state-dirty" : draft?.state === "saved" ? "state-ok" : "";
  return (
    <div class="status-strip" aria-label="状态">
      <div>
        <span class="label">保存状态</span>
        <span class={"value " + saveClass} title="草稿只写 work/studio-drafts，不写游戏表">{saveLabel}</span>
      </div>
      <div>
        <span class="label">检查结果</span>
        {draft && draft.changes ? (
          <span class="value" title="草稿检查（尺寸/蒙版/时长/预算）；五态规则条目尚未接入">
            草稿检查 {errors} 错误 · {warns} 注意 <span class="state-none">· 规则条目未执行</span>
          </span>
        ) : (
          <span class="value state-none" title="规则条目尚未接入；未执行不等于通过">未执行</span>
        )}
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

/** Native square avatar (ui/square_N.png and fallbacks), lazy-loaded; element badge if absent. */
export function Avatar({ id, element, size = 40 }: { id: string; element: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <ElementBadge element={element} />;
  return (
    <img class="avatar" src={api.avatarUrl(id)} width={size} height={size} loading="lazy" decoding="async"
      alt="" onError={() => setFailed(true)} />
  );
}
