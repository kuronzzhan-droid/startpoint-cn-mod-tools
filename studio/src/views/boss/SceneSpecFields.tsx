import { useEffect, useState } from "preact/hooks";
import { Json } from "../../modeApi";
import { SceneGroup, SceneSetting, SceneSpec } from "../../sceneApi";

export type ScenePath = (string | number)[];
const KIND_LABEL: Record<string, string> = { bgm: "背景音乐", field: "场地", name: "名称", level: "敌人等级",
  hp: "HP 修正", attack: "攻击修正", time: "时限", summon: "召唤物", mechanism: "机关", trial: "试炼", threshold: "试炼阈值" };
const DATE_COLUMNS: Record<string, "required" | "optional" | "schedule"> = {
  "master/shop/event_item_shop.orderedmap:26": "required",
  "master/shop/event_item_shop.orderedmap:27": "optional",
  "master/quest/event/advent_event_quest.orderedmap:5": "required",
  "master/quest/event/advent_event_quest.orderedmap:6": "optional",
  "master/quest/event/advent_event.orderedmap:3": "schedule",
  "master/quest/event/advent_event.orderedmap:24": "required",
  "master/quest/event/advent_event.orderedmap:25": "optional",
  "master/quest/event/advent_event.orderedmap:26": "optional",
  "master/item/item.orderedmap:19": "required",
  "master/item/item.orderedmap:20": "optional",
};
const DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/;

function assertJstDateTime(value: string, allowNone: boolean): void {
  if (allowNone && value === "(None)") return;
  const match = DATETIME_RE.exec(value);
  if (!match) throw new Error(allowNone ? "日期格式须为 YYYY-MM-DD HH:MM:SS 或 (None)" : "日期格式须为 YYYY-MM-DD HH:MM:SS");
  const [, y, mo, d, h, mi, s] = match;
  const year = Number(y), month = Number(mo), day = Number(d), hour = Number(h), minute = Number(mi), second = Number(s);
  if (year < 1970 || year > 2200 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
    throw new Error("日期时间超出有效范围");
  }
  const probe = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  if (probe.getUTCFullYear() !== year || probe.getUTCMonth() + 1 !== month || probe.getUTCDate() !== day) {
    throw new Error("日期不存在");
  }
}

function validateBoundText(setting: SceneSetting, next: string): void {
  if (!Array.isArray(setting.bindings)) return;
  for (const raw of setting.bindings) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
    const binding = raw as { table?: unknown; column?: unknown; path?: unknown };
    if (typeof binding.table !== "string" || typeof binding.column !== "number") continue;
    const dateMode = DATE_COLUMNS[`${binding.table}:${binding.column}`];
    if (dateMode === "required") assertJstDateTime(next, false);
    else if (dateMode === "optional") assertJstDateTime(next, true);
    else if (dateMode === "schedule" && next !== "") {
      for (const part of next.split(",")) assertJstDateTime(part, true);
    }
    if (binding.table === "master/quest/event/advent_event.orderedmap" && binding.column === 0) {
      if (next === "(None)" || !/^[A-Za-z0-9_.-]+$/.test(next)) throw new Error("活动代号 c0 须为非空标识符");
    } else if (binding.table === "master/quest/event/advent_event.orderedmap" && binding.column === 1) {
      if (next !== "(None)" && (!/^(?:0|[1-9][0-9]{0,9})$/.test(next) || Number(next) > 2147483647)) {
        throw new Error("original c1 须为 (None) 或 32 位非负整数");
      }
    } else if (binding.table === "master/string/custom_ability_string.orderedmap" && binding.column === 0
      && Array.isArray(binding.path) && typeof binding.path[0] === "string" && binding.path[0].startsWith("continue_cost_")) {
      const match = /^([1-9][0-9]{0,9}):([1-9][0-9]{0,9})$/.exec(next);
      if (!match || Number(match[1]) > 2147483647 || Number(match[2]) > 2147483647) {
        throw new Error("续战消耗须为 <正整数道具ID>:<正整数数量>");
      }
    }
  }
}

type Edit = (path: ScenePath, value: Json | undefined, error: string | null) => void;

export function SceneSpecFields({ spec, change }: { spec: SceneSpec; change: Edit }) {
  return <div class="scene-fields">
    <p class="small muted">数值和资源值会写入规格绑定的表格或行为资源；分组标题仅用于说明。高级 JSON 可调整阶段结构、资源与绑定。</p>
    <Group title="活动行" groups={spec.event ? [spec.event] : []} path={["event"]} singleton change={change} />
    <Group title="五档副本" groups={spec.tiers} path={["tiers"]} change={change} />
    <Group title="多阶段 · 场地与 BGM" groups={spec.phases} path={["phases"]} change={change} />
    <Settings title="召唤物" settings={spec.summons} path={["summons"]} change={change} />
    <Settings title="机关" settings={spec.mechanisms} path={["mechanisms"]} change={change} />
    <Settings title="试炼" settings={spec.trials} path={["trials"]} change={change} />
    <Group title="商店" groups={spec.shops} path={["shops"]} change={change} />
    <Group title="掉落" groups={spec.drops} path={["drops"]} change={change} />
  </div>;
}

function Group({ title, groups, path, singleton = false, change }: {
  title: string; groups: SceneGroup[]; path: ScenePath; singleton?: boolean; change: Edit;
}) {
  return <details><summary>{title}（{groups?.length ?? 0}）</summary>
    {Array.isArray(groups) ? groups.map((group, index) => <div class="scene-group" key={`${path.join("/")}/${index}`}>
      <h4>{group.name ?? group.id} <code>{group.quest ?? group.id}</code></h4>
      <Settings settings={group.settings} path={singleton ? [...path, "settings"] : [...path, index, "settings"]} change={change} />
    </div>) : <p class="error-text">规格分组必须是数组，请在高级 JSON 中修正。</p>}
  </details>;
}

function Settings({ title, settings, path, change }: { title?: string; settings: SceneSetting[]; path: ScenePath; change: Edit }) {
  const content = Array.isArray(settings) ? settings.map((setting, index) => <ValueEditor
    key={`${path.join("/")}/${index}`} setting={setting} path={[...path, index, "value"]} change={change} />)
    : <p class="error-text">设置必须是数组，请在高级 JSON 中修正。</p>;
  return title ? <details><summary>{title}（{settings?.length ?? 0}）</summary>{content}</details> : <>{content}</>;
}

function ValueEditor({ setting, path, change }: { setting: SceneSetting; path: ScenePath; change: Edit }) {
  const value = setting.value;
  const serial = JSON.stringify(value);
  const [text, setText] = useState(typeof value === "string" ? value : serial);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setText(typeof value === "string" ? value : serial); setError(null); }, [serial]);
  const input = (next: string) => {
    setText(next);
    try {
      const parsed: Json = typeof value === "string" ? next : JSON.parse(next);
      if (typeof value === "number" && (typeof parsed !== "number" || !Number.isFinite(parsed))) throw new Error("必须是有限数值");
      if (typeof value === "boolean" && typeof parsed !== "boolean") throw new Error("必须是 true 或 false");
      if (["hp", "attack", "time", "level", "threshold"].includes(setting.kind)
        && (next.trim() === "" || !Number.isFinite(Number(parsed)) || Number(parsed) <= 0)) throw new Error("必须是有限正数");
      if (typeof parsed === "string") validateBoundText(setting, parsed);
      setError(null); change(path, parsed, null);
    } catch (e) {
      const message = `输入无效：${(e as Error).message}`;
      setError(message); change(path, undefined, message);
    }
  };
  return <label class="scene-setting">
    <span>{KIND_LABEL[setting.kind] ?? setting.kind} <code>{setting.id}</code></span>
    {typeof value === "object" && value !== null ? <textarea class="mono" rows={3} value={text}
      onInput={e => input(e.currentTarget.value)} /> : <input class="mono" value={text}
      inputMode={typeof value === "number" ? "decimal" : "text"} onInput={e => input(e.currentTarget.value)} />}
    <span class="small muted">{setting.bindings?.length ?? 0} 个编译绑定</span>
    {error ? <span class="small error-text">{error}</span> : null}
  </label>;
}
