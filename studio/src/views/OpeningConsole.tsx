import { useEffect, useState } from "preact/hooks";
import { useClientProfile } from "../clientProfile";
import { opening, OpeningChecklist, OpeningServer } from "../openingApi";
import { Notice } from "./common";
import { RuleList } from "./rules";
import "./opening.css";

const STATUS = { ready: "只读检查就绪", blocked: "存在阻断项", pending: "存在待验证项" };
const CAPABILITY = { matched: "已匹配", mismatch: "缺少能力", unknown: "证据不完整，待验证" };

export function OpeningConsole() {
  const profile = useClientProfile();
  const [server, setServer] = useState<OpeningServer>("local");
  const [report, setReport] = useState<OpeningChecklist | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let alive = true;
    setReport(null); setError(null);
    opening.read(server, profile.selected).then(value => alive && setReport(value),
      e => alive && setError((e as Error).message));
    return () => { alive = false; };
  }, [server, profile.selected, refresh]);
  return <section class="page opening-console">
    <div class="page-head"><div><h1>开服台</h1>
      <p class="muted">根据当前链视图和本机配置生成待执行清单。所有服务端步骤由操作者另行执行。</p></div>
      <span class="pill readonly">只读检查 · 未执行部署</span>
    </div>
    <div class="version-row">
      <label>目标 <select value={server} onChange={e => setServer(e.currentTarget.value as OpeningServer)}>
        <option value="local">本地服</option><option value="test175">175 测试服（只读快照）</option>
      </select></label>
      <span class="small muted">客户端：{profile.label(profile.selected ?? "") || "待选择"}</span>
      <button onClick={() => setRefresh(value => value + 1)}>重新只读检查</button>
    </div>
    <Notice>只列本地服和 175 的步骤；不连接 175、不执行部署、重启或服务端写入。目标数据来自 profiles/local.json 配置的本机只读镜像，不能代表远端实时状态。</Notice>
    {error ? <Notice kind="error">{error}</Notice> : null}
    {!report && !error ? <p class="loading">正在比较链与目标 manifest……</p> : null}
    {report ? <OpeningResult report={report} /> : null}
  </section>;
}

export function OpeningResult({ report }: { report: OpeningChecklist }) {
  const caps = report.clientCapabilities;
  return <>
    <div class="opening-summary">
      <article><span class="muted">当前视图链尾</span><strong>{report.source.version}</strong>
        <span class="small">基线 {report.source.baseVersion ?? "待核对"} · {report.source.edgeCount} 条边</span></article>
      <article><span class="muted">目标 manifest 链尾</span><strong>{report.target.version ?? "未读取"}</strong>
        <span class="small">{report.target.configured ? "已配置本机镜像" : "尚未配置本机镜像"}</span></article>
      <article><span class="muted">检查结论</span><strong>{STATUS[report.status]}</strong>
        <span class="small">运行态：{report.runtime} · {report.createdAt}</span></article>
    </div>
    <p class="small muted">{report.note}</p>
    <RuleList checks={report.checks} title="链与目标检查" />
    <section><h2>需要补齐的边（{report.missingEdges.length}）</h2>
      {report.missingEdges.length ? <div class="opening-table"><table>
        <thead><tr><th>版本边</th><th>归档与摘要</th><th>适用范围</th></tr></thead>
        <tbody>{report.missingEdges.map(edge => <tr key={`${edge.from}:${edge.to}`}>
          <td class="mono">{edge.from} → {edge.to}</td><td>{edge.archives.map(archive => <div key={archive.name}>
            <strong>{archive.name}</strong><p class="small mono">{archive.sha256 ?? "SHA-256 待验证"}</p>
            {archive.size != null ? <span class="small muted">{archive.size.toLocaleString()} B</span> : null}
          </div>)}</td><td>{edge.localTestOnly ? "仅限本地候选" : "仍须逐边核验交付授权"}</td>
        </tr>)}</tbody></table></div> : <p class="muted">未列出待补边；请以检查结论判断是已对齐还是输入不完整。</p>}
      {report.target.manifestSha256 ? <p class="small mono">目标 manifest SHA-256：{report.target.manifestSha256}</p> : null}
    </section>
    <section><h2>客户端 provides：{CAPABILITY[caps.status]}</h2>
      <p>档案 <code>{caps.profile}</code> · {caps.available ? `${caps.providesCount} 项能力证据` : "能力证据不可用"}</p>
      <CapabilityList title="需要的能力" values={caps.requires} empty="没有列出的能力要求；历史边缺少 requires 时仍待验证。" />
      <CapabilityList title="缺少的能力" values={caps.missing} empty="没有明确缺失项。" />
      <CapabilityList title="证据缺失的边" values={caps.unknownEdges} empty="没有列出的未知边。" />
      <RuleList checks={caps.checks} title="能力核验详情" />
    </section>
    <section class="opening-steps"><h2>待执行清单</h2>
      <p class="muted">下列步骤尚未执行。检查就绪也不表示已开服。</p>
      <ol>{report.manualSteps.map((step, index) => <li key={index}>{step}</li>)}</ol>
      <h3>回滚与修正</h3><p>{report.rollback}</p>
      <div class="version-row">{report.entryLinks.map(link => <a key={link.id} class="header-btn" href={link.href}
        {...(link.href.startsWith("/api/") ? { target: "_blank", rel: "noreferrer" } : {})}>{link.label}</a>)}</div>
    </section>
    <details><summary>本次只读报告原文</summary><pre>{JSON.stringify(report, null, 2)}</pre></details>
  </>;
}

function CapabilityList({ title, values, empty }: { title: string; values: string[]; empty: string }) {
  return <details open={values.length > 0}><summary>{title}（{values.length}）</summary>
    {values.length ? <ul>{values.map(value => <li key={value}><code>{value}</code></li>)}</ul> : <p class="muted">{empty}</p>}
  </details>;
}
