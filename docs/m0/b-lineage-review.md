# M0.1：B 血统逐提交复核

本记录覆盖真实 merge-base 之后 B 工具目录的全部 53 个提交，其中任务书指定的 2026-09-06 起 17 个单列；另外 36 个也逐项核对。75 个 B/C 同名根 Python 文件是审计集合，24 个提交直接改变该集合。没有把 C 的文件日期或配方字节相同当成 B 修复已存在的证明。

## 只读来源与方法

- B HEAD：`c3da27a9a2de9ffd4cae2d0c8336b87c623af372`。
- C HEAD：`a2bc5f6cecb6af524d51db82f23536ccf042feec`。
- 真实 merge-base：`4eef6915c49f5705fad0c619679c92d74101688b`（2026-07-16）。B/C 位于不同 Git 对象库，使用只读 `GIT_ALTERNATE_OBJECT_DIRECTORIES` 暂时提供 C objects 后执行 `git merge-base`；没有 fetch、写入或修改两仓配置。
- 全范围命令：`git log <merge-base>..<B HEAD> -- tools/fantasy-gauntlet-mod-tools/*.py`；指定17项命令保留 `--since=2026-09-06`。逐提交读取 changed paths/diff，并以同名函数/类 AST 比较 C 当前实现；去除 docstring 后仍不相同的符号列在 JSON。
- `b-lineage-review.json` 保留53项完整SHA、日期、全部变更Python路径、同名文件与符号分布、逐文件diff摘要、决策理由；原始diff和执行日志在忽略的 `work/h1/`。AST相同只用于定位共同实现，不能替代运行时验证。
- 下文“不适用”包含明确未导入的 B 平台/内容政策/发布协议/严格HP扩展，不代表 C 实现了这些功能，也不代表两个分支行为等价。活动路径中的已知缺失修复不能仅以“选C”为由跳过。

## 指定的 17 个提交

| 提交 | 日期 | 判定 | 文件、理由与边界 |
|---|---|---|---|
| `048caa76` | 2026-10-07 | 不适用 | 无 B/C 同名根文件。7 个 B 一次性 local_test/赞助角色脚本的旧候选资源路径整理；不在 C 同名集合，也不在本次活动入口。 |
| `aececd81` | 2026-10-07 | 不适用 | `wf_character_flow.py`。B 独立发布编排新增 production_boundary_gates、声明、键并集及 live_store_drift_report；依赖 B 的生产根/实时叠层/角色 gates 模型。C 使用 release transaction、manifest、客户端合法性和 mana-board 门禁；本次不改变两套发布授权协议，不宣称 C 已具备 B 的新功能。 |
| `1a3c5728` | 2026-10-07 | 已回收 | `wf_client_legality.py`。M0 已以自有枚举和 wf.rules.instant_defaults 回收瞬发 Bool/multiply/+14..18 默认及非法 PF 等级检查；C 原有 client_legality_problems 已覆盖空值门禁。B 独立 ability_composer 未导入，GUI 调用本仓规则实现。 |
| `db23daa5` | 2026-10-02 | 不适用 | 无 B/C 同名根文件。仅 1.4.120 原生八岐试验发布、1.4.128 觉醒图标预载修复两个历史脚本；无 B/C 同名活动模块变更。 |
| `211379ba` | 2026-10-02 | 已回收 | `wf_dsl_sig.py`, `wf_gui.py`。回收 wf_dsl_sig 的 Option<SLvValue> 校验，防 ShowEffect p12/CreateHitArea p15 的 Some(number) 触发 F1034；与 nullable p8 同在拆出的 validator。独立角色工坊/存储/预览及 GUI 迁往 B composer 的架构不移植，保留 C 内嵌 composer。 |
| `19bf8bb9` | 2026-09-24 | 不适用 | 无 B/C 同名根文件。新增 B 独有 wf_dsl_subjects 及测试；C 当前没有该 API/消费方。七角色与稻穗的交付数据不是本次工具源码回收对象。 |
| `384bb89b` | 2026-09-18 | 不适用 | 无 B/C 同名根文件。只在 repair_abyss_ex20_exchange_115 历史脚本添加成绩版本兼容字段；本仓未导入/执行该 B 资源发布脚本。 |
| `f9328f4b` | 2026-09-18 | 已回收 | `wf_dsl_sig.py`, `wf_rogue_build.py`。计分鲨鱼同时从候选池、身份改名/搬运门禁及深层锚移除；r25 回归普通池，r26–30 五锚。回收 CreateCondition p8=null 的精确例外。C 所有克隆共用更严格 identity_locked_boss_reason，不另引入 B 的可局部闭合 clone 放宽分支；EX115 的修包/兑换数据脚本不执行。 |
| `ef6455c6` | 2026-09-18 | 不适用 | `wf_rogue_build.py`。normal/ex 双模式、700100/PRIVATE_PREFIX、20层EX与普通30层HP/时限/保底政策及专属clone族属于 B 新运行模式；C只有legacy单模式，没有 BUILD_MODE，也不复制已经发布的七角色资源。f932后续通用不可击杀修复已独立回收。 |
| `100a963c` | 2026-09-13 | 不适用 | 无 B/C 同名根文件。两个 1.4.107 武器次数/百倍血量木人历史发布脚本；无同名通用模块改动。 |
| `4d4c3265` | 2026-09-12 | 不适用 | 无 B/C 同名根文件。B 独有 wf_quest_time_revision 的成绩指纹分割/旧格式兼容；C发布器没有 active-patch quest_time_revisions 协议，不新增服务端成绩版本。 |
| `8ae133a0` | 2026-09-10 | 已回收 | `wf_rogue_build.py`。通用 Standard Funnel 反向 damage_share/ESDL watch 扫描已回收到 wf.rules.rogue_lineage，扫描失败关闭身份改名门禁；standard_identity_references 对 General/Standard 名称均生效。B Standard HP clone 的 DamageCheck解析、属性封锁保底/详情UI/固定奖励及服务器目录写法属于B专有模式，不套到C未导入的clone/详情编译器。 |
| `2e7ab5a0` | 2026-09-09 | 已回收 | `wf_rogue_build.py`。damage_resistance_totals 按同源合并规则汇总关卡条件、一次性、叠层三来源；immunity_axes 统一判阈值，apply_picks 在输出字典改变前拒绝冲突。四种伤害轴的90%+10%/40%、40%+40%+20%、关卡+一次性全部有负向回归。 |
| `a7ac300a` | 2026-09-08 | 不适用 | 无 B/C 同名根文件。B 独有 wf_race_character_nerf 和测试，针对作者角色/五重决战内容；不是C同名通用工具修复。 |
| `efb8fd96` | 2026-09-06 | 不适用 | `wf_publish.py`。仅 B 发布器 _register_active_patch 引入 quest_time_revisions。C wf_publish 无该函数，使用既有 C 发布/事务格式；引入服务端排行榜重置协议超出本次工具收拢。 |
| `070a9e4d` | 2026-09-06 | 不适用 | `wf_assets.py`。新增 png_decode_stored 是 B 历史横幅发布脚本的严格存储头读取器；C 及本仓无该读取器调用，现有 png_decode 明确接受普通/存储态供编辑，不能替换成严格读取而破坏编辑输入。实际1.4.101横幅修包不执行。 |
| `f348ee94` | 2026-09-06 | 不适用 | 无 B/C 同名根文件。仅 1.4.97/1.4.100 赛季称号与兑换同步三个内容发布脚本。 |

## merge-base 后其余 36 个提交

| 提交 | 日期 | 判定 | 文件、理由与边界 |
|---|---|---|---|
| `3382c1e9` | 2026-09-05 | 不适用 | 无 B/C 同名根文件。希耶提特定平衡和1.4.99双池清理发布；非C同名公共模块，本次不重放历史内容发布。 |
| `2f6db081` | 2026-09-04 | 不适用 | 无 B/C 同名根文件。灰09-02资源/icon closure历史候选构建脚本；外部CDN恢复数据不属于本次工具修复。 |
| `178ee615` | 2026-09-03 | 不适用 | 无 B/C 同名根文件。仅三份称号/武器代币/CDN历史发布脚本；无B/C同名文件修复。 |
| `353f8b3f` | 2026-08-31 | 不适用 | 无 B/C 同名根文件。二板觉醒1.4.95修包及专属测试，属于客户端/服务端已交付数据操作，不是当前工具编译API。 |
| `03c60209` | 2026-08-30 | 不适用 | 无 B/C 同名根文件。九名官方角色觉醒1.4.94迁移、审计和专属测试；未引入该历史发布器。 |
| `d91dd04c` | 2026-08-30 | 已回收 | `wf_dsl_sig.py`, `wf_rogue_build.py`。回收完整DSL签名/受控参数编辑校验，拆到 wf.rules.dsl_signature。回收实际mix路径的ActionDSL/ESDL闭包+目标地形门禁，钉选不能绕过，HP donor重排再次检查；按C实际解析等级缓存证明，并从_mix_boss_entry恢复已有混搭的原donor。B strict-target-HP审计文档/多族封面证据框架无C对应入口，不声称等价移植。 |
| `ab7c8c82` | 2026-08-30 | 不适用 | 无 B/C 同名根文件。西蒙角色兼容回退和指定深渊场地修包依赖 B 独有 wf_abyss_custom_position_fix/wf_simoun_balance；没有同名C活动文件变化。 |
| `6f8c197d` | 2026-08-29 | 不适用 | 无 B/C 同名根文件。1.4.88候选整合/1.4.92排行榜与重Roll发布脚本及其对账工具；不执行外部版本推进。 |
| `e83cbf74` | 2026-08-29 | 不适用 | 无 B/C 同名根文件。五名指定角色终态平衡与说明修订脚本；不是C公共API补丁。 |
| `d28f3e1e` | 2026-08-29 | 已回收 | `wf_balance_suite.py`, `wf_describe.py`, `wf_gui.py`, `wf_rogue_rewards.py`。恢复瞬发/持续来源枚举、角色组逗号解析、CT原始帧、固有状态整数等级、六属性独立伤害乘区和主位限制；同步真正被读取的词条中文表、延迟元数据、GUI两类puller和三级技能名称/说明字段。C延迟已按秒处理，保留其:g格式。balance_suite/rogue_rewards只改历史注释，无行为缺口。 |
| `0ac0e619` | 2026-08-28 | 已回收 | 无 B/C 同名根文件。M0已从B当前源导入生产可达 wf_battle_atlas_repack（C没有同名模块）；保留了该提交的图集重排实现。1.4.91发布脚本与独立 flatomo retarget 不加入当前入口。 |
| `d1ef3002` | 2026-08-28 | 不适用 | 无 B/C 同名根文件。B 独有装备强化商店购买阶段工具及测试；C无同名模块，此任务不修改既有商店交付数据。 |
| `7580b151` | 2026-08-27 | 不适用 | `wf_assets.py`。ID3标签之外零填充的兼容清理扩展。C mp3_encode 已通过严格逐帧/尾部/CBR门禁拒绝这种不受支持输入；B增加的是可接受输入范围，当前两次配方使用批准WAV经ffmpeg规范转码，没有该导出器输入。保留C编码字节合同，不把不支持但明确拒绝的输入称为已兼容。 |
| `9db4d420` | 2026-08-27 | 不适用 | `wf_rogue_build.py`。把所有元素软抗性改成不可驱散是B深渊常驻规则的内容政策，C有明确可驱散软卡接口和测试；不擅自更改C作者规则。跨来源导致最后出口封死的安全缺陷另由2e7修复。 |
| `67fc5538` | 2026-08-26 | 不适用 | `wf_rogue_build.py`, `wf_rogue_save.py`。B strict-target-HP/Standard HP缩放、多族专属克隆、DamageCheck绝对阈值回写、封面证明和诅咒多样性审计体系；C没有这些缩放/克隆/API，仍以自身general c2+受限standard c86和专属族排除工作。保持C stricter身份锁；没有宣称B复杂族能力已覆盖。 |
| `ed8aaec3` | 2026-08-26 | 不适用 | `wf_rogue_build.py`。B新增orochi_ex/sphere生命周期和专属相位HP克隆修复；C未启用该clone路径且仍屏蔽orochi_ex。B capability profile由其strict HP模式生产，C不生成该profile。 |
| `6f8c995c` | 2026-08-26 | 不适用 | 无 B/C 同名根文件。只修1.4.88整合脚本中的新角色实际出率；不操作抽池数据。 |
| `628e56a5` | 2026-08-26 | 不适用 | 无 B/C 同名根文件。深渊十连券扩展/奖励排程为B内容包和独有wf_rogue_reward_schedule；无同名C公共模块。 |
| `ca738189` | 2026-08-26 | 不适用 | 无 B/C 同名根文件。1.4.88角色/票券/奖励及专用像素/特效工具；无B/C同名根模块变化，保留原M0可达性筛选边界。 |
| `05ab6432` | 2026-08-26 | 不适用 | `wf_gui.py`, `wf_rogue_build.py`, `wf_rogue_bundle.py`, `wf_rogue_reroll.py`。B严格目标HP、多族专属克隆、Standard ESDL改写、审计收据及相应GUI/CLI开关。C未开放orochi_ex/球体等新clone族，rbb仍拒绝无法缩放的族；B audit_action_identity_closure用于允许这些新族，C当前不需要放宽。已单独回收后续适用于C的通用mix/身份反向引用门禁。 |
| `ac6e2a29` | 2026-08-24 | 不适用 | `wf_assets.py`, `wf_atf.py`, `wf_gui.py`, `wf_kyle_canary.py`, `wf_night_pack.py`。把素材/ATF/GUI读源切为B live-CDN overlay，涉及revision cache、voice dump和源库存。C由显式物化store及wf.view冻结视图提供输入；直接导入将改变配方视图和权限边界，不属于缺失的本地编译算法修复。 |
| `1a27da45` | 2026-08-24 | 不适用 | 无 B/C 同名根文件。B独有深渊抽卡横幅/雷龙角色包的live-CDN来源绑定；C无该套包编译入口。 |
| `5f491ce1` | 2026-08-24 | 已在 C 中 / 已回收 / 不适用 | 48 个同名文件，完整列表见 JSON。大规模上游同步：共同算法逐符号AST核对见JSON（如offline_toolchain、story_export及大量rogue函数相同）；原M0的75同名/51分叉清单继续作为逐文件底稿。路径项按活动消费方核对：本次修复rogue_build的--write前置server解析和quest/folder/publish目标；另由M0.1路径收敛修复rogue_rewards、rogue_shop、rogue_save、rogue_banner、rogue_validate及balance_suite的实际消费方（b0054ee）；其余GUI/flow/analysis/offline等70个活动模块消费分类见末表。Win32逻辑路径合法性/大小写冲突门禁已由M0拆至wf.deliver.logical_paths；本次另回收禁止codec_registry覆盖内置校验器及WF_FFMPEG显式错误失败关闭。B live-CDN/iOS/独立发布/新server JSON codec/哈希绑定资产替换等扩展不直接移植；C现有武器持续行/629合法性与作者总强度扩展保留，不回退为B旧内容。所有此提交之后的同名修复另逐提交核对，不能再以“C较新”概括放弃。 |
| `3600c6f4` | 2026-08-23 | 不适用 | `wf_rogue_build.py`。B服务器内容政策强制玩家rank130并删除700098/700099直达event_list改用共享hub；C legacy入口仍明确生成单一700099。未授权改变该产品入口/玩家门槛。 |
| `2cbbdf54` | 2026-08-22 | 不适用 | `wf_gui.py`。GUI快捷摘要改为多行描述+固有状态上限的显示增强；C已经保留line_descs完整描述，shortcut仍是旧摘要API。此提交不修编译出的数据，未将B整套GUI行摘要结构迁入。d28的当前描述器错误已另回收。 |
| `3b2b9329` | 2026-08-22 | 不适用 | 无 B/C 同名根文件。仅1.4.86双角色历史发布脚本。 |
| `edcd2e2e` | 2026-08-21 | 不适用 | 无 B/C 同名根文件。仅1.4.85摩西伊克历史平衡发布脚本。 |
| `6717aa27` | 2026-08-20 | 不适用 | `wf_assets.py`, `wf_atf.py`, `wf_gui.py`, `wf_kyle_canary.py`, `wf_publish.py`, `wf_publish_guard.py`。B新增iOS ETC2/EAC cutin平台输出、PNG/ATF成对补全及iOS包根；C当前为已有Android工具和配方，没有iOS发布输入/验收，本次不新增平台。 |
| `495e0115` | 2026-08-18 | 不适用 | 无 B/C 同名根文件。仅克劳德/深渊美术/hub的1.4.82–84内容发布脚本。 |
| `9ef32580` | 2026-08-17 | 不适用 | 无 B/C 同名根文件。仅泳装EX角色专属准备脚本中的材料成本修订。 |
| `6ac13136` | 2026-08-17 | 不适用 | 无 B/C 同名根文件。B mode15预设的法力奖励再平衡；C没有同名根模块，不改变游戏奖励政策。 |
| `6cd32094` | 2026-08-17 | 不适用 | 无 B/C 同名根文件。泳装EX/幻想双角色旧CDN向active搬迁及若干1.4.80/81发布脚本；不操作任何外部CDN或数据。 |
| `3ff57bf1` | 2026-08-17 | 已回收 | `wf_character_pack.py`, `wf_release.py`。C已修owned root权限但遗漏owned_directory_create的FILE_DELETE_CHILD，本次补齐子目录最小权限；wf_release._repo_paths仍隐式父目录，本次回收统一resolve_server_dir/resolve_active_store/resolve_cdn_root，配置未指定直接报错。 |
| `26cc9329` | 2026-08-16 | 不适用 | `wf_rogue_build.py`。B把固定通关奖励写死为1500玛纳/50代币/2突破材料以展示特定1.4.78活动；后续又改服务端奖励读取。C当前从模板构造，不擅自引入B服务器奖励约定。 |
| `43fbfb68` | 2026-08-15 | 不适用 | 无 B/C 同名根文件。仅部署/卫生测试路径调整，不改变同名工具运行实现；本仓卫生规则由自己的scripts/check-hygiene.sh维护。 |
| `8a9ddafa` | 2026-08-15 | 已在 C 中 | 66 个同名文件，完整列表见 JSON。这是共同工具基础快照，66个同名文件已在C中；逐符号1392项与C相同、99项当前C实现不同、5项B发布/外部fallback符号未在C保留。不是66文件逐字节一致：如archive_scan/asset_archive全体符号相同，而发布协议和外部fallback的差异按5f及后续条目单列，不恢复已废弃的仓外探索。 |

## 回收实现与上下文适配

1. **f9328f4b / 2e7ab5a0**：保留 C 更严格的统一身份锁；不引入 B 的局部闭包放宽。不可击杀鲨鱼不依赖外部引用扫描即可拒绝。抗性合计先按现有每来源合并方式，再做跨来源相加；效果包输出前检查，拒绝时输出字典保持原样。
2. **DSL签名**：C原来根本没有B validator，因此不能孤立复制f932的5行。将其最小完整校验及受控参数编辑API拆入 `wf/rules/dsl_signature.py`，从 `wf_dsl_sig.py` 兼容导出；保持原签名表，p8 nullable只允许CreateCondition的那个参数，不使其它enum/Bool/整数可空；同时保留后续Option<SLvValue>修复。
3. **Standard Funnel与混搭**：只回收反向引用读取和门禁，不引入整个B专属族clone框架。扫描损坏/缺失关闭身份操作。mix初选、钉选和HP重排都使用现有C完整terrain_compatibility。C的ramp/max等级与B上下文不同，证据按最终resolve_level结果分别缓存；已生成混搭回到原donor field查证据，避免把mod_rogue_fN误当新原生场地。
4. **描述与GUI**：真实枚举文字来源是 `词条条件代码全表.md`，一并按d28修改对应条目，保留其它C内容；`ability_enum_map.json`只修延迟单位。GUI区分instant/during puller，并同步第三级技能名/描述。该变化后的223/221/当前万圣验证由配方报告记录。
5. **发布根与Windows权限**：`wf_release._repo_paths`不再猜测仓外父目录与`.cdn`，统一解析器决定server/store/CDN。rogue_build在--write解析后、读取任何表或生成DSL前解析server，quest/folder/publish均用该显式根；import与dry-run不要求未使用的server。Windows owned child directory与已修过的owned root都不再要求Full Control才有的FILE_DELETE_CHILD；仍保留目录自身DELETE和所需列举/添加/属性权限。

## 回归与删修复变红

专属测试：`tests/test_h1_lineage.py`、`tests/test_h1_describe.py`、`tests/test_h1_rogue_gates.py`、`tests/test_h1_release_paths.py`、`tests/test_h1_codec_registry.py`，全部是合成数据；不把整行官方游戏表重新带入仓库。既有真实store测试按缺失输入跳过，不能算设备或生产验证。

初始C执行新codec回归为 **4 failed / 1 passed**；新核心测试为 **27 failed / 4 passed**；描述器为 **8 failed / 2 passed**。下表17组将每个修复在独立进程的源码副本中删除或恢复旧行为，再运行同一行为测试；原活动源码摘要前后相同。mix负例实际生成了被禁止的`mod_rogue_f5`而失败，不是夹具异常。

| 被撤回的修复 | 变红行为 | 实际结果 |
|---|---|---|
| 鲨鱼候选池拒绝 | shark_score_event 进入候选池 | 1 failed，exit 1 |
| 鲨鱼身份门禁 | 无外部引用时允许不可击杀对象 | 1 failed，exit 1 |
| 安全五锚 | r25重新变成score_event_shark | 1 failed，exit 1 |
| 跨来源关卡抗性合计 | 四条伤害出口被封死仍判可用 | 16 failed，exit 1 |
| apply_picks前置拒绝 | 非法组合仍写入效果包 | 1 failed，exit 1 |
| CreateCondition p8 nullable | 合法null被签名校验拒绝 | 1 failed，exit 1 |
| Option<SLvValue>精确类型 | Some(number)被误当可用 | 1 failed，exit 1 |
| 瞬发puller=9独立枚举 | 多球任一误作全队总和 | 1 failed，exit 1 |
| Standard Funnel反向引用 | 外部ESDL依赖未锁定 | 1 failed，exit 1 |
| mix钉选地形门禁 | 缺失闭包证据仍生成field/zone | 1 failed，exit 1 |
| mix按实际等级取证 | floor80错误套用level100证明 | 1 failed，exit 1 |
| HP重排恢复原donor | 合法混搭被当成无证据的生成field拒绝 | 1 failed，exit 1 |
| 发布显式server根 | 未配置server仍退回父目录 | 1 failed，exit 1 |
| owned子目录最小权限 | 仍索取FILE_DELETE_CHILD | 1 failed，exit 1 |
| rogue写入前解析server | 未配置server仍开始读表/后续生成 | 1 failed，exit 1 |
| 内置codec不可替换 | 任意调用方可替换flat/raw/nested校验器 | 4 failed，exit 1 |
| WF_FFMPEG显式配置权威 | 空/空白/相对/不存在/目录值错误回退PATH | 5子例failed，exit 1 |

日志：`work/h1/mutation-*.log`、`mutation-results.json`；执行副本由 `work/h1/mutations.py` 生成。该过程没有编辑活动文件或任何仓外目录。正常源码下五个专属测试文件共 **61 passed**（2.30秒）；相关rogue组 **255 passed / 24 skipped / 33 subtests passed**，发布/权限组 **148 passed / 1 skipped / 135 subtests passed**。其中发布组是在新增rogue前置回归前执行，该新增回归已包括在61及255项中。codec补修另执行character_pack/release关联组，**132 passed / 1 skipped / 135 subtests passed**。在最终路径源码下再运行H1与voice组为 **71 passed / 5 subtests passed**。全量最终结果统一以 `M0-REPORT.md` 的M0.1节为准。

## 明确保留的分支差异

B的iOS ETC2、live-CDN实时叠层、strict-target-HP、多族专属克隆、EX/普通双模式、排行榜重置协议、rank130/固定奖励/不可驱散元素软卡政策及独立角色工坊不因本次回收自动获得支持。本文没有将它们标成已回收；未来启用需对应输入、调用链、权限和验收。C已有的保守族排除、统一身份锁和物化视图保持其原有范围。
本任务只提交当前worktree代码与证据，不执行任何历史修包脚本、发布器、服务器写入或push。

## 75 个同名模块的路径消费终核

历史同名集合75项中，当前活动根模块70个，另5个已归档。按当前活动文件逐个核对 ROOT/REPO/PROJECT_ROOT、server/CDN解析与读写调用；文件SHA256保留在JSON。表中明确区分本仓工具数据、外部配置数据以及无活消费者的旧变量。`source.parent.parent`等由调用方显式文件推导的布局，不等于从模块位置猜测仓外根。

| 模块 | 数据归属 | 核对结论 |
|---|---|---|
| `wf_all_analysis.py` | 工具输出 + cdndata输入 | logs/all_analysis.json 属于工具根；character/text 镜像必须来自resolve_cdndata_dir（显式cdndata优先，否则配置server）。 |
| `wf_archive_scan.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_asset_archive.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_asset_inventory.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_asset_maintenance.py` | 调用方显式根 | repo_root 为 API/CLI 参数；策略、扫描及隔离记录均绑定该根，没有模块层级推导。 |
| `wf_asset_policy.py` | 策略文件相对根 | Policy.load 显式 repo_root 优先；source.parent.parent 是传入策略文件的布局合同，并非 __file__ 父目录。保留。 |
| `wf_asset_quarantine.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_assets.py` | store / 资源输入 | 素材根由传入/配置 store 提供；root_path 导入本身不构成仓外消费者。 |
| `wf_atf.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_balance_patch.py` | 工具输出 + cdndata输入 | logs marker/report 属于工具根，character/text 镜像从resolve_cdndata_dir（显式cdndata优先，否则配置server） 读取。 |
| `wf_balance_patch_v2.py` | 工具输出 + cdndata输入 | 与 v1 相同；不能把 logs 和 server assets 共用隐式上级。 |
| `wf_balance_suite.py` | 工具输出 + cdndata / server / CDN | logs、marker、报告与分享ZIP均工具根；镜像由resolve_cdndata_dir指定，只有publish才要求server；CDN按publish/export需求解析，任何写前预检。 |
| `wf_boss.py` | store 输入 | 经 quest_lib 活动 store；无模块 ROOT/REPO 消费者。 |
| `wf_boss_buff_harvest.py` | store 输入 / 显式输出 | 经活动 store/CLI 路径；无模块 ROOT/REPO 消费者。 |
| `wf_canary_skin.py` | 已归档 | M0已移至archive/legacy/tools，不是当前活动根模块；不为历史入口改写路径。 |
| `wf_catalog.py` | 受限 legacy 读源 | 旧 parent 参数只进入 find_world_upload；解析器已拒绝仓外查找，不能命中兄弟目录。不是实际仓外读写。 |
| `wf_chain_build.py` | store 输入输出 | 表访问经 quest_lib；无模块 ROOT/REPO 消费者。 |
| `wf_chain_squash.py` | server / CDN | repo_root 用于 assets/asset-patch；显式 CLI 或 server 解析器，CDN 单独解析。 |
| `wf_char_editor.py` | store 输入输出 | 显式/配置 store；无模块 ROOT/REPO 消费者。 |
| `wf_character_flow.py` | server / CDN / APK | 发布后 mana_board 回灌用显式 server；真实 CDN 绑定用统一配置；APK/bundle 不读模块父级。 |
| `wf_character_pack.py` | 调用方显式 LiveRoots | 输入 LiveRoots 绑定 common/medium/android/server；事务消费其已指定根，不自行猜测 checkout 父目录。 |
| `wf_character_requirements.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_character_rollback.py` | server / CDN | CLI 从 release._repo_paths 得到显式根；底层 snapshot/staging 按给定 LiveRoots/server 工作。 |
| `wf_character_workspace.py` | 调用方显式工作区 | package_dir/workspace 路径由调用者给定，无模块父目录 fallback。 |
| `wf_client_legality.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_decrypt_all.py` | 工具输入输出 | 默认 bundle/pathlist/voice/out 均 root_path() 仓内；可由 CLI 显式传入。 |
| `wf_deploy.py` | 工具输入 | 引用 GUI.ROOT 查工具包；ROOT 已是当前工具仓，不应改成服务端根。 |
| `wf_describe.py` | 工具数据 | 中文词条表和枚举JSON来自本模块目录。 |
| `wf_dev_catalog.py` | 工具 + server / CDN | ROOT 为 project_root；active patch 属 server，CDN单独解析；缺配只保留本仓安全占位，实际CLI要求配置。 |
| `wf_dsl.py` | store 输入输出 | 加载/保存使用传入路径或 quest_lib 活动 store；无模块父目录根。 |
| `wf_dsl_sig.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_enhancement_policy.py` | server / CDN | chain_sources 读取 server active patches 与 CDN；显式参数优先，缺参使用统一解析器。 |
| `wf_enhancement_switch.py` | 工具元数据 + store / CDN | Context.repo只存本仓/显式repo元数据，全文件没有使用它的路径读写消费者；实际store与CDN分别走统一解析器，不要求未使用的server。 |
| `wf_export_assets.py` | 工具输出 / 受限读源 | 默认out为root_path仓内；旧find_world_upload参数不能越过解析器的仓内边界。 |
| `wf_extract_paths.py` | 受限 legacy 读源 | 旧parent只传find_world_upload且已拒仓外；显式--store可读指定位置。 |
| `wf_field_catalog.py` | store 输入输出 | 访问quest_lib的显式活动store；无模块父目录根。 |
| `wf_fire_analysis.py` | 工具输出 + cdndata输入 | logs/fire_analysis.json工具根；character/textresolve_cdndata_dir（显式cdndata优先，否则配置server）。 |
| `wf_gui.py` | 工具 + server / CDN / store / DB | 工具脚本/work保持本仓；server assets、token、URL与存档默认分别延迟解析显式server；CDN/store独立配置。 |
| `wf_harvest_paths.py` | 受限 legacy 读源 | 旧parent只进入拒仓外的find_world_upload；不写模块父目录。 |
| `wf_kyle_canary.py` | 已归档 | M0已移至archive/legacy/tools，不是当前活动根模块；不为历史入口改写路径。 |
| `wf_mod_tool.py` | 统一配置核心 | project_root是本仓；env > profiles/local.json > 报错；旧profile警告兼容；禁止仓外自动扫描。 |
| `wf_night_pack.py` | 已归档 | M0已移至archive/legacy/tools，不是当前活动根模块；不为历史入口改写路径。 |
| `wf_night_shadow.py` | 已归档 | M0已移至archive/legacy/tools，不是当前活动根模块；不为历史入口改写路径。 |
| `wf_offline_store.py` | 统一store / 工具相对输入 | 默认resolve_store_roots使用统一env/local profile链；显式profiles_path保留旧API文件布局合同。REPO_ROOT仅把legacy_zip/tail_zip相对输入转成本仓路径；materialize输出由调用方传入。 |
| `wf_offline_toolchain.py` | 工具发现 / 签名配置 | _repository_root用于FFDec浅扫描及signer配置，须为本工具仓；不能扫描/写父级兄弟树。 |
| `wf_openai.py` | 工具配置 / 显式输出 | 配置及缓存按自身配置/调用路径，未发现模块父目录ROOT消费者。 |
| `wf_pack_consolidate.py` | 工具工作目录 + server / CDN | WORK_DIR为本仓work；active patch根由server/显式参数决定，CDN单独解析。 |
| `wf_patch_ability_main_position.py` | 显式store | 输入输出由调用路径指定；无模块父目录ROOT消费者。 |
| `wf_publish.py` | CDN / server；无效ROOT参数 | 旧ROOT仅传resolve_active_store；该解析器discover=False并忽略legacy根，不会访问上级。CDN与manifest server已经显式解析，保留死参数不作无谓改写。 |
| `wf_publish_guard.py` | 工具包 + CDN | PACKS=本仓work/character_packs；CDN由配置解析，不能挪到server。 |
| `wf_quest_lib.py` | store；无效ROOT参数 | 旧ROOT只传已禁止发现的resolve_active_store；p.parent.parent是已显式store桶文件回到store，合法保留。 |
| `wf_recover_pathlist.py` | 工具输入 / 受限 legacy 读源 | root_path默认输入仓内；旧parent只传已拒仓外的find_world_upload。 |
| `wf_release.py` | server / CDN / store | _repo_paths已恢复B显式三根解析；staging/snapshot归属所配置server工作区。 |
| `wf_release_guard.py` | 调用方显式server / CDN | repo_root是参数用于active patch；不从模块层级推导。 |
| `wf_remediation_baseline.py` | 调用方显式server | repo_root必须由CLI/API给定，database/manifest/env及证据run_dir由该授权输入派生。 |
| `wf_rogue_banner.py` | 工具pending / server / CDN | pending和publisher本仓；发布前解析server/CDN，cwd用显式server。 |
| `wf_rogue_build.py` | 工具数据 / store / server | MOD_DIR用于rogue规则；ROOT只剩未用的本仓常量。--write在任何表读取/生成前解析server；quest/folder/publish使用该根。 |
| `wf_rogue_bundle.py` | store | 经quest_lib/显式store读取闭包；无模块父目录ROOT消费者。 |
| `wf_rogue_nerf.py` | store | 表操作经quest_lib；无模块父目录ROOT消费者。 |
| `wf_rogue_reroll.py` | 工具CLI + server | builder路径与子进程cwd都在本仓；服务端quest/auth及DB根均显式解析；--apply在连接DB/启动builder前检查server/CDN。 |
| `wf_rogue_rewards.py` | 工具素材 + server / CDN / store | 源图本仓，镜像server；publisher本仓/cwdserver；写前CDN门禁。q.store_path(...).parents[1]是显式桶路径回到store。 |
| `wf_rogue_save.py` | server / DB / device | server与DB运行时解析，纯import无需server；random-boss在DB/device/表写前检查server/CDN，子进程使用WF_STORE。 |
| `wf_rogue_shop.py` | server / store | 镜像与回滚目标来自显式server；ASSETS_DIR仅保留调用方显式override。 |
| `wf_rogue_validate.py` | server + 工具素材 | CLI assets显式server；PNG来源工具目录；client-patch用显式参数或server。 |
| `wf_scan_masterdata.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_selftest.py` | 显式store | 通过活动store解析，未发现模块父目录ROOT消费者。 |
| `wf_seris_release_pack.py` | 已归档 | M0已移至archive/legacy/tools，不是当前活动根模块；不为历史入口改写路径。 |
| `wf_server_auth.py` | 调用方显式server | repo_root是传入的.env根；GUI/rogue调用方必须给真实配置server。 |
| `wf_share_variant.py` | server / CDN + 显式输出 | repo_root用于active patches；CDN与输出独立，不能退回父/.cdn。 |
| `wf_store_materialize.py` | server / CDN + 显式输出 | CLI已用resolve_server_dir/resolve_cdn_root；输出store另由参数给定。 |
| `wf_story_export.py` | store + 工具输出 | 默认store必须显式配置；DEFAULT_PATHLIST和DEFAULT_OUT本来已在本模块目录。 |
| `wf_sync.py` | 工具派发 | 由GUI导出的工具根及显式设备参数工作，无自行推导ROOT。 |
| `wf_ui_derive.py` | 无ROOT/REPO消费 | 未发现模块层级ROOT/REPO路径消费；输入输出按调用参数或模块本地数据工作。 |
| `wf_unique_mech.py` | 工具输出 + cdndata输入 | all_analysis/unique_assign在工具logs；character/textresolve_cdndata_dir（显式cdndata优先，否则配置server）。 |
| `wf_voice.py` | 显式工具配置 | WF_FFMPEG设置即权威：空、相对或不存在必须报错；未设置才查PATH，不再猜voice-tools。 |

六个补查入口已提交 `b0054ee`，其专属测试18通过，关联组361通过/25跳过/167子测试通过。rewards/shop/validate回收B已有路径思想，save采用延迟解析避免B的import强制依赖；banner/balance_suite是M1/M2补修。其余analysis/GUI/flow/reroll/offline/enhancement/share/consolidate及voice在 `ec6779d` 回收，16套374通过/4跳过/52子测试，offline默认链及voice补充组66通过/1跳过/15子测试。H1独立阅读最终diff确认未吞显式配置错误、没有lazy None直接做路径运算、发布前所需根已解析；最终全量结果见M0-REPORT。
