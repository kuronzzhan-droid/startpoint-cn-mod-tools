# 角色 × 能力矩阵

`python -B -m wf caps scan --tip 1.4.N --output work/m2/matrix/N` 使用 M1 的 manifest 依赖链和当前 PathConfig，扫描每个新增或改过的角色，导出稳定能力 ID 矩阵。无需 `wf.studio`，也不会导入外部脚本。人工维护的 C 层名称在 `data/layer_c_names.json`。

M2.2 增加 `--all-characters`：保留未改动官方角色，并对每个角色调用与交付共用的 `requires` 推导，沿能力、队长技、技能、切换技能、PF、固有状态和 DSL 引用闭包逐项取证。默认扫描范围不变；原先 108 行属于新增或修改子集，不能代表全角色。省略 `--tip` 时按所选 manifest 自动取得最高启用链尾，断链仍会报错。

`--apk-bundle <APK>` 可显式补充 CDN/store 中不存在的 APK 内置资源；它只在主视图缺失成员时读取 `assets/bundle.zip`，不会覆盖补丁数据。输出 `evidence.apk_bundle` 保存 APK、bundle 和实际读取成员的 SHA-256；扫描结束复核 APK 未变化。未提供 APK 或 bundle 中仍无引用资源时继续记为未解析，不推定官方资源存在。完整兼容报告见 [v34 与 v35e 对照](compat-v34-v35.md)。

## 输入和输出

路径优先使用显式参数，其次使用现有配置：

- `--store`、`--manifest`、可重复的 `--zip-dir`、`--lock`：与 `wf view` 的输入一致。默认 store 为 `store131`，manifest 为 `kulo/assets/asset-patch/manifest.json`；未配置的目录不会自动搜索。
- `--official-cdn`：官方 CDN 归档根；默认读 `official_cdn` 配置，未设置时取 `kulo/.cdn/cn`。官方基线保留 pinned 表校验，不把混有 MOD 的 store131 当官方数据。缺少官方角色基线会失败。
- `--server-assets`（别名 `--kulo-assets`）：读取 `character_overlimit.json`、`character_awake_extension.json` 和 `mission_char_awake_cnmod.json`；默认 `kulo/assets`。缺失不会静默当作空白名单。
- `--names`：可选 C 层名称 JSON；`--reference`：可选旧 `scan_raw.json`，逐角色逐字段比较，包含增删角色和完整 before/after。

输出均限制在当前 checkout。`matrix.json` 包含角色事实、能力 ID、A/B/C/platform 分层、每条判断依据、C 层名称及输入摘要；`matrix.csv` 每个能力 ID 一列，1 表示存在证据。`scan_raw.json` 保留原扫描字段，`角色机制矩阵.csv` 保留原中文矩阵列，`view.lock.json` 记录实际读取的 ZIP/store 摘要；指定参考时另写 `comparison.json`。

扫描缺失 DSL 或识别到未登记机制时保留具体清单，并返回非零，不把部分扫描标成完整。损坏 DSL、未知注册表 ID、输入漂移、外部输出路径也会拒绝。输入版本严格按 `--tip` 解析，不会用高版本替代请求的低版本。

服务端 JSON 是显式提供的快照，并不随客户端 `--tip` 回放；JSON 的 `scope` 与 `evidence.server_inputs` 清楚保留这一边界。角色专用 APK 标签沿用原矩阵中有文档依据的映射，并在 `capability_evidence.source` 标作“文档中的角色专用补丁映射”。未找到资源的特效目录推断仍保留“推断官方”字样。C 层名称来自原人工表，包含原先的“推断”标注；它不是新的实测结论。

新能力矩阵额外补齐官方合击资格：除了旧扫描的合击条件/触发，还读取能力首行 c1=true；第二行的 true 不算。该证据仅加入 `capability_evidence`，保留旧原始 `unison` 字段的“合击条件/触发”含义，避免把新旧字段口径混在一起。231的旧字段有11角色命中，新能力矩阵共有106角色具备 `official.unison@1` 证据；新增的95个徽章来自首行资格，不能解释为95个新玩法。

## 本次真实验收

当前只读 manifest 的最高链尾为 **1.4.231**，高于任务书要求的 1.4.229。独立配置在忽略目录 `work/m2/matrix/profile.json`，原 `profiles/local.json` 已恢复 M1.1 配置；复现时用 `WF_PATHS_PROFILE` 选择这份配置。它引用 ghmain manifest、原 store131 和官方 CDN，ZIP 目录包含原历史目录及 225–231 的归档目录。

```powershell
$env:WF_PATHS_PROFILE = (Resolve-Path work/m2/matrix/profile.json).Path
python -B -m wf caps scan --tip 1.4.231 --output work/m2/matrix/231
```

| 链尾 | ZIP | 角色 | 观察到的注册能力 | 缺失 DSL | 对原224字段差异 |
|---|---:|---:|---:|---:|---:|
| 1.4.224 | 119 | 108 | 25 | 0 | 0 |
| 1.4.229 | 124 | 108 | 25 | 0 | 107 |
| 1.4.231 | 126 | 108 | 25 | 0 | 110 |

224 的108个角色、全部原始字段与旧 `scan_raw.json` 相同；中文 CSV 与旧 `角色机制矩阵.csv` **逐字节相同**。229 和231的角色 ID 集合、每个角色的能力 ID 集合都与224相同。字段变化主要是227文案改写加入来源记录；休尔特平衡调整改变觉醒行数/PF所在行，黑与231两个气绝修复角色改变覆盖文本的重复引用次数。没有通过忽略这些字段来实现“相同”。[逐条差异](matrix-differences.md) 列全110项，包含对229的子集说明；[结构化验收](matrix-validation.json) 记录各产物 SHA-256。

实际产物位于 `work/m2/matrix/224/`、`229/`、`231/`。`step-differences.json` 定位225–231每一版本引入的字段变化。单元反证覆盖错误 PF 档位、错误触发种类、损坏/缺失 DSL、未登记能力、相同角色数量但ID变更、空官方基线和服务端白名单缺失。

定向测试 **18 passed**，JUnit 为 `work/m2/matrix/pytest.xml`。进程内变异让 DSL 扫描总是删掉 buffTargetAs 转换证据，现有测试因此 exit 1；证据为 `mutation.json` 和 `mutation.log`。以不同 `PYTHONHASHSEED` 独立重跑231，六个输出文件全部逐字节相同（`determinism.json`）；特效路径集合在输出前排序，不依赖 Python 集合迭代顺序。
