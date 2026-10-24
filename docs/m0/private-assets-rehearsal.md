# 私有资源迁移隔离演练

作者本轮已裁决审查清单全部可公开；真实目录保持公开。本演练验证未来改变目录选择时的迁移能力。

本轮只在 `work/m01/asset-rehearsal-d2y4w81j` 副本执行迁移，真实资源目录未移动。副本复制了当时的 2050 个跟踪文件，另补两个已被当前源码引用的新模块；未初始化 Git。对审查清单全部 17 个目录调用 `plan` / `apply_plan`：17 个目录迁移成功，26 个 Python/文档引用文件被重写，副本原目录全部移除，私有镜像全部存在。

验证使用清空 `WF_*` 的环境、`python -B`、副本与原仓 `work/m0/test-deps` 的 `PYTHONPATH`，临时目录与测试输出均位于副本内。14 个纯本地资源及消费者套件合计 **342 passed、101 skipped、184 subtests passed**。跳过项为 93 项 live store / 游戏资产、6 项客户端补丁源码、1 项服务端源码、1 项宿主 symlink 能力。迁移后的 `private-assets/assets/weapon-awaken/build_icons.py --check` 可直接运行，输出 `ok 18 files, 9 icons`。

演练发现 `.cjs` 静态相对路径未被迁移；补齐 JS 路径解析后，以原始文本对副本中命中的 67 个 `.cjs` 文件重写引用，再运行 wiki equipment preview / battle audio 两套 Node 测试：**14 tests passed**。没有重复迁移或覆盖已通过的 Python 文件。**237 项资产 SHA-256** 检查全部通过：真实资源字节未变，副本私有镜像与审查清单一致。

证据路径均相对当前 worktree，位于 `work/m01/asset-rehearsal-d2y4w81j/work/`：

- `relocation-report.json`：迁移与引用改写明细。
- `test-command.json`、`supplemental-local-sources.json`：测试环境与快照依赖补齐。
- `rehearsal-tests.log` / `.xml`、`rehearsal-extra-tests.log` / `.xml`：Python 子集结果。
- `node-resource-tests.log`：初次发现的真实 JS 引用失败。
- `node-reference-fix.json`、`node-resource-tests-recheck.log`：修复后 Node 14 项通过。
- `rehearsal-final-checks.json`：237 项摘要与直接 CLI 检查。

本结果覆盖列出的代表性本地消费者，未执行全部 JS 前端测试、所有归档消费者或自定义动态路径，也不包含设备、服务端和真实配方发布验证。未据子集结果宣称全部运行时引用均已覆盖。
