# wf-release-v1 服务端集成边界

本文记录独立发行工具与 `startpoint-cn` 服务端之间的最小契约，不是部署脚本，也不授权向远端推送。

## 结论

- 服务端契约有更新：目标服务端必须提供 `GET /api/server/capabilities`，并在顶层
  `serverCapabilities` 中声明 `content.sync@1` 及已支持的 Mode 能力。
- 罗尔夫不需要单独提交四张静态 JSON 表。服务端现有 Content Sync registry/converter 已从客户端
  orderedmap 动态生成角色运行表，静态行会成为第二权威。
- 当前 `codex/platform-capabilities-v1` 不能直接作为面向 `origin/main` 的 PR：它相对上游含 149 个
  提交、279 个文件，混有多人模式、后台和任务系统工作。必须在具备 Mode release 基础设施的目标分支上
  抽取窄提交，不能把整条历史一起合并。

## 罗尔夫转换证明

以已封印的罗尔夫工作区为输入，用当前服务端编译后的 converter 回读角色 `179999`：

| 运行表 | 结果 |
|---|---|
| `cdndata/character.json` | 与隔离旧包的同角色行一致 |
| `cdndata/character_text.json` | 与隔离旧包的同角色行一致 |
| `mana_node.json` | 与隔离旧包的同角色行一致 |
| `character.json` | 按当前契约重新派生；`name=""`、`skill_count=6` |

旧包隔离数据里的 `character.json` 使用中文 `name` 且 `skill_count=3`，不再是当前服务端权威形状。
因此 `quarantine/server-data/apply_rolf_rows.py` 永远只保留为来源证据，不得执行、移植或改造成安装步骤。

## 推荐的服务端提交栈

目标分支必须先具备当前 Mode registry、loaded-mode identity 与 mode digest 基础设施；仅有上游
`origin/main` 时不能直接套用以下补丁。前置满足后，按顺序抽取：

### 运行时与门禁

1. `7de965e7` — 构建本地 capabilities snapshot；
2. `7df83853` — 按 Unicode 码点排序 Mode identity；
3. `765e7a9f` — 注册 `/api/server/capabilities`；
4. `16c1bcc1` — 暴露通用顶层 `serverCapabilities`；
5. `04ace802` — 把 capabilities 测试纳入工作流选择器。

`8dbacab7` 是相邻的 benchmark fixture 修复，不是发行契约依赖，不应为了保持原历史而被强行捎带。

### 契约文档

1. `0789f5e8` — 本地 capabilities 发现协议；
2. `64d82038` — wf-release-v1 本地平台契约；
3. `b267308b`、`3620366f`、`c96960d2`、`12d5dcd8` — 顶层能力、冻结期、示例与 ownership
   的后续收敛。

抽取后必须在目标分支重新运行 capabilities focused tests、TypeScript 检查和服务端构建；原分支通过不能
替代目标分支验证。

## 部署与 PR 顺序

1. 先把上述窄契约栈合并到真实服务端目标分支；
2. 用目标机的 `target.json` 运行 TargetProbe，捕获真实 content digest、客户端版本与资源基线；
3. 用罗尔夫 sealed workspace 与 Patch Overlay 生成最终 Release；
4. 先 `plan-install`，再由明确授权的操作者执行 install；
5. 重启后以 capabilities、Content Sync 运行表和客户端真机行为分别验收。

没有真实 `target.json`/TargetProbe 事实时只能交付 Overlay 和准备工作区，不能伪造最终 requirements；
没有真机战斗观察时也不能把超级 Fever、三档特殊强化弹射或融雪剑宣称为设备验收通过。
