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

## M5.1：审查修复与文案规则

本节对应 `M5.1-任务书.md` 与 `M5-审查意见.md`，在 `63625fc` 基线上完成。全部写入限定本 worktree，外部输入只读；未访问 `m4-integrate`，没有 push、服务器操作、设备操作或原文修订。新增运行证据位于忽略的 `work/m51/`，不覆盖 M5 原验收材料。实现按主题拆分并完成本地提交；接口更新见[副本工坊文档](docs/studio/boss.md)，验收机器摘要见 [M5.1 validation](docs/m5/m51-validation.json)。

| 项目 | 最终行为 | 反证与证据 |
|---|---|---|
| H1 | 属性变化后的 C8016 待验证默认阻断；显式 `acknowledgePreload=true` 留在请求与检查记录中，仅豁免同一推荐属性及敌人资源行范围的未证明风险。已知问题、黑名单不能豁免；逗号 DSL 引用逐个遍历；交付失败判定包含草稿 checks | `test_boss_rules_preload.py`、`test_boss_rules_real.py`、`test_m51_boss_studio.py`；真实大恶魔 1/12/1 推荐 c72 `4(暗)→5(光)` 预览 `ok=false` |
| H2 | 按实际选中档位 c42 routine 收集 state c50，并逐层与 CUSTOM_POSITION 求差 | `test_boss_rules_terrain.py`、`test_boss_rules_real.py`；真实寄居蟹 1/10/3 等级 70→100 缺 p4 被拦，官方 1/10/4 带 p4 满足 |
| M1 | BothBoss 路由入口拒绝编辑及模板来源，入口敌人/地形标「入口自身，非战斗内容」，列出隐藏关 | `test_boss_entry_boundaries.py`；真实 1099001 两条编辑路径拒绝，maps 对应 16 个去重隐藏关 |
| M2 | 草稿自动传入候选遭遇 PNG 面积下界，可补三队清单；去重加边距面积 `>4096²` 直接阻断；对照历史最大值报警 | `test_m51_boss_studio.py`、`test_boss_rules_integrity.py`；包含恰好容量、超限、自动收集及预览/编译反证 |
| M3 | 自动分配排除客户端、其它草稿、四奖励 JSON 和 hard_multi_event_quest 键；base/cnmod 奖励同键均拦 | `test_boss_server_allocation.py`；真实输入共 3,895 个服务端占用键，正常顺延分配 |
| L1 | 商店增加 boss_coin_shop_category 同号行核验，缺少服务端输入也不能掩盖已知缺行 | `test_boss_rules_integrity.py` 的分类缺行反证 |
| L2 | 推荐属性同步实际有效服务端 quest 的 element；缺键阻断；新模板同样带 element | `test_boss_server_parameters.py`；真实 1012001 同步后，254 个无关服务端 value 原文逐字节不变 |
| L3 | field_data、field、zone、地形与引用 routine 悬空均判问题 | `test_boss_rules_terrain.py`；缺失引用和无关完整对象成对反证 |
| L4 | 两个 boss CLI 默认跟随 manifest 最高启用版本的完整依赖链，缺链拒绝；write-lock 走 local_output | `test_m51_boss_cli.py`；新链尾、禁用条目、缺链及外部输出路径反证 |
| L5 | 模板名称拒绝换行、单双/弯引号及 `::`，回读重放同样生效 | `test_boss_name_validation.py`；保留合法逗号的允许反证 |
| L6 | 已有副本两种写法归到同一 selector 草稿；新建草稿的合法 hard_multi 别名也归到同一分配 ID | `test_m51_boss_studio.py`、`test_m51_boss_aliases.py`；错误类型、错误难度、事件号不匹配、基线歧义均拒绝 |
| L7 | 读模型增加 field_sources_semantics，文档明确逐字段位置附的是整叶来源 | `test_boss_entry_boundaries.py`；明确 `column_origin_verified=false` |
| L8 | 编辑台不再伪造 choice_count=1，choice-folder 明确「本期未接入」并保持未执行 | `test_boss_rules_integrity.py`、`test_m51_boss_studio.py`；外部显式设计上下文的独立 checker 仍可使用 |
| D3 | 根据真实槽行 c0 精确关联 desc_override；全部覆盖串检查「自身为队长时」，草稿编译回读实际字节 | `test_m51_text_rules.py`、`test_m51_text_bridge.py`；无后缀键 `desc_override_lady_android_halloween` 注入禁语会阻断 |
| D4 | 禁止觉醒双值、字面Ⓜ和多效果压行；整槽主位限制逐非空行检查精确前1后2空格图标 | `test_m51_text_rules.py`；含多行漏图标、错误空格、混合主位槽、属性/姓名枚举允许反证 |

真实 236 全量地形/routine 回归覆盖 471 关：地形规则 471 项满足，多波规则 18 项满足、453 项不适用，新增阻断 0。H1/H2 另经真实 BossEditor.preview 验证，均为 `ok=false`；没有把规则单测冒充 API 预览或真机结果。

图集实读结果：官方共同决战 1006 收集 7 张、809,210 px；五重隐藏关 1099031 收集 18 张、5,847,162 px；奥格 1/81/5 收集 9 张、4,165,717 px。以上均为当前候选可解析直接资源及动作引用的**下界**，状态为待验证。特殊敌人、召唤属性变体及三队完整技能/PF闭包仍有缺口。历史对照来自 1.4.210：随机三人房最大 14.61Mpx、失败区间 15.2–16.2Mpx；1099031 来源会明确报警。历史数字不是当前通过阈值，也不是本次三人房运行结果。

文案依据明确禁止 `X%（觉醒后 Y%）`：相关列是词条低/满级，不能解释为觉醒前后。按照任务指定三份作者记录落实，完整报告见 [1.4.227–1.4.237 文案只读审计](docs/m5/m51-text-audit.md)。本次扫描全部 11 个版本，仅出报告：227–229 各有 17 项 D3/D4 命中，从 230 起消失；230–237 新增规则命中为 0。237 其他既有客户端规则仍有 61 项命中，其中 32 项位于 227 起改过文本，不能宣称所有文案规则已通过。完整服务端镜像仅在 232/237 可得，其余版本如实标未执行。

139985 的实际精确覆盖键在全部 11 个版本都被查到；当前原文为「雷属性共鸣时……」，没有「自身为队长时」。测试中的禁语是人为注入反证，未修改任何源文本。报告列出 56 组重点问题全文与槽位证据，保留逐版本全量结果与输入摘要。

历史字节回归均使用本轮当前实现重新执行：223 的 3/3 成员一致；221 从原表、母图及原已批准音频重建四角色，再经当前交付器重归档，11 包、310/310 成员逐字节一致，三层回读 310/310 一致。221 容器仅在排除 DOS 时间字段后 11/11 一致，不声称完整 ZIP SHA 相等；历史旧 221 的字节兼容性不等于通过当前公开交付门禁。

最终全量 pytest **exit 0：4,485 passed、354 skipped、26 warnings，562.50 秒**，基于 `6ff50c8` 运行。跳过项保留项目原有外部输入条件；警告为旧路径环境变量弃用提示。路径扫描 **0 项**，`git diff --check` 通过。此前一轮仅因审计报告中的机器绝对路径未满足卫生检查而失败，该行已改为本地配置引用，定向 5 项及本轮完整重跑全部通过。

详细统计、输入保留边界与证据摘要记录在 `docs/m5/m51-validation.json`。本地复现命令：

```powershell
python -B -m pytest --basetemp work/m51/full-verified-tmp --junitxml work/m51/pytest-full-final.xml -o cache_dir=work/m51/pytest-cache
python -B scripts/check_no_hardcoded_paths.py --json work/m51/path-scan-final.json
python -B work/m51/history/run_historical223.py
python -B work/m51/history/run_historical221.py
python -B work/m51/history/verify_historical221.py
```
