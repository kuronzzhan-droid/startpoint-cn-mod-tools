import { RuleResult } from "../api";
import { MultiplayerDetails, MultiplayerNote } from "./MultiplayerAdvisory";

// Five-state rule display

const STATE_ORDER = ["问题", "待验证", "未执行", "满足", "不适用"];
const STATE_CLASS: Record<string, string> = { 联机风险: "rs-warn", 问题: "rs-bad", 待验证: "rs-warn", 未执行: "rs-none", 满足: "rs-ok", 不适用: "rs-na" };

export function ruleCounts(checks: RuleResult[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const c of checks) { const key = c.category ?? c.status; counts[key] = (counts[key] ?? 0) + 1; }
  return counts;
}

export function RuleChips({ counts }: { counts: Record<string, number> }) {
  const keys = [...STATE_ORDER, ...Object.keys(counts).filter((k) => !STATE_ORDER.includes(k))];
  return (
    <span class="rule-chips">
      {keys.filter((k) => counts[k]).map((k) => <span class={"rs " + (STATE_CLASS[k] ?? "")}>{k} {counts[k]}</span>)}
    </span>
  );
}

export function RuleList({ checks, title }: { checks: RuleResult[]; title?: string }) {
  const shown = checks.filter((c) => c.status !== "不适用");
  const hidden = checks.length - shown.length;
  shown.sort((a, b) => STATE_ORDER.indexOf(a.status) - STATE_ORDER.indexOf(b.status));
  return (
    <div class="rule-list">
      {title ? <h4>{title} <RuleChips counts={ruleCounts(checks)} /></h4> : null}
      <MultiplayerNote checks={checks} />
      <ul>
        {shown.map((c) => (
          <li class={STATE_CLASS[c.status] ?? ""}>
            <span class="rs-state">{c.category ?? c.status}{c.blocking ? "·阻断" : ""}</span>
            <span class="rs-msg"><Message text={c.message} /></span>
            <span class="mono small muted">{c.rule}{c.character ? " · " + c.character : ""}</span>
            <MultiplayerDetails check={c} />
          </li>
        ))}
      </ul>
      {hidden ? <p class="small muted">另有 {hidden} 条「不适用」（输入不在规则范围）未展开。</p> : null}
    </div>
  );
}


/** "text rules failed: [...]" carries wf text panel findings as JSON; show them readably. */
function Message({ text }: { text: string }) {
  const match = /^(text rules failed|问题): (\[.*\])$/s.exec(text);
  if (match) {
    try {
      const items: any[] = JSON.parse(match[2]);
      return (
        <span>
          面板文案规则未通过（wf text）：
          <ul class="text-findings">
            {items.map((f) => (
              <li><strong>{f.message}</strong> <span class="mono small muted">{f.rule} · {f.source ?? ""}</span>
                {f.evidence?.matches ? <span class="small"> — {f.evidence.matches.join("；")}</span> : null}</li>
            ))}
          </ul>
        </span>
      );
    } catch {
      /* fall through to raw text */
    }
  }
  return <>{text}</>;
}
