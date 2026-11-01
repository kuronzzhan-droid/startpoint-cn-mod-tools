import { BatchPreview, BatchWritten } from "../batchApi";
import { href } from "../router";
import { BossRuleList } from "./boss/BossChecks";
import { Notice } from "./common";
import { canSaveBatchRow } from "../batchReviewState";

export function BatchReview({ value, selected, onSelect }: {
  value: BatchPreview; selected: number[]; onSelect: (rows: number[]) => void;
}) {
  return <div>
    <p class="muted">默认均未勾选。核对前后描述和检查后逐行选择；实测：未执行。「需人工」行不可写入；标为「仅存草稿，阻断交付」的变体可保存，完成所列处理后才能交付。</p>
    {value.rows.map(row => <section class="boss-block" key={row.id}>
      <label class="check"><input type="checkbox" checked={selected.includes(row.id)} disabled={!canSaveBatchRow(row.status)}
        onChange={e => onSelect(e.currentTarget.checked ? [...selected, row.id] : selected.filter(id => id !== row.id))} />
        第 {row.id} 行 · {row.characterId ?? row.target?.to ?? "未匹配"} · {row.status}</label>
      {row.reason && <Notice kind="warn">{row.reason}</Notice>}
      {row.source && <p class="small">{row.source.join(" ｜ ")}</p>}
      <table class="boss-table"><thead><tr><th>词条</th><th>修改前</th><th>修改后</th></tr></thead>
        <tbody>{(row.changes ?? row.result?.variant.changes ?? []).map((c, i) => <tr key={i}>
          <td>{c.table}/{c.key}{c.row != null ? ` · 行 ${c.row}` : ""}</td>
          <td>{c.beforeDescription || "—"}</td><td>{c.afterDescription || "—"}</td>
        </tr>)}</tbody></table>
      {!!row.result?.variant.manual.length && <Notice kind="warn"><strong>需人工：以下条目保留在克隆草稿，生成交付会阻断。</strong>
        <ul>{row.result.variant.manual.map((m, i) => <li key={i}>{m.table}/{m.key}{m.row ? ` · 行 ${m.row}` : ""}：{m.reason}</li>)}</ul>
      </Notice>}
      <BossRuleList checks={row.checks} compact />
    </section>)}
  </div>;
}

export function BatchDone({ result }: { result: BatchWritten | null }) {
  return result ? <Notice>已写入 {result.written.length} 份角色草稿。{result.written.map(c =>
    <span key={c.characterId}> <a href={href({ work: "content", shop: "characters", id: c.characterId, tab: "changes" })}>{c.characterId} 本次修改</a> </span>)}
  </Notice> : null;
}
