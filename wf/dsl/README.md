# 629 能力动作门禁

`check_629_actions(read_raw, overrides=..., changed_logicals=...)` 供 balance 与 deliver 在出包前调用。`read_raw(logical)` 读取原始基线，返回 bytes 或 `(bytes, source)`；`overrides` 为候选逻辑路径到 bytes 的映射。`status == "问题"` 必须阻断，报告保留能力表、键、行、动作路径和命令节点位置。

入口按 `ability_enum_map.json` 的布局读取 ability、leader_ability、ability_soul 和 equipment_enhancement_ability 的 `instant_content.kind == 629`，使用 `action_path`，缺省时从引用的 action_skill 各档 c7 解析路径。随后递归跟踪所有 `path$program`；环只遍历一次，选中动作的缺失或无法解析的依赖会报错。ability 与 leader 表缺失会阻断；没有装入的可选装备能力表不会被虚构为空表来提供完整性证明。

增量检查按前后能力表键差异、技能键差异以及被修改 DSL 的可达关系选根，检查每个选中根的完整调用闭包。无关旧键不阻止独立改动；传 `changed_logicals=None` 则检查全部根。不应把候选视图当作 `read_raw` 基线，否则前后差异会消失。

生命周期检查不依赖 `Command` 包装，能识别裸枚举、Event 包装和具名 JSON 节点。Wait 通过回调内容识别，不要求固定参数个数。普通字符串中的命令名不会被当作命令。`sanitize_for_629` 只返回独立新树，不修改原输入；它不会替调用方写回跨文件子程序。跨文件检查由上述门禁负责。

## 官方正向对照

可复现入口：`python -B -m wf.dsl.corpus --cdn <官方归档根> --output <本仓JSON路径>`。读取 `OfficialBaseline` 选出的 CN 官方归档至 `1.4.54`，保留内置 pinned 表摘要检查，不写外部索引缓存。统计摘要与每个实际输入成员的 SHA-256、归档名、成员名在 `docs/m1/official-629-corpus.json`。

本轮四张能力类表中找到 3 处 629 引用、3 棵唯一动作树：ability 1 处，leader 2 处，另两表 0 处。RemoveEvent、SetPowerFilpSuppress、NotifyPowerflipEnd 和 Wait 均为 0 次，树内没有额外 `path$program`。因此这份语料未提供降低任何禁止类别的合法正例，现有生命周期类别仍报「问题」。这是指定 CN 官方归档范围的统计，不推论其他地区、后续版本或所有官方语料。

门禁的生命周期结论与 `wf check dsl` 的完整签名检查分开。本轮官方 `estateguild_leader` 有 CreateSummonsMultiball 的 null 回调，旧签名检查会报错；该问题不构成 PF 生命周期证据。自动 629 门禁检查二进制可解析性与生命周期，不借这个旧签名缺口阻断官方正例。
