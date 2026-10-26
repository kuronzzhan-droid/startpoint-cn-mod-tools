# M0 配方重跑与公共视图库收编证据

最终结果：平衡 1.4.223 的 **1 个 ZIP / 3 个成员全部相同**；万圣 1.4.221 的 **11 个 ZIP / 310 个成员全部相同**。各做了两次生成，万圣两次使用独立输出目录。原期望 ZIP 的初次、最终 SHA-256 全部一致。完整逐成员长度、SHA-256、容器比较记录在 [recipe-results.json](recipe-results.json)。

## 1. 五个公共库的来源与取舍

源位置以 `WF_ROOT` 指代本机配置根。逐文件的两个原始 SHA-256 见 JSON 的 `view_source_decisions`。

| 文件 | cursed_abyss 与 bughunt 的实际差异 | 选择与迁入 |
|---|---|---|
| `base149.py` | 只差 SCR、ACTIVE、KULO 路径常量；bughunt 指向历史 scratchpad/bughunt repo | 取生产 cursed_abyss 逻辑，迁到 `wf/view/base149.py`；路径从配置根解析 |
| `live149.py` | 只差 OLD 工具路径 | 取 cursed_abyss，移除外部工具插入和强制清理 `sys.modules`；统一用本仓 API |
| `stage_all.py` | 原文件逐字节相同 | 通用 CSV、PNG、魂珠着色、JSON 样式函数迁到 `wf/view/stage_all.py`；特定 1.4.150 交付 main 留作历史归档 |
| `dsltools.py` | 原文件逐字节相同 | 迁到 `wf/view/dsltools.py`；额外提取 C 的独立 `dsl_signature_problems`，避免配方为了签名检查导入整个诅咒武器生成器 |
| `layout.py` | 只差外部 oldrepo 工具路径 | 保留字段映射与枚举逻辑，去掉外部路径插入，读本仓 `wf_describe` |

有意改变的工程行为：历史视图不再在 import 时扫描外部 active，改为 `HistoricalView`/`configure()` 显式构造；不再重配置调用者 stdout。叠层的版本范围、原排序、extra ZIP 顺序和后者覆盖规则不变，两个真实交付的字节验证证明本次使用范围一致。

## 2. 平衡 1.4.223：真实改表并重新编码

入口：`python -B -m recipes.balance1017 --write`。角色变更规格在 `recipes/balance1017/`，公共框架在 `wf/view/balance.py`。它按原 builder 执行 8 个角色的旧值断言、126/124 列检查、合法性检查及 raw 行替换，重新生成 ZIP。

历史视图是 `WF_TIP=206` 对应的 active 链，加原 extra 清单截至 1.4.222 的前缀。原 `out/平衡1017/extra_zips.txt` 已在后续追加目标 223 自身；直接读取当前整份清单会把目标输出作为基线，触发旧值断言。现将正确的历史前缀和每个输入 ZIP 的 SHA-256 固定在 `recipes/balance1017/input-zips.json`，没有修改任何外部清单，也没有修改期望。

| 生成 | ZIP 数 | 同字节成员 | 不同成员 | 除 DOS 时间戳外容器一致 |
|---|---:|---:|---:|---:|
| 第一次 | 1 | 3 | 0 | 1 |
| 第二次 | 1 | 3 | 0 | 1 |

三个成员分别是 ability、leader_ability、custom_ability_string。此次原配方没有 DSL 或服务端 character_text 变化。原期望：`WF_ROOT/out/平衡1017/patch/pinball-1.4.222-1.4.223-1-balance-1017-local.zip`。输出：`work/m0/balance1017/`。第一次记录位于 `work/m0/recipe-comparison-initial.json`，最终记录位于 `work/m0/balance1017/comparison.json`；两份都并入本目录 JSON。

## 3. 万圣：先如实重跑当前源，再恢复明确的历史分支

先运行当前四个 package 的原打包流程，再从原表、母本资产、批准的透明母图、蒙版、WAV 和台词完整重建四个 package。完整重建依次执行每人的 init、tables、kit、assets、pixel、art、voice，最后执行原 `hw_pack.py` 的 raw 行合并和分包算法；不是把原交付成员复制成新 ZIP。

当前源结果均为 **309/310 成员相同**：已有 package 重打一次、当前源完整重建两次，三者一致；完整重建的两轮彼此 **310/310 相同**。保留这组证据，避免掩盖外部源已变化的事实：

- 当前 package 重打：`work/m0/halloween221/`，诊断入口现为 `python -B -m recipes.halloween_current_packages`。
- 当前源全重建：`work/m0/halloween-full/run1/`、`run2/`。
- JSON 对应键：`halloween_current_packages`、`halloween_current_source_run1`、`halloween_current_source_run2`、`halloween_current_runs_equal`。

唯一差异在第 11 包：

- 成员：`production/upload/89/45fd1ab9d8e6c8f32572e98fdf60ece8ddc46d`。
- 逻辑资产：`battle/action/skill/action/ability_skill/ability_skill_crystal_swordman_halloween_pf3$ability_skill_crystal_swordman_halloween_pf3.action.dsl.amf3.deflate`。
- 原 221：497 字节，SHA-256 `39d0013867105abb217bfc2fdab9308ddcfe1aaa9b9556b6ddc264ee443e85ed`。
- 当前源：463 字节，逐字节等于原 `delivery-1.4.222` 的 PF3 修复成员。
- 当前 `hw_kit_seriol.py` 注释明确说明这是 221 真机报错后的 222 修复：删掉 `SetPowerFilpSuppress`、`NotifyPowerflipEnd` 两种只适用于真正强化弹射的命令。

**历史模式的证据与限制：** 没有宣称找到了完整保存的 221 旧版源码。依据当前 builder 的原树加载/克隆部分、上述修复注释和未变的官方 `research/apk_pf/knight_lv3.deflate`，恢复了明确公式：加载官方树，仅把根索引 10（buffTargetAs）设为 133，再按原 AMF 编码与 raw-deflate level 9 输出。先独立验证这个公式确实等于原 221 的 497 字节，再将它作为显式 `historical_version=1.4.221` 分支写入配方。生成阶段不读取期望 ZIP；期望 ZIP 只由独立比较程序读取。普通 `pf3_tree()` 调用仍保留 222 消毒修复，不回退当前行为。

## 4. 最终 221 历史配方：两个独立完整重建

入口：`python -B -m recipes.halloween221`（`recipes.halloween_full` 为同功能别名）；两次分别设置：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:WF_REPLAY_RUN = 'historical221-run1' # 第二次改为 historical221-run2
python -B -m recipes.halloween221
```

| 生成 | ZIP 数 | 同字节成员 | 不同成员 | 除 DOS 时间戳外容器一致 |
|---|---:|---:|---:|---:|
| 历史模式第一次 | 11 | 310 | 0 | 11 |
| 历史模式第二次 | 11 | 310 | 0 | 11 |
| 两次输出互比 | 11 | 310 | 0 | 11 |

输出在 `work/m0/halloween-full/historical221-run1/` 与 `historical221-run2/`，每处有 `pkgroot/`、`build-report.json`、`delivery/` 和 `comparison.json`。期望保持 `WF_ROOT/out/万圣新角色-20261016/delivery-1.4.221/` 的原 11 个 ZIP。

最终运行的附加证据：

- 完整重建实际读取的 **351 个 viewstore 成员**，与 `store131 + WF_TIP206 active + 原 extra 至220` 的 **105 个 ZIP 叠层**重新逐字节核验全部一致；不是仅信任物化目录的版本标签。见 JSON 的 `halloween_view_verification_final`。
- **56 个 WF/配方 Python 模块**的运行时来源均在本 checkout；没有 import 旧外部工具副本。见 `halloween_api_origins_final`。
- 四角色 × 两档立绘的派生门禁均返回空问题列表。
- 由原批准 WAV 重新生成 87 个游戏语音槽：露迪 23、莫弥亚 22、塞里奥尔 22、瑞西塔尔 20；所有语音及展示资产均计入最终 310 个成员的字节比较。

## 5. 容器时间戳、写入边界与检查

`wf/view/compare.py` 逐个读取 ZIP 成员比较长度、SHA-256 和真实字节；另外只在内存副本中归零本地文件头和中央目录的 DOS 日期/时间四字节，再比整个容器。最终 12 个 ZIP 的成员顺序相同；原始 ZIP SHA 会因构建时间变化而不同，但归零时间戳后全部逐字节相同。没有改写 ZIP 时间戳来伪装原容器，也没有改期望。

所有配方入口启用 `wf/view/safety.py` 的写入审计边界；Python 写入仅限当前 checkout，拒绝跨目录写、截断、删除、移动和硬链接/符号链接。Windows 本地长路径规范化后检查；UNC 与 extended UNC 输出直接拒绝，不能去前缀后降级成相对路径。ffmpeg 仅处理已有本地 WAV，临时 MP3 输出也在本仓 `work/m0/`，执行前显式检查输出目录和文件，传入本仓 TEMP/TMP 与工作目录，并清除可自行指定报告写入位置的 `FFREPORT`。子进程不继承 Python 审计，因此此边界依靠固定参数及输出检查，**不是 OS 沙箱**。没有调用生成服务、服务器、设备、邮件或部署逻辑。

检查命令（pytest 依赖来自本任务仓内 `work/m0/test-deps`）：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'work/m0/test-deps'
python -B -m pytest tests/test_m0_recipes.py -q --basetemp work/m0/tests-recipes-historical
# 4 passed in 0.39s
```

测试覆盖叠层顺序/源不改、ZIP 时间戳与负载差异分离、CSV/JSON 样式保留，以及历史 221/普通 222 PF3 分支。表构建器拆分后，又对四个角色执行独立 init+tables smoke，四项均通过。上述整个完整重建也在最终拆分代码上成功运行。

最终独立复核另补 `tests/test_m0_recipe_safety.py`：通过模拟审计事件验证外部截断与 extended UNC 被拒绝，不实际向外写入；验证 ffmpeg 在目录不合法时不启动、合法调用的输出/TEMP/TMP/cwd 受限；验证按任意模块别名加载 archive/legacy 以及外部 WF API 均显式报错；验证 `configure()` 切换视图会清空 live149 的 flat/nested 缓存。`python -B -m pytest tests/test_m0_recipes.py tests/test_m0_recipe_safety.py -q --basetemp work/m0/review-safety-focused-tmp` → **11 passed in 0.76s**。以上边界修复及 `store131` 配置别名不改变编码算法，完成后只复跑定向测试，未重复完整历史重建。

运行环境：Python 3.14.6、Pillow 12.3.0、NumPy 2.4.6、zlib 1.3.1.zlib-ng；ffmpeg 的完整版本见 JSON。源 builder 和提取的 C 模块原始 SHA-256 记录在 `recipes/source-provenance.json`。

## 6. M1 建议与范围说明

M0 已证明两个指定客户端交付可以由本仓 API 重放。服务端 JSON 的外部安装、进程状态和设备验收不属于这次离线 ZIP 验收，未执行。

M1 应把历史输入清单与源文件摘要进一步做成统一版本锁；将 `sanitize_for_629` 与历史兼容分支作为明确能力/版本记录；以这里的 313 个真实成员字节回归代替只测字段表面值。当前生效的 222 修复与历史 221 重放必须持续分开，不能把成功复现旧交付理解为该旧行为适合重新发布。

## 7. 最后一次顺序回归发现的环境污染

全量 pass3 出现测试顺序相关失败：新增安全测试先 import `voice`，传递导入 `wf/chars/halloween/env.py` 时，旧适配代码把 `WF_TARGET_STORE` 改成万圣 viewstore；后续 publish、weapon 等测试因而没有使用自己的 fixture store。这是真实的模块导入副作用，不能把后续失败都归因于缺少外部输入。

修复移除了 `env.py` 的 import 时环境写入；只有显式执行 `replay.main()` 才选择历史 viewstore，普通库 import 保持调用者环境。新增回归在预设无关 fixture store 后 reload 该模块并导入 voice/kit，断言整个 `os.environ` 不变。ffmpeg 环境测试同时注入 `FFREPORT`，确认两个子进程参数都已清除它。

按污染触发顺序运行 `python -B -m pytest tests/test_m0_recipe_safety.py tests/test_m0_recipes.py tests/test_publish.py -q --basetemp work/m0/review-import-order-tmp`，结果 **31 passed in 1.56s**。这次只修导入环境选择与执行边界，未重复完整历史重建；第 2、4 节的逐成员证据仍来自前述两次真实生成，最终全量测试结果以 M0 总报告为准。
