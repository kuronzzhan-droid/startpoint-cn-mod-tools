# APK 内置表撞名检查（C7051）

客户端将 CDN orderedmap 与 APK 内置的对应表做 union，同键会触发 ClientError 7051。检查面向本次实际输出的整张表，包含未修改但仍随整表投递的键；检查通过只说明选定 APK 与这些输出没有同名键，不代表真机已运行。

`master/skill/power_flip_action.orderedmap` 对应内置逻辑名 `master/skill/power_flip_action_iosbundled.orderedmap`，成员位于 APK 的 `assets/bundle.zip` 中，路径为 `production/android_bundle/<SHA-1 前两位>/<剩余 38 位>`。摘要复用 `core.sha1_path` 的盐与算法，不能使用普通无盐 SHA-1。

## 本机配置与调用

在不入库的 `profiles/local.json` 增加目标客户端 APK：

```json
{
  "wf_root": "<资料根>",
  "client_apks": {
    "<client_profile 名>": ["<相对 APK 路径>", "<另一个 APK 路径>"]
  }
}
```

相对路径沿用 `wf_root` 规则。build CLI 的 `--apk` 可重复；HTTP 构建请求的 `apk` 可显式提供一个路径或路径数组。显式参数优先于所选客户端档案的配置；没有选定 APK 时产生 `skipped` 警告，不能视作已通过检查。

独立检查无需草稿或基线视图，外部构建器也可使用：

```text
python -m wf.studio.draft bundle-check --apk <client.apk> --zip <delivery-1.zip> --zip <delivery-2.zip>
python -m wf.studio.draft bundle-check --apk <client.apk> --apk <other-client.apk> --delivery-dir <交付目录>
```

ZIP 参数与交付目录二选一。目录中若存在 `delivery-manifest.json`，只读取它的 `archives`；否则只读取该目录顶层的 ZIP，不递归读取同一交付的分层副本。撞名时退出码为 1；输入损坏属于错误，不能输出成功。

ZIP 的逻辑路径优先取同名 `.integrity.json` 的 `logical` 映射，并验证它与成员路径的 SHA-1 一致；sidecar 已声明的包 SHA-256、大小、成员列表、数量和成员 SHA-256 均复核。缺少映射时查询现有恢复路径表。无法识别的通用根成员会阻断 bundle-check，避免把未知表漏算成通过；外部构建器应保留配套 integrity 文件。

## Python API 与缓存

```python
from wf.studio.bundle_keys import check_bundle_keys, load_bundle_index, bundled_keys

report = check_bundle_keys(apks, tables={logical: table_bytes}, cache_dir=cache_dir)
# 或 check_bundle_keys(apks, zips=zip_paths, cache_dir=cache_dir)
index = load_bundle_index(apk, logical_paths=[logical], cache_dir=cache_dir)
keys = bundled_keys([index], logical)
```

`tables` 接受逻辑路径到字节的映射，也支持编译器的 `(root, logical)` 键；可包含非表资产，只检查 `.orderedmap`。表必须属于 `common` 根，错误根和重复逻辑目标均拒绝。`load_bundle_index` 使用恢复路径表与显式 `logical_paths` 定位内置表，返回 `schema`、`sha256`、`pathsSha256`、`tables` 和 `hashedTables`。`tables` 以普通 CDN 逻辑路径为键，值为排序后的键数组；`hashedTables` 以内置逻辑路径的 SHA-1 为键，值同上。调用者应传入全部输出逻辑路径，使新增表纳入索引。

没有逻辑名但具有 orderedmap 索引头的 APK 哈希成员也会严格解析并纳入 `hashedTables`，不猜测它的逻辑路径；截断、索引长度错误和重复键同样拒绝。哈希本身不能反推出文件类型：对于既无恢复路径、也无可识别表头的成员，仅能验证 ZIP 完整性。实际输出表通过显式逻辑名定位，因此不依赖此类内容识别。

缓存文件名为 `<APK SHA-256>.json`，默认放在本机应用数据目录下的 `wf-studio/bundle-index`；无应用数据目录时使用系统临时目录。可用 `WF_STUDIO_BUNDLE_CACHE` 或 Python `cache_dir` 指定仓库外工作目录。禁止将缓存放在仓库内。APK 内容或候选逻辑路径集合改变会重新提取；缓存含自身校验和，并验证逻辑表与哈希表的一致性，缓存损坏直接报错。当前缓存格式为 `wf-studio-bundle-keys/2`，旧版缓存自动重新提取。索引不保存 APK 原件，也不保存其绝对路径。

APK 必须有且只有一个 `assets/bundle.zip`，其他位置出现第二个 `bundle.zip` 也拒绝。APK 与内嵌 ZIP 重名成员、路径穿越、CRC 损坏、损坏的匹配 orderedmap、表内重复键均报错。orderedmap 解码复用现有严格原始行解析器，不将解析失败转换成空键集合。

## 交付与前端字段

build 在 deliver 后生成 `delivery/bundle-check.json`；交付详情的 `bundleCheck` 返回该文档，不存在时为 `null`。文档结构：

```json
{
  "status": "collision",
  "apks": [{"label": "client.apk", "sha256": "<摘要>", "bundledTables": 1}],
  "tables": [{
    "logical": "master/skill/power_flip_action.orderedmap",
    "bundledLogical": "master/skill/power_flip_action_iosbundled.orderedmap",
    "collisions": ["ranged"]
  }]
}
```

`status` 为 `ok`、`collision`、`skipped` 或 `error`；跳过与错误附带 `reason`。`apks[].label` 是文件名，`sha256` 是本次选定 APK 摘要，`bundledTables` 是该 APK 中严格解析过的内置表总数，包含只有哈希映射的表（等于索引 `hashedTables` 的条数）。每张输出表均列入 `tables`；`collisions` 为所有选定 APK 的撞名键并集。`collision` 和 `error` 阻断交付，`skipped` 保持警告与未核对状态。

p13 的 `wfx_ball_pf_action_*` 校验复用同一索引；未选 APK 时仅能报告未核对内置键，不能凭客户端档案名称推断内置表内容。

索引候选路径始终包含 `power_flip_action.orderedmap`，即使本次只输出字符串表、动作来自基线且 pathlist 没有动作表，也会严格解析该内置表。每个选定 APK 的已加载索引在一次检查中复用；选了 APK 但读取失败时，扩展键检查以 `CLIENT_EXTENSION_BUNDLE_ERROR` 阻断，只有确实未选 APK 才报 `CLIENT_EXTENSION_BUNDLE_UNCHECKED`。

构建结果以 `safetyChecks` 返回新增交付检查，并写入 `delivery/safety-checks.json`；交付清单通过可选字段 `safety_checks` 引用它。原有 `draftChecks` / `draft-checks.json` 保持草稿编译检查的契约。

离线 `wf check` 会核对安全检查与 `bundle-check.json`、`key-diff.json`、`client-extensions.json` 的一致性。新契约要求 bundle 与 key diff 汇总各有且只能有一项，且状态和阻断结果与完整详情相符；清空检查、重复汇总、缺失详情、非法条目或矛盾状态均阻断。这个回读只核对已保存证据，不会重新读取本机 APK 或重新运行设备。没有声明 `safety_checks` 的历史交付沿用旧契约。

合成测试见 `tests/test_studio_bundle_keys.py`，涵盖 staged/ZIP 输入、多个 APK 的交集、缓存复用与失效、错误及重复成员、损坏表、sidecar 摘要与逻辑映射校验。
