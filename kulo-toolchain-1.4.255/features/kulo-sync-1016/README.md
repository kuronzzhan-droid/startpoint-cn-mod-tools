# 测试服同步 kulo main（2026-10-16）

测试服 C:\startpoint-test 的服务端基线 = kulo df99b73c（10-09 staging）+ 我们的 PR / 测试服专用补丁；镜像树 D:\WF\serverfix-38。
正式服跑的是 kulo origin/main（10-15 18:34 编译，含 224aa2a6）。两者之间 kulo 有 53 个提交（kulo-commits.txt），src 改 170 个文件，+12593/−4159。

## 文件
- kulo-df99b73c..main-src.patch：kulo 基线→main 的 src 全量补丁
- kulo-changed-src.txt：kulo 改动文件清单（name-status）
- box-modified-src.txt：测试服相对 df99b73c 改过的 64 个 src 文件
- conflict-candidates.txt：两边都改过的 54 个文件（需要逐个合）
- box-vs-main.txt：测试服改动是否已被 kulo main 吸收
  - SAME-AS-MAIN（15 个）：直接用 main 版本即可
  - BOX-ONLY-FILE（3 个）：finish-receipt.ts（#34 重做版）、character-overlimit.ts（超限）、process-guards.ts（#35/#41 兜底）——保留
  - DIFFERS（46 个）：测试服改动未被 main 原样吸收，需按 hunk 判断

## 建议做法
以 kulo main 为新底，重放测试服专用项，而不是把 main 补丁打到测试服旧树上（联机层 kulo 已整体换成 coordinator/实时子进程架构，src/multi 旧树上打补丁冲突最多）。
测试服必须保留的：LOCAL_PATCH 分流（routes/cn/asset.ts）、测试号自动建号（player-login.ts）、准入测试包 build（client-admission.ts）、NPC_COPY_HOST_PARTY（tcp/lobby.ts）、超限服务端、/load gzip、boss_coin_shop cat20/98、测试服 .env（SINGLE_SCORE_SCALE、NPC_COPY_HOST_PARTY、MULTI_AI_FILL_TIMEOUT_MS=0、SQLITE_*）。
我们已进 kulo 的：#26（40ee8330 改写版）、#28（被 795cb94a+156c9d0a 取代）、#32（核心并入 main）、bughunt 0001–0007（#39 部分吸收，需核对）。

## 注意
- 156c9d0a 的实时子进程有今天正式服暴露的问题：主线程卡顿时子进程被封存后不重建（8003 下线），同步后测试服同样会有，直到修复。
- .env 的 MULTI_BATTLE_RELAY_PROCESS=1 在 main 里启动的是 realtime-owner 子进程（command-process-child.js），不是 PR#28 的 battle-relay。
