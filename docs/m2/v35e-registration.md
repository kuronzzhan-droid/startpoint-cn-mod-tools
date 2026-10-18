# M2.2：v35e/run5 能力登记依据

本次只登记最终 `v35e/run5`，不以 run3/run4 的整包作为接收方客户端。累计注册源是 `v35/run5/registry-draft.json`；文中的 `v35/` 和 `v34/` 是输入证据的逻辑根，分别对应任务书提供的 v35 构建根和 v34-r4 构建根，不是需要写入的目录。

## 固定产物

| 产物 | SHA-256 |
|---|---|
| v35e SWF | `89461f676b57a059bde58fe5897190db9b61013ae63947401fe1bf87106d6bcf` |
| v35e x86 签名 APK | `aab1f83518f5f2994d5aba409f7b8ce9b889598a2ce2db5de48e6928e5950c26` |
| v35e arm64 签名 APK | `160658520dae7e2ea2784bc224e0a360f798e45e6752837e31c6200ba236345b` |
| v34 SWF | `3d5c9745f519beee68557df7bce3e4ff635c9bb127069ed85a8fd02b5cbedb8a` |
| v34 x86 签名 APK | `eab0a49b2aa22c4827622e58b4b1d419fbea0e7e98022e46dbc75df2ecd44cd5` |
| v34 arm64 签名 APK | `d238e1d3a5d2e851104ac6de08ee00f8d950dcf3add3bbf756b4bae460d9846e` |

两份 v35e APK 的完整摘要分别满足任务书前后缀，包内游戏 SWF 摘要均等于最终 v35e；v34 两份签名包的非签名 ZIP 成员摘要分别与既有 `v34-evidence.json` 的 unsigned-aligned 包一致。原证据中的 `41e20a07…`、`b6d64900…` 是未签名包 SHA，未把它们误标为签名包，也未改写原证据。

`wf apk provides` 实读两份 x86 签名包生成 `work/m2_2/test-v34-provides.json`、`work/m2_2/test-v35e-provides.json`，分别提供 141、178 项能力，均无 unresolved 和 warnings。`wf/apk/data/` 下同名 fallback 保存相同方法和产物证据，仅将机器绝对源路径改成逻辑源路径；各自文件 SHA 固定在 `client_profiles.json`，因此两份 SHA 不相同。干净检出可使用只读 fallback。

`test-v34` 包名 `com.leiting.wt`、versionCode 1008002；`test-v35e` 同包名、versionCode 1008003。能力默认档案为 `test-v34`；历史发布器默认 `local-mumu` 保持。档案标明本地离线证据，不声明安装、部署或设备通过。

## 累计能力

| run5 能力名 | M2 稳定 ID | 必需归档 |
|---|---|---|
| wfx-effect-query-v1 | client.wfx.effect_query@1 | 112 |
| direct-base-v1 | client.direct.base@1 | 112、113、124、130 |
| direct-merge-v1 | client.direct.merge@1 | 112、114 |
| charge-cap-v2 | client.charge.cap@2 | 112、115 |
| ability-resistance-v1 | client.ability.resistance@1 | 112、116 |
| pf-snapcombo-v1 | client.pf.snapcombo@1 | 117 |
| pf-lv4-data-v1 | client.pf.lv4_data@1 | 87、88、89、118 |
| fever-items-v2 | client.fever.items@2 | 90、91、92、93、119 |
| leader-unlock-v1 | client.leader.unlock@1 | 120 |
| adaptive-element-v1 | client.element.adaptive@1 | 121 |
| overflow-heal-damage-v1 | client.heal.overflow_damage@1 | 112、122 |
| ability-visuals-v1 | client.ability.visuals@1 | 123 |
| super-fever-v1 | client.super_fever@1 | 112、125 |
| fever-voice-v1 | client.fever.voice@1 | 126 |
| dual-form-uid-v1 | client.dual_form.uid@1 | 128 |
| equipment-rules-data-v1 | client.equipment.rules_data@1 | 129 |
| wfx-hidden-unique-icons-v1 | client.wfx.hidden_unique_icons@1 | 131 |

此外登记完整 112–131 逐归档能力。127 是既有准备语音入口的通用化，没有虚构第 18 项 run5 语义能力。新增 17 项语义能力均含方法 SHA、数据入口、allowed_tables、参数表单、规则、golden、A 层和来源。

`wfx_registry.json` 保留原先尚未实现的 planned 效果码和 `wfx-core-v1`，新增的十个码 24–29、60–62、71 标记为 `local_candidate`。不把查询底座标成包含 pin 防驱散的 wfx-core。28/29 使用有符号 int32 flags；24/26 的 flags 为数值上限；各码先按 `effect_flags_overrides` 校验，不能套用全局 pin 位规则。run5 草稿里 direct-base 的历史 run4 SHA 保留，最终可消费客户端由 `integration_evidence` 的 v35e SWF/签名 APK 精确绑定。

Fever v2 按新 UID 或 `lvN` 语法产生依赖，旧 1299901–1299909 无等级格式继续允许 v34。`ModDualForm:<uid>` 需要新能力，原无参 `ModDualForm` 不因此被误报。隐藏标签只看 `wfx:` 字符串的第六段是否以大小写精确的 `hidden_` 开头，保留原 `hidden_` 前缀能力。

旧 wfx 档案没有从 `local-mumu` 全量继承。仅把七项已有能力映射到实际 v34 归档方法：伤害类型 #20、冲刺参数 #3、回槽限制 #31、Fever 比例 #4、两种描述覆盖 #2、PF 快照 #1；映射存于档案 `evidence.capability_patches`。缺少对应归档证据的历史装备外观等额外名称未新增到测试档案。M2 本身的 v34 141 项能力完整保留。

## 方法核对和兼容边界

[方法审计](v35e-method-audit.json)保存 37 条旧归档方法引用的 before/after SHA、最终锁来源及 intentional 分类；913 条旧方法引用保留，104 条新归档方法引用与最终 SWF 一致。数字按归档引用计数，共享方法可在多个归档中出现，不当作不同方法体数量。

提取从每轮归档 README 定位方法和所属 ABC，再按 run1–run5 最后一个 release-lock 取得最终 code SHA。对改变的 ABC 直接读取最终 SWF 的方法 code 字节并计算 SHA；未改变的辅助 ABC 与固定 v34 输入完整 payload 相同，沿用已绑定 v34 的方法记录。仅使用解析器读取原始 code 字节，未把重新序列化的 ABC 当成输入证据。

旧 YAML 的 `sha256` 原值保留；有意更新额外放入 `accepted_variants`，包含方法 SHA、唯一最终 SWF SHA、来源和原因。已选 v35e 时必须匹配该变体，不能用旧方法冒充新包；未知 SWF 不能借用此变体。新归档记录直接使用 v35e 最终方法，保证第四轮目标层数和第五轮隐藏标签不会被旧候选包误报满足。

`wf/apk/data/v35e-evidence.json` 使用锁定 v34 SWF 的增量证据：只有 before SHA 与原记录一致且分类为 intentional，才能替换旧方法，再追加 112–131。资源、原生和 ANE 条目仍受签名无关 APK payload 摘要约束；仅 SWF 不提供这些条目。原七项无方法 SHA 的资源/平台记录继续明确待补，不补造哈希。

所有证据属于包和离线方法层。完整 AIR、Android 视觉、联机、设备性能和实际部署均未验证。
