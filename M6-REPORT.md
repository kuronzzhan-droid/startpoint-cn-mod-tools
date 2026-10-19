# M6：BOSS 工坊第二期后端交付报告

本次在 `refactor/m5-boss` 分支、起点 `1507779` 上实施。写入范围限当前 worktree；冻结客户端版本链、服务端 JSON 镜像、客户端档案与反编译源码仅作只读输入。未访问 `m4-integrate`，未 push，未部署或启动业务服务器，未操作设备。

临时脚本、草稿、日志、ZIP 与完整核验记录都保存在被忽略的 `work/m6/`，不纳入版本控制。长期接口说明见 [boss-authoring.md](docs/studio/boss-authoring.md)。本报告记录本地代码、静态检查和交付包证据，不将其写成运行中服务器或真机结果。

## 功能与调用入口

| 范围 | 已实现 |
|---|---|
| 地形读取 | objectgroup、BOUNDS、9 个复活位及队伍/成员映射、命名对象、CUSTOM_POSITION、Tiled 原坐标和运行时中心坐标、field_data/field/zone/波次绑定 |
| 地形草稿 | 替换已有地形；新增、移动、删除命名站位；复制已有战斗层追加一波，自动补 field c7/c8 和转场对象 |
| 商店读取与编辑 | 领主币和魂珠商品、分类、价格、币种、库存与周期限制；商品增删改同步客户端、category_map 和服务端分类内商品 |
| 武器读取与编辑 | 装备、魂珠、强化词条、状态及到 120 级的材料链；克隆装备并改数值、词条、既有图标引用；编辑强化材料与 userCost |
| 行为读取与编辑 | GeneralBoss routine/marker/触发槽及 StandardBoss EnemyDsl 状态、试炼、免伤引用；同首领换招、跨首领借招、间隔、伤害倍率、试炼阈值编辑 |
| 无损编解码 | 客户端 TypePacker 导出的 104 个可达类型；可读字段、原始 wire 保存、JSON 往返及重编码 |
| 统一入口 | schema、BossEditor 预览/保存/编译、既有 build_draft 桥、客户端档案、HTTP 与 CLI |

只读 HTTP section 为 `terrain`、`shops`、`weapons`、`behavior`、`timeline`，路径为 `/api/boss/<URL编码的quest>/<section>`。CLI 为 `python -m wf.studio.draft ... boss <quest> --section <section>`。编辑继续使用原有草稿 POST 或 `--request`。`weapons` 和详情中的 `draftWeapons` 会显示已克隆但尚未上架的武器。

代码按资源字节、地形对象与操作、商品、武器、行为模型、编解码、隔离及门禁拆分；没有把全部逻辑塞入 HTTP 路由。新请求仍走同一预览、重放与编译路径，未增加第二套交付器。

## 数据保持与语义约束

- 地形、field_data、zone、敌人和行为资源采用当前副本拥有的派生键或路径。共享原件不改；基线已有同名派生资源会拒绝。连续地形、场景、行为操作能够复用本草稿拥有的资源。
- 换地形保留原 CUSTOM_POSITION 相对 BOUNDS 的位置语义，防止相同 `p1` 名称在两图中表示不同位置。追加战斗层必须与目标推荐属性一致；转场来源可单独借用。
- orderedmap 未改叶子的压缩字节保持；服务端 JSON 以键或分类内商品、商品内字段做局部拼接，未改 value 原文保持。无实际变化的成员不装包。
- 商品、武器和强化商品 ID 同时检查客户端、服务端与其它草稿。保存分配结果，编译时再检查其它草稿占用，防止保存后发生冲突。
- M2.4 真实 SWF 判定的 kind 列位：ability_soul 为 c44/c106，equipment_enhancement_ability 为 c47/c109；错误块、未被该 kind 消费的 strength 字段及不支持的 kind 拒绝。
- 图标引用使用现有装备/强化装备，并复用对应魂珠真实 c3/c4 组合；非空 c4 必须位于实际加载图集，独立 PNG 不能替代子纹理检查。
- 强化从 0 级开始，按各阶段等级差累计到 120；c11=2 表示羁绊证 userCost，不是按阶段只收费一次。克隆武器不会自动上架。
- 时间线以每个状态进入为 0 帧，60 fps；条件退出、循环和未知时长保留表达式或空区间。它是供前端使用的状态摘要，不是战斗模拟器。
- 伤害倍率编辑乘以所选动作闭包内已有 CreateNormalAttack 常量倍率；间隔只改 Time/TimeElapsed.Frame；试炼只改受支持的现有阈值结构。换招/借招时拒绝无限或过大 Repeat 与递归；所选动作或借招预载闭包缺失时也拒绝。参数编辑不把原生状态循环当成新借招。
- 帧间隔和 HitCountCheck 次数强制整数，拒绝客户端会静默截断的小数输入；DamageCheck 百分比允许小数，并验证写入后精确回读。
- 隔离改名前从当前候选扫描 damage_share、partner watch、GeneralBossAlive、StandardFunnel 反向引用。存在固定身份链接或扫描证据不完整时拒绝并说明链路，避免首领改名后断开伤害共享、死亡联动等机制；未扩大为整条机制闭包迁移。

## 真实副本交付与回读

验收使用冻结的 1.4.236 视图，分别建立独立草稿，保存后通过现有桥生成本地 236→237 候选包，再检验 ZIP CRC、解包、摘要和叠包读模型。所有真实构建显式选择 `test-v34`；它表示静态客户端档案匹配。

| 操作 | 真实副本 | 客户端成员数 | 保持相同的未改压缩叶 |
|---|---|---:|---:|
| 换地形 | `boss_battle:1/10/3` | 3 | 1,910 |
| 增站位 | `hard_multi:1006/1` | 3 | 1,631 |
| 改坐标 | `boss_battle:1/10/3` | 3 | 1,910 |
| 删站位 | 五重隐藏关 `1099031` | 3 | 1,910 |
| 追加一波 | `hard_multi:1006/1` | 5 | 3,398 |
| 新增商品 | `boss_battle:1/81/5` | 1 | 6,701 |
| 修改商品 | 同上 | 1 | 6,700 |
| 删除商品 | 同上 | 1 | 6,700 |
| 克隆武器 | 同上 | 8 | 5,483 |
| 修改强化材料 | 同上 | 1 | 920 |
| 同首领换招 | `boss_battle:1/81/5` | 6 | 8,742 |
| 跨首领借招 | 同上 | 6 | 8,742 |
| GeneralBoss 间隔 | 同上 | 7 | 56,414 |
| 招式伤害倍率 | 同上 | 7 | 8,742 |
| StandardBoss 试炼阈值 | `boss_battle:1/29/4` | 5 | 3,711 |
| StandardBoss 帧间隔 | 同上 | 5 | 3,711 |

上述 **16 项均 build ok=true、prepush exit 0，且完成解包回读**；最终包均显式使用 `test-v34` 客户端档案，各模块当前源码重放与最终交付字节一致。地形与行为交付服务端变更为 0。商店/武器五项还核对了服务端局部原文保持及两端分类、价格、库存、ID 注册、六阶费用引用；17 份源服务端文件摘要保持不变。

地形早期 `acceptance-1` 使用显式能力摘要，后续已在全新 `acceptance-profile` 目录为全部五项补做 `test-v34` 档案构建、ZIP 回读和当前源码重放；最终验收以新目录为准，旧结果保留作过程证据。

实际武器克隆为 5930011→5950001，六个强化商品 595000101–595000106，HP×1.1、攻击×1.2，魂珠词条 kind 34→32，使用已有 5930012 的本体和 70 级图标。材料操作将 593001106 阶段改为道具 10000402×12。另一副本在同一草稿存储预览克隆时自动分配 5950002。

行为六项均 `build ok=true`、prepush exit 0，并以 `a3ffedb` 当前代码重编译与最终 ZIP 逐成员摘要核对一致。每项仅改变目标 quest 的原有绑定叶，其余旧表叶及压缩叶保持；新增专属数据不覆盖原敌人或共享资源。

独立于编译器的实际 ZIP 语义核对也是 6/6：同首领 slot 2 确实采用来源 slot 3；跨首领采用五重水废龙 slot 11，2 个动作程序和 4 个特效预载资源均可读；GeneralBoss 原 30 帧改为 45 帧，其余 382 个状态和目标状态其它字段不变；一处 CreateNormalAttack 最小/最大倍率均由 0.15 的浮点表示乘以 1.2；光废龙试炼次数 40→45、另一状态间隔 120→95，两个 ESDL 各自其余全树不变。

## ESDL 完整语料验证

先验证当前 standard_boss 引用的 265 份资源，再将路径表中的 461 个 boss ESDL 名称、当前表引用及已提取目录中的 752 个文件名取并集。提取后的 JSON 只用于发现逻辑路径；实际原始字节全部从冻结 236 的 ManifestView 读取。

最终 **752 个候选、752 个可读、752 个通过，缺失 0、失败 0**。每份都执行 decode→`json.dumps(ensure_ascii=True)`→loads→encode，原始 deflate 字节 752/752 一致；另行从可读语义结构重建 AMF3，未压缩字节也 752/752 一致。原始压缩 wire 的保存用于精确往返，不将不同压缩策略的容器误判为语义差异。`view.verify` 通过，逐件 SHA256 与来源均留存。

任务引用的历史资料没有列出“官方六件”的具体文件名，原调查文档在指定只读目录中也已不存在。因此本次用可读官方 752 件全集覆盖验收，不把任意六个样本称为历史原六件。当前表引用的 265 件是该全集子集。

五重 v2 的 16 个隐藏副本检查了敌人、召唤、routine 和 DSL 闭包：17 个 routine、377 个 DSL，直接及间接 ESDL 引用为 **0**。这些副本实际使用 GeneralBoss 表驱动行为；不能虚构“若干五重 ESDL 往返”。其引用清单和表摘要另存于 `five-v2-closure.json`，行为借招的真实验收也使用了五重 v2 的既有招式。

## 反证与回归证据

| 任务要求或额外风险 | 证据 |
|---|---|
| 多波缺 c7 或 c8 | 真实追加波次候选分别清空两列；preview 和 compile 均 C8251 拒绝 |
| 商店缺同号 category | 真实分类 81 移除同号行，preview 拒绝 |
| 武器 kind 错位 | 将真实 soul kind 从 c44 放到 c47，preview 拒绝；同时核对 test-v34/test-v35e 实际 SWF |
| 借无有限终止保证的循环招式 | 保留完整真实 donor ActionDsl 元数据，仅用 Repeat(30, 0) 或 Repeat(30, -1) 包装原表达式；两者 preview 与保存后 compile 均拒绝 |
| 借超限循环招式 | 在真实借招来源动作加入 Repeat 9999 超限循环，preview 与保存草稿的 compile 均拒绝 |
| 借招缺预载 | 从真实来源候选移除对应 effect atlas，preview 与 compile 均 C8016 拒绝 |
| 图集错误 | 魂珠 c4 指向实际图集中不存在的子纹理，preview 拒绝 |
| 保存后 ID 冲突 | 两份已保存草稿分别制造入口、商品、装备、强化商品冲突；compile 全部拒绝 |
| 连续操作所有权 | terrain→scene→terrain、scene→terrain→scene、behavior→terrain→scene→behavior 回归；基线撞名拒绝 |
| 派生资源覆盖和重复借招 | 拒绝首次覆盖基线资源；允许复用本草稿已拥有的预载垫片和未触发槽 |
| 固定身份引用断链 | 真实 shark 三色随从的 79/100 档 c32 引用使其编辑被拒绝，候选零改动；StandardFunnel 固定引用的 steampunk_another_multi 同样拒绝 |

真实 damage 构建曾暴露既有 629 门禁的裸动作路径误拒。客户端加载链和实际 spheal 资源证明 `battle/action/...` 不必含 `$`；修复仅增加规范裸路径解析和递归检查。实际 damage 的 7 个原始成员字节通过门禁；往真实基线树的内存副本加入 `NotifyPowerflipEnd` 仍被拒绝。没有修改基线或放宽危险命令检查。相关 51 项针对测试及 3 项历史 629 测试通过，证据见 `work/m6/terrain/gate-review/`。

无限循环要求的反证依据来自原生 Repeat/ListeningEvent/ActionEvaluator 调用链：count 为整数，非正次数没有正常有限计数结束保证；外部销毁或整数回绕仍可能终止，因此不声称数学意义永久运行或已做设备证明。扫描 996 份原生敌人动作 JSON 的 1,557 个 Repeat 节点未发现非正次数；上述 0/-1 是按原生结构构造的真实候选反证，原始 donor 摘要保持不变。它与 9999 超限反例分别保留证据。

真实只读接口验证：3 个副本 × 5 个 section 共 15 次实际 StudioApp 路由调用均返回 200，CLI timeline exit 0，读取没有创建草稿。另有 Host、Origin、token 及请求/section 约束的定向测试。

历史回放使用本次任务生成的结果：223 的 3/3 个成员逐字节相同；221 从完整源资产重建，11 个归档共 310/310 成员、叠包 310/310 成员逐字节相同，旧清单语义一致。221 的 11 个 ZIP 在排除 DOS 时间戳后容器相同；不声称完整 ZIP SHA256 相同，也不声称历史包通过当前发布门禁。

## 全局验证与本地提交

最终功能代码为 `a3ffedb`。该提交的完整 pytest **exit 0：4825 passed、354 skipped、26 warnings，881.67 秒**，没有失败或错误。前两轮全量在新发现的身份引用、路径兼容和整数精度修复后主动终止，保留日志及 `superseded` 记录，不计作完成的全量证据。

最终路径扫描检查 **2,375 个文本文件，发现数 0**；`git diff --check` 和全仓已跟踪文件的提交卫生检查通过。最终验证数字及逐项证据 SHA256 见 [validation.json](docs/m6/validation.json)，全量日志保存在 `work/m6/full-verified.log` 与同名 JUnit XML。提交卫生日志保存在 `work/m6/hygiene-all.log`、`hygiene-staged.log`。

测试计数采用 pytest 终端汇总和外层进程 exit 0。原始 JUnit 含 5,179 个 testcase，无 error/failure，聚合头记录 7,556 tests、357 skipped，testcase 的 skipped 标记数也为 357。已只读核对本机 pytest 9.1.1 实现：unittest.subTest 会额外发送报告，终端不单列通过/跳过的子报告，JUnit 则累计它们并可能复用父 testcase 的 nodeid。因此这是统计粒度差异；按差值可推得额外 2,374 条通过、3 条跳过的子报告。原 XML 保持生成状态，机器摘要同时保留两种口径，没有把子测试统计混入主套件通过数。

最终全量命令使用独立 basetemp、pytest cache 与 TEMP/TMP，全部位于当前 worktree，子进程 stdin 关闭。可直接复现测试主体：

```powershell
python -B -m pytest --basetemp work/m6/recheck-temp --junitxml work/m6/recheck.xml -o cache_dir=work/m6/recheck-cache
python -B scripts/check_no_hardcoded_paths.py --json work/m6/path-scan.json
```

本地实施按主题分为以下提交；没有 push：

| 主题 | 提交 |
|---|---|
| 资源与服务端字节保持 | `00f2372` |
| 地形模型、编辑、预载与交叉操作 | `664cc01`、`ca5f6e7`、`e45d1bc`、`9438490` |
| 商店、武器与材料链 | `ae9f503` |
| 行为编解码、隔离、门禁及参数精度 | `b805808`、`89abea3`、`871f0b6`、`2eda7ec`、`a3ffedb` |
| schema/API/CLI 和编译 ID 避碰 | `8682929`、`189a6cd` |
| 真实 damage 交付需要的 629 裸路径兼容 | `bc1bb83` |

## 证据索引与验证边界

| 证据 | 本地相对路径 |
|---|---|
| 地形五项最终档案构建/回读 | `work/m6/terrain/acceptance-profile/summary.json`，各操作的 `roundtrip.json` |
| 地形最终源码重放 | `work/m6/terrain/current-profile-verification.json` |
| 商店武器五项构建/回读 | `work/m6/shop/acceptance-summary.json` |
| 商店武器最终源码和双端核对 | `work/m6/shop/current-verification.json`、`delivery-conformance.json` |
| 行为六项构建/重放 | `work/m6/esdl/acceptance-summary.json`、`acceptance-v2/<case>/final-replay.json` |
| 行为独立 ZIP 语义核对 | `work/m6/esdl/independent-conformance.json` |
| 真实分类/kind/图集反证 | `work/m6/shop/counterexamples.json` |
| esdl 语料和五重闭包 | `work/m6/esdl/codec-corpus.json`、`five-v2-closure.json` |
| 752 件官方全集 | `work/m6/esdl/official-all-summary.json`、`official-all-results.json`、`official-all-view-lock.json` |
| 行为真实反证 | `work/m6/esdl/real-negative-behavior.json`、`real-identity.json` |
| 非正 Repeat 反证及客户端语义 | `work/m6/esdl/real-unbounded-repeat.json`、`repeat-source-evidence.json` |
| 真实接口与 CLI | `work/m6/core/interfaces/summary.json` |
| 221/223 回放 | `work/m6/history/replay221.json`、`replay223.json`、`exit.json` |

prepush 保留了已知警告，没有把 exit 0 写成零警告：地形为 ERROR 0 / WARN 43 / INFO 10；武器克隆 WARN 29，其余商店武器 WARN 28。隔离快照没有 kulo#35 检查要求的服务端编译入口，该子项仍待验证；没有为消除提示构建或操作服务器。

三人图集估计继续保留 M5.1 的敌方下界和队伍输入完整性状态。本次没有三队完整角色/技能/PF 输入，没有真机、三人房、服务器部署或实际购买扣费验证。所有运行时结论均保持未执行；这些事项不在本任务授权范围内。

## M6.1：审查修复与时间线接口

本节对应 M6.1 任务书及 M6 审查意见，起点为 `1fb6633`，分支为 `refactor/m5-boss`。实现、测试输出与本地提交均限本 worktree；其它目录只读，未操作另一集成 worktree，未 push、部署、修改业务服务器或操作设备。新临时脚本、日志、回归产物与草稿保存在忽略目录 `work/m61/`，没有覆盖 M6 原验收证据。长期接口说明已更新到 `docs/studio/boss-authoring.md`。

### 修复范围与反证

| 任务项 | 最终行为与反证覆盖 |
|---|---|
| H1 watch | routine 改名完整复制自身 watch 子树，保留相位跳转及客户端从 watch 解析的预载。覆盖 interval/trial 两种参数、routine 与 code 同名边界，以及指定 boar 副本的实际预览、保存、编译与 watch 回读。 |
| H2 站位 | 合并 GeneralBoss、watch、递归 General Funnel 动作中的 CustomPosition，与 routine/esdl 站位共用门禁；同波同首领不同档位取并集。借招到缺少 IL* 的地形、删除被引用站位均拒绝；扫描输入不完整时拒绝删除。 |
| M1 商品时间 | shop_add/shop_edit 可设置 availableFrom/Until；新增默认 2000-01-01 起、无结束。两端同步，日期非法/倒置阻断，过期来源给出非阻断提示。 |
| M2 武器 | 克隆保留 materialByEquipment 限制及无关原文字节；受限来源缺证据拒绝。kind 校验使用交付所选 client_profile 或显式 provides 的实际 SWF，覆盖不同档案结果与未知客户端反例。 |
| M3 坐标 | add 缺少任一 x/y 拒绝；add/update 与换图后的站位完整矩形必须在该层 BOUNDS 内。覆盖非零原点、四边与尺寸越界、缩窄换图及 preview/compile 拒绝。 |
| L1 图集 | C8004 认可 item/item_icon/item_sec/scene/general 四类实际加载图集，仍拒绝缺成员或缺 PNG。 |
| L2 文案 | 商店/武器名称和描述拒绝半角逗号，中文逗号允许；克隆强化描述 c6 同步。 |
| L3 小数 | 客户端 TrialDamageCheckParams.percentage 是 Float，schema 接受 number；HTTP/编译按试炼种类校验，DamageCheck 允许 0 < percentage ≤ 100 的小数，HitCountCheck 和帧间隔继续拒绝小数。 |
| L4 userCost | schema 与直接编辑拒绝 type 0；克隆来源阶段继承 type 0 也拒绝。 |
| L5 二次地形 | 派生 ID/路径按 _v2、_v3 等序号避让旧交付资源；同草稿复用当前代。连续三次模拟上链后再编辑、再追加波次及保存编译保持通过。 |
| L6 倍率/Repeat | 私有槽重复倍率复用克隆；其它 boss/档位/槽/初始化/watch/Funnel 引用受保护。Repeat 按嵌套、跨程序及显式重复入口累计，999×999、600+600、根既被调用又独立触发均拒绝。 |
| L7 加载证据 | 新裸路径动作的 preview/compile 返回非阻断 boss.behavior-loading「待验证」，时间线亦提示。源码推断与静态回读不称为真机加载通过。 |
| 时间线 | GET /api/boss/<关卡>/timeline-summary 返回 moves/name/label/timeline。逐招复用 build_timeline；状态相对触发帧、hiddenAt/erasedAt/motions 一起平移，未知触发保持动作相对帧。同首领不同波次、初始化/watch 根入口、缺失 DSL、Host 守卫和候选草稿读取均有反证。 |

本次独立审查又实证发现并修复两个倍率/循环边界：跨 boss 借用已克隆动作后再调倍率会串改借招方；roots=[a,b] 且 a 调用 b，或 roots=[b,b] 时会漏算总执行次数。修复后第三方动作字节保持，1200 次展开明确拒绝。另修复时间线跨波次去重、绝对事件时刻遗漏平移和 GeneralBoss 属性码到内部属性码的换算。

### 当前数据与历史回归

236 视图完整枚举 1010 个 GeneralBoss 档位，其中 146 个带自身 routine watch。以这 146 档真实数据分别投影执行参数修改及 routine 改名，新 routine 下的 watch 子树与原树 146/146 完全相等；真实关卡能否编辑另按下段入口回归判定。471 个现有关卡的站位扫描新增阻断为 0。12 个档位的上界动作闭包存在输入缺失，不能宣称 1010 个档位的所有动作证据均完整；按实际关卡敌人等级选择档位后，470 关的 GeneralBoss/Funnel 命名站位引用证据完整，`practice:1021` 的 4 个原生 Funnel 动作缺失，明确返回非阻断「待验证」。此状态不推断成缺少命名站位，但删除站位必须先补齐引用证据，不能借待验证绕过删除门禁。

82 个领主战 watch 候选均实际执行：18 个可编辑战斗成功，覆盖 36 个敌人出现位置；1 个 BothBoss 聚合入口覆盖另外 2 个出现位置，被既有入口门禁拒绝；其余 63 个身份锁定候选被拒绝。所有拒绝均无候选改动。因此审查统计的 38 个未身份锁定出现位置全部得到验证，其中 36 个编辑成功、2 个由入口门禁阻断。指定 `boss_battle:1/13/4` 的 `boar_rider_multi_80` 改为 intervalFrames=45，实际 preview、保存、compile 均通过；新 routine 下完整保留原 watch，包括 `phase1_giga_lost_ready` 跳转。

入口回归脚本最初将 9 个五重相关候选都预判为聚合入口，末尾数量断言与真实结果不符；保留该次日志及脚本，随后修正验证脚本分类，并独立读回全部 82 条结果、boar 预览/编译及原 watch SHA，核验通过。此处只修正验证脚本断言，产品源码未变，未把拒绝项记作编辑成功。

ghost_fox 真实数据反证完成 5 案，每案先用同源合法 HP 草稿验证 preview、保存、compile 正向通过，再分别验证负请求的 preview/compile 都拒绝。自然关卡 `boss_battle:1/19/4` 删除 IL1 返回 C14102。精确 IL2 案只将该关卡的 field_data 单格内存投影为真实 `rush_05_ghost_fox`，其原生地形、站位及 DSL 全部保持真实字节，删除 IL2 返回 C14102；这属于真实数据投影，不称为自然可选关卡。

另外 3 案把真实 rush 槽 26/27、multi80 槽 31 借给 boar，都在 preview/compile 被既有 C8016 分身预载门禁先行拒绝。扫描到的 14 个 ghost_fox 含 CustomPosition 的真实槽/档闭包全部带 SpawnAlterEgo，因此不能把这些拒绝冒充新增站位门禁的直接证据，也没有删除真实 DSL 节点来绕过门禁。跨首领借招缺少 IL2 时的新增站位拒绝由 `tests/test_m61_behavior_positions.py` 独立反证覆盖。真实反证汇总见 `work/m61/behavior/ghost-fox/summary.json`，外层退出码 0。

真实时间线只读调用 4/4 返回 200：boar、光废龙、maou、hard_multi:1006/1 分别返回 45、136、94、171 个招式及 920、1320、815、1519 个事件；没有创建草稿。接口读取当前候选，不进行战斗模拟。

历史 223 本次回归 3/3 成员逐字节一致。历史 221 从四角色各七步骤完整源资产重建，11 个归档共 310/310 成员逐字节一致、差异 0；分层清单回读 310/310 一致，旧清单语义一致。11/11 归档排除 DOS 时间戳后相同；不声称原始 ZIP SHA256 全同。两项外层退出码均为 0。报告位于 `work/m61/history/`。

### 最终验证与证据

完整 `python -B -m pytest` 已结束：**4948 passed、354 skipped、26 warnings，exit 0**，pytest 用时 948.47 秒。跳过项主要依赖未配置的外部客户端/服务端源码、live store、历史资产及 POSIX/符号链接能力；本次没有把跳过项计作通过。26 条警告均来自旧环境变量 `WF_SERVER_DIR`/`WF_TARGET_STORE` 的弃用提示。

测试启动源码提交为 `253d4f2`；运行后逐项核对 1713 个 Python/schema 文件 SHA256，源码未变，随后仅补文档和证据摘要。原始终端计数与 JUnit 计数分别保存，避免 unittest.subTest 的额外 report 数混入终端通过数。

路径扫描：**2402 个文本文件，0 项命中**。全仓 `bash scripts/check-hygiene.sh --all` 已通过，最终文档另执行暂存区卫生检查及 `git diff --check`。

完整证据摘要及 SHA256 索引见 [m61-validation.json](docs/m6/m61-validation.json)。重要本地证据：

- `work/m61/behavior/verified/summary.json`、`watches.json`、`quests.json`：1010/146 档位及 471 关完整扫描。
- `work/m61/behavior/verified/integration-summary.json`、`watch-entries.json`、`boar-preview.json`、`boar-compiled.json`：真实领主战入口和指定 boar 编译回读。
- `work/m61/behavior/verified/integration-result-check.json`：入口分类修正后的独立结果核验。
- `work/m61/behavior/source-evidence.json`：watch 客户端取键/预载与 DamageCheck Float 的源码摘要。
- `work/m61/behavior/ghost-fox/summary.json`、`exit.json`、`projection.json`、`dsl-provenance.json`：5 案真实数据反证、原动作 SHA 和投影边界。
- `work/m61/timeline/summary.json`：真实接口结果及响应摘要。
- `work/m61/history/replay221.json`、`replay223.json`、`exit.json`：本次历史回归。
- `work/m61/full.log`、`full.xml`、`full-exit.json`：完整 pytest；`test-source-snapshot.json` 核对运行时与最终源码未变。
- `work/m61/path-scan.json`、`hygiene-all.log`：路径和提交卫生。

本地提交按主题拆分：

| 主题 | 提交 |
|---|---|
| watch 克隆与站位闭包 | `88ebbd4`、`b6c20d7`、`5022bf1`、`ba17239` |
| 站位边界与地形版本 | `bb139a0`、`10d8c6f` |
| 商品时间、图集与武器限制 | `7183b2d`、`8175102` |
| 时间线与 DamageCheck | `ff340ac`、`6676aae`、`e3c78c0`、`5e85be1` |
| 加载证据与共享动作隔离 | `c0519c8`、`253d4f2` |
| 持续接口文档 | `e8f975f` |

本节及验证摘要另作本地文档提交，未 push。

所有结论为本地代码、静态客户端档案、候选重放或历史字节证据。未做真机加载、实际战斗、三人房、实际购买扣费或业务服务器部署；不把这些未执行事项写成通过。

## M6.2：BOSS 参数语义与 v35k3 本地档案

本节对应 M6.2 任务书，起点为 `a6bcc44`，实施分支为 `refactor/m5-boss`。写入范围限当前 worktree；其他目录仅作只读输入，未操作其他集成 worktree，未 push，未访问业务服务器、本地 8001 服务、模拟器或设备。临时脚本、测试输出、构建产物和详细证据保存在忽略目录 `work/m62/`。

### BOSS 参数的最终语义

| 字段 | 行为 |
|---|---|
| `hpScale` / `attackScale` | 将当前 quest 行的三个对应实际值分别乘以输入数值 |
| `hpValue` / `attackValue` | 将三个对应实际值直接设为输入数值 |
| `hpMultiplier` / `attackMultiplier` | 保留历史绝对值写入行为；schema 标记 `deprecated: true`，API 返回“绝对值、已弃用”的非阻断提示 |

同一属性在一次有效参数集内只能指定一种模式。五档配置中，某档显式提供的模式覆盖该属性的公共模式；HP 与攻击可独立选择。正数、有限值、当前基值和结果范围均校验，拒绝零、负数、非有限值、非法基值及结果溢出，十进制计算避免将 `0.1 × 10` 写成不准确的小数。

预览、保存和编译响应提供 `parameterChanges`，逐操作列出关卡、字段、模式，以及小怪、浮游和 BOSS 各自的实际 before/after。现有编辑台输入改为明确的“设为绝对值”，并展示这些变化；API/CLI 可显式选择 Scale。新建副本先完成既有模板默认值初始化，再在初始化后的实际值上执行用户操作。

反证已覆盖 `0.1 → hpScale:10 → 1`、`hpValue:1 → 1`，以及同草稿再次追加 Scale 后确实再乘一次并返回提示。每次 Scale 都提示“同一草稿再次写入会再乘一次”；之前已有相同规范化关卡、相同属性的 Scale 时，另标记 `repeatScale:true`，中间的绝对赋值不会清除历史标记。重新读取、预览或编译同一份已保存草稿只重放既有操作，不额外追加乘法。攻击字段、旧字段兼容、五档覆盖、规范化关卡别名、冲突失败后草稿保持也有回归。独立复核的三组持久化组合全部通过。

已有副本的编辑请求可写成下例；目标副本由 API 路径或 CLI 位置参数指定。它将三类当前 HP 系数分别乘以 10，并将攻击系数设为 1：

```json
{"operation":"edit","parameters":{"hpScale":10,"attackValue":1}}
```

Boss 定向测试 **88 passed**，TypeScript 静态检查与 Vite 本地构建退出 0。构建证据包含本次工具结果汇总及源码/产物摘要；原始构建日志未保存。长期接口说明见 [boss-authoring.md](docs/studio/boss-authoring.md) 与 [boss.md](docs/studio/boss.md)。

### 真实 APK 登记与差异

实际读取 `v35k3-local-wf-x86.signed.apk`，包名为 `com.leiting.wf`，versionCode/versionName 为 `1008001` / `1.8.1`。完整 APK SHA-256 为：

```text
6981c48c42e43ebf6b85e5893cf40357affe4e7a31787e078f0ce28c3cd5f807
```

内置 SWF SHA-256 为 `c52e01b8a536f78a06f48cce07bd3e0f23b3814b9b7f861e02a20755f74cc2c1`。新增 `local-v35k3`，明确标为“本地自用，非测试服包”，没有改变默认客户端档案。

能力依据从实际 SWF 提取：838 个去重已登记方法中，808 个 code 和引用上下文都与固定 v35e 基线一致，23 个 code 变化，7 个仅引用上下文变化。上下文包含方法签名、直接常量引用、命名空间身份、异常表、activation trait、直接方法上下文和类声明；敏感常量只保留指纹，不在差异报告中展开。一个补丁的全部方法证据一致才授予对应能力，不按版本名称推断能力。

本档案提供 **123 项能力、101 个补丁**。30 个补丁暂扣；v35e 的 179 项能力中，共 56 项没有在本地档案中证明，包括未自动继承的 4 项官方系统声明。暂扣表示证据不足，不宣称客户端必然不支持，也不声称具有这些能力。真实能力请求仍会被兼容检查阻断。描述覆盖、普通 kind 422、R3 装备回充解析和普通 kind 检查已通过；需要暂扣直击基础能力的请求明确阻断。

差异逐项保存在以下长期材料中：

- [本地登记用法、能力边界与 30 项补丁说明](docs/m6/local-clients.md)。
- [APK 全成员差异](docs/m6/m62-package-diff.json)：各 6,131 个成员，6,122 个字节相同、9 个变化；包括 3 个签名成员和 6 个 payload，bundle 内 5 个成员另列。
- [SWF 全部差异](docs/m6/m62-full-swf-diff.json)：304 个 ABC 中 301 个原字节相同，方法体 96,825 → 96,863，29 个既有方法体变化、38 个新增、0 个删除；常量池、声明及非 ABC 标签差异也保留。
- [已登记方法与能力差异](docs/m6/m62-registered-method-diff.json)：每项变化的方法名、ABC、涉及补丁、前后 code/context SHA，以及全部未证明能力 ID。

后续同线本地包可在本 checkout 执行：

```text
python -B -m wf apk register-local <v35版本-local-wf-x86.signed.apk>
```

例如文件名 `v35k4-local-wf-x86.signed.apk` 默认登记为 `local-v35k4`，也可用 `--profile local-自选英文标识` 明确命名。命令只读输入 APK，把新登记原子写入忽略目录 `work/local-clients/<profile>/`，并接入档案列表、编辑台、provides、kind 和兼容检查。相同完整 SHA 幂等返回，不覆盖同名不同内容；真实 manifest 必须是 `com.leiting.wf`。内置 v35k3 上实际执行 provides、两次 register-local 与 kinds 均退出 0，APK 与参考 SWF 前后摘要保持。

独立审阅发现的方法上下文与显式 registry 边界缺口已修复并以反例验证。旧版 `wfx_gate` 也接入登记证据，要求 APK/SWF、provides 文件摘要和实际重新推导出的能力同时匹配；仅添加能力名称不能放行。自定义 registry/profiles 文件仍保持调用者限定的范围。

### 最终验证与历史逐字节保持

完整 `python -B -m pytest` 已结束：**5010 passed、354 skipped、26 warnings，exit 0**，外层用时 1143.55 秒。26 条警告均为既有 `WF_SERVER_DIR` / `WF_TARGET_STORE` 环境变量的弃用提示。跳过项保留为 skipped，不计为通过；原始终端结果与 JUnit 统计分别保存，避免将 unittest.subTest 的额外报告混入主套件计数。

测试从提交 `762b3d6` 的干净工作区启动，运行后核对 2066 份源码、schema、配置与数据文件 SHA256 未变。路径扫描 **2422 个文本文件、0 项命中**；全仓提交卫生检查通过，最终报告与摘要另做暂存区卫生及 `git diff --check` 检查。

APK 定向回归为 **171 passed、10 skipped、361 subtests passed**；随后新增的同 SWF 多 APK 配对反例单独通过，并被本轮全量覆盖。最终独立旧入口检查共 12 项身份与授权反例、10 项缓存反例、4 项精确配对反例，均通过。

历史 223 在当前实现生成完成后，再打开独立原 ZIP 比较，**3/3 成员逐字节相同**。历史 221 从四角色各七步骤的完整源资产重建，**11 个归档、310/310 成员逐字节相同、差异 0**，分层回读也为 310/310，旧清单语义相同。11/11 ZIP 排除 DOS 时间戳后容器相同；原始 ZIP SHA 并不相同，不将成员逐字节一致写成整个 ZIP 原字节一致。两项外层退出码均为 0。

历史构建及核验共保留 1,110 个去重外部输入文件的原 SHA，174 次 ffmpeg 子进程输出均受限于当前 worktree。最初历史验证脚本误将 Windows 子进程参数视为列表，修正证据脚本后在全新目录完成全部重建；原失败记录保留在 `work/m62/history/failed-attempt1/`。首轮全量测试在旧 `wfx_gate` 档案读取处收集失败，记录保留在 `work/m62/full-attempt1/`，未计作通过。

完整验证数字与逐项证据 SHA 索引见 [m62-validation.json](docs/m6/m62-validation.json)。详细原始材料包括 `work/m62/full.log`、`full.xml`、`full-exit.json`、`test-source-snapshot.json`、`history/summary.json`、`apk/acceptance.json`、`review/boss-independent.json`、`review/apk-final.json` 和 `review/apk-gate-final.json`。

本地提交按主题拆分：

| 主题 | 提交 |
|---|---|
| BOSS Scale/Value 语义、兼容提示及回归 | `f6351a3` |
| 编辑台明确绝对值并展示实际参数变化 | `8ff3cb8` |
| APK 与全 SWF 的逐条字节差异 | `73817ae` |
| 真实方法证据、本地登记与各兼容入口 | `762b3d6` |

本节与最终验证摘要另作本地文档提交，没有 push。

以上结论限本地代码、静态 APK/SWF 方法证据及历史字节回放；本任务没有运行设备、实际战斗、业务服务器或部署验收。
