# 本机路径配置

复制 `profiles/example.json` 为被 Git 忽略的 `profiles/local.json`，按需填写真实目录。
外部输入的唯一优先级是 **环境变量 > profiles/local.json > 未配置报错**。
没有自动扫描数据包、兄弟仓库或服务器目录的步骤。单纯声明 `wf_root` 不再自动推测 store、kulo、store131、runtimes 或 server。

```json
{
  "wf_root": "../work/external",
  "paths": {
    "store": "phone/WorldFlipper/dummy/download/production/upload",
    "server": "server",
    "cdn_dir": null,
    "cdndata": "server/assets/cdndata",
    "kulo": "kulo",
    "store131": "store131/production/upload",
    "runtimes": "runtimes"
  }
}
```

`wf_root` 的相对路径以配置文件所在目录为基准；`paths` 中的相对路径以 `WF_ROOT` 或 `wf_root` 为基准。
路径可写绝对路径。环境变量路径必须为绝对路径（`WF_ROOT` 保留相对配置文件目录的兼容规则）。
配置解析不会创建输入或输出目录。JSON 中的 `null` 表示未配置，空字符串、非字符串、显式指定但不存在的配置文件都报错。
调用 store/server/CDN 解析器时，显式目录不存在或形态错误也会报错，不会被 `lax` 当作未配置吞掉。

| 路径键 | 规范环境变量 | 旧别名 |
| --- | --- | --- |
| `store` | `WF_STORE` | `WF_TARGET_STORE` |
| `server` | `WF_SERVER` | `WF_SERVER_DIR` |
| `cdn_dir` | `WF_CDN_DIR` | — |
| `cdndata` | `WF_CDNDATA` | — |
| `source_store` | `WF_SOURCE_STORE` | — |
| `kulo`、`store131`、`runtimes` | `WF_KULO`、`WF_STORE131`、`WF_RUNTIMES` | — |
| `output`、`pathlist` | `WF_OUTPUT`、`WF_PATHLIST` | — |

旧别名仍可读取，但使用时会产生可见的 `UserWarning`。规范变量和别名同时存在时，解析到同一路径可以兼容，不同路径则报冲突，避免依赖隐含的选择顺序。

编辑台的实测截图白名单用 `paths.studio_screenshots`（字符串或字符串数组，例如模拟器共享文件夹里的截图目录），
也可用环境变量 `WF_STUDIO_SCREENSHOTS`（多个目录用系统路径分隔符）或 `python -m wf.studio --screenshots-dir`。
编辑台只展示这些目录里的 png/jpg/webp；记录里别处的截图路径只显示文字。

`WF_PATHS_PROFILE` 只用于指定路径配置 JSON，缺省读取本仓 `profiles/local.json`。
`WF_PROFILE` 只用于选择版本档案 ID（例如 `cn`）；把 JSON 文件名填入该变量会提示改用 `WF_PATHS_PROFILE`。
本地配置可保留 `active` / `profiles` 版本结构，版本条目支持 `store`、`cdndata`、`fallback`、`cdn_dir`、`server_dir`、`label` 和 `res_version`。
同一现代配置内，`paths` 是通用路径设置，优先于版本条目；环境变量仍拥有最高优先级。

旧仓根 `profiles.json` 仅作迁移兼容：读取就警告，其相对路径以**工具仓根**为基准。
旧路径与当前现代配置（包括环境变量）同时给出且不一致时，直接报冲突；相同值可兼容。
迁移时先把各路径和需要的版本元数据搬到 `profiles/local.json`，再移走旧文件。
`profiles.example.json` 继续演示旧格式，里面可选路径的 `null` 均可读取。

服务器必须显式配置，`resolve_server_dir()` 不会返回工具仓或其父目录。
CDN 可直接指定 `cdn_dir`，或者从显式 `server` 的 `.env` 中读取 `CDN_DIR` 并加上 `cn`，再检查 `<server>/.cdn/cn`。
未配置时，严格 CDN 解析器报错；为兼容离线模块导入，`resolve_cdn_root_lax()` 只返回本仓 `.cdn/cn` 占位路径，不创建目录，也不选择兄弟仓。
`resolve_cdndata_dir()` 优先使用显式 `WF_CDNDATA` / profile cdndata；未配置时必须先解析显式 server，再使用 `<server>/assets/cdndata`，目录须存在。GUI 只在访问资料镜像时解析它，未配置 server 不阻止仅配置 store 的离线导入；任何服务端资产写入仍要求显式 server。

`wf_offline_store.resolve_store_roots()` 默认使用同一 store 解析链；调用方显式传入 `profiles_path` 时，保留旧文件格式及相对该文件布局解析的 API 合同，用于离线 fixture 和兼容工具。`wf_story_export` 同样在运行命令时解析配置的 store，不猜测父目录里的数据包。

仅两项具备本仓默认值：`output` 为 `work/m0`，`pathlist` 为 `WF_PATHLIST_recovered.txt`。
`root_path()` 无显式根时使用本仓 `work/external`，供离线导入和相对路径定位；这不会把外部输入标成已配置。
`project_root()`、发布保护的 `PACKS`、角色支持层的默认 `ROOT` 和 GUI `ROOT` 都以本工具仓根为准。

## M1 自动视图

`python -m wf view --tip 1.4.N` 从 `paths.kulo/assets/asset-patch/manifest.json` 的依赖链读取 ZIP，以 `paths.store131` 为基线。后续离线交付可配置 ZIP 搜索目录与补充 manifest，路径相对 `wf_root`：

```json
{
  "view": {
    "zip_dirs": ["releases/first", "releases/latest"],
    "manifests": ["releases/latest/manifest.json"]
  }
}
```

搜索只访问这些目录的直接子文件，不遍历相邻 worktree。未设置 `view.manifests` 时读取配置目录内的 `manifest*.json`；目录内保留互斥的历史草稿时，应显式选择已确认的完整 manifest。不同文件给出的同一版本边或 SHA 不一致会拒绝，不按时间戳猜新版。同名 ZIP 在多个目录中必须字节相同。ZIP 按依赖链及数值 seq 排序，缺边、缺分包和重复 seq 均拒绝。

CLI `--manifest` 显式指定主清单时不继承 `view.manifests`；补充清单通过重复的 `--extra-manifest` 给出。`--zip-dir` 可重复，覆盖 profile 的 ZIP 搜索目录；主清单旁的 `active` 始终加入。`--base-version` 默认 `1.4.131`，其它基线必须明确指定。

`--write-lock work/m1/view.lock.json` 记录有序 ZIP 名称和 SHA-256，以及本次实际读取的 store 成员摘要；`--lock` 强制验证。空 `store_members` 表示禁止任何 store 回退。`--logical` 可重复，用于在创建锁时读取本次任务需要的额外逻辑成员。输入锁与首读摘要在会话内固定，`verify()` 在出包前再次复核。锁、报告和所有 CLI 输出均限定为本 worktree 内路径。

## 编辑台命名视图（`default_view` / `views`）

Studio 编辑台（`python -m wf.studio` 与 `python -m wf.studio.draft`）支持在 `profiles/local.json` 中声明命名只读视图（完整行为见 [`docs/studio/chain-views.md`](../docs/studio/chain-views.md)）：

```json
{
  "wf_root": "<工作目录>",
  "default_view": "local",
  "views": {
    "local": {
      "store": "wf-store/production/upload",
      "manifest": "startpoint-cn/assets/asset-patch/manifest.json",
      "zip_dirs": ["startpoint-cn/.cdn/cn/archive-common-diff"],
      "base_version": "1.4.54"
    }
  }
}
```

- `default_view`（可选字符串）：未显式传 `--view` 且未设环境变量 `WF_STUDIO_VIEW` 时默认加载的视图名（优先级：`--view` > `WF_STUDIO_VIEW` > `default_view`）。
- `views.<视图名>.store`：只读基线 `production/upload` 目录（相对路径按 `wf_root` 解析）。
- `views.<视图名>.manifest`：补丁链 `manifest.json` 路径（相对路径按 `wf_root` 解析）。
- `views.<视图名>.zip_dirs`：查找清单引用补丁 ZIP 的目录数组（相对路径按 `wf_root` 解析）。
- `views.<视图名>.base_version`（可选字符串）：基线 `store` 已具备的资源版本号（缺省为 `1.4.131`；基于官方 CN `1.4.54` 物化的 `store` 须显式填 `"1.4.54"`）。
- `views.<视图名>.tip`（可选字符串）：默认叠加到的清单链终点版本；省略时取清单最高启用版本。
- `views.<视图名>.overlay_base`（可选布尔，默认 false）：明确声明该视图为可分享 Overlay 的 dev 基线。只有严格 true 才开放；交付记录实际来源，内部链及无来源证据的旧交付拒绝导出，无绕过参数。见 [Overlay 导出](../docs/studio/overlay.md)。

## 交付只读预演服务端（`servers` / `rehearsal_server`）

交付前只读预演（`python -m wf.studio.draft rehearse --delivery-dir <交付目录> --server <名称>` 及编辑台构建后自动预演）使用独立的 `servers` 与 `rehearsal_server` 字段（完整契约见 [`docs/studio/rehearsal.md`](../docs/studio/rehearsal.md)）：

```json
{
  "wf_root": "<工作目录>",
  "servers": {
    "local": {
      "root": "startpoint-cn"
    }
  },
  "rehearsal_server": "local"
}
```

- `servers.<名称>.root`：用于只读核对版本链与服务端 JSON 变更的服务端根目录（其下应包含 `assets/asset-patch/manifest.json`，相对路径按 `wf_root` 解析；`<名称>` 限 1～64 位字母、数字、下划线或连字符）。预演全程只读，不会向该目录写入或覆盖任何文件。
- `rehearsal_server`（可选字符串或 `null`）：编辑台执行草稿交付构建（`build_draft`）成功后自动执行一次只读预演的目标服务端名称；设为 `null` 或省略时不自动预演。
- `servers.<名称>.apply_enabled`（可选布尔，默认 false）：只有严格 true 才允许 [应用与撤销](../docs/studio/apply-local.md) 写入该命名本地根。预演仍始终只读。不要给正式服、175 或远端快照开启；CLI/HTTP 不接受临时目标路径。开启后仍需交付检查与即时预演通过，不执行服务启停。

应用及 Overlay 的配置片段（与现有 store、manifest 等配置合并，不替换整份 profile）：

```json
{
  "servers": {"local": {"root": "local-server", "apply_enabled": true}},
  "views": {"dev": {"overlay_base": true}}
}
```
