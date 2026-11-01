# Patch Overlay 导出

将已有交付的三层 inner ZIP 导出为 schema 1 外层分享 ZIP，不写 CDN、服务端或原交付文件，不执行安装和重启。

```text
python -m wf.studio.draft export-overlay --delivery-dir <构建根或交付目录> --compatible-client "CN 1.8.1"
python -m wf.studio.draft export-overlay --delivery-dir <交付目录> --compatible-client "CN 1.8.1" --out <交付目录>/overlay/<新子目录>
```

缺省写入交付目录的 `overlay/`，输出目录必须为 overlay 本身或其下的新子目录，不允许 server、server-entries、patches、rehearsal 等语义目录；已存在则拒绝，不覆盖上次导出。构建先写私人 staging，manifest 最后写入 package staging，再封装外层 ZIP 并发布完整输出目录。外层 ZIP 根直接包含 `patch-manifest.json`、`README.md`、`requires.json` 和三个 `archive-*-diff/`，没有多余版本目录包裹。

## 视图门禁

机器 profile 中**构建所选的视图**必须标记 `views.<name>.overlay_base: true`。构建记录 `delivery/source-view.json` 的 name 和 overlayBase，并核对实际 store、manifest、补充 manifest、base_version、实际 ZIP 搜索目录（含 view_config 隐式 active/ 或 manifest 父目录）与配置一致；配置指定 tip 时按标准化版本核对。含额外叠加 ZIP 或指向其他 manifest 的显式覆盖不会继承基线授权。导出时还会读取当前 profile 开关。没有来源证据的历史交付需要重新生成，不能用当前默认视图代替历史来源。

未满足时默认拒绝，固定说明为：

> 本交付基于内部链，共享表带着其他内容，会盖掉收方的数据；请用 dev 基线视图重新生成

没有绕过参数。overlay_base 是操作者对基线性质的配置声明，不能证明实际资产质量或设备兼容性。生成结果和 `GET /api/deliveries/<name>` 提供 `overlayAvailable`、`overlayReason`，前端可据此禁用导出按钮并显示原因。available 表示来源与交付门禁通过；构建失败、缺清单/声明报告或阻断检查均返回 false。实际导出仍需通过下列文件校验。

## 分层依据和校验复用

`wf/deliver/manifests.py::write_manifests` 按成员元数据 root 生成 common、medium、android 三层 ZIP，缺内容的层生成 `.empty` 占位。其清单由 `delivery-manifest.json.upstream_manifest` 指向，通常是 `patches/<to>/patch-manifest.json`。导出读取该清单的 relativePath/layer/order，不从混合旧 ZIP 的序号或成员前缀猜归档层。

导出复用 `wf/tools/core/dev_catalog.py` 的 `_validate_staged_overlay`、`_pin_overlay_source`、`_stage_overlay_package`、`_write_outer_overlay`。验证文件类型、链接、路径、字节数、SHA-256、版本边、layer 与目录、order 与文件名一致、三层顺序从 1 连续。打包函数沿用摘要后缀规范化文件名，ZIP 内容字节保持一致。

编辑台额外要求 baseVersion 等于交付 from，targetVersion 等于交付 to，所有 inner ZIP 起点也等于 from。输入与输出 manifest 都通过 [patch-manifest.schema.json](patch-manifest.schema.json) 的 Draft 2020-12 校验，此文件来自任务提供的机器可读契约。当前唯一支持客户端是 `CN 1.8.1`。

仓库没有已验证的原版 cn-1.8.1-apk provides 档案，因此不从 test-v34 或客户端标签推断扩展能力：只允许依赖推导为 resolved、无 unresolved、无 clientCapabilities/clientPatches、无 serverFeatures/minServerVersion 且无服务端改动的纯 CDN 交付。完整原始 requires.json 作为来源依赖证据保留在包内，不再清空客户端能力字段；pack 描述来源交付，实际 Overlay 归档列表以 patch-manifest.json 为准。

外层 README 复用旧导出器安装说明：将内容解压至 `CDN_DIR/patches/<targetVersion>/`，由服主执行 `npm run start:cn` 重启，由启动时 Content Sync 检查并激活。服务端 JSON 和代码不属于此 CDN Overlay 包；本接口也不提供服务端升级安装器。

## 前端接口

`POST /api/deliveries/<name>/overlay`，body 必须恰为 `{"compatibleClient":"CN 1.8.1"}`，不接受 out、root、view 或绕过字段。走现有 WriteGuard，与同交付生成/预演/应用互斥。

成功 HTTP 200：

| 字段 | 含义 |
| --- | --- |
| name / ok | 交付名 / true |
| overlayAvailable / overlayReason | 来源门禁布尔与说明 |
| from / to / compatibleClient | 输出版本边与客户端标识 |
| outputDir / zip | 本地输出目录和外层 ZIP 路径 |
| manifest | 已通过 schema 的输出对象 |
| restartRequired / restartReason | true；安装后需人工重启的说明 |
| steps[] | `step/status`：view-gate、schema、layered-archives、stage、outer-zip |

拒绝或输入错误为 HTTP 400 的 error，鉴权失败 403。CLI 输出 `{"ok":true,"result":...}`；错误输出 `{"ok":false,"error":"原因"}` 并退出 1。下载复用已有 `/api/deliveries/<name>/file?path=delivery/overlay/<外层ZIP名>`，详情 files 也列出文件。
