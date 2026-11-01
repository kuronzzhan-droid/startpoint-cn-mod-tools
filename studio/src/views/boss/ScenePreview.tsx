import { SceneDifference, ScenePreview as Preview } from "../../sceneApi";
import { Notice } from "../common";
import { RuleChips, ruleCounts } from "../rules";
import { BossRuleList } from "./BossChecks";

const SUMMARY: Record<string, string> = { tables: "表", tableEntries: "表项", resources: "行为资源", phases: "阶段",
  tiers: "档位", summons: "召唤物", mechanisms: "机关", trials: "试炼", shops: "商店", drops: "掉落",
  changedFiles: "改动资源", serverFiles: "服务端本地候选" };

export function ScenePreview({ result }: { result: Preview }) {
  return <section class="scene-preview" aria-live="polite">
    <h2>场景编译预览 <RuleChips counts={ruleCounts(result.checks ?? [])} /></h2>
    <p>{result.ok ? "编译检查完成" : "编译存在问题"} · {result.canGenerate ? "可保存后生成本地交付" : "生成已阻断"}
      {result.runtime ? ` · 运行态：${result.runtime}` : " · 运行态：未执行"}</p>
    {(result.blockers ?? []).map((message, index) => <Notice key={index} kind="warn">{message}</Notice>)}
    {result.summary ? <p>{Object.entries(result.summary).map(([key, value]) => <span class="pill" key={key}>
      {SUMMARY[key] ?? key} {value}</span>)}</p> : null}
    <BossRuleList checks={result.checks ?? []} />
    {result.audit ? <details open={!result.audit.aligned}>
      <summary>解码资源与基准链对比：{result.audit.aligned ? "一致" : `${result.audit.differences.length} 处差异`}</summary>
      {result.audit.note ? <p>{result.audit.note}</p> : null}
      <DifferenceTable differences={result.audit.differences} />
      <details><summary>完整对比证据</summary><pre>{JSON.stringify(result.audit, null, 2)}</pre></details>
    </details> : <Notice kind="warn">未收到链资源对比证据，不能据此声称规格已复现。</Notice>}
    {result.diff ? <details open={result.diff.length > 0}><summary>当前规格改动（{result.diff.length}）</summary>
      <DifferenceTable differences={result.diff} />
    </details> : null}
    {result.outputSha256 ? <details><summary>编译输出 SHA-256</summary>
      {typeof result.outputSha256 === "string" ? <p class="small mono">{result.outputSha256}</p> : <div class="mode-table"><table>
        <thead><tr><th>本地候选文件</th><th>SHA-256</th></tr></thead><tbody>{Object.entries(result.outputSha256).map(([logical, hash]) =>
          <tr key={logical}><td class="small mono">{logical}</td><td class="small mono">{hash}</td></tr>)}</tbody></table></div>}
    </details> : null}
    <details><summary>完整预览报告</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
  </section>;
}

function DifferenceTable({ differences }: { differences: SceneDifference[] }) {
  return differences.length ? <div class="mode-table"><table><thead><tr><th>资源 / 位置</th><th>差异</th></tr></thead>
    <tbody>{differences.map((difference, index) => <tr key={index}>
      <td><code>{difference.logical ?? "规格"}</code><br /><code>{Array.isArray(difference.path) ? difference.path.join(" / ") : difference.path}</code></td>
      <td><pre>{JSON.stringify(difference, null, 2)}</pre></td>
    </tr>)}</tbody></table></div> : <p class="muted">未发现差异。</p>;
}
