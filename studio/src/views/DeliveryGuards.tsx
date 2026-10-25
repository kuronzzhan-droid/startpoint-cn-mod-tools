import { useState } from "preact/hooks";
import { BundleCheck, ClientExtensions, IconAlphaResult, KeyDiff } from "../api";
import { Notice } from "./common";
import { RuleList } from "./rules";

// Delivery guards that static checks used to miss (贝瑞塔 1.4.291–1.4.300):
// APK built-in table key collisions (C7051), key-level diff of shared tables against
// the target chain, derived icons that paint over the portrait's transparency, and the
// p12/p13 client keys a summoned ball's PF depends on.

const BUNDLE_STATE: Record<BundleCheck["status"], { label: string; cls: string }> = {
  ok: { label: "无撞名", cls: "rs-ok" },
  collision: { label: "撞名·阻断", cls: "rs-bad" },
  skipped: { label: "未核对", cls: "rs-warn" },
  error: { label: "扫描失败", cls: "rs-bad" },
};

export function BundleCheckPanel({ check }: { check: BundleCheck | null | undefined }) {
  if (!check) return <p class="small muted">没有 bundle-check.json（这次生成早于撞名检查，或生成未完成）。</p>;
  const state = BUNDLE_STATE[check.status] ?? { label: check.status, cls: "rs-warn" };
  const hits = (check.tables ?? []).filter((t) => t.collisions?.length);
  return (
    <div class="guard-block">
      <h4>APK 内置表撞名 <span class={"rs " + state.cls}>{state.label}</span></h4>
      <p class="small muted">客户端把 CDN 表和安装包里同名的 _iosbundled 表合并，同一个键出现两次就报 C7051。</p>
      {check.status === "skipped" ? (
        <Notice kind="warn">没有核对：{check.reason ?? "没有配置目标客户端的 APK"}。在本机配置 client_apks 后重新生成。</Notice>
      ) : null}
      {check.status === "error" ? <Notice kind="error">{check.reason ?? "扫描失败"}</Notice> : null}
      {check.apks?.length ? (
        <div class="small">核对的安装包：{check.apks.map((a) => (
          <span class="tag mono" title={a.sha256}>{a.label} · 内置表 {a.bundledTables}</span>
        ))}</div>
      ) : null}
      {hits.length ? (
        <table class="files">
          <thead><tr><th>输出表</th><th>撞名的键</th></tr></thead>
          <tbody>
            {hits.map((t) => (
              <tr><td class="mono small">{t.logical}</td><td class="mono small error-text">{t.collisions.join(", ")}</td></tr>
            ))}
          </tbody>
        </table>
      ) : check.status === "ok" ? <p class="small">本次输出的 {check.tables?.length ?? 0} 张表都没有和内置表重复的键。</p> : null}
    </div>
  );
}

const DELETION_LABEL: Record<string, string> = {
  nested_key_removed: "删了内层键",
  nested_map_replaced: "内层表被换成单值",
  csv_rows_removed: "CSV 少了行",
  csv_replaced: "CSV 被换成别的结构",
};

function KeyList({ label, keys, kind }: { label: string; keys?: string[]; kind: string }) {
  if (!keys?.length) return null;
  return (
    <>
      <div class="small">{label}</div>
      <div class={"kd-keys kd-" + kind}>{keys.map((k) => <span class="tag mono">{k}</span>)}</div>
    </>
  );
}

export function KeyDiffPanel({ diff, mdUrl }: { diff: KeyDiff | null | undefined; mdUrl: string | null }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!diff) return <p class="small muted">没有 key-diff.json（这次生成早于键级差异，或生成未完成）。</p>;
  const tables = diff.tables ?? [];
  const total = diff.counts ?? { added: 0, changed: 0, removed: 0, foreign: 0, unknown: 0 };
  const base = diff.baseline ?? {};
  const range = diff.delivery?.from && diff.delivery?.to ? ` · 交付 ${diff.delivery.from} → ${diff.delivery.to}` : "";
  return (
    <div class="guard-block">
      <h4>对目标链的键级差异
        {total.removed ? <span class="rs rs-bad">删键 {total.removed}·阻断</span> : null}
        {total.foreign ? <span class="rs rs-warn">非本角色键 {total.foreign}</span> : null}
        {total.unknown ? <span class="rs rs-warn">归属未知 {total.unknown}</span> : null}
        {!total.removed && !total.foreign && !total.unknown ? <span class="rs rs-ok">只动自己的键</span> : null}
      </h4>
      <p class="small muted">
        基线：{base.view ?? "交付所用视图"}{base.tip ? ` · 链尾 ${base.tip}` : ""}{range}。
        共享表按整文件投递，删键等于删掉别人的数据；并行线程叠边前拿这份清单对键。
      </p>
      {(diff.warnings ?? []).map((w) => <p class="small warn-text">{w}</p>)}
      {mdUrl ? <p class="small"><a href={mdUrl} target="_blank" rel="noreferrer">打开给并行线程的对键清单（key-diff.md）</a></p> : null}
      {tables.length ? (
        <table class="files">
          <thead><tr><th>表</th><th>新增</th><th>改动</th><th>删除</th><th>非本角色</th><th>归属未知</th></tr></thead>
          <tbody>
            {tables.map((t) => {
              const c = t.counts;
              const key = (t.archive ?? "") + "|" + t.logical;
              const isOpen = open === key;
              return (
                <>
                  <tr class="clickable" onClick={() => setOpen(isOpen ? null : key)}>
                    <td class="mono small">{isOpen ? "▾ " : "▸ "}{t.logical}</td>
                    <td>{c.added || ""}</td>
                    <td>{c.changed || ""}</td>
                    <td class={c.removed ? "error-text" : ""}>{c.removed || ""}</td>
                    <td class={c.foreign ? "warn-text" : ""}>{c.foreign || ""}</td>
                    <td class={c.unknown ? "warn-text" : ""}>{c.unknown || ""}</td>
                  </tr>
                  {isOpen ? (
                    <tr><td colSpan={6}>
                      <KeyList label="删除" keys={t.removed} kind="removed" />
                      {t.deletions?.length ? (
                        <ul class="small error-text">
                          {t.deletions.map((d) => (
                            <li class="mono">{d.path.join(" › ")}：{DELETION_LABEL[d.kind] ?? d.kind}
                              {d.removedRows != null ? `（${d.beforeRows} → ${d.afterRows} 行）` : ""}</li>
                          ))}
                        </ul>
                      ) : null}
                      <KeyList label="非本角色" keys={t.foreign} kind="foreign" />
                      <KeyList label="归属未知（没有当成自有键）" keys={t.unknown} kind="foreign" />
                      <KeyList label="新增" keys={t.added} kind="added" />
                      <KeyList label="改动" keys={t.changed} kind="changed" />
                      {t.truncated ? <p class="small muted">键太多，只列了一部分；全部见 key-diff.json。</p> : null}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      ) : <p class="small">这次交付没有改动表。</p>}
    </div>
  );
}

export function IconAlphaPanel({ result }: { result: IconAlphaResult | null | undefined }) {
  if (!result) return null;
  const slots = result.slots ?? [];
  const reasons = [...new Set(slots.filter((s) => s.status === "skipped").map((s) => s.message).filter(Boolean))];
  if (result.status === "skipped" || !slots.length) {
    return (
      <div class="guard-block">
        <h4>派生图标透明区 <span class="rs rs-none">未检查</span></h4>
        {reasons.length ? reasons.map((r) => <p class="small muted">{r}</p>)
          : <p class="small muted">{result.reason ?? "缺少立绘模板或形状蒙版，没有做这项检查。"}</p>}
      </div>
    );
  }
  const filled = slots.filter((s) => s.status === "warning" || s.status === "info");
  const warned = filled.filter((s) => s.status === "warning");
  const unchecked = slots.filter((s) => s.status === "skipped");
  return (
    <div class="guard-block">
      <h4>派生图标透明区
        {warned.length ? <span class="rs rs-warn">{warned.length} 张填了底色</span> : null}
        {filled.length && !warned.length ? <span class="rs rs-none">作者选了底色</span> : null}
        {!filled.length && !unchecked.length ? <span class="rs rs-ok">透明区保持透明</span> : null}
        {unchecked.length ? <span class="rs rs-none">部分未检查</span> : null}
      </h4>
      {unchecked.length ? reasons.map((r) => <p class="small muted">未检查：{r}</p>) : null}
      {warned.length ? <p class="small">官方头像是透明底、由界面底框衬底。立绘透明的地方被铺了底色，一般应回立绘页勾上「透明底」。</p> : null}
      {filled.length ? (
        <table class="files">
          <thead><tr><th>槽位</th><th>被填色比例</th><th></th></tr></thead>
          <tbody>{filled.map((s) => (
            <tr>
              <td class="mono small">{s.slot}{s.form != null ? ` · ${s.form}` : ""}</td>
              <td>{s.ratio != null ? (s.ratio * 100).toFixed(1) + "%" : "—"}</td>
              <td class="small muted">{s.authorBackdrop ? "作者选择了底色" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      ) : null}
    </div>
  );
}

export function ClientExtensionsPanel({ result }: { result: ClientExtensions | null | undefined }) {
  if (!result || (!result.checks?.length && !result.requires?.length)) return null;
  return (
    <div class="guard-block">
      {result.requires?.length ? (
        <p class="small">召唤球 / 双人 PF 等扩展键需要的客户端能力：{result.requires.map((c) => <span class="tag mono">{c}</span>)}</p>
      ) : null}
      {result.checks?.length ? <RuleList checks={result.checks} title="客户端扩展键（p12 / p13）" /> : null}
    </div>
  );
}
