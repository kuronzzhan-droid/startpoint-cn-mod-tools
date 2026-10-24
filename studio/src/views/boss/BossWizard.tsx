import { useEffect, useMemo, useState } from "preact/hooks";
import { boss, BossOptions, BossRead, BossRequest, BossTemplates, BossTemplateSource } from "../../bossApi";
import { href } from "../../router";
import { ElementBadge, Notice } from "../common";
import { InfoTip } from "../Delivery";
import { ChecksPanel } from "./BossChecks";
import { ElementSelect, PreloadConfirm, PreviewState, useLivePreview } from "./BossParams";
import { Src } from "./BossRead";
import { MODE_LABEL, MODE_ORDER, questElement, questElementValue, shortName } from "./bossModel";
import { BossParameterPreview } from "./BossParameterPreview";

const DEFAULTS = { level: "100", hp: "1.5", atk: "1.3" };
// 与后端 template_rows 同一套：换行类字符、单双引号、弯引号和 :: 都拒绝。
const NAME_BAD = new RegExp("[\\r\\n\\v\\f\\x1c\\x1d\\x1e\\x85\\u2028\\u2029\"'\\u201c\\u201d\\u2018\\u2019]|::");

/** 新建共同决战：选模板来源 → 名称与难度 → 预检（含分配的 ID）→ 写入草稿。 */
export function BossWizard({ source }: { source?: string }) {
  const [templates, setTemplates] = useState<BossTemplates | null>(null);
  const [options, setOptions] = useState<BossOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(source ?? null);
  const [filter, setFilter] = useState("");
  const [detail, setDetail] = useState<BossRead | null>(null);
  const [name, setName] = useState("");
  const [level, setLevel] = useState(DEFAULTS.level);
  const [hp, setHp] = useState(DEFAULTS.hp);
  const [atk, setAtk] = useState(DEFAULTS.atk);
  const [element, setElement] = useState("");
  const [restricted, setRestricted] = useState("");
  const [bgm, setBgm] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [preview, setPreview] = useState<PreviewState>({ state: "idle", checks: null, ok: false });
  const [writing, setWriting] = useState(false);
  const [writeError, setWriteError] = useState<string | null>(null);

  useEffect(() => {
    boss.templates().then((t) => { setTemplates(t); if (!picked) setPicked(t.default); }, (e: Error) => setError(e.message));
    boss.options().then(setOptions, () => setOptions(null));
  }, []);
  const chosen = templates?.sources.find((s) => s.selector === picked) ?? null;
  // Keep the picked source visible in the long list (deep link from a detail page).
  useEffect(() => {
    const box = document.querySelector<HTMLElement>(".wizard-sources");
    const item = box?.querySelector<HTMLElement>(".source-option.on");
    if (box && item) box.scrollTop += item.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3;
  }, [templates, picked]);
  useEffect(() => {
    setDetail(null);
    if (!chosen) return;
    const el = questElement(chosen.recommendedElement) ?? "";
    setElement(el);
    setRestricted(el);
    setBgm("");
    setAcknowledged(false);
    boss.read(chosen.selector).then(setDetail, () => setDetail(null));
  }, [chosen?.selector]);
  useEffect(() => { setAcknowledged(false); }, [element]);

  const problems: string[] = [];
  if (name && (name.length > 80 || NAME_BAD.test(name))) problems.push("名称最多 80 字，不能有换行、引号或 ::");
  const levelNumber = Number(level);
  if (!Number.isInteger(levelNumber) || levelNumber < 1 || levelNumber > 999) problems.push("等级要是 1–999 的整数");
  for (const [value, label] of [[hp, "HP 系数（绝对值）"], [atk, "攻击系数（绝对值）"]] as const) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) problems.push(`${label}要是大于 0 的数`);
  }
  if (bgm && options && !options.bgm.some((b) => b.id === bgm)) problems.push(`BGM 组「${bgm}」不在当前视图里`);
  if (picked && templates && !chosen) problems.push(`「${picked}」不在模板白名单里`);

  const request = useMemo((): BossRequest | null => {
    if (!chosen) return null;
    return {
      operation: "create_shared", sourceQuest: chosen.selector,
      ...(name.trim() ? { name: name.trim() } : {}),
      parameters: {
        level: Number(level), hpValue: Number(hp), attackValue: Number(atk),
        ...(element ? { recommendedElement: questElementValue(element) } : {}),
        restrictedElement: restricted ? questElementValue(restricted) : null,
        ...(bgm ? { bgm } : {}),
      },
      ...(acknowledged ? { acknowledgePreload: true } : {}),
    };
  }, [chosen?.selector, name, level, hp, atk, element, restricted, bgm, acknowledged]);
  const live = useLivePreview(chosen ? "new" : null, request, problems, setPreview);
  const fresh = live.preview && request && live.previewedFor === JSON.stringify(request);
  const canWrite = !!fresh && live.preview!.ok && !writing;
  const allocation = fresh ? live.preview?.allocation : null;

  const write = async () => {
    if (!canWrite || !request) return;
    setWriting(true);
    setWriteError(null);
    try {
      const result = await boss.apply("new", request);
      location.hash = href({ work: "content", shop: "boss", quest: result.questId, tab: "changes" });
    } catch (e) {
      setWriteError((e as Error).message);
    } finally {
      setWriting(false);
    }
  };

  const groups = useMemo(() => {
    const terms = filter.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const shown = (templates?.sources ?? []).filter((s) =>
      terms.every((t) => `${s.name} ${s.selector} ${s.id}`.toLowerCase().includes(t)));
    return MODE_ORDER.map((m) => ({ mode: m, items: shown.filter((s) => s.mode === m) })).filter((g) => g.items.length);
  }, [templates, filter]);

  const step = !chosen ? 1 : !fresh ? 3 : live.preview?.ok ? 4 : 3;

  return (
    <section class="page boss-wizard">
      <a class="back" href={href({ work: "content", shop: "boss" })}>← 全部副本</a>
      <div class="page-head">
        <div>
          <h1>新建共同决战</h1>
          <p class="muted">从已有遭遇复制场景、敌人和 BGM，套用官方暗凛（hard_multi 1006）的共同决战骨架。自动分配活动 / quest / 目录节点 / zone / 奖励组，开放时间固定 2000-01-01、不结束。
            <InfoTip text={templates?.note ?? ""} /></p>
        </div>
      </div>
      <ol class="wizard-steps" aria-label="步骤">
        {["选模板来源", "名称与难度", "预检与分配的 ID", "写入草稿"].map((label, i) => (
          <li class={i + 1 < step ? "done" : i + 1 === step ? "on" : ""}>{i + 1}. {label}</li>
        ))}
      </ol>
      {error ? <Notice kind="error">读取模板白名单失败：{error}</Notice> : null}
      <div class="boss-layout">
        <nav class="boss-side wizard-sources" aria-label="模板来源">
          <h4>模板来源 <span class="count">{templates?.sources.length ?? 0}</span></h4>
          <input class="search small-search" type="search" placeholder="筛选 boss 名 / ID" value={filter}
            onInput={(e) => setFilter((e.target as HTMLInputElement).value)} />
          {!templates ? <p class="small muted">正在读取……</p> : null}
          {groups.map((g) => (
            <div class="source-group">
              <h5>{MODE_LABEL[g.mode]}</h5>
              <ul role="listbox" aria-label={MODE_LABEL[g.mode]}>
                {g.items.map((s) => <SourceOption s={s} on={s.selector === picked} onPick={() => setPicked(s.selector)} />)}
              </ul>
            </div>
          ))}
          {templates?.excluded.length ? (
            <details class="tech">
              <summary>为什么有些副本不在这里</summary>
              <ul class="small">{templates.excluded.map((x) => <li>{x.reason}（{x.count} 个）</li>)}</ul>
            </details>
          ) : null}
        </nav>

        <form class="boss-main boss-params" onSubmit={(e) => { e.preventDefault(); live.runNow(); }}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); write(); } }}>
          {chosen ? (
            <section class="boss-block">
              <header>
                <h3>来源：{shortName(chosen.name)}</h3>
                <span class="spacer" /><Src c={chosen.source} />
              </header>
              <p class="small">
                <span class="mono">{chosen.selector}</span> · {MODE_LABEL[chosen.mode]} · 原 Lv{chosen.level}
                {questElement(chosen.recommendedElement) ? <> · <ElementBadge element={questElement(chosen.recommendedElement)!} /> {questElement(chosen.recommendedElement)}</> : null}
              </p>
              {detail ? (
                <p class="small muted">
                  复制：场景 <span class="mono">{detail.boss.field.id}</span> · zone <span class="mono">{detail.boss.zone.id}</span>
                  {" "}· {detail.boss.terrain.wave_count ?? "?"} 波 · 敌人 {[...new Set(detail.boss.enemies.map((e) => e.code))].join("、") || "—"}
                  {" "}· BGM <span class="mono">{detail.boss.quest.fields.bgm}</span>
                </p>
              ) : <p class="small muted">正在读取来源遭遇……</p>}
            </section>
          ) : <Notice>先在左侧选一个模板来源。</Notice>}

          <fieldset class="param-block">
            <legend>名称与难度</legend>
            <div class="param-fields">
              <div class="param-field wide">
                <label for="wz-name">名称</label>
                <input id="wz-name" value={name} maxLength={80} placeholder={chosen ? `留空沿用来源名「${shortName(chosen.name)}」` : ""}
                  onInput={(e) => setName((e.target as HTMLInputElement).value)} />
                <span class="small muted">活动页显示为「共同决战【名称】」；不能有换行、引号或 ::</span>
              </div>
              <div class="param-field">
                <label for="wz-level">等级</label>
                <input id="wz-level" type="number" min={1} max={999} value={level} onInput={(e) => setLevel((e.target as HTMLInputElement).value)} />
                <span class="small muted">模板默认 100</span>
              </div>
              <div class="param-field">
                <label for="wz-hp">HP 系数（绝对设为）</label>
                <input id="wz-hp" type="number" min={0} step={0.1} value={hp} onInput={(e) => setHp((e.target as HTMLInputElement).value)} />
                <span class="small muted">默认设为 1.5（杂兵/浮游/boss 一起）</span>
              </div>
              <div class="param-field">
                <label for="wz-atk">攻击系数（绝对设为）</label>
                <input id="wz-atk" type="number" min={0} step={0.1} value={atk} onInput={(e) => setAtk((e.target as HTMLInputElement).value)} />
                <span class="small muted">默认设为 1.3</span>
              </div>
              <div class="param-field">
                <label for="wz-restricted">出战限定</label>
                <ElementSelect id="wz-restricted" label="出战限定" allowNone value={restricted} onChange={setRestricted} />
                <span class="small muted">默认与来源属性相同</span>
              </div>
              <div class="param-field">
                <label for="wz-element">副本属性</label>
                <ElementSelect id="wz-element" label="副本属性" value={element} onChange={setElement} />
                <span class="small muted">改了会检查召唤物预载（C8016）</span>
              </div>
              <div class="param-field">
                <label for="wz-bgm">BGM 组</label>
                <input id="wz-bgm" class="mono" list="wz-bgm-list" value={bgm} placeholder="留空沿用来源"
                  onInput={(e) => setBgm((e.target as HTMLInputElement).value)} />
                <datalist id="wz-bgm-list">{options?.bgm.map((b) => <option value={b.id}>{b.tracks.join(" · ")}</option>)}</datalist>
              </div>
            </div>
          </fieldset>
          {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
          {fresh ? <BossParameterPreview preview={live.preview} /> : null}
          <PreloadConfirm checks={live.preview?.checks ?? null} acknowledged={acknowledged} onChange={setAcknowledged} />

          <section class="boss-block">
            <header><h3>会分配的 ID</h3><InfoTip text="预览不预留 ID；写入草稿时重新分配，以写入结果为准。自动跳过客户端表、服务端四份奖励 JSON、hard_multi_event_quest.json 和其它未交付草稿已占用的号。" /></header>
            {allocation ? (
              <dl class="kv alloc">
                <dt>活动 event</dt><dd class="mono">{allocation.event}</dd>
                <dt>quest</dt><dd class="mono">{allocation.quest}</dd>
                <dt>目录节点</dt><dd class="mono">event_folder_events/2/{allocation.node}</dd>
                <dt>zone / field_data</dt><dd class="mono">{allocation.zone}</dd>
                <dt>奖励组</dt><dd class="mono">{allocation.reward}</dd>
              </dl>
            ) : <p class="small muted">{live.preview && !live.preview.ok ? "预检被阻断，没有分配结果。" : "预检后显示。"}</p>}
          </section>

          <div class="save-row">
            <button type="submit" disabled={!request || problems.length > 0}>立即检查</button>
            <button type="button" class="primary" disabled={!canWrite} onClick={write} title="Ctrl+Enter">
              {writing ? "写入中……" : "写入草稿"}
            </button>
            <span class="small muted">{!request ? "先选模板来源" : !fresh ? "预检中……" : live.preview?.ok ? "预检通过，可以写入" : "有阻断项，不能写入"}</span>
          </div>
          {writeError ? <Notice kind="error">写入失败：{writeError}</Notice> : null}
          <p class="small muted">写入后打开这份新草稿的「本次修改」：保存 → 生成本地交付。编辑台不分配正式版本号、不上测试服。</p>
        </form>

        <ChecksPanel title="预检" checks={preview.checks}
          state={preview.state === "running" ? "running" : undefined}
          note={preview.state === "invalid" ? "输入有问题，先改正：" + (preview.note ?? "") : "选好来源后自动预检。"} />
      </div>
    </section>
  );
}

function SourceOption({ s, on, onPick }: { s: BossTemplateSource; on: boolean; onPick: () => void }) {
  const el = questElement(s.recommendedElement);
  return (
    <li role="option" aria-selected={on}>
      <button type="button" class={"source-option" + (on ? " on" : "")} onClick={onPick}
        title={`${s.name} · ${s.selector}${s.default ? "（默认：官方暗凛）" : ""}`}>
        {el ? <ElementBadge element={el} /> : null}
        <span class="side-label">{shortName(s.name)}{s.default ? <span class="tag">默认</span> : null}</span>
        <span class="small muted">{s.kind === "boss_battle" ? `难度 ${s.selector.split("/").pop()}` : "共同"} · Lv{s.level}</span>
      </button>
    </li>
  );
}
