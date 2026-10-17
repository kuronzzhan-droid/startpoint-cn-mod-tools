# 历史交付配方

这些配方只读 `profiles/local.json` 配置的 `wf_root` 下的历史输入，产物写到本仓 `work/m0/`。入口启用写入审计边界，拒绝 Python 向仓库外写文件；原 store、kulo active、原交付 ZIP 均不修改。

ffmpeg 子进程使用显式检查后的本仓输出、TEMP/TMP 和工作目录；它不继承 Python 审计，此限制不是操作系统沙箱。UNC 输出被拒绝。

## 平衡 1.4.223

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m recipes.balance1017 --write
```

使用 `WF_TIP=206` 对应的 active 叠层，再按 `balance1017/input-zips.json` 的顺序加载至 1.4.222。清单锁定相对路径与 SHA-256；原目录中的可变 `extra_zips.txt` 现在已包含目标 223，配方明确不以目标 ZIP 作为输入。输出在 `work/m0/balance1017/`。

## 万圣四人 1.4.221

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:WF_REPLAY_RUN = 'historical221-run1'
python -B -m recipes.halloween221
```

每次独立重跑选一个新的 `WF_REPLAY_RUN` 名称。入口依次执行四人的 init、tables、kit、assets、pixel、art、voice，最后按原算法合并表并分成 11 个 ZIP。立绘输入是已批准的透明母图及原统计蒙版，语音输入是已批准 WAV 及台词；不调用图像或语音生成服务。输出在 `work/m0/halloween-full/<run>/`。

原 `hw_kit_seriol.py` 已含后续 222 的 PF3 消毒修复。本历史配方显式选择 `historical_version=1.4.221`，重建「官方 knight_lv3 源树只把根 buffTargetAs 改成 133」的历史公式。这个版本分支是根据原构建器、修复注释和原始官方树恢复的，不声称发现了保存完好的 221 旧源码。普通 kit 调用仍保留 222 修复。期望 ZIP 只在独立比较阶段读取，生成阶段不读取它。

`python -B -m recipes.halloween_current_packages` 是诊断入口：读取当前四个 package 直接打包。现有 package 已含 222 修复，因此这个诊断结果与 221 的 PF3 成员不同。完整证据见 `docs/m0/recipe-results.md` 与对应 JSON。

## 依赖与验证

需要当前本地 Python、Pillow、NumPy、ffmpeg，以及配置根下的历史 store/active/extra ZIP、万圣 viewstore、art、voice、research 输入；语音台词沿用当前用户 Downloads 中原文件。所有机器相关位置均通过配置根或当前用户目录解析。

`wf.view.compare.compare_delivery` 对每个 ZIP 成员比较原始字节，并另算只归零 ZIP 本地头/中央目录 DOS 时间戳后的容器相等性。不会改动任何 ZIP，也不会替换期望值。
