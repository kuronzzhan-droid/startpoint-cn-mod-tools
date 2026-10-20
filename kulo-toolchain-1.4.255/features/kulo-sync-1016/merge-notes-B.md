# merge-notes-B(serverfix-39,worker B)

格式:文件 | hunk | box 意图 | 决定 | 理由

## src/lib/quest/finish/single-finish-transaction.ts(9 hunk,全取 main;保留 1 处非冲突 box 增量)
- L16 imports | 改用 finish-receipt 域表 | 取 main | main 356f621a 已用 player-operation-receipt + SINGLE_FINISH_RECEIPT_OPERATION 实现同一"每局一次回执"
- L126 args.playerData | 事务内重读余额的兜底快照 | 取 main | main 事务内 getPlayerSync,null 直接抛错
- L144 receiptPlayIds[] | 多个 playId 记回执 | 取 main(receiptPlayId 单值) | 同行为,main 形状
- L178 回执检查+消费注册 | #34 一局只结一次 | 取 main | main 还多查 multi 回执、CLOCK_ABORT、clockVersion,覆盖更全
- L240 useBoostPoint 括号 | 纯格式 | 取 main | 等价
- L266 `if (!registered) deletePlayerActiveQuestSync` | 未注册局清行 | 取 main | main 对 !registered 早退不发奖,该行不可达
- L427 / L446 练习历史 | bughunt "practice zones empty warn only" | 取 main | main 77d47f75 只把 BattleHistoryPayloadValidationError 降为 warn,其余抛出——同意图更严
- L864 写回执 | recordFinishReceiptSync + prune | 取 main | insertPlayerOperationReceiptSync 同语义
- 非冲突区保留:SINGLE_SCORE_SCALE(仅 BOSS_BATTLE / WORLD_STORY_EVENT_BOSS_BATTLE)| main 无 | 保留 box | 测试服专属口径,main 未吸收

## src/routes/api/singleBattleQuest.ts(7 hunk,全取 main)
- 全部 hunk(finish 锁、回执重放、事务内重读余额、receiptPlayIds 传参、null 响应重放)| #34 | 取 main | main 已有 acquireFinishExecution(`single:${playerId}`)、getPlayerOperationReceiptSync 回放、结算命令内重读;另删两条自动合并残留的未用 import(finishRequestPlayId、getFinishReceiptSync)。文件现与 kulo main 逐字一致

## src/routes/cn/load.ts(6 hunk,全取 main)
- L43 import runPersistenceWriteScope | #36 | 取 main | 见下
- L162 维护+修复整段 | #36 单写事务 | 取 main | main 已把 load 维护、validator、对账、Rush 壳、深渊刷新、组装全包进一个 runPersistenceTransaction("load_maintenance")= 一次 COMMIT
- L247 now 取值 | getServerTime | 取 main | main 用事务内 now
- L257 / L290 注释 | 注释差异 | 取 main | 无行为
- L311 afterRepairs→finish() 提前提交 | #36 序列化前提交 | 取 main | main 在事务内组装、事务外 serializePlayerSnapshot 转换
- 文件现与 kulo main 逐字一致。gzip(CN_LOAD_HTTP_COMPRESSION)不在本文件,在 cn-response-hook / cn-response-encoding(非本人文件)

## src/lib/persistence-coordinator.ts(1 hunk + 非冲突 box 增量)
- L14 imports + 自动合并进来的 runPersistenceWriteScope | #36 惰性写作用域 | 整文件取 main,删 runPersistenceWriteScope | load.ts 取 main 后没有调用方;留着是死代码,而且原实现绕过了 main 的受理/写闸门(withPlayerWriteQueue 直排)

## src/cn-server.ts(4 hunk)
- L33 import | process-guards | 合并两侧(crash-report + installProcessGuards) | 都要
- L179 /crash 限流判定 | request.url | 取 main(routeOptions.url) | main 更稳,带 query 也能命中
- L584 优雅关停 | box 自写 gracefulShutdown + forceExit | 取 main createGracefulShutdown,requestGracefulShutdown 加 `forceExit` 参数:关停完成后 forceExit 就 process.exit(exitCode ?? 1) | 结构按 main,只移植"致命异常后不等残留句柄"这一点
- L637 IPC 关停 / installProcessGuards | #35 进程级异常守卫 | 两者都留:先 main 的 parent IPC 监听,后 installProcessGuards({ onFatal → exitCode=1; requestGracefulShutdown("uncaughtException", true) }) | main 没有 unhandledRejection/uncaughtException 处理

## src/data/domains/abyss-tower-progress.ts(2 hunk)
- L66 / L88 | 仅注释措辞 | 取 main | 224aa2a6 已是同一跳过无变化写事务的逻辑;文件 = main

## src/lib/persistence-coordinator.ts → 见上

## src/routes/web_api/diagnostics.ts(1 hunk)
- L2 import + 自动合并出的重复 /battles 路由 | box 加 /battles 遥测 | 整文件取 main | main 已有 /battles(经 RoomCommandGateway "runtime.battles");box 版本会注册重复路由,启动即报错

## src/routes/cn/asset.ts(1 hunk)
- L346 补丁 location | LOCAL_PATCH_BASE_URL / AFTER / FILES 分流下载 | 取 box | 测试服专属,main 没有;常量和 compareVersion 在非冲突区已就位

## 编译
- serverfix-39 自身 tsc 被 src/multi/http/battle.ts 的冲突标记挡住(他人文件),而且树里没有 assets/,TS2307 大量误报。
- 我在 scratch 副本里先把 battle.ts 临时按 main 解开再跑 tsc:本人 8 个文件、finish-receipt.ts、process-guards.ts 零错误。剩下的错误只有缺 assets JSON 的 TS2307,以及由此连带的 unknown(box-gacha-1001、how-to-get-sources 等)。

## 需复核
1. #36:/load 取了 main 的"整段一个事务"。box 的惰性版本(无修复时不开 BEGIN IMMEDIATE、在序列化前提交)没有移植,因为 main 已满足"单次 COMMIT"。若要"无变化不开写事务",应走 kulo PR #42 的路线。player-data.ts 里自动合并进来的 `afterRepairs` 选项(他人文件)现在没有调用方,是可选参数,无害,由该文件负责人决定去留。
2. #34:single 结算已完全换成 main 的 player_operation_receipts(operation=SINGLE_FINISH_RECEIPT_OPERATION)实现。src/data/domains/finish-receipt.ts 现在只剩 src/lib/persistence/commands.ts 和 src/multi/http/battle.ts(他人文件)在引用。若这两处也改走 main 实现,finish-receipt.ts 可删。另需确认测试服旧库里 finish-receipt 写下的回执,迁移后是否还要回放(main 不读它)。
3. SINGLE_SCORE_SCALE 放在 main 事务内回执检查之后、发奖之前,直接改写 body.score。main 在开启写线程时 args 会跨线程序列化;改写只影响本次命令,结果不变,但写线程路径未实测。
4. cn-server:致命异常时 createGracefulShutdown 失败分支本身就会 process.exit(1);成功分支靠新加的 forceExit 退出。需确认 main 的 quiesce 在 uncaughtException 场景下不抛错。
