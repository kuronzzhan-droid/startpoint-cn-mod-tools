import { ComponentChildren } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { RuleResult } from "../../api";
import {
  AnyBossRequest, boss, BossDoc, BossDraftSummary, BossList, BossOptions, BossParameters, BossPreview, BossRequest,
} from "../../bossApi";
import { href } from "../../router";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { ELEMENT_ORDER, fiveTier, preloadState, questElement, questElementValue } from "./bossModel";
import { BossParameterPreview } from "./BossParameterPreview";

/** What the right-hand checks column shows for the current form. */
export interface PreviewState {
  state: "idle" | "running" | "done" | "invalid";
  checks: RuleResult[] | null;
  ok: boolean;
  note?: string;
}

interface Values {
  level: string;
  hp: string;
  atk: string;
  element: string;      // 副本属性（quest 枚举的中文名）
  restricted: string;   // "" = 不限定
  bgm: string;
  scene: string;
}

const MAX = 2147483647;

export function valuesOf(doc: BossDoc): Values {
  const f = doc.quest.fields;
  return {
    level: String(f.level ?? ""), hp: String(f.hp_boss ?? ""), atk: String(f.attack_boss ?? ""),
    element: questElement(f.recommended_element) ?? "", restricted: questElement(f.restriction) ?? "",
    bgm: String(f.bgm ?? ""), scene: doc.field.id ?? "",
  };
}

/** Changed parameters only; returns problems for invalid inputs instead of sending them. */
export function diffParameters(values: Values, current: Values, options: BossOptions | null,
  keys: (keyof Values)[] = ["level", "hp", "atk", "element", "restricted", "bgm", "scene"]):
  { parameters: BossParameters; problems: string[] } {
  const parameters: BossParameters = {};
  const problems: string[] = [];
  const changed = (k: keyof Values) => keys.includes(k) && values[k].trim() !== current[k].trim();
  if (changed("level")) {
    const n = Number(values.level);
    if (!Number.isInteger(n) || n < 1 || n > 999) problems.push("等级要是 1–999 的整数");
    else parameters.level = n;
  }
  for (const [key, name, label] of [["hp", "hpValue", "HP 系数（绝对值）"], ["atk", "attackValue", "攻击系数（绝对值）"]] as const) {
    if (!changed(key)) continue;
    const n = Number(values[key]);
    if (!Number.isFinite(n) || n <= 0 || n > MAX) problems.push(`${label}要是大于 0 的数`);
    else parameters[name] = n;
  }
  if (changed("element") && values.element) parameters.recommendedElement = questElementValue(values.element);
  if (changed("restricted")) parameters.restrictedElement = values.restricted ? questElementValue(values.restricted) : null;
  if (changed("bgm")) {
    if (options && !options.bgm.some((b) => b.id === values.bgm.trim())) problems.push(`BGM 组「${values.bgm}」不在当前视图的 battle_bgm_group 里`);
    else parameters.bgm = values.bgm.trim();
  }
  if (changed("scene")) {
    if (options && !options.scenes.some((s) => s.id === values.scene.trim())) problems.push(`场景「${values.scene}」不在当前视图的 field 表里`);
    else parameters.scene = values.scene.trim();
  }
  return { parameters, problems };
}

/** Debounced live preview through POST …?preview=true; stale answers are dropped. */
export function useLivePreview(target: string | null, request: AnyBossRequest | null, problems: string[],
  onState: (state: PreviewState) => void): { preview: BossPreview | null; previewedFor: string | null; runNow: () => void } {
  const [preview, setPreview] = useState<BossPreview | null>(null);
  const [previewedFor, setPreviewedFor] = useState<string | null>(null);
  const seq = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const body = request ? JSON.stringify(request) : null;
  const run = () => {
    window.clearTimeout(timer.current);
    if (!target || !request || problems.length) return;
    const mine = ++seq.current;
    onState({ state: "running", checks: preview?.checks ?? null, ok: false });
    boss.preview(target, request).then((result) => {
      if (mine !== seq.current) return;
      setPreview(result);
      setPreviewedFor(body);
      onState({ state: "done", checks: result.checks, ok: result.ok });
    });
  };
  useEffect(() => {
    window.clearTimeout(timer.current);
    seq.current++;
    if (problems.length) {
      setPreview(null); setPreviewedFor(null);
      onState({ state: "invalid", checks: null, ok: false, note: problems.join("；") });
      return;
    }
    if (!body) {
      setPreview(null); setPreviewedFor(null);
      onState({ state: "idle", checks: null, ok: false });
      return;
    }
    timer.current = window.setTimeout(run, 600);
    return () => window.clearTimeout(timer.current);
  }, [target, body, problems.join("|")]);
  return { preview, previewedFor, runNow: run };
}

export function ElementSelect({ value, onChange, allowNone, label, id }: {
  value: string; onChange: (v: string) => void; allowNone?: boolean; label: string; id: string;
}) {
  return (
    <select id={id} aria-label={label} value={value} onChange={(e) => onChange((e.target as HTMLSelectElement).value)}>
      {allowNone ? <option value="">不限定</option> : !value ? <option value="">（未设置）</option> : null}
      {ELEMENT_ORDER.map((e) => <option value={e}>{e}</option>)}
    </select>
  );
}

/** 「确认未证明的预载」—— only for 待验证; known-bad (问题) is never waivable. */
export function PreloadConfirm({ checks, acknowledged, onChange }: {
  checks: RuleResult[] | null; acknowledged: boolean; onChange: (v: boolean) => void;
}) {
  const state = preloadState(checks ?? []);
  if (state === "blocked-known") {
    return (
      <Notice kind="error">
        <strong>改属性被阻断（C8016）。</strong>这只 boss 的召唤物在新属性下已知会缺预载，或命中了 C8016 黑名单敌人；
        确认也不能放行。只能保留原属性，或换一个没有这个问题的副本。
      </Notice>
    );
  }
  if (state !== "pending" && !acknowledged) return null;
  return (
    <div class="preload-confirm">
      <p><strong>属性变了，但召唤物的预载垫片没法证明。</strong>进本时若召唤物按新属性取资源而没有预载，会报 C8016 崩溃。
        编辑台只读了客户端表和 DSL，这个风险要真机才能排除。</p>
      <label class="check">
        <input type="checkbox" checked={acknowledged} onChange={(e) => onChange((e.target as HTMLInputElement).checked)} />
        我已了解这个风险，仍写入草稿（只对这次的属性和敌人档位有效；改了属性或档位要重新确认）
      </label>
    </div>
  );
}

const FIELD_KEYS = ["level", "hp", "atk"] as const;

/** 调整参数：单档或五档一起改，实时预检，阻断时不能写入。 */
export function BossParams({ doc, questId, list, drafts, onPreview, onWritten }: {
  doc: BossDoc; questId: string; list: BossList | null; drafts: BossDraftSummary[] | null;
  onPreview: (state: PreviewState) => void; onWritten: (questId: string) => void;
}) {
  const [options, setOptions] = useState<BossOptions | null>(null);
  useEffect(() => { boss.options().then(setOptions, () => setOptions(null)); }, []);
  const current = useMemo(() => valuesOf(doc), [doc]);
  const [values, setValues] = useState<Values>(current);
  const [acknowledged, setAcknowledged] = useState(false);
  const [scope, setScope] = useState<"one" | "five">("one");
  const [tierCurrent, setTierCurrent] = useState<Values[] | null>(null);
  const [tierValues, setTierValues] = useState<Values[] | null>(null);
  const [writing, setWriting] = useState(false);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string; link?: string } | null>(null);
  // The request just written stays disabled until the page has re-read the draft.
  const [writtenFor, setWrittenFor] = useState<string | null>(null);
  useEffect(() => { setValues(current); setAcknowledged(false); setWrittenFor(null); }, [current]);

  const quest = doc.quest;
  const groupItems = useMemo(() => (list?.items ?? []).filter((i) => i.kind === quest.kind && i.group === quest.group), [list, quest]);
  const isFive = quest.kind === "boss_battle" && fiveTier(groupItems);
  const tierSelectors = isFive ? [1, 2, 3, 4, 5].map((n) => `boss_battle:${quest.path.slice(0, -1).join("/")}/${n}`) : [];
  const target = scope === "five" ? tierSelectors[0] : questId;

  useEffect(() => {
    if (scope !== "five" || !isFive) return;
    setTierCurrent(null);
    Promise.all(tierSelectors.map((s) => boss.read(s))).then((reads) => {
      const v = reads.map((r) => valuesOf(r.boss));
      setTierCurrent(v);
      setTierValues(v.map((x) => ({ ...x })));
    }, (e: Error) => setMessage({ kind: "error", text: "读取五档当前值失败：" + e.message }));
  }, [scope, isFive, quest.group]);

  const built = useMemo((): { request: BossRequest | null; problems: string[] } => {
    if (scope === "five") {
      if (!tierCurrent || !tierValues) return { request: null, problems: [] };
      const common = diffParameters(values, current, options, ["element", "restricted", "bgm", "scene"]);
      const tiers = tierValues.map((v, i) => diffParameters(v, tierCurrent[i], options, [...FIELD_KEYS]));
      const problems = [...common.problems, ...tiers.flatMap((t, i) => t.problems.map((p) => `第 ${i + 1} 档：${p}`))];
      const empty = !Object.keys(common.parameters).length && tiers.every((t) => !Object.keys(t.parameters).length);
      if (empty) return { request: null, problems };
      return {
        problems, request: {
          operation: "edit", tiers: tiers.map((t) => t.parameters),
          ...(Object.keys(common.parameters).length ? { parameters: common.parameters } : {}),
          ...(acknowledged ? { acknowledgePreload: true } : {}),
        },
      };
    }
    const single = diffParameters(values, current, options);
    if (!Object.keys(single.parameters).length) return { request: null, problems: single.problems };
    return {
      problems: single.problems,
      request: { operation: "edit", parameters: single.parameters, ...(acknowledged ? { acknowledgePreload: true } : {}) },
    };
  }, [scope, values, current, tierValues, tierCurrent, options, acknowledged]);

  const live = useLivePreview(target, built.request, built.problems, onPreview);
  const fresh = live.preview && built.request && live.previewedFor === JSON.stringify(built.request);
  const canWrite = !!fresh && live.preview!.ok && !writing && writtenFor !== JSON.stringify(built.request);

  // Changing the element (or the tier set) drops an earlier confirmation.
  useEffect(() => { setAcknowledged(false); }, [values.element, scope]);

  const write = async () => {
    if (!canWrite || !built.request) return;
    setWriting(true);
    setMessage(null);
    try {
      const result = await boss.apply(target, built.request);
      setWrittenFor(JSON.stringify(built.request));
      setMessage({
        kind: "info", text: `已写入草稿（${result.status.label}）。到「本次修改」保存后才能生成。`,
        link: href({ work: "content", shop: "boss", quest: result.questId, tab: "changes" }),
      });
      onWritten(result.questId);
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setWriting(false);
    }
  };

  if (doc.routing.kind === "BothBoss") {
    return (
      <Notice kind="warn">
        <strong>这是五重决战的入口（BothBoss 路由），只读。</strong>入口自己不是一场战斗：它只负责按两轮选择把玩家送进隐藏关。
        改入口的等级、倍率或属性不会影响实际战斗，所以这里不开放修改，也不能作「新建共同决战」的模板来源。
        要改难度，请打开左侧列出的隐藏关。
      </Notice>
    );
  }

  const set = (key: keyof Values) => (value: string) => setValues({ ...values, [key]: value });
  const otherDrafts = (drafts ?? []).filter((d) => tierSelectors.includes(d.characterId) && d.characterId !== target);
  const isFiveStage = quest.kind === "boss_battle" && quest.path[1] === "99";

  return (
    <form class="boss-params" onSubmit={(e) => { e.preventDefault(); live.runNow(); }}
      onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); write(); } }}>
      <p class="hint">
        改动先在右侧实时预检（规则阻断时不能写入）；写入只进本地草稿，保存后在「本次修改」里生成测试补丁。
        <InfoTip text="技术细节：POST /api/boss/drafts/<quest>?preview=true 只计算候选与五态检查，不写草稿；写入后 params.requests 记录操作序列，编译时按当前视图重放。" />
      </p>
      {isFiveStage ? <Notice>这是五重决战的隐藏关，通常由五重 v2 构建器按 spec 生成。在这里改只写本地草稿，不会回写构建器的 spec；下次用构建器重建会覆盖。</Notice> : null}
      {quest.kind === "practice" ? <p class="small muted">练习木人没有服务端归属：改副本属性只改客户端表。</p> : null}
      {isFive ? (
        <div class="segmented scope" role="group" aria-label="修改范围">
          <button type="button" class={scope === "one" ? "on" : ""} aria-pressed={scope === "one"} onClick={() => setScope("one")}>
            只改这一档（第 {quest.path[quest.path.length - 1]} 档）
          </button>
          <button type="button" class={scope === "five" ? "on" : ""} aria-pressed={scope === "five"} onClick={() => setScope("five")}>五档一起改</button>
        </div>
      ) : null}
      {scope === "five" && otherDrafts.length ? (
        <Notice kind="warn">第 {otherDrafts.map((d) => d.characterId.split("/").pop()).join("、")} 档另有独立草稿。五档修改挂在第 1 档的草稿上；两份草稿会各自生成交付，可能改到同一行。</Notice>
      ) : null}

      <fieldset class="param-block">
        <legend>{scope === "five" ? "五档共用" : "数值"}</legend>
        <div class="param-fields">
          {scope === "one" ? (
            <>
              <Field id="bp-level" label="等级" note={`当前 Lv${current.level}`} changed={values.level !== current.level}>
                <input id="bp-level" type="number" min={1} max={999} step={1} value={values.level} onInput={(e) => set("level")((e.target as HTMLInputElement).value)} />
              </Field>
              <Field id="bp-hp" label="HP 系数（绝对设为）" note={multiNote(doc, "hp")} changed={values.hp !== current.hp}>
                <input id="bp-hp" type="number" min={0} step={0.1} value={values.hp} onInput={(e) => set("hp")((e.target as HTMLInputElement).value)} />
              </Field>
              <Field id="bp-atk" label="攻击系数（绝对设为）" note={multiNote(doc, "attack")} changed={values.atk !== current.atk}>
                <input id="bp-atk" type="number" min={0} step={0.1} value={values.atk} onInput={(e) => set("atk")((e.target as HTMLInputElement).value)} />
              </Field>
            </>
          ) : null}
          <Field id="bp-element" label="副本属性" note={`当前 ${current.element || "—"}；敌人属性为「继承」时 boss 跟着变`} changed={values.element !== current.element}>
            <ElementSelect id="bp-element" label="副本属性" value={values.element} onChange={set("element")} />
          </Field>
          <Field id="bp-restricted" label="出战限定" note={`当前 ${current.restricted || "不限定"}`} changed={values.restricted !== current.restricted}>
            <ElementSelect id="bp-restricted" label="出战限定" allowNone value={values.restricted} onChange={set("restricted")} />
          </Field>
          <Field id="bp-bgm" label="BGM 组" note="battle_bgm_group 里已有的组" changed={values.bgm !== current.bgm}>
            <input id="bp-bgm" class="mono" list="bp-bgm-list" value={values.bgm} onInput={(e) => set("bgm")((e.target as HTMLInputElement).value)} />
          </Field>
          <Field id="bp-scene" label="场景" note="field 表里已有的场景；改了会给这一关派生独立 field_data" changed={values.scene !== current.scene}>
            <input id="bp-scene" class="mono" list="bp-scene-list" value={values.scene} onInput={(e) => set("scene")((e.target as HTMLInputElement).value)} />
          </Field>
        </div>
        <datalist id="bp-bgm-list">{options?.bgm.map((b) => <option value={b.id}>{b.tracks.join(" · ")}</option>)}</datalist>
        <datalist id="bp-scene-list">{options?.scenes.map((s) => <option value={s.id}>{s.background}</option>)}</datalist>
      </fieldset>

      {scope === "five" ? (
        <fieldset class="param-block">
          <legend>每档数值</legend>
          {!tierValues || !tierCurrent ? <p class="small muted">正在读取五档当前值……</p> : (
            <div class="table-scroll">
              <table class="boss-table tier-edit">
                <thead><tr><th>档</th><th>等级</th><th>HP 系数（绝对设为）</th><th>攻击系数（绝对设为）</th></tr></thead>
                <tbody>
                  {tierValues.map((v, i) => (
                    <tr>
                      <th scope="row">第 {i + 1} 档</th>
                      {FIELD_KEYS.map((k) => (
                        <td>
                          <input type="number" aria-label={`第 ${i + 1} 档 ${k === "level" ? "等级" : k === "hp" ? "HP 系数（绝对设为）" : "攻击系数（绝对设为）"}`}
                            class={v[k] !== tierCurrent[i][k] ? "changed" : ""} step={k === "level" ? 1 : 0.1} min={k === "level" ? 1 : 0}
                            value={v[k]} onInput={(e) => setTierValues(tierValues.map((t, j) => j === i ? { ...t, [k]: (e.target as HTMLInputElement).value } : t))} />
                          <span class="small muted"> 原 {tierCurrent[i][k]}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p class="small muted">五档草稿挂在第 1 档（{tierSelectors[0]}）；每档只发送改过的值。</p>
            </div>
          )}
        </fieldset>
      ) : null}

      {built.problems.length ? <ul class="inline-problems">{built.problems.map((p) => <li>{p}</li>)}</ul> : null}
      {fresh ? <BossParameterPreview preview={live.preview} /> : null}
      <PreloadConfirm checks={live.preview?.checks ?? null} acknowledged={acknowledged} onChange={setAcknowledged} />

      <div class="save-row">
        <button type="submit" disabled={!built.request || built.problems.length > 0}>立即检查</button>
        <button type="button" class="primary" disabled={!canWrite} onClick={write}
          title={!built.request ? "还没有改动" : !fresh ? "等预检跑完" : !live.preview?.ok ? "有阻断项，不能写入" : "Ctrl+Enter"}>
          {writing ? "写入中……" : "写入草稿"}
        </button>
        <button type="button" class="ghost" disabled={!built.request} onClick={() => {
          setValues(current); setTierValues(tierCurrent?.map((t) => ({ ...t })) ?? null); setAcknowledged(false);
        }}>放弃改动</button>
        <span class="small muted">
          {!built.request ? "还没有改动" : writtenFor === JSON.stringify(built.request) ? (target === questId ? "已写入，正在重新读取草稿……" : "已写入第 1 档的草稿")
            : !fresh ? "预检中……" : live.preview?.ok ? "预检通过，可以写入" : "有阻断项"}
        </span>
      </div>
      {message ? (
        <Notice kind={message.kind}>{message.text}{message.link ? <> <a href={message.link}>打开「本次修改」→</a></> : null}</Notice>
      ) : null}
      {fresh && live.preview?.changes?.length ? (
        <details class="tech">
          <summary>技术细节：这次会改 {live.preview.changes.length} 个表叶{live.preview.serverTargets?.length ? `、${live.preview.serverTargets.length} 份服务端文件` : ""}</summary>
          <ul class="small mono">
            {live.preview.changes.map((c) => <li>{c.table} · {c.path.join("/")}{c.old === null ? "（新增）" : ""}</li>)}
            {live.preview.serverTargets?.map((t) => <li>server · {t}</li>)}
          </ul>
        </details>
      ) : null}
    </form>
  );
}

function multiNote(doc: BossDoc, kind: "hp" | "attack"): string {
  const f = doc.quest.fields;
  const values = [f[`${kind}_zako`], f[`${kind}_funnel`], f[`${kind}_boss`]];
  if (values.every((v) => v === values[0])) return `当前系数 ${values[0]}；杂兵/浮游/boss 三项直接设为输入值`;
  return `当前 杂兵 ${values[0]} / 浮游 ${values[1]} / boss ${values[2]}；三项直接设为输入值`;
}

function Field({ id, label, note, changed, children }: {
  id: string; label: string; note?: string; changed?: boolean; children: ComponentChildren;
}) {
  return (
    <div class={"param-field" + (changed ? " changed" : "")}>
      <label for={id}>{label}{changed ? <span class="tag pend">已改</span> : null}</label>
      {children}
      {note ? <span class="small muted">{note}</span> : null}
    </div>
  );
}
