# 能力注册表

每个 `.yml` 文件是一项有版本号的能力声明；文件名必须等于 `id`。`python -m wf check <文件>` 校验 schema，`load_registry()` 返回按 ID 索引的字典。声明是数据，加载过程不执行补丁脚本。

`client.apk.patch001@1` 至 `client.apk.patch111@1` 覆盖归档的全部补丁。纯平台、性能及界面条目保留 `layer: platform`，不会因为不直接改变战斗数值而从目录消失。命名语义能力由这些补丁组合：例如 `client.pf.level4@1` 必须同时有 #87、#88、#89，`client.overlimit.lv120@1` 覆盖等级资源与 O1–O12。O1–O12 也各有独立声明。B 层包含 722/419、觉醒、合击位、629；B 层不要求自制 APK 补丁。

`provided_by.patches` 是必须全部满足的归档号。`methods` 的 SHA-256 指向方法的 **code 字节**，不是整个方法记录、P-code 文本或 SWF 的摘要。方法定位键是 `(patch, abc, label)`；哈希缺失保留 `null` 和「待补」，不填示例哈希。资源类 #79/#82/#86 与原生平台 #97–100 没有 SWF 方法证据，正是这类显式缺口。`server.required` 和 `server.features` 描述另需配合的服务端功能，不代表服务端已部署。

`data_surface` 提供 requires 扫描入口：`kind_bindings`、`dsl_nodes`、`unique_prefixes`、`unique_ids`、`tables` 和语义 `selectors`。`kinds` 只保留为无上下文的目录查询索引，不能凭编号判断行依赖或客户端支持。`tables` 只用于整表出现即需要能力的情况；通用 ability 表不在这里，否则会误把所有角色判断为依赖所有扩展。逐补丁归档声明不重复挂这些入口，内容优先引用语义能力。C 层角色机制名称属于矩阵数据，不凭名称推断客户端能力。

带 `kinds` 的声明必须同时给出 `allowed_tables`、`allowed_blocks` 和显式配对的 `kind_bindings`，例如 `[{block: instant_content, kind: 722}, {block: during_content, kind: 419}]`。校验保证两种索引与配对一致；扫描通过共享 `surfaces.matches_kind` 按表及准确配对选择能力，不取编号与块的笛卡尔积。instant 419/422/423/424 是官方独立效果，不推导 PF 或补丁依赖。during 422/424 分别使用 #3/#20；during 423 在角色表使用 #31，在武器魂及装备强化表使用 `client.equipment.gauge_gain_rules@1`（equipment-rules R3）；instant 724 使用 #4。

`requires.kindSites` 保留五张能力表（含 `ex_ability`）的实际行位置；支持与否由目标档案真实 SWF 的 `(table, block, kind)` 分支决定，注册表不承担放置拒绝。公开交付在生成 ZIP 前复用相同检查，编辑台缓存也保存完整位置身份。旧 requires 的 `capabilityEvidence` 如果保留表和块，仍执行真实分支检查；缺表或块时阻断为待验证并要求重新推导，不按编号猜测。R3 规则掩码借用的列不作为固有状态引用。角色专用 #1/#5/#6/#7/#15/#32/#55/#65 及晒伤语义能力为 C 层（需要 APK），其 `character_ids` 与角色引用闭包用于确定受影响内容；缺少归属输入时保留 partial。`inferenceNotes` 记录候选表缺基线而按全表扫描的保守处理。

无数字归档号的独立方法能力使用 `provided_by.patches: []`、`methods.patch: null`，同时必须有完整方法 SHA 和 `provided_by.swf_sha256` 白名单。R3 只绑定 test-v34/test-v35e 的实际 SWF；摘要输入必须显式包含 `method_capabilities`，缺方法、哈希不符或 SWF 不在白名单均不能提供该能力。`patch: null` 表示未分配归档号，与 `sha256: null` 的方法证据待补不同。

## APK 能力输入

```text
python -m wf apk provides <APK、SWF、构建记录或摘要文件> --output work/m2/provides.json
python -m wf check compat --requires <requires.json> --provides work/m2/provides.json
python -m wf apk kinds --profile test-v34
python -m wf apk kinds --profile test-v35e --output work/m2_3/test-v35e-kinds.json
```

`apk kinds` 输出五张能力类表的各块 kind 集合、方法标签、code SHA 和 SWF SHA。档案通过 `evidence.swf_path` 定位本地文件，实际文件必须匹配 `evidence.swf_sha256`；也可用 `--swf` 显式指定同摘要的 SWF/APK。读取器在内存解析 APK 的 SWF，不提取到外部目录。注册表按该档案提供能力的同 kind、同块表范围合并后比对真实分支，不一致返回非零。缺少真实产物时兼容检查保留阻断的待验证结果；旧反编译源码仅作参考。基础客户端方法体夹具验证了两张武器表不会凭版本标签或字符串常量误报 423 支持。

`wf/apk/data/v34-evidence.json` 仅收录可审计的摘要和归档映射，不含 APK、SWF 或游戏成员。它来自 v34 的 #1–101 方法保留报告、#102–107 实际 `final_pcode` 和 #108–111 r2 实际方法记录；原始文档的摘要同时保留，不能只靠文件名或版本号认出一个客户端。

完整 APK 通过 SWF 摘要与全部非签名 ZIP 成员摘要匹配。x86 和 arm64 的原生能力分别处理；签名变化不会改变成员摘要。只有 SWF 匹配时仅提供有方法证据的条目，不能据此证明资源表、台座图集或 native/ANE 条目。未知 APK/SWF 明确拒绝，需要调用者提供摘要。

自定义摘要格式为 `schema: wf-apk-summary/1`，包含 `patches` 数组，每项提供 `number`、`status`（`recorded` / `declared` / `applied` / `already_present` / `enabled`）与 `methods`。方法使用声明里的 `patch`、`abc`、`label`、`sha256`。`official_systems: true` 是对 B 层的显式声明；缺少它不会自动给未知客户端补上 B 层。缺失方法 SHA 不从注册表反填为已验证；注册表已有 SHA 而输入缺失或不符时，不提供该补丁及依赖它的组合能力，记录问题。只有注册表明确待补的方法可保留待验证；额外未登记方法进入 `warnings`，不用于证明能力。

原始 `patch-list.json` 只是执行配置，因此仅读取其中明确启用的条目并按归档号合并，不能推断其 base 已具备其他补丁，也不把配置当作执行结果。这些条目未附注册表要求的方法 SHA 时进入 `unresolved`，不提供对应能力。v34 的完整构建记录由固定摘要绑定到已收录归档证据，输出明确写明这是记录推导。所有这些证据均属于离线静态层，不代替客户端运行和设备验收。
