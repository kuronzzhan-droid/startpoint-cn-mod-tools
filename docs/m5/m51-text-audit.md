# M5.1 文案只读审计：1.4.227–1.4.237

本次覆盖 manifest 中 1.4.227 至当前可读链尾 1.4.237 的 11 个版本，逐版本回读全部覆盖文案与技能档位。仅输出报告，未修改任何玩家原文、补丁、服务端镜像或 manifest。

D3/D4 新增检查在 1.4.227–1.4.229 各命中 17 项能力队长前置问题；这些问题从 1.4.230 起不再命中。1.4.230–1.4.237 的 D3/D4 确定性命中均为 0。其他既有文案规则仍有命中，不能据此宣称整个文案规范已通过。

## 输入与判定范围

- 只读 manifest 沿用 `work/m5/evidence/view-config-236.json` 的 `manifest` 配置；本次 `cdn_version=1.4.237`。仅在工作区中的审计配置补入 237 的 `shipped` ZIP 目录并跟随当前链尾。确切输入路径保存在忽略的 `work/m51/text/view-config.json`，输入摘要见机器报告。
- 存储基线为 store131，逐视图依赖链、ZIP SHA-256、已读取的 store 成员 SHA-256、文本表 SHA-256 均保存在 JSON。每个视图调用 verify，服务端输入也前后核验，manifest 原字节前后相等。
- 每版全表扫描包括继承的官方/旧文本、孤立覆盖键与所有实际技能档位；未把历史问题算作该版本新引入。另从 1.4.226 对比起累计追踪 227 起修改的覆盖串和技能字段，报告此集合中的当前问题数。跨档规则也跟踪所属技能位置，因此“变动位置数”不是角色数。
- 只有 1.4.232 和 1.4.237 提供了该版本 `shipped/server/character_text.json` 与 `character_text_rank_p5b.json` 两份完整本地镜像；其余版本服务端检查为未执行。1.4.227 的 patch.json 不是完整镜像，未冒充历史全表。没有服务器或设备验证。
- [机器可读摘要与去重明细](m51-text-audit.json) 保存全部 11 版汇总和 56 组不同全文/槽位证据的重点问题。每版完整逐项结果在 `work/m51/text/audit-1.4.N.json`，摘要记录其 SHA-256；这些本地执行产物不纳入版本控制。重点明细覆盖 227 起变动文本的所有问题，以及全表 D3/D4 问题。

## 每版结果

| 版本 | 扫描条目（含当版可用镜像） | 客户端问题 | 227起变动客户端文本问题 | D3/D4问题 | 含镜像总问题 |
|---|---:|---:|---:|---:|---:|
| 1.4.227 | 2914 | 76 | 47 | 17 | 76 |
| 1.4.228 | 2914 | 76 | 47 | 17 | 76 |
| 1.4.229 | 2914 | 76 | 47 | 17 | 76 |
| 1.4.230 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.231 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.232 | 7144 | 59 | 30 | 0 | 596 |
| 1.4.233 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.234 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.235 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.236 | 2914 | 59 | 30 | 0 | 59 |
| 1.4.237 | 7144 | 61 | 32 | 0 | 598 |

232/237 的合计增加主要来自完整镜像的旧档位写法差异，因此不应与没有镜像的版本直接比较合计。最新 237 客户端比 236 多 2 个规则命中，来自同一条 159985 能力3覆盖串：强化『伯爵之礼』的定性说明含持续10秒与两个-10%数值，分别命中既有 skill-enhance 和 skill-form。这里是一个文本位置的两个规则结果，未改原文。

237 的有效服务端对照另有 7 项差异：119998、119999 的 c5/c7/c9 在提供的镜像中缺失；169978 的 c9 被 p5b 整行覆盖后仍含4轮、5倍、合计20倍与20%旧描述，客户端已经是定性描述。这些是显式本地镜像与客户端视图的差异，不是线上状态判断。

## 139985 精确覆盖键

11 个版本都查到 `character[139985].c17 → leader_ability[139985]`，该槽每行 c0=`lady_android_halloween`，精确覆盖键为 `desc_override_lady_android_halloween`；不依赖 `_leader`、`_ls` 或 `_1`–`_6` 后缀。逐版本证据位于 JSON 的 `versions[].character_139985`。

这些版本的实际原文一致，没有「自身为队长时」：

```text
雷属性共鸣时，雷属性角色攻击力+100%、技能伤害+100%
雷属性共鸣时，Fever模式中，雷属性角色技能充能速度+30%
```

反证在此无后缀精确键注入「自身为队长时」后，wf text 文档检查、编辑门禁和草稿实际字节回读都阻断。该测试证明不会漏掉此键；不能把注入测试当成当前原文存在违规。

## 作者规则与边界

规则目录 `wf/rules/text_standard.json` 升级为 1.2.0，共60条：49条部分检查，11条保留人工语义核对。作者依据按任务指定读取：

- 作者经验记录 wf-leader-override-text-rules：固定文案禁止「自身为队长时」和 `X%（觉醒后 Y%）`；低/满级列不是觉醒前后；整槽主位限制每行使用精确 icon，禁字面Ⓜ和多条效果压行。
- `.../wf-panel-text-standard-1017.md`：覆盖键是 `desc_override_<c0>`，并规定面板术语、乘区和技能说明边界。
- `.../wf-skill-enhance-text-rule.md`：强化说明在队长/能力中定性表达，不向技能本体重复写入；本任务沿用已有对应检查。

三份依据的原始 SHA-256 位于规则目录 `author_rules_sources`。主位图标常量与本仓 `wf_featured_main_ability.MAIN` 逐字比对：前1空格、`<icon id='main'>`、后2空格。

- 整槽每行 c1=false 时，每个非空说明行必须带图标；混合主位/非主位记录的槽保留语义核对，不能把非主位效果强行标为主位。基诺维 ability1 正是混合槽，已作不误报反证。
- 压行检查只判定「／」两边都含明确效果词或增减数值的形式；雷／风属性、基诺维／杰拉德／凯尔姓名列表和六属性结算枚举不构成两条效果压行；action_skill 的官方分隔符仍允许。
- 无槽位数据的旧读取快照仍兼容，但依赖槽位身份的语义判断不能声称已验证。新快照带可审计的 override_slots。

## 重点问题逐项索引

下面56组按全文与槽位证据去重。相同位置同规则在不同版本文案变化时单列。JSON 保留完整原文、命中片段、精确槽位、角色ID和所有出现版本；本索引没有只抽样展示。

| # | 位置 | 规则（text.standard.省略） | 出现版本 | 227起变动文本 |
|---:|---|---|---|---|
| 1 | `desc_override.desc_override_ginovi` | special-pf | 1.4.227–1.4.229 | 是 |
| 2 | `desc_override.desc_override_ginovi_1` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 3 | `desc_override.desc_override_ginovi_3` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 4 | `desc_override.desc_override_fox_oracle_autumn_6` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 5 | `desc_override.desc_override_white_tiger_summer_6` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 6 | `desc_override.desc_override_wind_spgirl_campus` | special-pf | 1.4.227–1.4.229 | 是 |
| 7 | `desc_override.desc_override_wind_spgirl_campus_1` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 8 | `desc_override.desc_override_cube_boss_playable` | special-pf | 1.4.227–1.4.237 | 是 |
| 9 | `desc_override.desc_override_haniwa_green_playable` | special-pf | 1.4.227–1.4.237 | 是 |
| 10 | `desc_override.desc_override_rec_android_seaside_6` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 11 | `desc_override.desc_override_guildknight_leader_tavern_3` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 12 | `desc_override.desc_override_guildknight_leader_tavern_1` | term-pf | 1.4.227–1.4.237 | 是 |
| 13 | `desc_override.desc_override_guildknight_leader_tavern_2` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 14 | `desc_override.desc_override_psychic_teleport_moon_5` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 15 | `desc_override.desc_override_lion_swordman_moon` | special-pf | 1.4.227–1.4.229 | 是 |
| 16 | `desc_override.desc_override_lion_swordman_moon_1` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 17 | `desc_override.desc_override_lion_swordman_moon_5` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 18 | `desc_override.desc_override_kyle_moon` | special-pf | 1.4.227–1.4.229 | 是 |
| 19 | `desc_override.desc_override_kyle_moon_3` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 20 | `desc_override.desc_override_kyle_moon_5` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 21 | `desc_override.desc_override_black_wolf_knight_moon_6` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 22 | `desc_override.desc_override_combat_animal_moon_5` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 23 | `desc_override.desc_override_cnmod_inaho_midautumn` | special-pf | 1.4.227–1.4.237 | 是 |
| 24 | `desc_override.desc_override_cnmod_inaho_midautumn_4` | skill-enhance | 1.4.227–1.4.237 | 是 |
| 25 | `desc_override.desc_override_cnmod_inaho_midautumn_4` | skill-form | 1.4.227–1.4.237 | 是 |
| 26 | `desc_override.desc_override_mosiyike` | special-pf | 1.4.227–1.4.237 | 是 |
| 27 | `desc_override.desc_override_seris_dragon_king_1` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 28 | `desc_override.desc_override_seris_dragon_king_2` | leader-relocation | 1.4.227–1.4.229 | 是 |
| 29 | `action_skill.hoshikawa_ririi` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 30 | `action_skill.golden_dragon_jr` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 31 | `action_skill.darkness_dragon` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 32 | `action_skill.resistance_princess_smr21` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 33 | `action_skill.desert_priest` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 34 | `action_skill.lightbullet_wiz_vt21` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 35 | `action_skill.wind_oracle_1anv` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 36 | `action_skill.resistance_princess` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 37 | `action_skill.xiaketi` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 38 | `action_skill.cnmod_epuration_empress` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 39 | `action_skill.one_eyed_rabbit_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 40 | `action_skill.security_robot_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 41 | `action_skill.cobra_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 42 | `action_skill.epuration_infantry_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 43 | `action_skill.epuration_monk_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 44 | `action_skill.epuration_variant_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 45 | `action_skill.epuration_empress_playable` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 46 | `action_skill.spheal_mascot` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 47 | `action_skill.liangyue_onmyoji` | skill-tier-wording | 1.4.227–1.4.237 | 是 |
| 48 | `desc_override.desc_override_ginovi` | special-pf | 1.4.230–1.4.235 | 是 |
| 49 | `desc_override.desc_override_wind_spgirl_campus` | special-pf | 1.4.230–1.4.237 | 是 |
| 50 | `desc_override.desc_override_lion_swordman_moon` | special-pf | 1.4.230–1.4.231 | 是 |
| 51 | `desc_override.desc_override_kyle_moon` | special-pf | 1.4.230–1.4.235 | 是 |
| 52 | `desc_override.desc_override_lion_swordman_moon` | special-pf | 1.4.232–1.4.237 | 是 |
| 53 | `desc_override.desc_override_ginovi` | special-pf | 1.4.236–1.4.237 | 是 |
| 54 | `desc_override.desc_override_kyle_moon` | special-pf | 1.4.236–1.4.237 | 是 |
| 55 | `desc_override.desc_override_crystal_swordman_halloween_3` | skill-enhance | 1.4.237 | 是 |
| 56 | `desc_override.desc_override_crystal_swordman_halloween_3` | skill-form | 1.4.237 | 是 |

## 本地验证

- 文案、标准、全表审计、双镜像、有效文本、技能档位与编辑台文本定向组：183 passed。
- 新增 D3/D4 反证及 draft 编译/交付桥接定向组：33 passed，包括已保存检查全绿但实际编译字节含禁语时仍阻断。两组存在重复用例，不将数量相加冒充独立测试数。
- 反证涵盖无常用后缀的139985队长键、无数字后缀的能力键、误导性后缀、所有孤立覆盖键、觉醒双值、主位前后空格、漏第二行图标、字面Ⓜ、效果压行、混合主位与属性枚举允许例，以及只改c1触发新增问题。
- 每个审计视图与已提供镜像前后字节核验通过。只读报告有真实文案问题，不自动改文案。全量 pytest、路径扫描和223/221逐字节结果由 M5-REPORT.md 的 M5.1总报告记录。

复现脚本和准确视图配置保留在本 worktree 的 `work/m51/text/audit_versions.py`、`work/m51/text/view-config.json`。所有输出均在本 worktree；其他路径只读，无 push、服务器操作或设备操作。
