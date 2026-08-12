# WF 独立发行工作台

`wf_release_ui.py` 是独立于旧 `wf_gui.py` 的 loopback 工作台。它把已经完成的严格 CLI 能力按十个阶段
串起来，不重新实现分享包、角色工作区、Overlay、TargetProbe 或兼容性 parser。

## 启动

```powershell
python -X utf8 wf_release_ui.py --open
python -X utf8 wf_release_ui.py --port 8767
```

服务固定绑定 `127.0.0.1`，端口默认为系统分配。页面持有每次进程启动时生成的随机会话 token；
准备操作只接受带 token 的 strict JSON POST。API 返回不回显输入绝对路径。

## 十个阶段

1. **检查分享包**：验证旧 `wfshare` 方言、ZIP、分片、report/requires、脚本与 server-data 风险；
2. **隔离导入**：只写一个明确的新目录，脚本进入 quarantine，绝不执行；
3. **采纳角色**：完整路径映射 + 显式表 claim + 四张角色服务端表 → production 37/37 sealed workspace；
4. **创建编辑副本**：保持原封印 workspace 不变，以递增包版本创建隔离副本；
5. **重新封印**：对编辑后的已声明文件重做 37/37、所有权和 seal；
6. **2D 预览**：普通 PNG、pixelart atlas/timeline 或 sealed workspace；
7. **生成 Overlay**：从 sealed workspace 客户端 roots 构建确定性 Patch Overlay；
8. **捕获 requirements**：把角色 capabilities 与当前 TargetProbe 事实绑定；
9. **目标能力检查**：只读区分 `modern`、`transition`、`legacy` 并列出阻断码；
10. **安装计划**：完整验证 Release，按目标能力预览版本、ownership、no-op 与恢复边界。

页面**没有** `install`、`rollback`、`publish`、store materialize 或设备按钮。安装和恢复继续保留在带精确
确认词的 CLI；真实发布仍需单独授权。这样浏览器工作流不会把“预览/准备”误变成 live 写入。

目标能力级别不是用户开关。`modern` 必须由严格 capabilities、Server Bundle 与 Runtime 三方一致证明；
`transition` 必须是 capabilities 精确 404、旧 CDN 三层闭包有效且工具持有运行进程；其余旧服归为
`legacy`，只允许检查、导入、编辑、预览和导出。工作台不会把缺失证据自动降级成更宽松的写权限。

## 导入其他人的包后能编辑到什么程度

- `mappingStatus=complete`：客户端 payload 进入 `roots/<root>/<logicalPath>`，可在隔离工作区内用现有
  表/资产工具编辑，然后重新做 claim、37/37 与 seal；
- `mappingStatus=opaque/partial`：只有哈希存储路径，不能可靠知道逻辑资源名，工作台拒绝把它伪装成
  可编辑角色；需要作者提供映射或从可信 PathList/包清单建立逐条证据；
- 包内脚本与 server-data 始终隔离。UI 不提供“运行作者脚本”按钮；
- 目前 UI 是严格流程编排器，不是通用表格/DSL/贴图编辑器。具体编辑仍由小型专用工具完成。

## CDN 版本冲突、兼容导入和恢复

Patch Overlay 是一条显式 `fromVersion → targetVersion` 边。工具不会通过改文件名、跳过起点或覆盖
`cdnRoot/cn` 来“兼容”冲突：

- 同一基线制作的两个包必须按 Overlay 唯一递增链重新基于前一包链尾构建；
- `capture-requirements` 锁定当前 `contentDigest`、clientVersion 和 resourceBaseline；
- `plan-install` 在任何 materialize/停服之前给出不兼容码；
- 安装器只切换 `cdnRoot/patches/<targetVersion>`，并保留精确 previous receipt；
- 回退只恢复保留的 Content/Mode 状态，不宣称数据库/存档可安全降级。

罗尔夫范例的边为 `1.4.324 → 1.4.347`。若目标当前不是该起点/content digest，不能直接导入；应从
目标真实链尾重建 Overlay 和 requirements，而不是覆盖版本号。恢复也必须以该目标自己的 retained
previous 为准。

## 罗尔夫迁移边界

`docs/examples/legacy-character-adoption.rolf.json` 已覆盖 20 张客户端表、超级 Fever、三档特殊强化
弹射、unique condition 180000 与四张角色服务端表。客户端部分可生成 sealed workspace、2D 预览和
Patch Overlay。当前服务端 Content Sync 已能从这些权威 orderedmap 动态生成 `character.json`、
`cdndata/character.json`、`cdndata/character_text.json` 和 `mana_node.json`；不需要再为罗尔夫提交静态
四表行，也不得执行隔离区里的 `apply_rolf_rows.py`。服务端仍须合并 capabilities/Content Sync 契约栈，
具体依赖和 PR 边界见 `docs/wf-release-v1-server-integration.md`。

动态转换回读还确认旧脚本里的 `character.json[179999]` 已过时：当前 converter 按契约输出空 `name`
和六个技能位，而不是旧脚本的中文名与三个技能位。静态合并旧行会制造第二权威并覆盖正确派生结果。

2D 预览能复现罗尔夫常规像素动画的 9 个序列/428 个 timeline 帧，也能切换 special 的 2 个序列/
168 个 timeline 帧；超级
Fever 仪表、三档光柱与融雪剑的 `parts` 骨架/矩阵/补间仍只能作为素材和数据证据，不是真机演出证明。

## 当前 UI/UX 仍需补强

- Windows 原生文件选择器；当前为粘贴绝对路径，换来更小的桌面依赖和清晰的安全边界；
- client table、DSL、角色属性的 schema-aware 表单编辑；当前只编排已有严格工具；
- 多发行物 Overlay 链的可视化与 dry-run diff；当前结果是机器可读 JSON；
- server-data migration 的独立评审/生成页；在服务端契约未确定前不放宽；
- 战斗 `parts` 骨架与矩阵补间渲染、声音同步和真机验收登记。

这些缺项不会通过调用旧 GUI、猜 profile 或直写 live root 绕过。后续每项应作为独立小模块接入。
