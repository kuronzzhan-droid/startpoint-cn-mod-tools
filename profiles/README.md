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
GUI 的未配置 cdndata 占位路径同样限制在本仓 `assets/cdndata`。

仅两项具备本仓默认值：`output` 为 `work/m0`，`pathlist` 为 `WF_PATHLIST_recovered.txt`。
`root_path()` 无显式根时使用本仓 `work/external`，供离线导入和相对路径定位；这不会把外部输入标成已配置。
`project_root()`、发布保护的 `PACKS`、角色支持层的默认 `ROOT` 和 GUI `ROOT` 都以本工具仓根为准。
