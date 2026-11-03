import { useCallback, useEffect, useState } from "preact/hooks";
import { corridor, CorridorStatus, Finding, Json, Registry, short } from "../../corridorApi";
import { Notice } from "../common";
import { Ctx, CorridorCtx, FindingList, Tag, useCorridor } from "./widgets";
import { CharactersPage, SoulsPage, WeaponsPage } from "./PoolPages";
import { RelicsPage } from "./RelicsPage";
import { EventsPage } from "./EventsPage";
import { EncountersPage } from "./EncountersPage";
import { BalancePage } from "./BalancePage";
import { LocalesPage } from "./LocalesPage";
import { ReleasesPage } from "./ReleasesPage";
import "./corridor.css";

export const PAGES: [string, string][] = [
  ["overview", "总览"], ["characters", "角色池"], ["weapons", "武器"], ["souls", "魂珠"], ["relics", "遗物"],
  ["events", "事件"], ["encounters", "遭遇/首领"], ["balance", "商店·奖励·难度"], ["locales", "中英文本"], ["releases", "变更与发布"],
];

const ENTITY_PAGE: Record<string, string> = {
  relic: "relics", event: "events", character: "characters", weapon: "weapons", soul: "souls", encounter: "encounters",
  act: "encounters", rules: "balance", locale: "locales", element: "characters", shop: "balance",
};

export function findingLink(f: Finding): string {
  const page = ENTITY_PAGE[f.entity_type ?? ""] ?? "overview";
  const id = f.entity_id && ["relics", "events"].includes(page) ? "/" + encodeURIComponent(f.entity_id) : "";
  return `#/corridor/${page}${id}`;
}

export function Corridor({ page = "overview", id }: { page?: string; id?: string }) {
  const [status, setStatus] = useState<CorridorStatus | null>(null);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await corridor.status());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    refresh();
    corridor.registry().then(setRegistry, () => setRegistry(null));
  }, []);

  const revision = status?.workspace?.revision ?? 0;
  const run = useCallback(async (commands: Record<string, Json>[], message?: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await corridor.commands(revision, commands, message);
      await refresh();
      setTick((t) => t + 1);
      return result;
    } catch (e) {
      setError((e as Error).message);
      await refresh();
      setTick((t) => t + 1);
      return null;
    } finally {
      setBusy(false);
    }
  }, [revision]);

  const ctx: CorridorCtx = { status, registry, revision, tick, busy, run, refresh: async () => { await refresh(); setTick((t) => t + 1); }, setError };
  const v = status?.validation;
  return (
    <Ctx.Provider value={ctx}>
      <div class={"cor" + (busy ? " cor-busy" : "")}>
        <div class="cor-head">
          <h1>深渊回廊</h1>
          {status?.workspace ? (
            <>
              <span class="pill" title="编辑台工作区乐观锁版本（不等于 rules_revision / 内容版本）">工作区 r{status.workspace.revision}</span>
              <a href="#/corridor/overview" title="阻断项必须清零才能打包发布">
                <Tag kind={v?.blockers ? "bad" : "ok"}>阻断 {v?.blockers ?? "?"}</Tag>
              </a>
              <a href="#/corridor/overview"><Tag kind={v?.warnings ? "warn" : ""}>警告 {v?.warnings ?? "?"}</Tag></a>
              <Tag kind={status.workspace.active_profile === "test" ? "warn" : "info"}
                title="difficulty.active_profile：test=试验倍率，formal=三幕目标曲线">难度档 {status.workspace.active_profile}</Tag>
              {!status.workspace.locks_ok ? <Tag kind="bad">主数据哈希变化</Tag> : null}
            </>
          ) : null}
          <nav class="cor-nav" aria-label="回廊页面">
            {PAGES.map(([key, label]) => (
              <a key={key} class={page === key ? "active" : ""} href={`#/corridor/${key}`}>{label}</a>
            ))}
          </nav>
        </div>
        {error ? <Notice kind="error"><div style="white-space:pre-wrap">{error}</div>
          <button class="ghost" onClick={() => setError(null)}>知道了</button></Notice> : null}
        {!status ? <div class="loading">读取回廊工作区…</div>
          : !status.configured ? <Notice kind="warn">还没配置深渊回廊编辑。{status.hint}</Notice>
          : !status.workspace ? <ImportFirst status={status} />
          : page === "overview" ? <Overview status={status} />
          : !registry ? <div class="loading">读取效果清单…</div>
          : page === "characters" ? <CharactersPage />
          : page === "weapons" ? <WeaponsPage />
          : page === "souls" ? <SoulsPage />
          : page === "relics" ? <RelicsPage id={id} />
          : page === "events" ? <EventsPage id={id} />
          : page === "encounters" ? <EncountersPage />
          : page === "balance" ? <BalancePage />
          : page === "locales" ? <LocalesPage />
          : page === "releases" ? <ReleasesPage />
          : <Overview status={status} />}
      </div>
    </Ctx.Provider>
  );
}

function ImportFirst({ status }: { status: CorridorStatus }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const missing = Object.entries(status.config?.sources ?? {}).filter(([, ok]) => !ok).map(([k]) => k);
  return (
    <div class="cor-card">
      <h3>从源文件导入</h3>
      <p>把当前回廊运行时文件（proto-server 配置、v3f 角色池叠加层、遗物/事件/文本/遭遇池）无损读进编辑台工作区。
        源文件不会被改动；完整分档表与魂珠目录只按哈希锁定。</p>
      {missing.length ? <Notice kind="error">缺少源文件：{missing.join("、")}</Notice> : null}
      {status.master?.errors.length ? <Notice kind="error">{status.master.errors.join("；")}</Notice> : null}
      {err ? <Notice kind="error">{err}</Notice> : null}
      <button class="primary" disabled={busy || missing.length > 0} onClick={async () => {
        setBusy(true);
        try {
          await corridor.importSource(null);
          location.reload();
        } catch (e) {
          setErr((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}>导入</button>
    </div>
  );
}

function Overview({ status }: { status: CorridorStatus }) {
  const ws = status.workspace!;
  const m = status.master!;
  const v = status.validation!;
  const [snapMsg, setSnapMsg] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const { refresh, setError } = useCorridor();
  const act = async (fn: () => Promise<unknown>, done: string) => {
    try {
      await fn();
      setNote(done);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div class="cor">
      {note ? <Notice>{note}</Notice> : null}
      <div class="cor-grid">
        <div class="cor-card">
          <h3>工作区</h3>
          <dl class="cor-kv">
            <dt>revision</dt><dd>r{ws.revision}</dd>
            <dt>导入时间</dt><dd>{String(ws.source.imported_at ?? "")}</dd>
            <dt>遗物 / 事件</dt><dd>{ws.counts.relics} / {ws.counts.events}</dd>
            <dt>角色覆盖条目</dt><dd>{ws.counts.overrides}（v3f 叠加层）</dd>
            <dt>已退休 ID</dt><dd>{ws.counts.tombstones}</dd>
            <dt>宿主 / 源活动</dt><dd>{String(ws.source.runtime_host_event_id)} / {String(ws.source.encounter_source_event_id)}
              <span class="muted small">（用途不同，不要求相等）</span></dd>
          </dl>
          {ws.upstream_changed.length ? (
            <Notice kind="warn">源文件导入后被改过：{ws.upstream_changed.join("、")}。编辑台不会覆盖源文件；要吸收上游改动请重新导入（会先自动快照，保留稳定 ID 与墓碑）。
              <div><button onClick={() => window.confirm("用源文件重建工作区？当前改动会被源文件覆盖（已自动快照，可恢复）") &&
                act(() => corridor.importSource(ws.revision), "已重新导入")}>重新从源文件导入</button></div>
            </Notice>
          ) : null}
        </div>
        <div class="cor-card">
          <h3>锁定的主数据 {ws.locks_ok ? <Tag kind="ok">哈希一致</Tag> : <Tag kind="bad">已变化</Tag>}</h3>
          <dl class="cor-kv">
            <dt>游戏数据版本</dt><dd>{m.source_version}（{m.status}）</dd>
            <dt>tier_table</dt><dd class="mono">{short(m.tier_sha256)}</dd>
            <dt>魂珠目录</dt><dd class="mono">{short(m.soul_sha256)}</dd>
            <dt>角色</dt><dd>入表 {m.characters} · 排除 {m.excluded_characters}</dd>
            <dt>武器</dt><dd>入表 {m.weapons} · 属性待定 {m.pending_weapons}</dd>
            <dt>魂珠</dt><dd>{m.souls}</dd>
          </dl>
          {m.errors.length ? <Notice kind="error">{m.errors.join("；")}</Notice> : null}
          {!ws.locks_ok ? (
            <button onClick={() => window.confirm("确认接受新的 tier_table/魂珠目录作为锁定版本？") &&
              act(async () => {
                const s = await corridor.status();
                await corridor.commands(s.workspace!.revision, [{ op: "source.relock" }], "重新锁定主数据");
              }, "已重新锁定主数据")}>重新锁定主数据</button>
          ) : null}
        </div>
        <div class="cor-card">
          <h3>快照</h3>
          <div class="cor-toolbar">
            <input type="text" placeholder="快照说明" value={snapMsg} onInput={(e) => setSnapMsg((e.currentTarget as HTMLInputElement).value)} />
            <button onClick={() => act(() => corridor.snapshot(snapMsg || "手动快照"), "已保存快照")}>保存快照</button>
          </div>
          <ul class="small">
            {(status.snapshots ?? []).map((s) => (
              <li key={s.id}>
                <span class="mono">{s.id}</span> r{s.revision} {s.message} <span class="muted">{s.kind}</span>{" "}
                <a href="javascript:void 0" onClick={() => window.confirm(`把工作区恢复到快照 ${s.id}？（当前内容会先自动快照）`) &&
                  act(() => corridor.restore(s.id, ws.revision), `已恢复到 ${s.id}`)}>恢复</a>
              </li>
            ))}
          </ul>
          <div class="cor-toolbar small">
            <a href="/api/corridor/export?format=workspace" download>导出工作区 JSON</a>
            <label>导入工作区 JSON <input type="file" accept="application/json" onChange={async (e) => {
              const file = (e.currentTarget as HTMLInputElement).files?.[0];
              if (!file) return;
              try {
                const doc = JSON.parse(await file.text());
                if (window.confirm(`用 ${file.name} 替换当前工作区？（会先自动快照）`)) {
                  await act(() => corridor.importWorkspace(ws.revision, doc), "已导入工作区");
                }
              } catch (err) {
                setError("文件不是合法 JSON：" + (err as Error).message);
              }
            }} /></label>
          </div>
        </div>
        <div class="cor-card">
          <h3>服务端能力边界</h3>
          <ul class="small">
            <li>生效：规则数值、遗物/事件增删改、角色档位覆盖与移出池（v3f 叠加层）、boss 转可玩整组开关与最早幕、全局排除轮次与幕排名段。</li>
            <li>仅候选（发布被 B-014 阻断）：单个角色「可进开局包」/最早幕、武器/魂珠/遗物/事件策略、幕级首领白名单、单品价格。</li>
            <li>文本 locales_v3.json 编进客户端；服务端只下发 key，改文案需重编客户端才可见。</li>
            <li>试验服没有内容版本锁：应用=替换文件+受控重启；进行中的局按兼容检查拒绝或需确认。</li>
          </ul>
        </div>
      </div>
      <div class="cor-card">
        <h3>校验 <Tag kind={v.blockers ? "bad" : "ok"}>阻断 {v.blockers}</Tag><Tag kind={v.warnings ? "warn" : ""}>警告 {v.warnings}</Tag></h3>
        <FindingList findings={v.findings} onPick={(f) => { location.hash = findingLink(f); }} />
      </div>
    </div>
  );
}
