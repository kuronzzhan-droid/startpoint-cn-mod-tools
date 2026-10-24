import { useEffect, useRef, useState } from "preact/hooks";
import { RuleResult } from "../api";
import {
  CapRequirement, characterCompat, CharacterCompatReport, ClientProfileInfo, describeRequirement, lookupCaps,
  programCaps, useCaps, useClientProfile, verdict,
} from "../clientProfile";

// 目标客户端：顶部选择器、行内能力标记、生成结果里的缺能力说明、角色级「需要 v35e」标记。

function plainLine(p: ClientProfileInfo, fallback: ClientProfileInfo | undefined): string {
  const version = p.versionCode ? `（versionCode ${p.versionCode}）` : "";
  if (p.default || !fallback) {
    return `${p.label} 测试包${version}：已登记 ${p.capabilityCount} 项客户端能力。要发给只装了这个测试包的玩家，就选它。`;
  }
  const names = p.extra.slice(0, 4).map((e) => e.title).join("、");
  return `${p.label} 测试包${version}：比 ${fallback.label} 多 ${p.extraCount} 项能力` +
    (p.extra.length ? `（功能层面 ${p.extra.length} 项，如 ${names}${p.extra.length > 4 ? " 等" : ""}）` : "") +
    `。只有装了 ${p.label} 的玩家能用依赖这些能力的内容。`;
}

/** Header control: which test APK the players you send patches to have installed. */
export function ClientProfilePicker() {
  const state = useClientProfile();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => { if (box.current && !box.current.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); setOpen(false); } };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => { window.removeEventListener("mousedown", onDown); window.removeEventListener("keydown", onKey, true); };
  }, [open]);
  const profiles = state.profiles?.profiles ?? [];
  const fallback = profiles.find((p) => p.default);
  const nonDefault = !!state.info && !state.info.default;
  return (
    <div class="profile-picker" ref={box}>
      <button class={"profile-toggle" + (nonDefault ? " alt" : "") + (open ? " on" : "")} onClick={() => setOpen(!open)}
        aria-expanded={open} aria-haspopup="dialog"
        title={state.error ? "读取客户端档案失败：" + state.error : "目标客户端：生成补丁、行内提示都按这个测试 APK 检查（点开切换）"}>
        目标客户端 <span class={"profile-badge" + (nonDefault ? " alt" : "")}>{state.info?.label ?? (state.error ? "未知" : "…")}</span>
      </button>
      {open ? (
        <div class="profile-pop" role="dialog" aria-label="选择目标客户端">
          <h3>目标客户端</h3>
          <p class="small">
            选你要发补丁给的玩家，手机里装的是哪个测试 APK。生成补丁时按它做兼容检查：补丁用到的客户端扩展能力（例如 WFX 直击倍率、隐藏固有状态图标），
            这个 APK 必须有，否则那部分在玩家那里会崩溃或不生效。能力、词条和文案编辑页也按它标出「需要 v35e」之类的提示。
          </p>
          {state.error ? <p class="error-text small">读取客户端档案失败：{state.error}</p> : null}
          <div class="profile-options" role="radiogroup" aria-label="客户端档案">
            {profiles.map((p) => (
              <label class={"profile-option" + (state.selected === p.id ? " on" : "") + (p.available ? "" : " off")}>
                <input type="radio" name="client-profile" value={p.id} checked={state.selected === p.id} disabled={!p.available}
                  onChange={() => { state.set(p.id); }} />
                <span class="profile-option-body">
                  <span class="profile-option-head">
                    <span class={"profile-badge" + (p.default ? "" : " alt")}>{p.label}</span>
                    {p.default ? <span class="tag">默认</span> : null}
                    <span class="mono small muted" title={p.description}>{p.id}</span>
                  </span>
                  <span class="small">{plainLine(p, fallback)}</span>
                  {!p.available ? <span class="small error-text">能力证据读不到：{p.error}</span> : null}
                </span>
              </label>
            ))}
          </div>
          <p class="small muted">
            只记在这台电脑的这个浏览器里；不改测试服、不改任何 APK。比较只用登记的离线证据
            {fallback?.verification ? `（${fallback.verification}）` : ""}，不代表装机实测。
          </p>
        </div>
      ) : null}
    </div>
  );
}

/** Small read-only badge naming one profile (e.g. in a generate result). */
export function ProfileBadge({ id, title }: { id: string | null | undefined; title?: string }) {
  const state = useClientProfile();
  const info = state.profiles?.profiles.find((p) => p.id === id);
  if (!id) return <span class="profile-badge none" title={title ?? "没有按客户端档案比较"}>未选档案</span>;
  return <span class={"profile-badge" + (info && !info.default ? " alt" : "")} title={title ?? id}>{state.label(id)}</span>;
}

/** Inline chip: 「v34 即可」 / 「需要 v35e」 / 位置或标记问题; nothing when no client extension is involved. */
export function CapChip({ req, what }: { req: CapRequirement | null | undefined; what?: string }) {
  const state = useClientProfile();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => { if (box.current && !box.current.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); setOpen(false); } };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => { window.removeEventListener("mousedown", onDown); window.removeEventListener("keydown", onKey, true); };
  }, [open]);
  const v = verdict(req, state);
  if (v.kind === "none" || !req) return null;
  const miss = v.kind === "needs" && !v.satisfied;
  const cls = v.kind === "ok" ? "ok" : v.kind === "needs" ? (miss ? "miss" : "needs") : "bad";
  const detail = describeRequirement(req, state);
  const tail = miss ? `\n当前目标客户端是 ${state.label(state.selected)}：按它生成会被兼容检查拦下。` : "";
  const title = (what ? what + "\n" : "") + detail + tail;
  return (
    <span class="cap-chip-wrap" ref={box}>
      <button type="button" class={"cap-chip " + cls} title={open ? undefined : title} aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }} onDblClick={(e) => e.stopPropagation()}>{v.label}</button>
      {open ? <span class="cap-pop" role="tooltip">{title}</span> : null}
    </span>
  );
}

/** Chip for a DSL program (skill / ability-triggered skill): follows ACUnique etc. to unique strings. */
export function ProgramCapChip({ path }: { path: string | null | undefined }) {
  const usable = !!path && path.startsWith("battle/");
  const req = useCaps(usable ? "program:" + path : null, () => programCaps(path!));
  return <CapChip req={req} what={`技能程序 ${path}`} />;
}

const CAP_RULES = new Set(["capability.missing", "capability.method-hash", "capability.patch-evidence"]);

/** Missing client capabilities of a generate result / delivery, with the patches and the profiles that have them. */
export function MissingCapabilities({ checks, profile }: { checks: RuleResult[]; profile: string | null | undefined }) {
  const state = useClientProfile();
  const missing = checks.filter((c) => c.blocking && c.id && CAP_RULES.has(c.rule));
  const ids = [...new Set(missing.map((c) => c.id!))];
  const req = useCaps(ids.length ? "caps:" + ids.join(",") : null, () => lookupCaps({ capability: ids }));
  if (!missing.length) return null;
  const order = state.profiles?.profiles ?? [];
  const satisfiers = (id: string) => order.filter((p) => req?.profiles[p.id] && !req.profiles[p.id].missing.some((m) => m.id === id));
  const all = order.filter((p) => req?.requiredClientProfiles.includes(p.id));
  const better = all.find((p) => p.id !== profile);
  return (
    <div class="missing-caps" role="group" aria-label="缺少的客户端能力">
      <h5>目标客户端 {profile ? state.label(profile) : "（未选档案）"} 缺少的能力（{ids.length}）</h5>
      <ul>
        {ids.map((id) => {
          const check = missing.find((c) => c.id === id)!;
          const cap = req?.capabilities.find((c) => c.id === id);
          const title = cap?.title ?? /^缺 (.+?)（/.exec(check.message)?.[1] ?? id;
          const patches = check.patches ?? cap?.patches ?? [];
          const lacking = check.missing_patches ?? [];
          const who = satisfiers(id);
          return (
            <li>
              <strong>{title}</strong> <span class="mono small muted">{id}</span>
              <div class="small">
                {check.rule === "capability.missing" ? "提供它的补丁：" : "问题："}
                {check.rule === "capability.missing"
                  ? (patches.length ? patches.map((n) => <span class="tag mono">#{n}</span>) : "独立方法能力（无补丁编号）")
                  : check.message}
                {lacking.length && lacking.length !== patches.length ? <span class="muted">（这个客户端缺 {lacking.map((n) => "#" + n).join(" ")}）</span> : null}
                {" · 能满足的客户端："}
                {req ? (who.length ? who.map((p) => <ProfileBadge id={p.id} title={p.id} />) : <span class="error-text">已登记档案都没有</span>)
                  : <span class="muted">查询中……</span>}
              </div>
            </li>
          );
        })}
      </ul>
      {better ? (
        <p class="small">
          这些能力 <ProfileBadge id={better.id} /> 都有：补丁只发给装了 {better.label} 的玩家时，把目标改成它再生成。
          {state.selected !== better.id ? <button class="small-btn" onClick={() => state.set(better.id)}>把目标客户端改为 {better.label}</button> : null}
        </p>
      ) : req && !all.length ? <p class="small error-text">没有哪个已登记的客户端档案同时满足这些能力。</p> : null}
    </div>
  );
}

/** Whole-roster report (docs/m2/compat-v34-v35.json), loaded once. */
export function useCharacterCompat(): { report: CharacterCompatReport | null; error: string | null } {
  const [report, setReport] = useState<CharacterCompatReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { characterCompat().then(setReport, (e: Error) => setError(e.message)); }, []);
  return { report, error };
}

/** Profiles this character needs according to the roster report (empty when the default profile already works). */
export function neededProfiles(report: CharacterCompatReport | null, cid: string, defaultProfile: string | undefined): string[] {
  const entry = report?.characters[cid];
  if (!entry || !defaultProfile) return [];
  if (entry.profiles[defaultProfile]?.satisfied !== false) return [];
  return report!.profiles.filter((p) => entry.profiles[p]?.satisfied);
}

/** Character header badge: 「需要 v35e」 from the roster report, with the missing capabilities in the tooltip. */
export function CharacterProfileBadge({ cid }: { cid: string }) {
  const state = useClientProfile();
  const { report } = useCharacterCompat();
  const fallback = state.profiles?.defaultClientProfile;
  const needed = neededProfiles(report, cid, fallback);
  if (!report || !fallback || !report.characters[cid]) return null;
  const entry = report.characters[cid];
  if (!needed.length && entry.profiles[fallback]?.satisfied) return null;
  const miss = entry.profiles[fallback]?.missing ?? [];
  const satisfied = !!state.selected && needed.includes(state.selected);
  const title = `依据全角色兼容报告（资源版本 ${report.tip}，离线静态结果）：\n${state.label(fallback)} 缺 ` +
    miss.map((m) => `${m.title}（补丁 ${m.patches.map((n) => "#" + n).join(" ")}）`).join("、") +
    (needed.length ? `\n满足：${needed.map((p) => state.label(p)).join("、")}` : "\n没有已登记档案满足") +
    (satisfied ? "" : `\n当前目标客户端 ${state.label(state.selected)} 不满足：这个角色的内容按它生成会被拦下。`);
  return (
    <span class={"cap-chip " + (needed.length ? (satisfied ? "needs" : "miss") : "bad")} title={title} tabIndex={0} aria-label={title}>
      {needed.length ? `需要 ${state.label(needed[0])}` : "所有档案都不满足"}
    </span>
  );
}
