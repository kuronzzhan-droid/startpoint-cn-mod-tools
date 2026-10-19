# 副本工坊：读模型、草稿与本地交付（M5）

副本后端提供统一读模型、参数草稿和共同决战模板，并复用编辑台已有的交付链。它从指定版本的客户端视图和只读服务端 JSON 镜像读取输入，将草稿与交付写在当前 checkout 内。应用、安装、服务器变更、发布和 push 均不由这些接口自动执行。界面接入情况另见[编辑台说明](README.md)。

## 读取副本与来源

`BossReader` 接受 `ManifestView`、`StudioSource` 或内存候选视图。`list()` 返回 `wf-boss-list/1`：`items` 是每个实际难度叶子，`groups` 是分组信息；不能用组数代替可进入的副本数。范围包括领主战、共同决战、五重决战及木人练习。

`show(selector)` 返回 `wf-boss/1`，包含以下关联：

| 字段 | 内容与边界 |
|---|---|
| `quest` | 原始行、字段解释、表路径、叶子路径、难度、等级和属性；`field_sources` 保留零基列号与来源 |
| `entrance` | 领主节点及节点组、练习目录，或共同决战事件与 `event_folder_events` 入口 |
| `field_data` / `field` / `zone` | 场景、地形、战斗波次和敌人槽位所用的实际表行 |
| `terrain` | 解码后的地形资源及 `objectgroup` 波次；波次数不从 zone 行数推测 |
| `enemies` | 单人/多人槽位、原生敌人类别、等级档、属性、HP/攻击值及各项来源；缺资源或未支持类别明确标记 |
| `rewards` | score / rare 奖励行和币种引用 |
| `shops` | 商店分类、商品及武器；该读模型只读取客户端，服务端同步仍标为未执行 |
| `routing` | `BothBoss` 的隐藏关选择路由；它不是同屏多 boss 的含义 |

优先传完整 selector，例如 `boss_battle:1/81/1`、`hard_multi:1006/1` 或列表返回的 `practice:...`。裸数字只在当前视图中唯一时可用；重名必须加类型和路径。练习表 c0 是目录，练习副本身份取 orderedmap 的叶子键，不能把 c0 当唯一副本 ID。程序应沿用列表返回的 `selector`，不要自行拼接未经核验的 ID。

每条来源记录保留 `logical`、`leaf_path`、`table_sha256`、`table_layer`、`layer`、`scope`：

- `scope=leaf` 的 `layer` 表示整条 CSV 叶子最后发生语义变化的层，不表示每个字段首次引入的版本。
- `table_layer` 仅表示整表最终载入层；`scope=table` 表示尚未核验叶子的变化层。
- `field_sources` 虽按字段列位展示，来源仍是整叶来源，不是单格首次引入层或单格最后变更层；`field_sources_semantics` 明确给出 `granularity=whole_leaf` 和 `column_origin_verified=false`。
- 本地候选变化标为 `boss-draft`。同表内未改的叶子保留其来源，不将整表都归为草稿新增。
- 共同决战到原领主商店的 `_hard` 场景命名关联标为 `association.kind=field_family_inference`。这是命名推断，不是客户端外键。

离线读取与规则检查示例，路径均是相对于调用目录的示意输入，需替换为实际只读资料位置：

```powershell
python -m wf boss list --tip 1.4.236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --json work/boss/list.json
python -m wf boss show hard_multi:1006/1 --tip 1.4.236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --write-lock work/boss/view.lock.json --json work/boss/dark-template.json
python -m wf check boss hard_multi:1006/1 --tip 1.4.236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --json work/boss/check.json
```

`wf boss` 支持重复 `--zip-dir`、重复 `--extra-manifest`、`--base-version`、`--lock` 与 `--write-lock`；输出前调用视图验证。`wf check boss` 还接受保存的 `wf-boss/1` JSON、`--baseline` 和 `--context`。只有快照而没有实际视图时，依赖资源或服务器的规则会保持「未执行」或「待验证」。清单、锁、ZIP 和 store 必须来自同一条经摘要核验的版本链；文件名相同不代表内容相同。

省略 `--tip` 时，两条命令都选择 manifest 最高启用版本并核验它到基线的完整依赖链；缺链或缺包即失败，不退回旧版本。`--write-lock` 与 JSON 输出均受 `local_output` 限制，只能写当前 checkout。

## 字段列位与来源

下表列号均从 **c0** 开始；不是电子表格的第一列编号。权威映射来自客户端生成类 `pinball/master/generated/BossBattleQuestValues.as`、`HardMultiEventQuestValues.as`、`PracticeQuestValues.as`，仓内集中映射在 [`wf/boss/schema.py`](../../wf/boss/schema.py) 和 [`wf/boss/parameters.py`](../../wf/boss/parameters.py)。

| 含义 / 请求字段 | 领主战 `boss_battle` | 共同决战 `hard_multi`、练习 `practice` |
|---|---|---|
| 名称 | c2 | c2 |
| 开始 / 结束时间 | c5 / c6 | c5 / c6 |
| 前置条件原始段 | c7–c16 | c7–c16 |
| 出战限定属性 `restrictedElement` | c68 | c69 |
| 体力 | c69 | c70 |
| score 奖励组 | c70 | c71 |
| 推荐属性 `recommendedElement` | c72 | c73 |
| 隐藏推荐属性 | c73 | c74 |
| 杂兵 / 浮游 / boss HP 修正 `hpValue` / `hpScale` | c97 / c98 / c99 | c98 / c99 / c100 |
| 杂兵 / 浮游 / boss 攻击修正 `attackValue` / `attackScale` | c100 / c101 / c102 | c101 / c102 / c103 |
| 敌人等级 `level` | c106 | c107 |
| 难度 rank | c107 | c108 |
| `field_data` | c109 | c110 |
| BGM 组 `bgm` | c110 | c111 |
| 时间限制 | c111 | c112 |
| `BothBoss` / 隐藏关标记 | c122 / c123 | 不按此映射解释 |

`scene` 修改的是所引用 `field_data` 的 c0（`field` 键）；`field_data` c1 是地形，c2 是 zone。编辑会为该副本派生独立 `field_data`，避免改动其他共用者。HP/攻击的 `Value` 直接设置表内三个对应修正，`Scale` 则分别乘以三项当前值，不修改全局敌人基础数值或等级表。旧 `hpMultiplier` / `attackMultiplier` 是绝对值、已弃用，仍保留赋值语义。完整规则和实际数值预览见 [M6.2 参数语义](boss-authoring.md)。属性整数采用客户端原生枚举 0–5；`restrictedElement: null` 写为 `(None)`。限定属性与推荐属性是不同字段。

改变 `recommendedElement` 会同步实际有效的服务端 quest 键的 `element`。领主战先找 `_cnmod` 覆盖键、再找本体键；共同决战使用 `hard_multi_event_quest.json`。缺少该键会拒绝编辑。木人没有此服务端归属。客户端推荐枚举与敌人 c0 枚举不同，不应互换数值。

共同决战服务器行由客户端 quest 行导出，写入交付内 `assets/hard_multi_event_quest.json` 的新 quest 键：c71 对应 `scoreRewardGroupId`，c2 对应 `name`，c72 对应 `clearRewardId`，c85–c88 对应 B/A/S/S+ 时间（秒乘 1000），c94–c97 对应角色经验、玛纳、等级点、经验池奖励。转换实现见 [`wf/boss/template.py`](../../wf/boss/template.py)。服务端 JSON 按键合并，未改键的值保留。

## 参数请求与共同决战模板

请求由 [`schemas/studio-draft.schema.json`](../../schemas/studio-draft.schema.json) 中的 `bossRequest` / `bossParameters` 定义，拒绝未知字段。用同一 schema 检查 API 请求文件：

```powershell
python -m wf.studio.draft schema --def bossRequest
python -m wf.studio.draft validate work/boss/edit.json --def bossRequest
```

已有副本可修改等级、HP/攻击倍率、限定/推荐属性、现有 BGM 组和现有场景：

```json
{
  "operation": "edit",
  "parameters": {
    "level": 100,
    "hpValue": 1.5,
    "attackValue": 1.3,
    "restrictedElement": null,
    "recommendedElement": 0
  }
}
```

等级为 1–999 的整数；实际敌人必须存在客户端可以选取的等级档，否则规则阻断。倍率须为有限正数且不超过 2147483647。`bgm` 必须是当前视图 `master/battle/asset/battle_bgm_group.orderedmap` 的有效键；客户端根据该组解析普通战斗、首领和过渡音乐，单独存在音频文件不能替代 BGM 组。尚未被现有关卡引用的有效组也可选择。`scene` 是当前 `field` 的有效键。任意写入 `fieldData`、奖励键或 CSV 列号不在请求接口中。

换档后除初始站位 c41 外，还沿选中 c42 routine 收集 `general_boss_state` c50 站位，与该波次 `CUSTOM_POSITION` 求差，缺任一个即阻断。`field_data`、field、zone、地形、已引用 routine 等悬空引用判为「问题」。

`both_boss=true` 的路由入口（例如五重 1099001）不能编辑参数、参与五档修改或作为 `sourceQuest`。其 `show` 的 `content_scope`、敌人与地形标为「入口自身，非战斗内容」；`routing.hidden_quests` 列出 maps 指向的真正隐藏关。

改推荐/敌方属性后，C8016 证据为「待验证」默认阻断。请求可显式附带 `"acknowledgePreload": true` 接受此次操作未证明的预载风险；该值保存在 `params.requests`，检查结果保留 `acknowledgment`、状态仍为「待验证」。确认只在推荐属性与所选敌人资源行保持相同的范围内复用；仅改 HP/BGM 无需重复确认，改变属性或敌人档位资源后必须重新显式确认。已证明缺垫片及 C8016 黑名单故障不接受免责。

每次预览和编译都自动收集实际候选遭遇的敌方、场景及动作引用 PNG，作为图集面积下界。可附带 `atlasBudget: {"parties": [["character/.../sprite_sheet.png"], [], []], "enemy_sheets": []}` 补三队清单；补充清单不能移除自动收集项。去重加边距面积 `>4096²` 为「问题」并阻断；面积未超限仍待验证，不证明运行时装箱或三人房成功。报告对照 1.4.210 的历史随机房最大 14.61Mpx、失败区间 15.2–16.2Mpx，并单列来源为 1099031 的历史风险；历史数字不是当前通用通过阈值。

五档编辑仅适用于叶子恰好为 `1`–`5` 的领主战分组。公共 `parameters` 先应用，每档 `tiers` 再覆盖对应参数；数组必须恰好五项：

```json
{
  "operation": "edit",
  "parameters": {"hpValue": 1.5},
  "tiers": [
    {"level": 20},
    {"level": 40},
    {"level": 60},
    {"level": 80},
    {"level": 100}
  ]
}
```

新建共同决战只接受 `create_shared`，且必须是新草稿的第一步：

```json
{
  "operation": "create_shared",
  "sourceQuest": "boss_battle:1/81/1",
  "name": "丑王奥格",
  "parameters": {"level": 100, "hpValue": 1.5, "attackValue": 1.3}
}
```

模板以官方暗凛 `hard_multi:1006/1` 的 quest/event 结构为骨架，从 `sourceQuest` 复制遭遇的 `field_data`、zone、名称及 BGM 组；未指定 `sourceQuest` 时默认暗凛本身。默认等级 100、HP 系数设为 1.5、攻击系数设为 1.3，再应用显式参数；限定属性和推荐属性默认取遭遇的推荐属性。它复制已有敌人机制，不生成新 AI、美术、武器或商店；事件美术仍继承模板。

模板自动执行以下一致性操作：

- 分配空闲事件 ID、quest ID、入口节点、`field_data`、zone 和奖励组；同时排除现有视图、四份服务端奖励 JSON、`hard_multi_event_quest.json` 与其他未交付的新草稿占用。奖励本体表与覆盖表同键都拒绝。默认从事件 2100 起找空位，quest 为 `event × 1000 + 1`。
- 在终始之战目录 `event_folder_events/2` 下增加 `13,event,node` 入口，其中 13 是 `HardMultiEvent` 类型。
- 清理继承的前置条件，将 quest/event 开始时间设为 `2000-01-01 00:00:00`，结束时间为空。
- 克隆暗凛 score / rare 奖励及对应服务器键，重写新奖励引用。服务器输入同时读取普通表与 `_cnmod` 覆盖表；模板出现多个 rare 组时明确拒绝，避免错误推断分配。
- 为新增 quest 生成对应服务端行，并在保存前运行实际候选视图的规则。

可选 `ids` 格式为 `{"event":"2100","node":"30"}`，事件必须为 2000–9999 的十进制字符串，node 为正整数字符串；实际占用一律拒绝，示例 ID 不保证空闲。优先省略并使用返回的 `allocation`。预览不预留 ID，因此正式保存的分配以保存响应为准。

`edit` 不接受 `name`、`sourceQuest`、`ids`；`create_shared` 不接受 `tiers`。新建后可继续 `edit`，编译始终从原来源重放「创建＋后续编辑」，属性变化预加载检查仍相对原遭遇进行。

模板 `name` 禁止换行、单双引号、弯引号及 `::`，避免把未核验 CSV/富文本分隔写入名称。`boss.choice-folder` 的规则函数可读取外部设计上下文，但编辑台本期未接入 folder 编辑，结果明确为「未执行」，不计为已接入功能。

## 独立草稿与 CLI

副本使用 `BossDraftStore`，默认路径为 `work/studio-drafts/boss/`；角色草稿仍在角色自己的命名空间。`--drafts` 或 `WF_STUDIO_DRAFTS` 指定的是共同根目录，副本存储再追加 `boss/`。例如 selector `hard_multi:1006/1` 对应目录 `boss/hard_multi_1006_1/`，不把 `:` 或 `/` 直接用于目录名。

草稿 `subjectKind="boss"`；为兼容交付格式，身份字段仍名为 `characterId`，其值在副本草稿中代表副本身份。`code`、目标 selector、命名空间和 `baseView` 必须一致；角色与副本混用或手工篡改身份会拒绝。

对基线已有副本，裸 ID 与完整 selector 均规范到同一 selector 草稿；保存、撤销和交付请使用响应 `questId`。已有旧裸 ID 草稿会继续由两个别名共同访问；若旧数据已同时存在两份别名草稿则拒绝继续编辑，不自动合并冲突。尚未进入基线的新建草稿继续使用所分配的 quest ID；`hard_multi:event/1` 与 `hard_multi:questId` 别名也会归到该草稿，并核验事件号推导及基线歧义。

每个副本保存一个可重放的 boss change，`params.requests` 记录操作序列，`params.inputs.client/server` 记录实际读取输入的 SHA-256。再次编辑先重放并复核旧摘要，编译也重复此验证；来源版本、客户端表或服务端镜像漂移不能静默通过。`files` 与 `pending` 为空，实际表和服务器字节在编译时生成。撤销这个 change 撤销整个操作序列，不是单独撤销序列中的一步。

编辑命令的全局参数必须写在子命令之前。注意此处 `--tip 236` 是小版本整数；前面的 `wf boss --tip 1.4.236` 接受完整版本字符串。

```powershell
python -m wf.studio.draft --drafts work/studio-drafts --tip 236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --server-dir inputs/server boss hard_multi:1006/1
python -m wf.studio.draft --tip 236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --server-dir inputs/server boss hard_multi:1006/1 --request work/boss/edit.json --preview
python -m wf.studio.draft --tip 236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --server-dir inputs/server boss new --request work/boss/create.json
python -m wf.studio.draft list --boss
python -m wf.studio.draft show hard_multi:1006/1 --boss
python -m wf.studio.draft save hard_multi:1006/1 --boss
python -m wf.studio.draft revert hard_multi:1006/1 c-0123456789ab --boss
```

`--preview` 只计算候选及检查，不写草稿。去掉它才执行修改。新建响应里的 `questId` 是随后读取、修改、保存和生成所用的身份；不要拿 `sourceQuest` 代替新身份。`--manifest-extra` 和 `--zip-dir` 可以重复。新建需要完整的只读服务端奖励输入，参数编辑也建议提供同一服务端镜像以完成关联检查。

## HTTP API

`<quest>` 使用 URL 编码后的 selector，例如 `hard_multi%3A1006%2F1`。裸数字的唯一性规则与 CLI 相同。接口与 CLI 共用 `BossEditor`、`BossDraftStore` 和交付桥，不另外维护生成实现。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/boss` | 副本列表及分组 |
| GET | `/api/boss/<quest>` | 当前候选详情、草稿、检查和 `runtime` |
| GET | `/api/boss/drafts` | 独立副本草稿列表；每项附 `status`、`requestCount`，新建草稿附 `created`（名称、模板来源、分配） |
| GET | `/api/boss/drafts/<quest>` | 与角色草稿同形的草稿视图：`changeset`、`status`、`actions`（保存 / 生成 / 导出可用，应用 / 发布不开放） |
| GET | `/api/boss/templates` | 新建共同决战的模板来源白名单及排除原因 |
| GET | `/api/boss/options` | 当前视图可选的 BGM 组（`battle_bgm_group` 键）和场景（`field` 键） |
| POST | `/api/boss/drafts` | `create_shared` 新草稿 |
| POST | `/api/boss/drafts/<quest>` | `edit`；新草稿也通过此接口继续修改 |
| POST | 上述两个修改地址加 `?preview=true` | 只预览同一请求 |
| POST | `/api/boss/drafts/<quest>/save` | 请求体 `{}`，保存并校验草稿 |
| POST | `/api/boss/drafts/<quest>/changes/<change>/revert` | 请求体 `{}`，撤销 boss change |
| GET | `/api/boss/deliveries/defaults` | 来源版本、本地候选目标版本及默认 provides |
| POST | `/api/boss/drafts/<quest>/build` | `{"from":"1.4.236","to":"1.4.240","provides":"inputs/client-provides.json"}` |
| GET | `/api/boss/deliveries?cid=<quest>` | 副本交付列表；query 参数也须 URL 编码 |
| GET | `/api/boss/deliveries/<name>` | 交付报告、成员、服务器变更、检查与文件清单 |
| GET | `/api/boss/deliveries/<name>/file?path=delivery/check.json` | 读取指定交付内文件 |

全部请求检查回环 Host 及端口。POST 还要求 `X-WF-Studio-Token`、`Content-Type: application/json`；浏览器 Origin 必须同源或属于明确配置的允许来源，拒绝 `Sec-Fetch-Site: cross-site`。本机非浏览器调用可省略 Origin。会话令牌由服务写入草稿根 `.session.json` 并注入页面 meta。守卫失败为 403，错误内容类型为 415，非法 JSON、schema、选择器或参数为 400。

`/api/boss` 的每个 `items` 项另附 `recommendedElement`、`restrictedElement`（quest 原值）、`fieldData`、`bothBoss` 与 `mode`，`groups` 附 `mode`，顶层附 `modes`（含分组依据）。`mode` 只用于界面分组：`main_lord` 是场景以 `mod_mainboss_` 命名的领主战节点（命名归类），`five` 是领主战节点 99，`other` 是全部由隐藏关组成的领主战组（锚点），阶段链的隐藏关随所在组归类；它不改变选择器和规则。

修改预览 `ok=false` 返回 400。被规则阻断时 `checks[0]` 仍是 `boss.inputs` 汇总，其后附上全部五态结果（含未阻断项），界面据此标出阻断规则；每条结果带 `quest`（所属副本选择器），五档修改可以区分档位。生成接口可能以 HTTP 200 返回 `ok=false` 和错误报告，调用方必须读取 JSON 的 `ok`、`error`、`checks`、`compatChecks`，不能仅以 HTTP 状态判断交付成功。服务端异常与检查失败不会被标成设备验证通过。

## 编辑台界面

编辑内容 → BOSS工坊。路由：`#/content/boss` 总览，`#/content/boss/q/<URL 编码选择器>[/encounter|terrain|rewards|shop|behavior|params|changes]` 副本详情（旧链接 `/moves` 落到 `behavior`），`#/content/boss/new[/<模板来源>]` 新建共同决战。

- 总览按模式分组（主线领主战 / 官方领主战 / 共同决战 / 五重决战 / 练习木人 / 其他），卡片显示 boss 名、副本属性、档数与等级范围、来源层（官方原版或补丁版本，完整来源在悬停提示）。可按名字 / quest ID / 场景搜索，按属性、来源、有无草稿筛选；`/` 聚焦搜索，回车打开第一个结果，方向键在卡片间移动。本地新建、尚未进补丁的共同决战单列。
- 详情三栏：左列同组难度（五档、五重的隐藏关等），中间「遭遇」（入口、关卡数值、场地与波次、敌人档位与站位）、「奖励与商店」（score / rare 原值、商店分类、商品、武器），右列检查。来源以小标签显示，悬停给出整叶来源语义；原始列号收在「技术细节」。
- 「调整参数」只发送改过的字段，约 0.6 秒后调用预览接口；右列显示五态结果，有阻断时「写入草稿」不可用。改属性得到 C8016「待验证」时须勾选确认（写入 `acknowledgePreload`）；「问题」（已知缺垫片或黑名单）不能确认放行。叶子恰为 1–5 的领主战组可「五档一起改」，草稿挂在第 1 档。BothBoss 入口（五重 1099001 等）只读并说明原因；五重隐藏关可改但提示构建器会覆盖。
- 新建共同决战向导：左列白名单来源，中间名称与难度（默认 Lv100、HP ×1.5、攻击 ×1.3、限定 / 副本属性取来源属性），右列预检；预检结果显示将分配的活动 / quest / 目录节点 / zone / 奖励组（保存时重新分配）。写入后跳到新草稿的「本次修改」。
- 第二期三页（接口见 [boss-authoring.md](boss-authoring.md)），每次提交一个操作：约 0.6 秒后预检，右列显示该页当前操作的五态结果，阻断时不能写入；写入后本页按新草稿修订重新读取。
  - 「地形」：逐层画 1080×1920 战场（边界框 ×6）——边界、9 个复活位（队-成员）、命名站位、boss 初始位置（zone 站位或 esdl `initialPosition`）、墙与出口；routine c50 引用的站位标「行为引用」。拖动或点表格行移动站位、新增站位（必须填坐标、整个落在本层边界内，否则不发送）；「换地形」从当前视图已有地形（field_data c1）中选，左右对照当前与换后，原站位按边界原点平移；「追加一波」选同推荐属性的来源层和可选转场出口来源，表格对照现在 / 追加后的场景 c7、c8（追加后取自预检结果）。
  - 「商店与武器」：分类商品表（价格、库存 / 周期限购、开放、奖励），可改价格与库存、下架；武器卡显示图标、数值、魂珠 / 强化词条（kind 名取角色词条编辑器同一份清单）、到 120 的强化链和累计材料，可改强化材料（羁绊证 userCost 只开放 type 2）；「克隆武器」五步向导（母本 / 名称与数值 / 词条 kind 与强度 / 已有图标引用 / 确认），确认页显示预检分配的新武器 ID 与 6 个强化商品 ID。顶部汇总最近一次预检的三处同步、C8004 与 kind 落位结果。
  - 「行为」：首领切换；GeneralBoss 出招槽（触发它的状态）可同首领换招、跨首领借招、改伤害倍率（乘数）；状态表可搜索、按有出招 / 定时 / 试炼筛选，GeneralBoss 与 StandardBoss 都可改定时帧数与试炼阈值。每个出招与状态动作都有「预览」：优先用 `/api/boss/<关卡>/timeline-summary` 中同程序或同槽的条目，没有则用出招 DSL 路径调 `/api/studio/timeline`（基线视图，不含本草稿换招）。
  - M6.1 后开放：GeneralBoss 状态表的改间隔（c46/c47 类型 2 定时）/ 改试炼（c22–c26 次数，技能连锁 4–9），routine 改名时自身 watch 整棵复制；出招槽「借招」填来源首领代码与槽号（同等级档），C8016 预载、循环、CustomPosition 站位与图集预算都在预检里拒绝；地形命名站位每行「删除」，被 c50 / 动作闭包引用或证据不完整都拒绝（C14102）；每个商店分类「新增商品」从本分类克隆一行，上架默认 2000-01-01、下架留空 = 不结束，来源已过期（早于服务端固定时刻 2025-08-05）给非阻断提示。
  - 只读辅助接口：`GET /api/boss/terrain-preview?path=`（解码一个已有地形）、`/api/boss/weapon-icons`（有 PNG 的装备 c6 / 强化 c4 图标引用）、`/api/boss/icon.png?path=item/...`；`/api/boss/options` 多了 `terrains`。
- 「本次修改」抽屉与角色工坊同一套保存 / 生成 / 导出：生成在后台跑、显示阶段进度，结果写 `work/studio-deliveries/boss/`；导出列出这一副本的交付。真机一栏始终「未记录」。

## 五态规则与证据边界

规则结果使用 `满足`、`问题`、`待验证`、`不适用`、`未执行` 五态；`blocking` 独立说明是否阻断。每项保留 `rule`、`message`、`evidence_nature`、`source`、`rule_version`。源码推断和经验推测不升级为真机实锤，静态检查通过也不替代客户端运行。

当前规则针对实际候选视图检查：

- 多波地形与 field c7/c8 动画、每层边界/墙/回球线/命名站位、协力 9 个复活位、非末层出口，以及 zone/地形波次引用。
- 单人和多人各自槽位的同屏 boss 站位冲突；活动敌人的原生等级档是否存在。
- 属性变化后召唤物预加载是否覆盖实际资源；不能用未经调用的文件或未消费的标记槽代替有效证据。
- 选门数量与层级、`BothBoss` 路由、自制内容时间和前置条件、新 ID 冲突。
- 客户端与服务端 score/rare 奖励键及商店分类、商品、类别映射闭合。
- 三人房图集预算；缺完整编队/敌人图集输入时保留不完整状态。

额外设计上下文通过 `wf check boss --context` 提供，例如选门意图或三人图集资源列表；上下文不是资源证据的替代品。阻断问题会在草稿预览/保存或编译阶段拒绝。未覆盖的玩法行为、客户端能力和真机结果保留「未执行」；`runtime` / `deviceValidation` 均不由本地生成改为已验证。

## 复用本地交付链

先取得修改或新建响应里的副本身份，再使用 `build --boss`。以下版本只是调用示例，目标版本必须向前且在输入链中尚未占用：

```powershell
python -m wf.studio.draft build hard_multi:1006/1 --boss --from 1.4.236 --to 1.4.240 --out work/boss/delivery-example --baseline-manifest inputs/manifest.json --baseline-zip-dir inputs/patches --base-store inputs/store131/upload --server-dir inputs/server --provides inputs/client-provides.json
```

生成复用 [`wf/studio/deliver_bridge.py`](../../wf/studio/deliver_bridge.py) → 既有 `wf deliver` / prepush / `wf check` / compat 链。`--from` 必须等于草稿 `baseView`，解析精确基线后验证摘要；可以通过 `--view-lock` 读取锁定视图，输出记录 `baseline.lock.json`。还支持重复 `--baseline-manifest-extra`、重复 `--baseline-zip-dir`、`--base-version`、`--pathlist`。HTTP 构建使用编辑器来源视图及相同服务器输入，输出位于 `work/studio-deliveries/boss/`。

`--out` 必须是当前 checkout 内的空目录，不能与草稿目录重叠。纯无变化请求不能生成空交付；客户端按精确 CDN 根逐字节剔除相同成员，服务器按输入摘要及键合并生成。产物包括：

- `inputs/changeset.json`、内容寻址 blobs、草稿与编译检查快照，可由原有交付工具再次消费。
- `delivery/` 内不超过 5 MiB 的 ZIP、legacy 与 upstream layered manifest、common/medium/android 三根的归档信息、`requires.json`、prepush、奖励检查、前后摘要断言、基线锁与 `SHA256SUMS`。
- `delivery/draft-checks.json`、`delivery/check.json`、`delivery/compat.json` 及顶层 `build-report.json`。报告 `compat` 是状态字符串，逐项结果在 `compatChecks`，草稿规则原始结果在 `draftChecks`。

`provides` 必须描述实际目标客户端的能力和方法摘要，不能用版本号代替。缺少 provides 默认令 `ok=false`、`compat="未确认"`，CLI 非零退出。CLI 的显式 `--allow-unknown-client` 只允许缺少 provides 的本地交付，并在报告及清单留痕；它不把兼容性改为通过，也不能越过已提供客户端的真实缺能力问题。HTTP 可使用请求内的 provides，或服务启动时的 `--provides` 默认文件。

M6 在现有参数及共同决战模板上增加地形、关联商店商品、武器克隆与材料、现有行为参数和借招操作，并提供只读行为时间线。具体请求与边界见[第二期编辑接口](boss-authoring.md)。生成交付不代表已应用到服务器、已安装客户端、已公开发布或已完成三人真机验收。

## 维护与验证入口

读模型与来源测试见 `tests/test_boss_model.py`；规则测试见 `tests/test_boss_rules_*.py`；接口、身份、独立存储、请求校验与 CLI 路由见 `tests/test_studio_boss_routes.py`；草稿重放、二次编辑、五档、摘要漂移和 ID 互斥见 `tests/test_studio_boss_drafts.py`；候选规则及交付连接见 `tests/test_studio_boss_checks.py`；界面所用的分组、模板白名单、选项、草稿视图与阻断预览的完整结果见 `tests/test_studio_boss_ui_glue.py`。叶子来源历史按「同一不可变视图对象 + 同一 ZIP 列表与 store」缓存，编辑台每次预览不再重解析全部历史表；草稿叠层（带 `changes`）从不共享缓存。新增规则应保留证据来源与五态语义，并通过同一候选编译链验证。
