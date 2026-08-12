# wf-release-v1 服务端集成边界

本文记录独立发行工具与 `startpoint-cn` 服务端之间的最小契约。它不是部署脚本，也不授权推送、合并、安装或写入真实目标。

## 当前结论

- 服务端契约需要更新：目标必须提供 `GET /api/server/capabilities`，并在顶层 `serverCapabilities` 中声明实际支持的能力。
- 已基于最新 `origin/main` 建立窄分支 `codex/server-capabilities-pr`，不再依赖旧的 149-commit 混合分支。
- 罗尔夫的 Character Release 只要求 `content.sync@1`；当前窄分支可提供该能力和稳定 `contentDigest`。
- 当前窄分支不声明 `mode.release-contract@1`。任何 Mode Release 都必须继续失败关闭，不能因 Mode API 为 `1` 就推断可安装。
- 罗尔夫不应另外向服务端提交四张静态 JSON 行。服务端已有 Content Sync registry/converter，运行表应由客户端权威表动态生成。

## PR 就绪的服务端提交

目标仓库分支从最新 `origin/main` 创建，提交顺序为：

1. `e72208a5` — 为 bundled/release Content Snapshot 暴露稳定内容摘要；
2. `4435f092` — 记录由 loader 验证的 Mode 字节身份，并只声明现有五项基础 seam 能力；
3. `dbc12576` — 注册只读 `/api/server/capabilities`，投影七键精确响应；
4. `38710e1a` — 把新增覆盖纳入变更测试选择器；
5. `df7a169f` — 定义服务端能力契约并加入运行时文档索引。

该分支没有引入玩法逻辑、角色数据、管理路由、数据库迁移或工具代码。是否推送并向上游开 PR 仍需作者明确授权。

## 当前服务端能力

顶层能力集合为：

- `content.sync@1`
- `mode.hook.quest-start@1`
- `mode.hook.rush-finish@1`
- `mode.hook.rush-parties-serialized@1`
- `mode.host.base-table@1`
- `mode.host.transaction-server@1`

集合不包含 `mode.release-contract@1`。工具必须逐项比较 Release 的 `serverCapabilities` 要求，缺一项即拒绝规划或安装。

## 罗尔夫转换事实

以已封印的罗尔夫工作区为输入，当前服务端 converter 回读角色 `179999` 的四张运行表：

| 运行表 | 结论 |
|---|---|
| `cdndata/character.json` | 与隔离旧包的同角色行一致 |
| `cdndata/character_text.json` | 与隔离旧包的同角色行一致 |
| `mana_node.json` | 与隔离旧包的同角色行一致 |
| `character.json` | 按当前服务端权威 converter 重新派生 |

隔离旧包中的 `character.json` 使用中文 `name` 和旧 `skill_count`，不再是当前服务端权威形状。因此旧 `server-data/apply_rolf_rows.py` 只保留为来源证据，不得执行、迁移或改造成安装步骤。

超级 Fever、特殊强化弹射、三档光柱、融雪剑和语音属于客户端内容/资产或玩法表现验证，不是静态服务端行 PR 的理由。它们是否完整必须分别由 Release 内容闭包和真机行为验收证明。

## 跨仓契约验证

服务端生成的七键响应已直接交给工具仓 `wf_release_v1.probe._parse_capabilities` 解析，工具接受以下能力集合：

```text
content.sync@1
mode.hook.quest-start@1
mode.hook.rush-finish@1
mode.hook.rush-parties-serialized@1
mode.host.base-table@1
mode.host.transaction-server@1
```

源码开发态允许 `serverBundle.bundleId=null`，用于本地诊断；正式 TargetProbe 必须针对已验证的嵌入式 Server Bundle，因而要求真实 Bundle digest。不得用开发态响应伪造部署证明。

## 后续部署与发行顺序

1. 经作者授权后推送服务端窄分支并向目标服务端仓库开 PR；
2. 合并后构建、验证并部署新的 Server Bundle；
3. 在目标机准备显式 `target.json`，运行 TargetProbe 获取真实 Bundle、Runtime、Content 和 Mode 身份；
4. 用罗尔夫 sealed workspace 与目标事实生成 Character Release；
5. 先运行 `plan-install`，再由明确授权的操作者执行安装；
6. 重启后分别验收 capabilities、Content Sync 运行表和客户端真机行为。

没有真实 `target.json` 和 TargetProbe 事实时，只能交付 Overlay、legacy 分析计划和准备工作区，不能伪造最终 requirements。没有真机战斗观察时，也不能把超级 Fever、三档特殊强化弹射或融雪剑宣称为设备验收通过。
