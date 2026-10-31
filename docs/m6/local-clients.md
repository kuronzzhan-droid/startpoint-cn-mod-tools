# 本地客户端登记与 v35k3 方法证据

`local-v35k3` 是本地自用 `com.leiting.wf` 档案，**不是测试服包**。登记只说明离线 APK/SWF 及已核方法证据；不说明安装、设备行为、联网目标或服务端部署。默认客户端仍是 `test-v34`，旧发布默认档案也不变。

## 一键登记后续 v35 本地包

```text
python -B -m wf apk register-local <v35版本-local-wf-x86.signed.apk>
python -B -m wf apk provides <v35版本-local-wf-x86.signed.apk> --out work/my-client/provides.json
python -B -m wf apk kinds --profile local-v35版本 --out work/my-client/kinds.json
```

例如 `v35k4-local-wf-x86.signed.apk` 默认使用 `local-v35k4`。文件名不是 `v35...-` 开头时，明确传入 `--profile local-自选英文标识`；标识只接受小写字母、数字和连字符。名字只用于生成档案 ID，**不用于推断能力**。

命令读取 APK 的真实二进制 AndroidManifest.xml、全部非签名 ZIP 成员摘要及主 SWF。包名必须是 `com.leiting.wf`；`com.leiting.wt`、坏 ZIP、缺 SWF、损坏 manifest、没有任何完整方法证据的输入均拒绝。输入 APK 始终只读。

新登记保存到当前 checkout 的 `work/local-clients/<profile>/`，包含 `registration.json` 和 `provides.json`。它们自动进入 `load_profiles()`、CLI、编辑台选择与交付兼容检查，保留在 Git 忽略目录。同名且相同完整 APK SHA 重复执行返回 `already_registered`；同名不同内容拒绝覆盖，需要新的 `--profile`。先在本 checkout 的隐藏暂存目录写齐两个 JSON，再整体更名；写入失败不会暴露半份档案。不能把登记输出改到 checkout 外。

旧 `wfx_gate` 也接入同一登记。它对 `local_candidate` 同时核验登记 APK/SWF 对、当前 provides 文件摘要、实际提供的能力 ID，以及从方法证据重新推导的能力 ID；单独添加能力名不会放行。其纯推导缓存按登记完整内容、参考证据和全部 registry YAML 内容摘要失效，每次仍重新验证所提供文件的摘要。显式指定另一份 profiles 文件时，不混入全局本地登记。

内置 `local-v35k3` 的资料在 `client_profiles.json` 与 `wf/apk/data/local-v35k3-*.json`。运行相同原始包的登记命令会重新读取真实方法后返回幂等结果，不创建另一份档案。

## 能力依据与拒绝边界

参考文件 `wf/apk/data/v35e-method-contexts.json` 来自完整 SHA 锁定的真实 v35e SWF。838 个去重方法都按实际方法体重新取 SHA，并与原归档的 1,056 条非空方法记录（含跨补丁重复和独立方法）核对一致。方法定位覆盖短名、全限定名、script initializer、匿名方法与闭包，不依赖方法体序号猜测名字。

`register-local` 对每个方法同时比较 code SHA 和引用上下文指纹。指纹包括方法签名、异常表、直接引用的 string/int/uint/double、namespace 与 namespace set、multiname、activation slot/const trait 的类型和默认值、`newfunction`/`callstatic` 的直接方法上下文，以及 `newclass` 对应的类声明。PrivateNs 保留池索引身份，不能把两个同文本私有命名空间当成一个。不能解码的 opcode 或不支持的 activation trait 直接拒绝。

一个补丁的全部已登记方法都与参考 code 和上下文一致，才提供它及依赖它的能力。独立方法能力仍要求自己的全部方法；native、ANE、资源、原生 SDK 或只有空方法摘要的记录不由 SWF 授权。登记不自动追认新方法、新机制，也不将发生变化的方法标为“有意且兼容”。静态直接引用检查不是完整动态调用图证明，也不是设备验收。

接受的旧方法变体只绑定本次登记的完整 SWF SHA，不扩展未知 SWF；显式传入的自定义 registry 保持调用者的边界。`withheld` 表示**尚未证明等价**，不表示客户端必然不支持。它列在 `provides.warnings` 中，因此成功识别档案的 `provides` 命令可以退出 0；交付若确实需要其中某项能力，仍由兼容检查明确阻断。

## v35k3 身份与 v35e 差异

| 项目 | v35e | local-v35k3 |
| --- | --- | --- |
| 包名 | `com.leiting.wt` | `com.leiting.wf` |
| versionCode / versionName | `1008003` / `1.8.1` | `1008001` / `1.8.1` |
| APK SHA-256 | `aab1f83518f5f2994d5aba409f7b8ce9b889598a2ce2db5de48e6928e5950c26` | `6981c48c42e43ebf6b85e5893cf40357affe4e7a31787e078f0ce28c3cd5f807` |
| SWF SHA-256 | `89461f676b57a059bde58fe5897190db9b61013ae63947401fe1bf87106d6bcf` | `c52e01b8a536f78a06f48cce07bd3e0f23b3814b9b7f861e02a20755f74cc2c1` |
| 非签名成员摘要 | `9c3fbf84b4f7018dfc926ffac1be86854bd63eecde5f44a87f1806a4d788b5de` | `f1340914ff3d8a7ec56a10787d8fb16d276da3cfccd0baa05795108f4b963c9c` |

原 APK 位于 `${WF_ROOT}/out/水杰拉德-20261018/local/v35k3-local-wf-x86.signed.apk`。

- [APK 成员逐条差异](m62-package-diff.json)：两包各 6,131 个成员，6,122 个逐字节相同，9 个变化。其中 3 个是签名成员；6 个 payload 是 manifest、bundle、bundle SHA1、SWF、classes.dex 和 resources.arsc。bundle 内另列 5 个成员差异。原生库与 ANE 成员未变，但这不补足原先没有方法证据的能力声明。
- [全 SWF 逐条差异](m62-full-swf-diff.json)：304 个 ABC 中 301 个完整原字节相同。方法体总数 96,825 → 96,863；29 个已有方法体变化、38 个新增、0 个删除，96,796 个已有方法体保持。池及声明结构变化另列，敏感常量只保留摘要。
- [已登记方法逐条差异与能力清单](m62-registered-method-diff.json)：838 个去重已登记方法中，808 个 code 和上下文都相同；23 个 code 改变、7 个仅引用上下文改变。每项均列 ABC、方法名、涉及补丁、完整前后 code/context SHA；这些数字是注册范围，与上一项全 SWF 范围不同。

本档案提供 **112 项能力、95 个补丁**，v35e 原有 179 项能力中的 **67 项未证明**，没有新增能力声明。
运行时依赖复核后，撤回 R3 装备回槽、充能上限、灼伤及 #5/#53/#115/#116：解析入口未变不足以证明下游 #31/#112 的运行时等价。
它仍包括描述覆盖与普通 kind 422；不会复制已变化的直击基础、溢出治疗等能力。4 项旧官方系统声明也未从“这是 v35”推断继承。

另撤回 #129 装备规则和 #108 O8：前者缺完整方法基准，后者缺台座资源绑定证据。
下面逐项列出 36 个暂扣补丁；另暂扣 R3 独立方法能力。
方法差异 JSON 保留原审计快照，当前能力与 withheld 清单以 `wf/apk/data/local-v35k3-registration.json`
和可重算的 `local-v35k3-provides.json` 为准。

| 补丁 | 暂扣依据 |
| --- | --- |
| 5 | 下游 #112 的 WFX 状态规格未证明等价 |
| 19 | ClientAdmission 的 beforeQueue、load、refreshSession、transport 及匿名方法 27、31 的引用上下文变化 |
| 31 | ActionEvaluator/evalCommand 改变 |
| 42 | DevConfig_gf_android 构造器引用上下文改变 |
| 52 | 与补丁 19 相同的 6 项 admission 方法依据 |
| 53 | 下游 #112 的 WFX 状态规格未证明等价 |
| 54 | MemberImpl/scheduleDirectAttack 改变 |
| 56 | MemberImpl/scheduleDirectAttack 改变 |
| 78 | OwnedOverLimitLogic/getAwakingCrystalToOverLimit 改变 |
| 79 | 原登记为非 SWF / 空方法证据，不能从本次方法核验授予 |
| 80 | GeneralCharacterLogic/getPedestalImagePath 改变 |
| 81 | GeneralCharacterLogic/getHalfPedestalImagePath 改变 |
| 82 | 原登记为非 SWF / 空方法证据 |
| 84 | OwnedOverLimitLogic/getOverLimitState 改变 |
| 85 | OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit 改变 |
| 86 | 原登记为非 SWF / 空方法证据 |
| 97 | 原登记为非 SWF / 空方法证据 |
| 98 | 原登记为非 SWF / 空方法证据 |
| 99 | 原登记为非 SWF / 空方法证据 |
| 100 | 原登记为非 SWF / 空方法证据 |
| 101 | OwnedCharacterLogic/getPossibleOverLimitCountByItem 改变 |
| 108 | O8 台座资源未绑定非 SWF 资产证据 |
| 109 | OverLimitWindow/getOverLimitState 改变 |
| 110 | OverLimitWindow/run、getStatusInformation 改变 |
| 111 | ExpodOverLimitByItemDialog/getDescription 改变 |
| 112 | ConditionSlot$/wfxSpec 改变 |
| 113 | MemberImpl/scheduleDirectAttack 改变 |
| 114 | MemberImpl/scheduleDirectAttack 改变 |
| 115 | 下游 #112 的 WFX 状态规格未证明等价 |
| 116 | 下游 #112 的 WFX 状态规格未证明等价 |
| 120 | BattleCharacterLogic 的 getOpitionAbilitiesWithoutAbilitySoul、getInstantAbiltyCountWithoutLimit、wfxPartyMask、wfxExtraLeaders 改变 |
| 121 | BattleCharacterLogic/getElement、wfxAdaptiveElement 改变 |
| 122 | AbilityDamageShot/finish、MemberImpl/applyHeal、SquadManagerImpl/updatePhase 改变 |
| 125 | AbilityDamageShot/finish、UniqueConditionLogic/wfxSuperPreload 改变 |
| 129 | 方法基准未覆盖 wfCountEquipment 及完整预载调用上下文 |
| 130 | ConditionSlot$/wfxSpec 改变 |

## 验证证据

M6.2 在真实 APK 上执行了 `provides`、`register-local` 两次及 `kinds --profile local-v35k3`，均退出 0；`kinds.mismatches` 为空。`resolve_client` 成功并核对证据文件与 APK/SWF 摘要。描述覆盖、kind 422、普通 leader instant kind 423、R3 ability_soul during kind 423 的兼容检查通过；请求暂扣的 `client.direct.base@1` 明确阻断。原 APK 和参考 SWF 核验前后完整 SHA 相同。

上段是 M6.2 原执行记录；本次运行时依赖复核已纠正其中 R3 的过度授予。
当前请求 R3 必须因 #31 证据不足阻断，不能把历史通过结果用作现行授权。

测试覆盖同 code 不同常量、私有 namespace 身份、activation 默认值、newclass 声明、显式 registry 不扩权、缺方法、假 SHA、坏 APK、测试服包、同名冲突、幂等、写入失败不暴露半份档案，以及“同 kind 的另一能力暂扣时不误报已知表越界”。当需要完整设备语义或新能力授权时，必须另行补齐对应方法审阅和验收证据。
