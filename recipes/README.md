# 历史交付配方

这些配方只读配置的历史输入，产物默认写到本仓 `work/m0/`。在 `profiles/local.json` 显式配置 `wf_root`、`paths.kulo`、`paths.store131`，或设置对应的 `WF_ROOT`、`WF_KULO`、`WF_STORE131` 环境变量；外部路径没有隐式默认值。`paths` 内相对路径基于 `wf_root` 解析。入口启用写入审计边界，拒绝 Python 向仓库外写文件；原 store、kulo active、原交付 ZIP 均不修改。

ffmpeg 子进程使用显式检查后的本仓输出、TEMP/TMP 和工作目录；它不继承 Python 审计，此限制不是操作系统沙箱。UNC 输出被拒绝。

## 平衡 1.4.223

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m recipes.balance1017 --write
```

配方锁定 `tip=206` 对应的 active 叠层，再按 `balance1017/input-zips.json` 的顺序加载至 1.4.222。`balance1017/base-lock.json` 保存 85 个 active ZIP 的精确顺序、名称和 SHA-256；`input-zips.json` 保存 32 个 extra ZIP 的相对路径和 SHA-256。运行前和出包前检查 active 清单及摘要，任何漂移都会报错。原目录中的可变 `extra_zips.txt` 现在已包含目标 223，配方明确不以目标 ZIP 作为输入。

当前八角色完整构建的所有输入成员都由 ZIP 叠层提供，实际读取的 `store131` 成员数为 **0**。因此锁文件显式写 `store_members: {}`，运行时禁止新增未锁定的 store 回退；它不是未启用校验的 `null`。若以后配方确实需要 base 成员，必须审阅并补齐该成员的摘要，不能自动接受活目录。输出在 `work/m0/balance1017/`，integrity JSON 记录实际读取成员的来源和摘要。

## 万圣四人 1.4.221

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:WF_REPLAY_RUN = 'historical221-run1'
python -B -m recipes.halloween221
```

每次独立重跑选一个新的 `WF_REPLAY_RUN` 名称。入口依次执行四人的 init、tables、kit、assets、pixel、art、voice，最后按原算法合并表并分成 11 个 ZIP。立绘输入是已批准的透明母图及原统计蒙版，语音输入是已批准 WAV 及台词；不调用图像或语音生成服务。蒙版直接读取原 `pkgroot/art-official-shape-masks.npz` 和配套 JSON，核对摘要，**没有重新计算**。缺失缓存时明确失败，不在原目录重建。输出在 `work/m0/halloween-full/<run>/`。

原 `hw_kit_seriol.py` 已含后续 222 的 PF3 消毒修复。本历史配方显式选择 `historical_version=1.4.221`，重建「官方 knight_lv3 源树只把根 buffTargetAs 改成 133」的历史公式。这个版本分支是根据原构建器、修复注释和原始官方树恢复的，不声称发现了保存完好的 221 旧源码。普通 kit 调用仍保留 222 修复。期望 ZIP 只在独立比较阶段读取，生成阶段不读取它。

## 万圣当前源完整构建（含 222 修复）

```powershell
$env:WF_REPLAY_RUN = 'current222-run1'
python -B -m recipes.halloween_full
```

此入口从原表、母本资产、透明母图、缓存蒙版和 WAV 完整执行上述七步，保留普通 kit 的 222 PF3 修复，生成 `1.4.220 → 1.4.222` 的 11 个完整角色包。它与 `halloween221` 的历史分支明确分开，禁止复用另一模式的 run 目录。原 222 交付只包含一个 PF3 修复成员，因此验收先核对该成员与 222 交付一致，再核对全体 310 成员等于「原 221 交付叠加原 222 修复」。本次记录见 `docs/m0/recipe-repair-review.md`。

`python -B -m recipes.halloween_current_packages` 仍是读取现有四个 package 直接打包的诊断入口；它不代表完整重建。M0 的历史证据见 `docs/m0/recipe-results.md` 与对应 JSON。

## 依赖与验证

需要当前本地 Python、Pillow、NumPy、ffmpeg，以及配置根下的历史 store/active/extra ZIP、万圣 viewstore、art、voice、research 输入；语音台词沿用当前用户 Downloads 中原文件。所有机器相关位置均通过配置根或当前用户目录解析。

`wf.view.compare.compare_delivery` 对每个 ZIP 成员比较原始字节，并另算只归零 ZIP 本地头/中央目录 DOS 时间戳后的容器相等性。不会改动任何 ZIP，也不会替换期望值。
