# 交付前本地服只读预演

预演读取已有交付和本机配置的服务端目录，检查版本边能否追加，并生成同一份可供本地与测试服 175 使用的 manifest 条目候选。它不会复制 ZIP 到服务器、改 manifest、合并服务端 JSON、停启服务、访问数据库或操作模拟器。它也不会建立新的草稿 change 或重新出包；原有 compile → build_draft → deliver/check 链路保持。

## 本机配置

在不入库的 `profiles/local.json` 增加可选字段：

```json
{
  "wf_root": "<资料根目录>",
  "servers": {
    "local": {"root": "<本地服务端目录>"},
    "test175": {"root": "<测试服只读快照目录>"}
  },
  "rehearsal_server": "local"
}
```

`servers` 与 `views`、版本 `profiles` 独立。`root` 必须指向包含 `assets/asset-patch/manifest.json` 和 `active/` 的服务端根目录；相对路径按既有 `wf_root` 规则解析，支持环境变量和用户目录展开。`WF_PATHS_PROFILE` 可选择配置文件。server 名称只允许 1–64 位字母、数字、下划线或连字符，首位必须为字母或数字。

`rehearsal_server` 缺省或 null 时不自动预演；设置后，角色、武器和副本共用的 `build_draft` 在生成交付检查报告后自动跑一次。构建未产出交付、编译直接异常或取消时没有可预演的交付。自动结果写入 `build-report.json.rehearsal`。**构建 `ok` 与 `rehearsal.ok` 分开**：构建成功不代表适用于当前服务端，前端必须单独显示。

现有 Studio 候选会携带 `local_test_only`。预演会阻断它，不会将本地候选偷偷转成可部署条目。生成的 `manifestEntry` 不含该标记，但在 `status=blocked` 时仍然只是候选，不得追加。原交付、原标记与既有交付门禁保持原样；本功能不提供取消本地限定或正式发布的接口。

## CLI 与 Python

```powershell
python -m wf.studio.draft rehearse --delivery-dir <构建根目录或交付目录> --server local
python -m wf.studio.draft rehearse --delivery-dir <报告目录> --server local --zip <分包1.zip> --zip <分包2.zip>
```

接受标准构建根的 `delivery/`、直接交付目录以及显式 ZIP 列表。目录优先读取 `delivery-manifest.json` 的 archives 与 legacy_manifest；历史交付可直接使用唯一的 `manifest-entry-*.json`。两种元数据都没有时扫描该目录顶层 ZIP。显式 ZIP 列表也须与同目录已有元数据一致，不能借它跳过缺失分包。

输出一行 JSON：`{"ok":true,"result":<预演结果>}`；阻断时 `ok=false`、退出码 1，通过时退出码 0。无效 server 名或不可写报告路径等操作错误返回 `{"ok":false,"error":"原因"}`。输入错误、版本冲突和摘要不符会尽量写成可审阅的 blocked 报告。

Python 函数为 `wf.studio.rehearsal.rehearse(delivery_dir, server="local", zips=None, write=True)`；关键字 `write=False` 完全不落报告，适合只读检查不可修改的历史交付。HTTP 与 CLI 默认写报告。它仅检查提供的输入；单独给 ZIP 无法证明外部未列出的服务端改动或遗漏末尾分包不存在。

## 检查范围

- 从 manifest 启用的 patch 依赖关系确认唯一连续向前链及链尾，检查顶层 cdn_version 一致；停用条目不算启用链尾。
- 交付 from 必须等于链尾，to 必须高于链尾与 from；id 或目标版本已登记（含停用条目）时阻断。
- ZIP 必须属于同一边，名称 `pinball-<from>-<to>-<序号>-<名字>.zip`，序号从 1 连续；按整数排序。
- 回读每个 ZIP，核对 CRC、重复成员（含跨分包）、路径安全、大小、SHA-256，以及已有交付或 integrity sidecar 中的摘要和成员表。
- active 同名文件 SHA-256 不同则阻断；同名相同可通过。不会写入 active。
- 输入交付或条目含 `local_test_only` 字段即阻断，值为 false 也不例外。
- `server/` 按服务端根相对路径读取，限 `assets/` 和 `out/`。历史片段按下文显式映射规则核对；README 和 merge-manifest 不作为目标，操作指令不执行。
- 服务端 JSON 递归按 JSON Pointer 列出新增、替换和候选未包含的旧键；后者必须保留，绝不默认删除。根数组另列 appendValues/omittedValues，必须逐项人工核对。已有目标标记整文件覆盖风险。标准 `assert-box.json` 中服务端候选摘要、旧值摘要和目标完整性也会核对。
- 有服务端 JSON/代码时需手工重启；只有资源时由 manifest 热加载，不需重启。预演前后复核所有实际读取的服务端文件及同名 active 文件的 SHA，检测输入漂移。

这不是完整交付质量、客户端兼容、设备运行或远端当前状态证明；已有 check/compat 与人工验收继续适用。服务端目录仅作本机文件读取，配置 test175 快照不代表连接了远端。

## 输出与手工上边

报告在解析后的交付目录中写为 `rehearsal-<server>.json` 和中文 `rehearsal-<server>.md`；不同 server 分开，重复同 server 更新最近一次。拒绝将报告写入任一已配置服务端，拒绝穿越、符号链接越界和覆盖硬链接报告。可变预演报告不列入 Studio 构建的 `SHA256SUMS`，避免再次预演使交付校验和失效。

`manifestEntry` 包含 HOWTO 要求的 `id/type/name/version/depends_on/enabled/archive/archive_size/chain/files/archive_integrity/created_at`。所有分包完整性记录都由当前 ZIP 回读生成，包含 name/size/sha256/members/files/member_sha256；已有逻辑路径映射时保留 logical。`archive_size` 为第一分包大小。条目不含机器路径；复制同一个 `manifestEntryJson` 即可供本地和 175 使用。

`manifestEntryJson` 是两空格缩进、CRLF 换行、结尾换行的 JSON 字符串；UTF-8 编码后无 BOM。服务端完整 manifest 手工写回也须保持同样格式，并同时更新顶层 `cdn_version`。以下仅为格式示例，预演不会执行：

```python
raw = (json.dumps(manifest, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n").encode("utf-8")
```

中文报告给出按配置根目录展开的逐步手工清单：先消除阻断、复核新鲜输入摘要、手工备份、核对 ZIP、逐键合入服务端、追加条目并更新 cdn_version、按需重启、人工设备验证，之后将同一批 ZIP 与同一段条目转至 175。此清单不授权或执行部署。

## 前端对接

`POST /api/deliveries/<name>/rehearse`，body **仅**接受 `{"server":"local"}`，不接受 root、任意输出路径或部署开关。沿用 `Content-Type: application/json`、`X-WF-Studio-Token`、Host、Origin 和 Sec-Fetch-Site 守卫。生成中的同一交付拒绝预演。

成功完成检查返回 HTTP 200：

```json
{
  "name": "<交付名>",
  "ok": false,
  "rehearsal": {
    "schema": "wf-studio-rehearsal/1",
    "server": "local",
    "status": "blocked",
    "ok": false,
    "currentVersion": "1.4.10",
    "from": "1.4.9",
    "to": "1.4.10"
  }
}
```

示例省略其他字段。检查阻断仍为 HTTP 200，必须读 `ok/status/checks`；请求字段、交付名、server 名或写入边界错误返回 HTTP 400 的 `error`；鉴权失败为 403。未配置 server 或输入不可读是可落报告的 blocked 结果。

`GET /api/deliveries/<name>` 新增 `rehearsal`，等于所有 server 中 `createdAt` 最新的报告，历史无报告为 null。构建响应和 build-report 也有该字段，未配置自动预演为 null。BOSS 与武器继承同一交付路由，前缀分别为 `/api/boss/deliveries/`、`/api/studio/weapons/deliveries/`。报告文件可经既有 `/file?path=delivery/rehearsal-local.md` 下载。

完整结果字段如下（schema 见 `schemas/studio-rehearsal.schema.json`）：

| 字段 | 类型与语义 |
|---|---|
| schema/server/createdAt | 格式版本、配置名、UTC ISO 时间 |
| ok/status | 布尔与 ready/blocked；不代表已部署 |
| serverReadOnly/runtime | 固定 true / 未执行 |
| deliveryDir/serverRoot | 本机报告来源目录、解析后的配置根；未配置根为 null |
| currentVersion/from/to | 启用链尾与交付边，尚未解析为 null |
| checks[] | rule/status/blocking/message；逐项结果，错误必须显示 |
| archives[] | 回读的 name/size/sha256/members/files/member_sha256，可选 logical |
| manifestEntry/manifestEntryJson | 同一条可移植候选对象及格式化字符串，任何 blocked 结果均为 null，不提供可直接追加候选 |
| manifestFormat | encoding=UTF-8、bom=false、newline=CRLF、indent=2 |
| serverChanges[] | target/source/destination、beforeSha256/sha256、baselineMatches（未声明旧摘要为 null）、kind=json/code、addedKeys/replacedKeys/omittedKeys、wholeFileOverwriteRisk、changed；JSON 另有 mergeMode，根数组另有 appendValues/omittedValues |
| restartRequired/restartReason | true/false/null 与中文理由；输入未检查完整时为 null |
| serverSnapshot | 相对路径 → SHA-256 或 null（读取时不存在），仅含实际核对文件 |
| manualSteps[] | 中文操作清单，不可自动执行 |

界面建议将预演结论单列，blocked 显示全部阻断项；不要把旧报告当作当前实时状态。上边前必须重新预演，人工核对同一份 ZIP 与条目。此次仅交付后端与接口说明，未改前端源码。

## 严格核对规则

仅采用 enabled 严格为 true 且 type 为 patch 的条目，保留 manifest 顺序，不排序修补断链。version/depends_on 必须是三段版本号且向前增长。手工清单展示实际 currentVersion，不把交付 from 冒充当前链尾。

历史 `server-entries/merge-manifest.json` 可声明 `targets: {"源文件.json": ["assets/现用表.json"]}`，支持一对多。character、cdndata/character、cdndata/character_text、mana_node 旧名没有显式映射时阻断为“未核对”；其他文件默认 assets 路径。append_object_keys 的 file/object_pointer/keys 用于检查声明新增键；目标已有同值也列入 existingClaimedKeys 并阻断。unchangedKeys 列同值键；数组只列实际新增和需保留的值，不把根数组当整表替换。

legacy_manifest 支持交付目录内的子目录；显式 ZIP、扫描到的 ZIP、sidecar 均不得越界。patch-manifest、ZIP 完整性记录和 sidecar 的 local_test_only 也参与阻断。任何 blocked 结果的 manifestEntry/manifestEntryJson 均清空。

只有完整构建成功才自动预演。预演异常保留原构建结果、报告与校验和，单独返回 rehearsal blocked。预演 IO 不占据全局任务锁，但同一交付的重复预演仍拒绝。无关损坏 server 配置不会阻止有效目标写报告。
