# M0.1 配方与 prepush 修复验收

本记录对应审查 M3、L3、L5。执行边界：只写当前 worktree；原 store、active、历史构建输入与期望交付只读；未接触其它 worktree、服务、设备，未 push。生产数据不是测试夹具，锁文件与比对文件只保存名称、摘要和比较结果。

## M3：平衡配方完整锁定底座

`recipes/balance1017/base-lock.json` 保存 `tip=206` 对应的 **85 个 active ZIP**，按原 `HistoricalView` 的实际叠加顺序记录精确名称和 SHA-256。范围从 `131→132` 到 `205→206`，包含同一版本跨多个 seq 的包。已有 `input-zips.json` 继续锁定后接的 **32 个 extra ZIP**，截止 222，不输入目标 223。

运行开始与出包前，`wf/view/balance_inputs.py::verify_balance_view` 都校验 active 文件列表、顺序及摘要；它重新枚举目录，因此构建期间新增或删除相关 ZIP 也会失败。extra ZIP 的摘要在导入配方时校验，失败明确抛出 `ValueError`，不依赖可由 `python -O` 关闭的断言。

原底座读取观测得到一个需要如实说明的事实：八个角色的完整平衡构建只读取 **3 个视图成员**，全部由 `pinball-1.4.220-1.4.221-1-halloween4-characters-local.zip` 提供，**实际使用 store131 成员数为 0**。因此 `store_members` 锁定为空对象，而不是虚构未发生的 base 读取。`HistoricalView` 对非 `None` 的锁逐次核验 store 回退成员；空对象意味着任何 store 回退都会报 `unlocked store131 member`，不会静默读取活目录。未来新增真实 base 依赖时，必须审阅并补齐成员摘要。

针对 active 增加、删除、内容替换，以及 store 成员改动和未锁成员回退，新增负向测试。`base149`、`live149` 同时延迟到实际使用时解析外部路径，使纯内存/临时目录测试不再要求真实 kulo/store131 配置。

最终重建的 223 对原交付 **3/3 成员逐字节一致**。ZIP 容器 SHA-256 不同；只归零 ZIP local/central headers 的 DOS 时间戳后容器完全相同。完整证据：[m01-balance-replay.json](m01-balance-replay.json)，其中还记录实际读取的 3 个输入成员及其来源/摘要。

## L3：当前源完整构建与历史 221 分开

入口现在明确区分：

- `python -B -m recipes.halloween221`：显式传入 `historical_version="1.4.221"`，恢复历史 PF3 公式，完整构建 `1.4.220→1.4.221`。
- `python -B -m recipes.halloween_full`：不选择历史分支，保留 222 的两条 PF3 命令清理，完整构建 `1.4.220→1.4.222`。

两入口都从原表、母本资产、批准透明母图及 WAV 执行四角色 init、tables、kit、assets、pixel、art、voice 后分包。当前源入口不是读取现有 package 直接打包的诊断入口。两种模式共用同一个 run 目录会明确报错。

本次两模式均从新的本地 run 目录完整执行。随后 H1 回收了 `wf_describe` 修复；平衡完整重跑，万圣两模式分别重执行全部四角色 kit 和最终分包，对受影响的描述/行构造做最终验证。已经生成且不受描述器变动影响的图像与语音保留，不重复转换。完整构建报告与最后 kit 复验报告分别保存在各 run 目录的 `build-report.full-before-describe.json` 和 `build-report.json`。

| 构建与比较对象 | ZIP 数 | 相同成员 | 不同成员 | 证据 |
| --- | ---: | ---: | ---: | --- |
| 历史 221 对原 221 | 11 | 310 | 0 | [m01-halloween221-replay.json](m01-halloween221-replay.json) |
| 当前源对「原 221 + 原 222 修复」 | 11 | 310 | 0 | [m01-halloween-current-replay.json](m01-halloween-current-replay.json) |
| 当前源对原 221 | 11 | 309 | 1 | 同上 `compared_to_original221` |
| 当前源修复成员对原 222 修复成员 | 1 个成员 | 1 | 0 | 同上 `fix222_members` |

原 222 交付只是一个 PF3 修复 ZIP，所以当前源的 11 个完整包不能称为与原 222 容器逐字节一致。这里比较的是原 221 叠加 222 后的完整成员映射。唯一发生变化的成员为：

`production/upload/89/45fd1ab9d8e6c8f32572e98fdf60ece8ddc46d`

- 原 221：497 字节，SHA-256 `39d0013867105abb217bfc2fdab9308ddcfe1aaa9b9556b6ddc264ee443e85ed`。
- 当前源与原 222：均为 463 字节，SHA-256 `9c305dfd2a8befc43c2fffeaa1014a036e6a096a1681ca70c40e24deeb08cec5`。

历史 221 的 11 个 ZIP 均只存在 DOS 时间戳差异，归零时间戳后容器完全一致。各模式完整构建都验证了 351 个实际读取的 viewstore 成员与 105 个历史 ZIP 叠层相同；最终 kit 复验验证 53 个所读成员，57 个运行时 WF/配方模块均来自本仓。

蒙版 **没有重算**。立绘读取原 `${WF_ROOT}/out/万圣新角色-20261016/pkgroot/art-official-shape-masks.npz` 和配套 JSON，沿用原加载器验证缓存摘要。NPZ 为 9,485 字节，SHA-256 `abccd9513b0a555aa721a0287d5fa219c108fb502fa7b39eed115bd7bece0dba`。现在如果原缓存或元数据缺失，会在尝试重新计算之前报错；每角色 art 报告记录 `recomputed: false` 与摘要。

## L5：pathlist 当前差异与参数

本次只读核查时，原 prepush 使用的 `${WF_ROOT}/out/kulo-patch-toolkit/prepush/WF_PATHLIST_recovered.txt` **不存在**。因此不能宣称两份文件一致，也不能推断原交付执行当时这份文件是否存在。原代码遇到缺失文件会只使用内建表路径；对当前磁盘状态计算的覆盖差异如下：

| 项目 | 数值 |
| --- | ---: |
| 仓内文件大小 | 6,130,646 字节 |
| 仓内非空行/有效路径 | 100,089 |
| 原位置缺失时的内建有效路径 | 58 |
| 仓内增加覆盖 | 100,031 |
| 仓内丢失覆盖 | 0 |

仓内文件 SHA-256 为 `05ab0aef6e046cc4b8429b1d715898d58ffd0bd9532f9632fa7c6404df78b591`。详细计数、差集摘要及样例见 [prepush-pathlist-review.json](prepush-pathlist-review.json)。这表示链解码检查可识别更多逻辑路径，不应把 M0 改动称为完全等价的定位调整。

`wf_prepush_check.py` 新增 `--pathlist <文件>`，优先于配置，显式文件缺失返回参数错误（exit 2）。默认继续使用 `WF_PATHLIST`/路径配置/仓内表，并补充内建表名。若需要复现「原文件缺失、仅内建 58 条」的当前原脚本行为，可以显式指定一个本地空路径表文件；不需要更改仓内原表。

## 本地复验入口与边界

本机沿用仓内已有 `work/m0/test-deps` 作为 pytest 依赖，没有安装到外部。测试命令：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'work/m0/test-deps'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -q tests/test_m01_balance_lock.py tests/test_m01_halloween_modes.py tests/test_m01_prepush_pathlist.py tests/test_m0_recipes.py tests/test_m0_recipe_safety.py --basetemp work/m0.1/pytest-recipes-final
```

结果：**22 passed，exit 0**；日志 `work/m0.1/recipe-tests-final.log`。全量 pytest 和路径扫描由 M0.1 总报告统一记录。

重跑显式配置 `WF_ROOT`、`WF_KULO`、`WF_STORE131`，设置 `WF_OUTPUT=<本worktree>/work/m0.1/recipes`。完整构建 run 为 `historical221-m01` 与 `current222-m01`，所有产物在 `work/m0.1/recipes/`。日志分别为 `work/m0.1/balance-build-final.log`、`halloween221-build.log`、`halloween-current-build.log`、`halloween221-kit-final.log`、`halloween-current-kit-final.log`。

Python 启动时禁写 bytecode，配方写入审计限制在本 worktree；TEMP/TMP 与 ffmpeg 输出/cwd 都在本地 `work/`。ffmpeg 子进程不继承 Python 审计，现有边界检查和环境净化仍保留，不能把它描述成 OS 沙箱。期望 ZIP 只在独立比较阶段读取，没有作为生成输入；本次没有改写期望值。
