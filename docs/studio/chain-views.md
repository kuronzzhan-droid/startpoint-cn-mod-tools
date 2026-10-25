# 编辑台链视图与 store 导出

编辑台可以直接读取「基线 store + manifest + ZIP 搜索目录」。`active/` 只是可选的兼容目录，不再是必需结构。所有输入只读；只在显式导出时建立新目录。

## 命名视图

机器配置 `profiles/local.json` 可增加 `views` 和可选的 `default_view`。它与已有版本配置 `profiles` / `active` 分开，避免把资源视图与客户端档案混淆。下例路径仅为格式示例，需替换为本机已有输入：

```json
{
  "wf_root": "D:/WF",
  "default_view": "local",
  "views": {
    "test175": {
      "store": "out/kulo-patch-toolkit/store131/production/upload",
      "manifest": "outputs/work/test175/manifest.json",
      "zip_dirs": ["outputs/releases", "archives"],
      "base_version": "1.4.131",
      "tip": "1.4.282"
    },
    "local": {
      "store": "out/kulo-patch-toolkit/store131/production/upload",
      "manifest": "startpoint-cn-kulo/assets/asset-patch/manifest.json",
      "zip_dirs": ["outputs/releases"]
    },
    "prod": {
      "store": "out/kulo-patch-toolkit/store131/production/upload",
      "manifest": "outputs/work/prod-snapshot/manifest.json",
      "zip_dirs": ["archives"]
    }
  }
}
```

相对路径按现有 `wf_root` 规则解析。选择顺序为显式 `--view`、环境变量 `WF_STUDIO_VIEW`、`default_view`；未选择时仍支持旧的 `view` 配置和本机默认链。显式 `--manifest`、`--store`、`--zip-dir`、基线版本与 `--tip` 可覆盖所选视图的对应字段。未知视图名立即报错。

```powershell
python -m wf.studio --view test175
python -m wf.studio.draft --view test175 ability 131104
```

## 基线、链终点与额外覆盖

- `base_version` 表示 **store 已经具有的版本**，默认 `1.4.131`。只应用从该版本开始、沿 `depends_on` 能连续到达链终点的边，不再次应用基线之前的补丁。
- `--tip` 表示 manifest 链的选择终点，支持小版本号（例如 `282`；启动入口也支持 `1.4.282`）。省略时采用配置中的 `tip`，再省略则选择清单最高启用版本。链有缺口时失败，不悄悄降级。
- 草稿入口通过 `--view-base-version` 指定来源基线，启动入口使用 `--base-version`。草稿 `build --base-version` 表示显式覆盖交付构建基线；省略时沿用所选视图，不会重置为 `1.4.131`。
- `--extra-zips-file` 每行一个 ZIP，可重复；空行和 `#` 注释忽略，相对 ZIP 路径相对于清单文件所在目录。额外 ZIP 在 manifest 链之后按顺序覆盖，同一 CDN 成员后写者生效。
- 来源摘要中的 `tip` 仍表示 manifest 链终点；`version` 表示叠加已知命名补丁后的最高版本。例如链到 `1.4.282`，另叠加 `pinball-1.4.282-1.4.285-1-*.zip` 时，摘要是 `tip=1.4.282`、`version=1.4.285`。无法从名称识别版本的 ZIP 仍可用于读取覆盖，并列入 `extraZips`，但不会捏造版本号或据此允许交付。
- 构建要求 extra ZIP 从 manifest `tip` 开始形成连续的向前依赖链；同一边的分包必须按 `1, 2, …` 顺序完整列出。例如 `282→285` 可以直接跳版本，`282` 后直接接 `284→285` 则缺少前置边，构建会拒绝。分包集合来自显式清单；仅凭包名无法证明清单以外没有遗漏的末尾包。

```powershell
python -m wf.studio.draft --manifest manifest.json --store D:/inputs/production/upload --zip-dir D:/archives --zip-dir D:/deliveries --tip 282 --extra-zips-file extras.txt ability 131104
```

ZIP 搜索仅遍历指定目录，递归但不跟随子目录符号链接或 Windows junction，跳过 `.git`、`node_modules`、`__pycache__`。按 manifest 文件名先找候选，再按 `archive_integrity` 的大小和 SHA-256 筛选。同名错误构建不会盖过摘要匹配的正确构建；缺失、摘要不符、无摘要时同名内容冲突、重复 ZIP 成员、链歧义均报错。未提供摘要的历史条目仍兼容，但不能据此任取内容不同的同名包。

允许的 CDN 根包括 `upload`、历史 `small_upload`、`medium_upload`、`android_upload`、`ios_upload`，成员必须满足两位目录加 38 位 SHA-1 尾部的结构。ZIP 路径穿越和任意其他成员均拒绝。额外 ZIP 与清单 ZIP 一起进入 `wf-view-lock/1` 的 SHA-256 输入锁，并在 `verify()` 时复核；同一读取会话也检查 ZIP 和已使用 store 成员的变化。

## 导出给构建器

命令行 `build` 与 HTTP「生成」都使用编辑时选定的完整来源视图。`--from` 必须等于叠加后的 `version`；显式 `--baseline-manifest`、`--baseline-manifest-extra`、`--baseline-zip-dir`、`--base-store`、`--base-version` 优先于对应来源配置，extra ZIP 始终保留并接受链与 SHA-256 复核。目标已占用、来源陈旧和输入漂移继续阻断交付。

```powershell
python -m wf.studio.draft --view test175 --extra-zips-file extras.txt build 131104 --from 1.4.285 --to 1.4.286 --out work/studio-deliveries/local-286 --server-dir D:/inputs/server --allow-unknown-client
```

输入锁与交付清单的 `tip` 仍为 manifest 截止点。离线交付检查从锁中的基线版本和有序 ZIP 重建完整终点，核对其等于 `from_version`，不会把最高文件名当作连续版本证明。

```powershell
python -m wf.studio.draft --view test175 export-store --out D:/WF/outputs/work/my-build/viewstore
python -m wf.studio.draft --view test175 export-store --out E:/build/viewstore --copy
```

输出为单行 JSON；`result.store` 是可交给现有构建器的 `.../viewstore/production/upload`。其他 CDN 根保留在同级目录，并生成 `viewstore.json`，记录输入 ZIP、基线版本、链终点、链接/复制/覆盖数量及输入锁。

默认对未覆盖的 store 文件建立硬链接，ZIP 覆盖成员始终写为新文件，因此导出覆盖不会写穿原基线。目标目录必须尚不存在，且不能位于基线 CDN 输入目录内；已有输出不覆盖。硬链接要求同盘，跨盘请用 `--copy`；失败会明确报错，不自动切换模式。若构建器会原地修改读取的 store 文件，也应使用 `--copy`，因为硬链接共享原文件数据。输出的完整性标志是最终写入的 `viewstore.json`；中途失败的未完成目录保留供排查，不声称成功。

Python 接口为 `ManifestView(tip, store=..., manifest=..., search_dirs=[...], base_version=..., extra_zips=[...], view_name=...)`、`build_source(...)` 与 `wf.view.export.export_store(view, destination, copy=False)`。`build_source` 支持 `extra_lists` 和命名视图；服务端 `describe()` 返回 `version`、`tip`、`baseVersion`、`view`、`extraZips`、`chain` 等字段。

## 验证

`tests/test_studio_chain_views.py` 使用合成小链覆盖无 `active/`、递归搜索、同名错误构建、历史 `small_upload`、额外 ZIP 优先级与漂移、命名视图、非 131 基线、链终点、两种 store 导出及基线字节不变。`tests/test_studio_build_view.py` 通过命名视图和显式基线覆盖执行真实角色克隆交付；`tests/test_studio_build_baseline.py` 覆盖 HTTP 基线传递、连续边、分包与锁终点的负向守卫。既有 `tests/test_m1_view.py` 继续检查链顺序、歧义、缺口、输入锁和 store 漂移。
