# M2.2 客户端档案与后端接口

`wf deliver` 与编辑台「生成」默认选择 `client_profiles.json` 的
`default_client_profile`，当前为 `test-v34`。选择 `test-v35e` 必须明确传入档案名。
旧发布器的 `default_publish_profile` 保持自己的授权边界。

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
