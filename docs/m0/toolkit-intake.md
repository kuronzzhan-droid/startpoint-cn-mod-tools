# APK 与 prepush 临时库收编

源根使用 `${WF_ROOT}` 表示配置的工作资料根。源文件只读；SHA256 是迁移前原始字节摘要。

APK 共 40 个文件：10 个通用库进入 `wf/apk`；30 个任务/版本专用脚本进入 `archive/legacy/apk`。`perf2_core.py` 的通用单方法框架改名 `patching.py`。归档不作为活动模块导入、不进入测试发现。

`common.read_base_swf(source, expected_sha=None)` 改为显式输入文件与可选哈希，不再隐式选择个人下载目录的 v29 APK。活动库使用包内导入，不读外部 APK、不修改 `sys.path` 或 `sys.dont_write_bytecode`。

prepush 拆为 6 个模块，保留原检查算法、CLI 参数和退出码；保留 `wf_prepush_check.py` 兼容入口。`WF_PATHLIST_recovered.txt` 从本仓根读取。检查器的 `--git-since` 和 kulo#35 子进程能力仅保留接口，本次测试不对外部仓库执行 Git/Node。

归档源码也已移除固定绝对路径。历史工作目录从 `wf.paths.root_path()` 解析；下载目录与签名密钥文件分别通过 `WF_DOWNLOADS` / `paths.downloads`、`WF_ANDROID_KEYSTORE` / `paths.android_keystore` 显式配置。归档的旧端点补丁使用 `WF_LEGACY_APK_ORIGIN` 和可选 `WF_LEGACY_APK_LAN_HOST`，不保留真实公网/LAN 地址值；未提供源端点时拒绝执行。`fetch_tools.py` 的复制动作放入 `main()`，导入不再复制文件。归档脚本保留版本上下文和外部基线要求，未声明可作为现行构建入口直接运行。

验证命令：在 worktree 内指定本地测试依赖后，`python -B -m pytest tests/test_m0_apk.py tests/test_m0_prepush.py -q -p no:cacheprovider`，结果 **12 passed in 0.34s**。覆盖单方法字节变化、无关方法/标签保持、幂等、未知基线拒绝、跨方法越权拒绝、分支偏移重排、导入无路径副作用，以及 prepush 数字链序、叠层、清单错误、C8601、文案误改/漏档、等级缺口新旧分类、CLI JSON 与退出码。所有 fixture 写在 `work/m0/prepush-tests/`。

对迁移前 prepush 与拆分后模块的顶层函数/类逐一做 AST 比较：**无遗漏，只有 `load_pathlist` 的路径解析改变**；其余检查算法保持一致。证据保存在本地 `work/m0/apk-prepush-validation.json`。APK 源原始 SHA256 见下表与同名 JSON；本次未运行历史 APK 构建、签名、设备或服务端检查，因此不代表任何 APK 的实机验收。

| 来源相对路径 | 去向 | SHA256 | 决策 |
|---|---|---|---|
| `${WF_ROOT}/perf-v30-20261015/tools/abcfmt.py` | `wf/apk/abcfmt.py` | `2d35f0fb5476bde3a400756ece1467a4dce665fd9c9e7618e1c6815cb5f51f82` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/asm.py` | `wf/apk/asm.py` | `c033836d0a7aa109b81509c1cb0731be82fc543c76d8d3b43881f9dab7d81e87` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/avm_mini.py` | `wf/apk/avm_mini.py` | `b169c2127de6d536229a0bf620729c00d4d02120dae36a8062acada6ff679da1` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/bodies.py` | `wf/apk/bodies.py` | `daa069c919b46d25bf6b25e367f1ac2744ffd64f76d6d0469e0eacf42d0d25d8` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/build_e0.py` | `archive/legacy/apk/build_e0.py` | `6f667074e320fdbc7acebff0e1dcb8821403bd58e87882538e00bcf1eb077451` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/build_perf2_apk.py` | `archive/legacy/apk/build_perf2_apk.py` | `52f0ed20f5b74bddc3c3b76c6100525cbaa8751674dd12b8180db1754d48b862` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/build_perf_apk.py` | `archive/legacy/apk/build_perf_apk.py` | `ade104daff1cafed047dc2a1cdc02d8446610f6198bebf55f39c9286cd46cec3` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/build_x86.py` | `archive/legacy/apk/build_x86.py` | `93dad51b1a9316cbedf4f76042d507cbb119dbfab50a547f5a1347a4339fb3ac` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/bump_versioncode.py` | `wf/apk/bump_versioncode.py` | `0d04f0cd425027a29e57def9a71da3cb8113c4c8b915747035dedbd2baed0740` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/common.py` | `wf/apk/common.py` | `45c60c75e3d022d434006d606bbbfb3850fed8f79de0d3638190769b1dec9b9e` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/diff_v29_vs_original.py` | `archive/legacy/apk/diff_v29_vs_original.py` | `0a0f44c5c93671816ffbf533f8b8eebd70f98cf20e46177c969cbefd6d2f35c0` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/dump_helpers.py` | `archive/legacy/apk/dump_helpers.py` | `abbec6e11a3ded78acf7f041d2584cf25b1a2b9b99caf5777f90c17af4892d73` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/dump_perf2_pcode.py` | `archive/legacy/apk/dump_perf2_pcode.py` | `70a7922e5b28952a196e8bca20a1e2e538320e423a9e393b96bb7ca296309807` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/fetch_tools.py` | `archive/legacy/apk/fetch_tools.py` | `18d6b4a30a78f7e744fdbfcd1a6bc93e884316422d3ceb5cbe28813e1a7b2a04` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/inspect_helper_pool.py` | `archive/legacy/apk/inspect_helper_pool.py` | `9e011f1d7fffed5e9c9cf7129f89b98a242a84fc8451935aa46218024453bfae` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/opwalk.py` | `wf/apk/opwalk.py` | `c3e17d85438d5f1a62320c811b77bdfd7f475a123e0e8ea2ac759062bb9d6080` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/patch_perf.py` | `archive/legacy/apk/patch_perf.py` | `8774d4809f0cd648687c121306f54551c482ed83672b225d12303eb0dc34455a` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/perf2_apply.py` | `archive/legacy/apk/perf2_apply.py` | `d000586e73c2c430b91e3efc8a3e1f6676ee20c02f36b95b78a3b689f88a6966` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/perf2_core.py` | `wf/apk/patching.py` | `b5d50c6ae613e22773f8dd969df0faf80a3afe4a1aa1bef790b561ceb94c4a8a` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/perf2_patches.py` | `archive/legacy/apk/perf2_patches.py` | `08c28cf3492d0c5c03ae87a51e0477e18a00438f4358d21ee08c87536841c224` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/probe_sha.py` | `archive/legacy/apk/probe_sha.py` | `c4b28bba8beca1fb17e776962bce526c52b23bd83cab6ebbf9d9e2424c062fc3` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_abc_reader.py` | `archive/legacy/apk/ref_abc_reader.py` | `85c3235250e42f171210667d2821484a152b92ed72dca3743f5a8bfc09ad3c98` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_build_coop_apk.py` | `archive/legacy/apk/ref_build_coop_apk.py` | `827057057af149d5a053dc0ed74c6cc96f144031ce44a224b54c908480346e8e` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_build_local_baseline.py` | `archive/legacy/apk/ref_build_local_baseline.py` | `7f45aa17625b813344e9db43ccd6165dcb2ff5d9c7cb3074143d3bfdb787c968` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_inspect_v28.py` | `archive/legacy/apk/ref_inspect_v28.py` | `77c1934d320bf08a2095af49baf12fb2b0df6424bc41546199333645c6c333b4` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_patch_coop_grace.py` | `archive/legacy/apk/ref_patch_coop_grace.py` | `325d676f3256f9d866236f786ca06ce2ae16ad9ee7101de8c4e7b8ed233fa51f` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_patch_local_endpoints.py` | `archive/legacy/apk/ref_patch_local_endpoints.py` | `b494f647fe926d25245383cb58d2461c5412e9c907a5f3c5e50de165e1786495` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_pcode_utils.py` | `archive/legacy/apk/ref_pcode_utils.py` | `4e8ab68342dfa056d73abbcc17128f6444390e23a32cff9b8556610ae7f32b0b` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_test_coop_grace.py` | `archive/legacy/apk/ref_test_coop_grace.py` | `cf9b73c92adf9a336c0f6cca6aae07262d0dd1ad28fe41562b1b4c3fc440fc03` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_verify_coop_apk.py` | `archive/legacy/apk/ref_verify_coop_apk.py` | `b7cb34030f51f2f73732831f10cca8d486f1b88b2355514f0bca3b6d7ba7c3fa` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/ref_verify_local_baseline.py` | `archive/legacy/apk/ref_verify_local_baseline.py` | `8f3e663537fb614f0166146f83818e7f50b40bd787e60d8df62181615732e98f` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/sign_perf2_apk.py` | `archive/legacy/apk/sign_perf2_apk.py` | `88a0e2f1629331bdebc9b4ab39b9e2c78d3091fa9aae4d22ec6f04ef460ed184` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/sign_perf_apk.py` | `archive/legacy/apk/sign_perf_apk.py` | `fef55278a6735d5bc220f99b87593d73cd90ad48dce5b90f4924a354bfff946c` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/swfabc.py` | `wf/apk/swfabc.py` | `d3a56b7f23d809e14d78b0ac11e55f8bf127fb60f1d9dfd5814502cc691eaad3` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/swftags.py` | `wf/apk/swftags.py` | `81d253a0c27ada1f4e377384484fcadd8bf8a360e4d93b456483ef1128ea6b06` | 通用库：包内相对导入，消除固定数据和导入路径副作用 |
| `${WF_ROOT}/perf-v30-20261015/tools/table_sizes.py` | `archive/legacy/apk/table_sizes.py` | `396514bf4a6ba316eaea4f79b2a1fd55c201fcd486c051df4dcc671bac210103` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/test_perf.py` | `archive/legacy/apk/test_perf.py` | `9d061421aaced2f4f5039097697fe043aae840162a2bb00a47046de21e0ec585` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/test_perf2.py` | `archive/legacy/apk/test_perf2.py` | `17c32f68f0ff257357a869e1d5aa662e10732893b0f83ccd7e298dcb0e28ad70` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/verify_perf2_apk.py` | `archive/legacy/apk/verify_perf2_apk.py` | `61915bbbeb6d130af11c1e63fbae6eb9bbfae6d2b1fc6f1d999a58e05fb9aa65` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/perf-v30-20261015/tools/verify_perf_apk.py` | `archive/legacy/apk/verify_perf_apk.py` | `4ad123b2c377daf7dcc97ca2fa132747626a189680b8da80f8c6e1d3356c0820` | 版本/任务专用或诊断脚本：完整收编归档，不加入活动兼容层和测试发现 |
| `${WF_ROOT}/out/kulo-patch-toolkit/prepush/wf_prepush_check.py` | `wf/deliver/prepush*.py; wf_prepush_check.py` | `df9535bb83a6943431e1151f2d460e7ae8f37e9d604ea07dae9866a28ea87e70` | 按视图/链/文本/伴随/等级/CLI拆分；保留检查函数及命令参数；不再修改sys.path；pathlist由仓根读取 |
