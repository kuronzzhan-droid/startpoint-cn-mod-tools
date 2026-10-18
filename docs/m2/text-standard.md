# 面板文案规则与只读核查

`wf text` 接入《MOD 角色面板文案规范 v1（草案）》全部 10 节，共 58 条规则。规则真源是 `wf/rules/text_standard.json`；每条含稳定 ID、章节、要求、适用文本表面、依据性质与可执行范围，`wf check rules` 和 `wf text rules` 均可读取。

依据分为**作者规范**和**官方模板引用**。后者表示规范引用了官方写法，不代表本次独立重查了官方全部 533 条模板，更不代表真机验证。没有把格式偏好标为客户端崩溃或数据非法。

## 适用范围

- §1—8、§10：`desc_override_*` 的覆盖文案，包含没有角色归属的覆盖键。非覆盖 `custom_ability_string` 和官方自动生成能力文本不套这份新规范。
- §9：`action_skill` 的所有实际技能档 c1 描述及各档写法一致性；c0 名称也扫描现有命名约束，保留 `+`/`++` 升级后缀，不把名称当效果描述，不修改技能名称。一次全表核查会包含继承的旧文本和没有直接角色归属的技能键，问题不等同于被该版本新引入。
- M1 原有的恒真条件、名称约束、重复强化跨字段检查保持生效。基础技能与能力出现相同效果名不足以证明重复，因此仍为待验证。

58 条中，47 条仅能检查列举的确定性写法，11 条需要原数据或人工语义核对。原有 13 条 automatic 规则已全部降为 partial，覆盖边界明确标注「仅列举写法」。部分检查和人工条款即使没有命中，仍为**待验证**；无适用输入为**不适用**。这不是把尚未实现的语义核验当通过。

需要语义核对的内容包括对象/条件是否相同、满级数值是否真实、独立乘区是否适用、主位图标是否与数据一致、状态/形态首次出现的获得和进出条件、效果搬入队长技后是否完整，以及副作用和现有译名是否保留。静态规则不会据此替用户修改文案。

## 命令

```powershell
python -B -m wf text rules --output work/m2/text/rules.json
python -B -m wf text check <角色ID> --tip 1.4.229
python -B -m wf text read <角色ID> --tip 1.4.229 --output work/m2/text/character.json
python -B -m wf check text work/m2/text/character.json --json work/m2/text/check.json
python -B -m wf text audit-standard --tip 1.4.229 --output work/m2/text/audit-1.4.229.json
```

`audit-standard` 沿配置的 manifest 构建版本视图，回读全部覆盖文案和技能档位，不靠角色名筛选，因而不会漏掉孤立覆盖键。输出必须用 `.json` 后缀，同时写同名 Markdown。JSON 保留所有已扫描键、文本 SHA-256、所有确定性问题的完整原文和命中、每条规则的状态、输入表摘要、manifest 实际版本及完整视图锁。Markdown 逐项列出全部确定性问题，不截断为前若干项。

发现确定性问题时退出 1；输入或格式失败退出 2；没有确定性问题但语义仍待验证时退出 0，报告状态保留待验证。退出 0 不表示全部规则或玩法已经通过。

可加 `--server-text <character_text.json>` 和 `--rank-text <character_text_rank_p5b.json>`，明确指定**该版本**的完整服务端镜像。两份镜像均扫描 c4/c6/c8 名称、c5/c7/c9 技能描述和档位一致性，读取字节均记入摘要；缺失的镜像明确标未执行。另以角色键合并 base 与 p5b，p5b 存在该键时整行覆盖 base，再与客户端 `character_text` c5/c7/c9 逐字对照；不存在逐列回填。差异写入 `text.server_effective` 问题和 `effective_server_checks`，缺任一完整镜像为待验证，不以零命中当一致。不能用当前服务器文件冒充历史版本文件，也不能把 `*.patch.json` 的 old/new 增量当完整镜像。

`wf check text` 对读取快照运行同一套 `check_character`，逐规则输出五态。它不重新读取原始客户端/服务端来源，因此来源重新核验保持未执行。

## API 与规则维护

```python
from wf.text.standard import rule_catalog, check_entry, coverage
from wf.text.rules import check_character
from wf.text.release import audit_workspace, write_report

violations = check_entry("desc_override_hero_1", "自身PF伤害+20%")
states = coverage({"desc_override"}, violations)
```

`check_entry` 仅返回可证明的文本违规，包含 `rule/state/location/message/evidence`；调用者必须结合 `coverage`，不能以空列表宣称语义全面满足。`check_character` 自动加入待验证覆盖项并保留旧版跨字段门禁。`prepare_edit` 使用相同规则，拒绝本次新引入的问题，与编辑无关的原有问题继续保留，不改现有双镜像和逐字节暂存策略。

添加规则应先修改 JSON 条目，再在 `standard_checks.py` 实现必须的文本检查；能用正则表达的固定禁用词直接放条目的 `patterns`。每个实际执行的规则都有反例，所有无自动检查的条目必须为 `review`。规则只做判定，不自动替换词语或数值。

规范中的例外保持原义：凯尔「每1连击再+X%」是连续数值成长，不当计数触发错误；§6 追加技能允许「以强化弹射伤害计算」，不被§10普通伤害换算写法误报；形态之间以分号分句时，两个不同的「X」形态不会被误判重复条件；类型名或技能名中的词不作术语替换。§6 对629技能伤害说明的示例与“只在非技能伤害时注明”存在表述张力，该条保留部分检查和待验证，不强行选择一个解释。

## 两份服务端镜像

编辑路径继续要求显式提供 base 与 p5b，修改技能描述时逐档同步 action_skill、客户端 character_text 和两份服务端镜像。稀疏表只改已有角色；不存在的角色不补键；两份都不存在则失败。输入漂移、部分档位编辑、只提供一份镜像都会失败。JSON 仅替换字符串 token，键序、缩进、换行、转义和无关内容保留，未更改任何部署路径。

伤害倍率规则仅匹配明确连接伤害的倍率及列举的段数写法，不将持续时间、层数或速度的倍数视作伤害倍率。

针对规范新增了可见差异反例：给 rank_p5b 的单个技能字段写入「对敌人造成43倍火属性伤害」时，全表核查必须报出 p5b 的具体键/列；新技能文案通过时两份镜像的三个实际档位都更新，而两个源文件字节保持原样。

## M2.1 有效文本与技能档位

`wf text check`、`wf check text` 共用 `check_character` 的有效服务端对照；`audit-standard` 使用同一个 `compare_effective`。快照没有完整镜像来源摘要时只报告待验证，不推测缺失镜像为空。对照仅说明提供的静态文本一致，不能证明来源重新核验或上线状态。

§9 新增 `text.standard.skill-tier-wording`：逐个技能比较全部实际档位的 c1 描述，忽略空白和数值差异（引号内名称中的数字保留），保留效果名、条件、标点与连接方式。非数值写法不同即报问题。c0 按名称规则单独检查，合法 `+`/`++` 名称不触发技能效果分隔符规则。全表包括孤立技能键，以及两份镜像各自的档位；这些检查不自动修改任何文案。

139985 迟缓反例采用 1.4.227 客户端与当时准备的 rank 增量：客户端是「对迟缓效果中的敌人追加雷属性伤害」，增量是「对迟缓效果中的敌人伤害提升」。重新读取原增量 SHA-256 `7f98778b3c54382683492646ab279d2b2629270fd8ef224dbee90da3c3e65664`，并从明确指定的 ghmain manifest 重建 1.4.227 客户端视图后，临时构造该角色覆盖行验证：c5/c7 报两项差异，修齐后无差异。该证据是准备增量与客户端对照，**不是完整历史镜像或部署证据**。
