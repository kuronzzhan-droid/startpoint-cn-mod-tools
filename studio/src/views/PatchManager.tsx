import { useEffect, useMemo, useState } from "preact/hooks";
import { api, Patch, PatchChain } from "../api";
import { href } from "../router";
import { Notice } from "./common";

function size(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

export function PatchManager({ archive }: { archive?: string }) {
  const [chain, setChain] = useState<PatchChain | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [onlyView, setOnlyView] = useState(false);

  useEffect(() => {
    api.patches().then(setChain, (e: Error) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!chain) return [];
    const q = query.trim().toLowerCase();
    return chain.patches.filter((p) => (!onlyView || p.inView) &&
      (!q || `${p.name} ${p.archive} ${p.version} ${p.description}`.toLowerCase().includes(q)));
  }, [chain, query, onlyView]);

  if (error) return <section class="page"><Notice kind="error">补丁链读取失败：{error}</Notice></section>;
  if (!chain) return <section class="page"><div class="loading">正在读取补丁链……</div></section>;
  const selected = archive ? chain.patches.find((p) => p.archive === archive) : undefined;
  if (selected) return <PatchDetail patch={selected} />;

  return (
    <section class="page">
      <div class="page-head">
        <div>
          <h1>补丁管理</h1>
          <p class="muted">{chain.note}</p>
        </div>
        <div class="stats">
          <div><span class="label">清单版本</span><strong>{chain.cdnVersion}</strong></div>
          <div><span class="label">视图版本</span><strong>{chain.viewVersion}</strong></div>
          <div><span class="label">条目</span><strong>{chain.count}</strong></div>
        </div>
      </div>
      <div class="search-row">
        <input class="search" type="search" placeholder="按名称、文件名或版本筛选" value={query}
          onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
        <label class="check"><input type="checkbox" checked={onlyView}
          onChange={(e) => setOnlyView((e.target as HTMLInputElement).checked)} />只看当前视图叠加的</label>
      </div>
      <div class="table-wrap">
        <table class="patches">
          <thead>
            <tr><th>版本</th><th>名称</th><th>来源</th><th>状态</th><th>大小</th><th></th></tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr>
                <td class="mono nowrap">{p.dependsOn ? `${p.dependsOn} → ` : ""}{p.version ?? "—"}</td>
                <td>
                  <div>{p.name}</div>
                  <div class="mono small muted">{p.archive}</div>
                </td>
                <td class="small">{p.origin}</td>
                <td class="small"><PatchState patch={p} /></td>
                <td class="small nowrap">{size(p.archiveSize)}</td>
                <td><a href={href({ work: "patches", archive: p.archive })}>查看</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PatchState({ patch }: { patch: Patch }) {
  const parts: string[] = [];
  if (patch.enabled === true) parts.push("清单启用");
  if (patch.enabled === false) parts.push("清单停用");
  parts.push(patch.presentInActive ? "active 有文件" : "active 无文件");
  if (patch.inView) parts.push("已叠入视图");
  return <span>{parts.join(" · ")}</span>;
}

function PatchDetail({ patch }: { patch: Patch }) {
  const [members, setMembers] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.patchMembers(patch.archive).then((m) => setMembers(m.members), (e: Error) => setError(e.message));
  }, [patch.archive]);
  return (
    <section class="page">
      <a class="back" href={href({ work: "patches" })}>← 返回补丁列表</a>
      <div class="page-head">
        <div>
          <h1>{patch.name}</h1>
          <p class="muted">{patch.origin} · {patch.dependsOn ? `${patch.dependsOn} → ` : ""}{patch.version}</p>
        </div>
      </div>
      {patch.description ? <p>{patch.description}</p> : null}
      {patch.changes.length ? (
        <>
          <h3>包含的内容</h3>
          <ul>{patch.changes.map((c) => <li>{c}</li>)}</ul>
        </>
      ) : null}
      <h3>文件</h3>
      <p class="mono small">{patch.archive} · <PatchState patch={patch} /></p>
      {error ? <Notice kind="warn">无法读取 ZIP 成员：{error}</Notice> : null}
      {members ? (
        <details>
          <summary>ZIP 成员 {members.length} 个（哈希路径）</summary>
          <ul class="mono small members">{members.slice(0, 500).map((m) => <li>{m}</li>)}</ul>
        </details>
      ) : null}
      <Notice>本版不提供导出、应用或发布动作；需要时请使用现有发布流程。</Notice>
    </section>
  );
}
