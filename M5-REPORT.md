# M5 副本工坊后端交付报告

本次完成副本读模型、规则门禁、参数草稿、共同决战模板，以及编辑台 API / CLI 到既有交付链的桥接。实现、测试、草稿、历史重建和验收包均写在本 worktree；其它资料只读。没有访问 m4-integrate，没有 push、发布、安装、服务器操作或设备操作。前端不在本次范围。

接口契约、字段含义、请求示例和验证状态见 [副本工坊文档](docs/studio/boss.md)。机器摘要见 [验收摘要](docs/m5/validation.json)。包含原始游戏资源和机器绝对路径的证据保留在忽略的 `work/m5/`，不纳入版本控制。

## 实现与边界

| 模块 | 实现 |
|---|---|
| `wf/boss/` | quest、入口、field、zone、地形波次、实际敌人等级档、奖励、商店与武器关联；来源记录区分整表覆盖层和叶子语义变化层 |
| `python -m wf boss list/show` | 指定版本链读取，JSON 输出和视图锁；同名 ID 需使用 `kind:path` selector |
| `wf/rules/`、`wf check boss` | 任务书十一项规则、额外撞号与敌人档位规则；每项保留依据性质、五态结果及阻断标记 |
| `wf/boss/parameters.py` | 等级、三类 HP / 攻击修正、限定 / 推荐属性、现有 BGM 组、独立场景引用、五档数值 |
| `wf/boss/template.py` | 官方暗凛 1006 骨架，复制已有遭遇，分配 quest/event/zone/节点/奖励组，挂入终始之战页 |
| `wf/studio/` | 独立 boss 草稿目录、schema、原有 Host / Origin / token 守卫、预览 / 保存 / 撤销 / 交付路由，复用已有 delivery bridge |

草稿保存可重放的操作和输入摘要；编译时重放、重新校验输入与规则，来源漂移会被拒绝。服务端按键合并，客户端使用原有压缩叶保留方式。缺失的可选服务端表保留 `null` 前置摘要，与已存在的空 JSON 文件区分；新增文件和后续漂移均有实际 assert-box 回归。场景编辑派生副本专属 `field_data`，不会修改其它副本共用的场景引用。裸 ID 冲突不猜测类型，完整 selector 可以区分领主战、共同决战和练习。

quest 的 BGM 字段是 `BattleBgmGroup` 键。校验直接读取 `master/battle/asset/battle_bgm_group.orderedmap`，不以音频文件存在或其它 quest 使用过该值替代主表外键检查；有效但尚未使用的组可选，无组的音频文件会被拒绝。

规则落实情况如下。这里的「真机实锤」是规则来源的证据性质，不是本次做过设备验证。

| 要求 | 规则与检查输入 | 依据性质 |
|---|---|---|
| 多波 c7/c8 | `boss.multiwave-field`，实际地形 objectgroup 与 field 行 | 源码推断 |
| 每层边界 / 站位 / 9 复活位 | `boss.terrain-layers`，逐层解析实际地形；支持原生 WALL 数字后缀 | 源码推断 |
| 同屏 boss 站位不重复 | `boss.concurrent-positions`，单人 / 多人各自槽位 | 源码推断 |
| 改属性的 C8016 垫片 | `boss.element-preload`，实际召唤 DSL、marker 空槽和完整预载树；不采信声明布尔值 | 真机实锤 |
| 三选一在 folder 层 | `boss.choice-folder`，设计上下文中的层级与选择数量；未提供意图时为未执行，不自动推断入口选择语义 | 源码推断 |
| BothBoss 只作路由 | `boss.both-route`，隐藏关 group/map/default 引用 | 源码推断 |
| 自制开放时间 | `boss.custom-time`，quest/event 固定起始 2000 年、无结束时间 | 作者规范 |
| 奖励客户端键 | `delivery.reward-keys`，直接复用 M2.1 检查器 | 源码推断 |
| 商店三处同步 | `boss.shop-sync`，客户端商品、服务端商品与 category_map | 真机实锤 |
| 三人房图集预算 | `art.atlas-budget`，候选 PNG 尺寸和三队输入；缺项明确报告 | 经验推测 |
| 共同决战无前置 | `boss.visible-prerequisites`，自制 quest c7–c16；不改官方原有解锁条件 | 源码推断 |

额外门禁包括实际分配键撞号，以及活动波次内已知敌人没有可选等级档时阻断。原生档位按客户端键顺序选择，不以排序后的键替代原生行为。未知敌人种类不会伪装为已核验。

## 1.4.236 实际盘点

验收固定到本地可读清单的 `1.4.236`，读取 131 个 ZIP、1,469 个叠层成员。主清单当时已含 237，但没有把 237 纳入基线。230–236 使用本地 `shipped` 材料。清单和同名包存在多条历史，依据摘要选择正确来源，没有以文件名相同当作内容相同。

| 范围 | 本次实际读回 | 与制作流程总结 §5 的关系 |
|---|---:|---|
| 主线领主战 | 9 个节点、45 个难度叶 | 9 个领主口径一致；80–88 每节点五档 |
| 自制共同决战 | 27 个活动、27 个 quest | 27 个口径一致 |
| 五重 | 节点 99 下 39 个叶 | 包含隐藏路由与变体；不能称为 39 个可见入口 |
| 木人练习 | 114 个叶 | 总结未给底层叶数，本次补充；身份使用表键，不能使用 c0 |
| 领主商店武器 | 关联 108 把，其中 54 把为 145→146 新增 | 总结所说 54 把是新增领主武器；其余为原有官方关联商品 |

上述目标合计 **225 个 `show` 全部读回，缺失敌人引用为 0**。完整 `list` 包含官方等其它现存内容，共 471 个 quest、123 个分组。来源层来自整条历史链的叶子语义比较；例如后续整表覆盖不代表每条旧关卡在该层新增。

证据：`work/m5/evidence/boss-reader-236-final.json`、对应 `.lock.json`、`inventory-236.json`。地图、敌人、奖励、商店的每个关联对象附带来源；场景命名推导的商店关联另外标为推断。

## 历史共同决战重建

使用本次 `template_rows`，以官方 `hard_multi:1006/1` 为结构模板、主线奥格 `1081005` 为遭遇来源，在 145 视图下采用历史 ID：event 2081、quest 2081001、folder 2/node 5、zone/field_data `mod_mainboss_org_hard`、奖励组 11000935。历史 ID 仅用于纯函数对照，不绕过新建时的撞号门禁。

| 表行 | 比较结果 |
|---|---|
| quest | 130/130 格语义一致 |
| zone | 1 行全部格一致，包含奥格自身机关 |
| field_data | 3/3 格一致 |
| event_folder_events | 3/3 格一致，即 `13,2081,5` |
| hard_multi_event | 26 格中 21 格一致，以下 5 格不同 |

差异逐格解释，列号从 c0 开始：

| 列 | 新模板值 | 历史值 | 原因 |
|---|---|---|---|
| c0 | `studio_shared_2081` | `hard_multi_mainboss_mod_mainboss_org` | 内部标识采用本期命名；历史为当时制作的标识 |
| c4 | `quest/event/banner/hard_multi/hard_multi_event_steam_robot_dark` | `quest/event/banner/hard_multi/mod_mainboss_org` | 历史手工提供奥格横幅；本期继承暗凛模板美术 |
| c5 | `quest/event/bossbattle_banner/hard_multi/hard_multi_event_steam_robot_dark` | `quest/event/bossbattle_banner/hard_multi/mod_mainboss_org` | 历史手工提供战斗横幅 |
| c6 | `quest/event/animation_background/hard_multi/hard_multi_steam_robot_dark/background` | `quest/event/animation_background/hard_multi/mod_mainboss_org/background` | 历史手工提供活动背景 |
| c7 | `quest/event/logo/hard_multi/steam_robot_dark/steam_robot_dark_logo` | `quest/event/logo/hard_multi/mod_mainboss_org` | 历史手工提供 logo |

145 到 236 还有三个后续变更：quest c71 奖励组由 `11000935` 改为 `12100081`，event c16 从 `49300` 改为 `10000403`，c17 从 `(None)` 改为 `49300`。这些来自 146 的领主武装配套，不是 143–145 原模板差异。本次按 145 作历史验收，没有拿 236 的奖励行冒充原始制作结果。

证据：`work/m5/acceptance/reconstruction145.json`、`work/m5/evidence/template-org-cell-differences.json`。

## 草稿、交付和反证

从冻结的 236 只读基线创建「M5验收共同决战」草稿，分配 quest `2100001`、zone `studio_shared_2100`，保存后通过已有交付链输出本地候选。`236→237` 仅是固定历史基线上的本地验收版本，不是为当前共享链申请新版本，更没有覆盖现有 237 包。

验收包包含 **1 个 ZIP、7 个客户端成员、3 份服务端文件**。最终 ZIP 为 **638,783 字节**；服务端目标为 `assets/hard_multi_event_quest.json`、`assets/score_reward_cnmod.json`、`assets/rare_score_reward_cnmod.json`。结构、CRC、成员摘要、清单、前后断言、兼容性检查和奖励检查通过。解包后重新组成视图，入口、quest、zone、单波地形、9 复活位、实际敌人和奖励均完整。

逐叶和逐键保留核验结果：**16,934 个既有压缩叶逐字节一致，150 个既有服务端值的 JSON 原文逐字节一致**。交付 SHA256SUMS 中 23 个文件全部匹配。服务端输入目录没有写入。

| 反证 | 实际候选输入 | 结果 |
|---|---|---|
| 多波缺 c7 | 基于真实 1006 地形构造两波候选，清空 field c7 | 预览与编译均拒绝，C8251 |
| 改属性无垫片 | 真实深界王删六条垫片并改推荐属性，另伪造布尔声明 | 预览与编译均拒绝，不采信声明 |
| 撞号 | 请求已存在 event 或节点 | 分配阶段拒绝；自动分配还排除其它新草稿占用 |
| 奖励缺客户端键 | 新服务端奖励保留，删除对应候选客户端组 | 预览与编译均拒绝，复用 M2.1 |

最终交付目录为 `work/m5/acceptance/new-shared-final-v2/`；解包证据为 `work/m5/acceptance/roundtrip-final-v2.json`、`unpacked-boss-final-v2.json`。反证见 `work/m5/rules-evidence/negative-candidates.json` 和 `summary.json`。API 回归还检查跨来源、混合 character/boss 草稿、路径穿越、Host / Origin / token 守卫及交付目录隔离。

另用真实 236 视图完成三类参数预览：奥格五档等级 20/40/60/80/100、HP 与攻击倍率、限定属性、实际 BGM 组和场景；官方共同决战 1006；木人 practice 1001。五档只修改五个 quest 叶并新增五个独立 `field_data`，每个新引用只归对应难度所有；共同决战和木人各只改变一个 quest 叶，其余叶保持一致。这三项预览没有落草稿或服务端改动。证据为 `work/m5/evidence/boss-parameters-preview-236.json`。

## 验证状态与可复查材料

最终全量 pytest **exit 0：4,401 passed、354 skipped、26 warnings，686.82 秒**。跳过项保留项目原有外部输入条件，26 条警告为旧路径环境变量的弃用提示。运行基于功能与回归提交 `ffb6ec2`；后续只增加本报告和验收摘要。

```powershell
python -B -m pytest --basetemp work/m5/full-final-routes-tmp --junitxml work/m5/pytest-full.xml -o cache_dir=work/m5/pytest-cache
python -B scripts/check_no_hardcoded_paths.py --json work/m5/path-scan.json
```

最终路径扫描 **0 项**，提交卫生检查和 `git diff --check` 通过。CLI 的真实 list / show / check 三条命令均 exit 0，JSON 与 Python 模型逐对象一致；这些结果不替代带完整上下文的规则验收。全量日志与 JUnit 结果分别位于 `work/m5/pytest-full.log`、`pytest-full.xml`。

历史回归均在本次实际重建：223 为 **3/3 成员逐字节一致**；221 从原始四角色表、母图和已批准音频重建，**11 包、310/310 成员逐字节一致**，三层回读 310/310 一致。221 的 ZIP 容器写入时间不同，排除 DOS 时间字段后 11/11 容器一致；不能把容器 SHA 不同描述为完整 ZIP 原字节相等。该项是历史编码 / 归档回归，不表示带旧 PF3 的 221 通过当前公开交付门禁。详见 `work/m5/evidence/replay223.json`、`replay221.json`。

最终正向验收包检查没有阻断项，但保留以下证据边界：

- 旧 prepush exit 0；其 kulo#35 `checkPatchChainIntegrity` 因隔离快照没有所需服务端编译入口而未执行。既有交付器自身的版本顺序、seq、重复、缺包及前后摘要检查已实际执行。没有为消除提示去构建、启动或修改服务端。
- prepush 保留实际警告，不能把 exit 0 写成零警告。最终包为 ERROR 0 / WARN 43 / INFO 10，其中 5 条等级警告涉及既有关卡的 variable 档位；225 项「缺失敌人引用为 0」不表示所有变量档位完整。
- 图集规则已接入。官方 1006 的实际资源可确定四张 PNG，去重加边距面积下界为 **1,048,242 px**；三队 18 角色与技能/PF/召唤闭包、部分 StandardBoss 间接资源及 APK 内置效果尚无完整输入。三人房预算因此保持「待验证 / 未执行」，没有把历史约 15.2Mpx 失败记录写成固定阈值或通过依据。
- APK provides 来自仓内 v34 静态补丁证据，只用于声明匹配；没有声明本次 APK、真机或三人房运行成功。通用规则目录中不属于本期参数 / 模板操作的试炼 esdl 等检查同样保留真实状态。

所有原始证据和日志在 `work/m5/`，可在本机复核；本地提交仅含实现、回归测试、接口文档和去机器路径的验收摘要。
