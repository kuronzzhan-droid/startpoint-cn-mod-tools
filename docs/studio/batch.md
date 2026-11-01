# 批量平衡表与角色变体

这两个入口仅写本地角色草稿，不修改输入主表、store 或服务端。预览不写草稿、不预留 ID。

## 平衡表

角色工坊点击「平衡表导入」，进入 `#/content/characters/balance-import`。
粘贴带表头 TSV / CSV，或读取本地文本文件，解析后映射列名。
每行表示一项改动；合并单元格、每角色一大块的宽表须先整理为逐行格式，不自动向下填充角色。

| 字段 | 解释 |
| --- | --- |
| character | 精确角色 ID、名字或代码名；同名歧义拒绝 |
| entry | 能力1–6、队长技或该角色的精确能力键 |
| before / after | 完整机器中文描述，或指定原始列时的精确原始数值 |
| row | 可选，词条内行号从 1 起；多行且不能由描述唯一匹配时必填 |
| column | 可选，原生列号从 0 起，如 c51；队长技使用自己的原生列空间 |

只转换当前模式启用、且由当前 kind 声明的数值字段。原始数值必须是标准整数，非负字段拒绝负数。
中文描述模式要求仅一个数值变化，按字段单位精确换算，支持原值相等的双端点同步替换；重新渲染必须完整等于目标描述。
原始数值模式不推测百分比、帧数或次数的单位，不允许借此修改枚举、条件或结构。
未知角色、未知词条、共享词条、多行歧义、重复目标行、含糊描述和预检阻断均显示「需人工」。
每行通过现有 `AbilityEditor.preview` 返回前后中文描述及五态检查。
初始勾选为空，必须逐行勾选才能写入；输入、映射或草稿改变后要重新预览。
保存时校验预览摘要，并把同角色选中行组合复检、写入现有 `ability_edit` 草稿。
批次写入失败会恢复原草稿；不会自动覆盖其他未提交的工作。

映射存储在被忽略的 `work/studio-batch/balance-mapping.json`；前端预览时记住映射。
CLI 默认读取上次映射，或显式提供 JSON。CLI 的预览默认不保存映射，使用 `--remember-mapping` 才保存。
切换表格后，前端清除不存在的列映射；CLI 复用映射时自动清除新表缺少的可选行号、原始列映射。

```text
python -m wf.studio.draft balance-import --file work/sample.tsv --mapping work/mapping.json
python -m wf.studio.draft balance-import --file work/sample.tsv --mapping work/mapping.json --review <预览返回的review> --select 1 --select 3
```

映射文件示例：`{"character":"角色","entry":"词条","before":"修改前","after":"修改后","row":"行号","column":"原始列"}`。
列名由文件决定，不要求采用示例名称。默认不写，`--select` 可重复；缺少对应预览摘要时拒绝写入。

## 变体

角色页「复制为变体」提供目标列表、新 ID 编辑和联动空闲查询，保留首行填写的起始号段。
查询覆盖角色、玛纳段、能力/队长技/技能键及残留草稿目录；批内重复 ID 单独标红。查询不预留 ID。
选择规则、添加目标后，先预览再勾选创建，每个目标得到一份 `character_clone` 草稿。
母本是当前加载的只读视图，不叠加母本未交付的编辑草稿。

乘区目标为技能7、强化弹射5、直接攻击6、能力8、全伤害9。
确定等价的普通加成映射到目标类型，独立加成映射到目标独立乘区；全伤害9没有普通加算，转为独立全伤害。
保留数值和原属性/种族组；自身伤害加成扩为全队，原全队加成保留，空组填 `(None)`。特殊目标和未验证触发组合需人工。
去主位资格同时处理能力首行 c1 与已知 202 前置；攻击力种类、数值和受益对象保持原样。
诺瓦已知的持续194/固有20/上限1、双阈值均100000组合从全队任一改为全队总和，先汇总再封顶；其他组合需人工。
技能仅自动替换确定的四字段限时伤害 buff 构造器，保留时长、强度、次数，生成独立程序路径。
全伤害版限时 buff 保留母本的原伤害类型。副本拥有独立 c27 身份，可与母本同队。

未确定的效果、固有条件不等价、外部动作程序闭包、自定义覆盖文案和技能文案同步均列出「需人工」。
例如721的固有敌人条件不会被擅自清除；565也不会为转换全伤害而丢掉固有条件。
可以保存包含这些条目的克隆草稿，审核状态明确标为「含需人工（仅存草稿，阻断交付）」。
文案待同步项可在克隆角色的文案页完成：填入新覆盖描述，或修改对应档位的技能描述；保存时重算待办和阻断。
编译时重新验证实际文案，撤销同步会再次阻断。未知规则项仍须补齐规则并重新预览克隆，不因修改其他文案而放行。
每个发生改动的词条键全部行使用独立 c0，文本键和对应覆盖键均检查并登记草稿占用。
角色页显示的是机器生成的逐行描述，不能视作已经完成玩家文案、客户端兼容或真机验收。

换属性规则入口保留拦截。角色表只改 c3 不够：母本技能 DSL 仍按旧属性产生伤害及抗性降低，
能力条件、音效和玛纳材料也尚未形成完整转换闭包。纯函数有属性组、显式 element、抗性枚举的候选转换测试，
它不能证明整角色跨属性安全，因此 API 和前端都不开放跨属性写入。

## 接口

所有 POST 沿用 Studio 的回环地址、Origin 与会话 token 守卫。

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| GET | `/api/studio/characters/balance/mapping` | 读取上次列映射 |
| GET | `/api/studio/characters/variants/ids/check`、`ids/next` | 联动键占用检查/从 near 起查空闲 ID，from 为母本 ID |
| POST | `/api/studio/characters/balance/parse` | `{text}`，只解析表头和行 |
| POST | `/api/studio/characters/balance/mapping` | `{mapping}`，记住本地映射 |
| POST | `/api/studio/characters/balance/preview` | `{text,mapping}`，返回 rows 和 review |
| POST | `/api/studio/characters/balance/apply` | 加上 `{review,selected:[1,...]}` |
| POST | `/api/studio/characters/variants/preview` | `{from,rule:"zone",targets:[{to,zone}]}` |
| POST | `/api/studio/characters/variants/apply` | 同预览请求，加上 review 和 selected |

变体 zone 使用 `skill / power_flip / direct / ability / all`。
最多1000条平衡表行、20个变体；两种批次都拒绝重复目标与过期预览。
