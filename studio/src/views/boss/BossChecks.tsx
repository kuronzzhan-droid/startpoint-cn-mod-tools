import { ComponentChildren } from "preact";
import { RuleResult } from "../../api";
import { RuleChips, ruleCounts } from "../rules";
import { RULE_LABEL } from "./bossModel";

const STATE_ORDER = ["问题", "待验证", "未执行", "满足", "不适用"];
const STATE_CLASS: Record<string, string> = { 问题: "rs-bad", 待验证: "rs-warn", 未执行: "rs-none", 满足: "rs-ok", 不适用: "rs-na" };

type QuestResult = RuleResult & { quest?: string };

/** "第 1、2、5 档" for tiers of one node; otherwise the quest paths. */
function questsLabel(quests: string[]): string {
  const paths = quests.map((q) => q.split(":").pop() ?? q);
  const prefix = paths[0]?.split("/").slice(0, -1).join("/");
  if (quests.every((q) => q.startsWith("boss_battle:")) && paths.every((p) => p.split("/").slice(0, -1).join("/") === prefix))
    return "第 " + paths.map((p) => p.split("/").pop()).join("、") + " 档";
  return paths.join("、");
}

/** Same rule, state and message on several quests (five-tier edits) are shown once. */
function merged(checks: QuestResult[]): (QuestResult & { quests: string[] })[] {
  const groups = new Map<string, QuestResult & { quests: string[] }>();
  for (const c of checks) {
    const key = [c.rule, c.status, c.blocking, c.message, JSON.stringify((c as any).issues ?? [])].join("|");
    const entry = groups.get(key);
    if (entry) { if (c.quest) entry.quests.push(c.quest); }
    else groups.set(key, { ...c, quests: c.quest ? [c.quest] : [] });
  }
  return [...groups.values()];
}

/** Five-state boss rule results, blocking first; long evidence folds into 「技术细节」. */
export function BossRuleList({ checks, compact }: { checks: RuleResult[]; compact?: boolean }) {
  // The request summary (boss.inputs) repeats the blocking rules; show it only when nothing else explains.
  const rules = checks.filter((c) => c.rule !== "boss.inputs");
  const summary = checks.find((c) => c.rule === "boss.inputs");
  const multi = new Set(rules.map((c) => (c as QuestResult).quest).filter(Boolean)).size > 1;
  const all = merged(rules.length ? rules : checks);
  const shown = all.filter((c) => c.status !== "不适用");
  const hidden = all.length - shown.length;
  shown.sort((a, b) => Number(b.blocking) - Number(a.blocking)
    || STATE_ORDER.indexOf(a.status) - STATE_ORDER.indexOf(b.status));
  return (
    <div class={"boss-rules" + (compact ? " compact" : "")}>
      {summary && rules.length ? <p class="small error-text">{plainSummary(summary.message)}</p> : null}
      <ul>
        {shown.map((c) => {
          const extra = c as RuleResult & { issues?: string[]; limitations?: string[]; acknowledgment?: { acknowledgePreload: boolean } };
          return (
            <li class={STATE_CLASS[c.status] ?? ""}>
              <div class="br-head">
                <span class="rs-state">{c.status}{c.blocking ? " · 阻断" : ""}</span>
                <strong class="br-name">{RULE_LABEL[c.rule] ?? c.rule}</strong>
                {multi && c.quests.length ? <span class="small muted">{questsLabel(c.quests)}</span> : null}
              </div>
              <p class="br-msg">{c.message}</p>
              {extra.issues?.length ? (
                <ul class="br-issues">{extra.issues.map((i) => <li>{i}</li>)}</ul>
              ) : null}
              {extra.acknowledgment?.acknowledgePreload ? <p class="small warn-text">已显式确认未证明的预载风险（只豁免「待验证」，不豁免已知故障）。</p> : null}
              {extra.limitations?.length || c.evidence_nature || c.source ? (
                <details class="tech">
                  <summary>技术细节</summary>
                  <p class="small mono">{c.rule}{c.evidence_nature ? " · 依据：" + c.evidence_nature : ""}</p>
                  {c.source ? <p class="small muted">{c.source}</p> : null}
                  {extra.limitations?.length ? <ul class="small">{extra.limitations.slice(0, 12).map((l) => <li>{l}</li>)}
                    {extra.limitations.length > 12 ? <li>……另 {extra.limitations.length - 12} 条</li> : null}</ul> : null}
                </details>
              ) : null}
            </li>
          );
        })}
      </ul>
      {hidden ? <p class="small muted">另有 {hidden} 条「不适用」（这次改动不在规则范围）。</p> : null}
    </div>
  );
}

function plainSummary(message: string): string {
  return message.replace(/^boss rules rejected the candidate: /, "规则阻断：");
}

/** Right-hand column: what the checks are about and their results. */
export function ChecksPanel({ title, checks, state, note, children }: {
  title: string; checks: RuleResult[] | null; state?: "running" | "stale" | "idle"; note?: string;
  children?: ComponentChildren;
}) {
  const blocking = (checks ?? []).filter((c) => c.blocking && c.rule !== "boss.inputs").length
    || (checks ?? []).filter((c) => c.blocking).length;
  return (
    <aside class="boss-checks" aria-label="检查结果" aria-live="polite">
      <header>
        <h3>{title}</h3>
        {checks ? <RuleChips counts={ruleCounts(checks.filter((c) => c.rule !== "boss.inputs" || checks.length === 1))} /> : null}
      </header>
      {state === "running" ? <p class="small muted">检查中……</p> : null}
      {state === "stale" ? <p class="small warn-text">改动后还没重新检查。</p> : null}
      {checks && checks.length ? (
        <>
          <p class={"small " + (blocking ? "error-text" : "state-ok")}>
            {blocking ? `${blocking} 项阻断：不能写入草稿` : "没有阻断项"}
          </p>
          <BossRuleList checks={checks} compact />
        </>
      ) : !state || state === "idle" ? <p class="small muted">{note ?? "未执行：还没有改动。"}</p> : null}
      {children}
      <p class="small muted boss-checks-foot">五态：满足 / 问题 / 待验证 / 不适用 / 未执行。静态检查通过不等于真机验证；真机一栏始终是「未记录」。</p>
    </aside>
  );
}
