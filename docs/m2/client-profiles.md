# M2.2 客户端档案与后端接口

`wf deliver` 与编辑台「生成」默认选择 `client_profiles.json` 的
`default_client_profile`，当前为 `test-v34`。选择 `test-v35e` 必须明确传入档案名。
旧发布器的 `default_publish_profile` 保持自己的授权边界。

## 新 APK 登记与 1008094 证据

`python -m wf apk provides <APK> --out work/client/provides.json` 只识别已登记的完整 SWF
摘要；未知摘要的 `unknown APK/SWF digest; provide a method/patch summary record` 是证据门槛。
它不会按 APK 文件名、versionCode 或 README 声明自动继承旧版能力。

自用包可执行：

```text
python -m wf apk register-local <APK> --profile local-example
python -m wf apk provides <APK> --out work/client/provides.json
```

`register-local` 仅接受 `com.leiting.wf` 和 `local-...` 档案名，写入忽略目录
`work/local-clients/<档案名>/registration.json` 与 `provides.json`。
它解析实际 AndroidManifest 和 SWF，对固定 v35e 基线的每个方法比较 code 摘要和
常量、namespace、签名、异常表等引用上下文摘要；一项补丁的必需方法全部一致才授予能力。
变更、缺失、native/ANE 方法列入 withheld。不要改包名或取消此限制去登记测试服 APK。

公开测试服档案采用可审阅的证据文件与 `client_profiles.json`：

1. 从实际 APK 读取包名、versionCode，记录各架构 APK SHA-256 和内置 SWF SHA-256。
2. 用 `wf.apk.method_snapshot.snapshot` 提取实际方法及上下文摘要，与
   `wf/apk/data/v35e-method-contexts.json` 比较；`verified_evidence` 仅保留完全证明的补丁。
   语义已改变的方法需要额外的代码审查和绑定该 SWF 的 accepted_variants，不能仅替换摘要。
3. 把不含原始代码、官方资产、本机路径的 registration/provides 放在 `wf/apk/data/`，
   通过 `wf.apk.local_registry` 的固定已审阅记录表注册。`provides_for` 可从 registration 重算结果。
4. `client_profiles.json` 增加档案：`package_name`、`versionCode`、`provides` 相对路径、
   `provides_sha256`、`m2_capabilities`，以及 `evidence.swf_sha256`、`apk_sha256_by_arch`。
   `resolve_client` 会校验 provides 文件摘要及它与档案的 APK/SWF 绑定。
5. 由配置维护者在忽略的本机 profile 中设置 `client_apks.<档案名>` 路径数组；
   撞名检查和实际 kind 分支检查使用这些 APK。登记摘要不会替用户下载或安装 APK。
6. 运行 `wf apk provides`、档案测试和交付检查。只有目标工作流所需能力都有充分证据时才改默认。

已登记 `test-merge-1008094`：包名 `com.leiting.wt`，versionCode `1008094`，
arm64 与 x86 包的内置 SWF 相同：
`2fa334cca6b104bdcae061c5ed9bc63eb52d59db7e687c90d24742e61759e7b4`。
838 个方法观察记录保存在 `test-merge-1008094-registration.json`，
103 项可证明能力保存在 `test-merge-1008094-provides.json`；44 个补丁证据组仍 withheld。
这是静态能力证据，不是设备验收、安装或部署结果。

**默认仍为 test-v34**：1008094 的 PF4、直击基础倍率、WFX 状态规格等关键方法与 v35e
已审核基线不同，完整继承尚未证明。还需审核 `MemberImpl/startPowerFlip`、
`BattleFlipperImpl/update`、`BattleFlipperView/draw`、`ConditionSlot$/wfxSpec`、
`MemberImpl/wfxDirectFactor` 等变更方法，以及 native/ANE/资源类证据。
README 所述 C25/C26、伤害数字配色等新增行为未凭版本说明授予能力；需要相应方法与语义审查。
withheld 表示待验证，不代表已证明不支持。生成时可显式选择新档案，但缺失能力检查仍阻断。

## 命令行与生成结果

```text
python -m wf deliver changeset.json --out work/my-delivery --client-profile test-v35e ...
python -m wf.studio.draft build 139990 --from 1.4.236 --to 1.4.237 --out work/my-draft --client-profile test-v35e ...
```

省略 `--client-profile` 时使用默认档案。单独提供 `--provides` 仍可比较明确指定的
客户端证据；同时提供档案名时，两者的文件摘要、SWF 和 APK 摘要必须相符，否则直接报错。
档案 `provides` 指向任务要求的 `work/m2_2` 产物；干净检出没有该文件时，只读使用
`provides_fallback` 指向的入库证据。两份文件各自有固定 SHA-256，不从版本名推断能力。

交付产生 `provides.json`、`compat.json`，并在 `delivery-manifest.json` 的
`client_compatibility` 记录档案与结果。缺能力时 `wf deliver` 返回非零退出码；
编辑台构建结果 `ok=false`，读取交付时重新比较，不能通过修改成功标记绕过检查。
编辑台原有显式 `--allow-unknown-client` 仍用于缺客户端证据的本地草稿，结果标为
「未确认」并留痕；明确选择档案后，该选项不免除所选档案的比较。

## 只读 HTTP 接口

`GET /api/client-profiles` 返回 `defaultClientProfile` 和可选 `clientProfiles`。

`GET /api/capabilities/requirements` 接受以下查询参数，其中前三项可以重复：

| 参数 | 含义 | 示例 |
| --- | --- | --- |
| `kind` | 注册的词条 kind | `422` |
| `unique` | unique_condition 的 c0 字符串 | `wfx:28:72:10000:3:hidden_test` |
| `dsl` | DSL 节点名或注册的 DSL selector | `dsl.buffTargetAs.convert` |
| `selector` | 精确注册的 selector | `wfx.hidden_unique_icons` |
| `customKey` | custom_ability_string 的键 | `wfx_pf4_139990` |
| `uniqueId` | 固有状态 UID，用于区分旧 Fever 固定范围与新通用范围 | `1299910` |
| `clientProfile` | 本次比较的选中档案，缺省为默认档案 | `test-v35e` |

响应包含 `capabilities`、`requiredClientProfiles`、逐档案 `profiles` 检查详情、
`clientProfile` 和 `selectedCompatible`。`recognized=false` 表示标记没有命中注册能力，
不能据此声明未知数据有效。`requiredClientProfiles` 是能满足本次已登记能力需求的档案集合，
并非客户端安装或设备实测结果。

`GET /api/deliveries/defaults` 同时返回默认档案及可选档案；
`POST /api/drafts/<cid>/build` 请求体的 `clientProfile` 指定本次生成档案。
请求指定档案会覆盖编辑台启动时的默认 `provides`，但请求同时携带互相矛盾的
`clientProfile` 与 `provides` 会报错。前端应随当前选择发送 `clientProfile`。

## 依赖与方法证据边界

角色引用闭包包含角色对应的 PF4、视觉、Fever 语音配置，以及引用能力的自适应属性、
队长技能解锁、PF override 快照配置。单独修改这些能力或 PF 表时也会跟随相同配置键。
`ModDualForm:<uid>`、新的 Fever UID 范围或第 4 段 `lvN` 使用 v35e 语义；
原有无参数双形态及旧 Fever 数据保留 v34 能力声明。

隐藏 WFX 图标严格匹配 `wfx:` 前缀和第 6 段的 `hidden_` 前缀，与 v35e HUD 方法一致。
数值字段是否合法由相应数据规则判断，图标能力检测不把非法数值误当作不存在的隐藏标记。

旧能力方法哈希保留原值；有意更新的方法通过 `accepted_variants` 绑定具体 SWF 摘要、
新方法摘要、来源和原因。来源声明为该 SWF 时仅接受该版本方法；未知方法、缺少方法、
能力与补丁两份记录不一致仍阻断。通过离线比较不等于完整游戏语义或设备行为已验证。
