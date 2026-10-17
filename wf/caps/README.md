# 能力注册表

每个 `.yml` 文件是一项有版本号的能力声明；文件名必须等于 `id`。`python -m wf check <文件>` 校验 schema，`load_registry()` 返回按 ID 索引的字典。声明是数据，加载过程不执行补丁脚本。

`client.apk.patch001@1` 至 `client.apk.patch111@1` 覆盖归档的全部补丁。纯平台、性能及界面条目保留 `layer: platform`，不会因为不直接改变战斗数值而从目录消失。命名语义能力由这些补丁组合：例如 `client.pf.level4@1` 必须同时有 #87、#88、#89，`client.overlimit.lv120@1` 覆盖等级资源与 O1–O12。O1–O12 也各有独立声明。B 层包含 722/419、觉醒、合击位、629；B 层不要求自制 APK 补丁。

`provided_by.patches` 是必须全部满足的归档号。`methods` 的 SHA-256 指向方法的 **code 字节**，不是整个方法记录、P-code 文本或 SWF 的摘要。方法定位键是 `(patch, abc, label)`；哈希缺失保留 `null` 和「待补」，不填示例哈希。资源类 #79/#82/#86 与原生平台 #97–100 没有 SWF 方法证据，正是这类显式缺口。`server.required` 和 `server.features` 描述另需配合的服务端功能，不代表服务端已部署。

`data_surface` 提供 requires 扫描入口：`kinds`、`dsl_nodes`、`unique_prefixes`、`unique_ids`、`tables` 和语义 `selectors`。`tables` 只用于整表出现即需要能力的情况；通用 ability 表不在这里，否则会误把所有角色判断为依赖所有扩展。逐补丁归档声明不重复挂这些入口，内容优先引用语义能力。C 层角色机制名称属于矩阵数据，不凭名称推断客户端能力。

## APK 能力输入

```text
python -m wf apk provides <APK、SWF、构建记录或摘要文件> --output work/m2/provides.json
python -m wf check compat --requires <requires.json> --provides work/m2/provides.json
```

`wf/apk/data/v34-evidence.json` 仅收录可审计的摘要和归档映射，不含 APK、SWF 或游戏成员。它来自 v34 的 #1–101 方法保留报告、#102–107 实际 `final_pcode` 和 #108–111 r2 实际方法记录；原始文档的摘要同时保留，不能只靠文件名或版本号认出一个客户端。

完整 APK 通过 SWF 摘要与全部非签名 ZIP 成员摘要匹配。x86 和 arm64 的原生能力分别处理；签名变化不会改变成员摘要。只有 SWF 匹配时仅提供有方法证据的条目，不能据此证明资源表、台座图集或 native/ANE 条目。未知 APK/SWF 明确拒绝，需要调用者提供摘要。

自定义摘要格式为 `schema: wf-apk-summary/1`，包含 `patches` 数组，每项提供 `number`、`status`（`recorded` / `declared` / `applied` / `already_present` / `enabled`）与 `methods`。方法使用声明里的 `patch`、`abc`、`label`、`sha256`。`official_systems: true` 是对 B 层的显式声明；缺少它不会自动给未知客户端补上 B 层。缺失方法 SHA 不从注册表反填为已验证；实际 SHA 与注册表不符则不提供该补丁及依赖它的组合能力。

原始 `patch-list.json` 只是执行配置，因此仅推导其中明确启用的条目，不能推断其 base 已具备其他补丁，也不把配置当作执行结果。v34 的完整构建记录由固定摘要绑定到已收录归档证据，输出明确写明这是记录推导。所有这些证据均属于离线静态层，不代替客户端运行和设备验收。
