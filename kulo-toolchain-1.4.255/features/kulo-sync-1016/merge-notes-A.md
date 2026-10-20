# merge-notes-A（serverfix-39，worker A）

范围：src/multi/tcp/server.ts, tcp/battle.ts, state/SessionManager.ts, lounge/state.ts, http/lobby.ts, tcp/lobby.ts, room/manager.ts, five-boss/lobby-runtime.ts, tcp/handshake.ts, coordinator/embedded.ts, http/battle.ts
结果：除 tcp/lobby.ts 外，10 个文件与 kulo origin/main 逐字节一致（取 main 侧后，box 在冲突外自动合入的部分也全是 main 已有内容或重复块）。全部 LF、无冲突标记；tsc 在这些文件上零错误。

## src/multi/tcp/server.ts（12 块）
- L24 import：box 无新增 / main 加 business-rpc、getRoom → 取 main。
- L70 attachSessionSocket 主体：box=PR#28 旧版 relay 接管 + clientAdmission 准入 → 取 main（main 已是 795cb94a/156c9d0a realtime-owner relay + socket-admission）。PR#28 版丢弃。
- L293/L310/L443/L463/L474/L527/L556/L582/L651/L683（握手准入、relay adopt、onData、relay 活动/关闭回调、startBattleRelay、server 创建/关闭）：box 全是 PR#28 relay 与旧 clientAdmission 形态 → 全取 main（规则 3）。
- 冲突外 box 自动合入的重复 import（battleRelayBridge/handleBattleRelayActivity/RelayActivity 二次导入）→ 删除（main 已有）。
- handleRuntimeServerError（#32 listen error handler）main 已吸收。

## src/multi/tcp/battle.ts（4 块）
- finalizeSent 标记、battleTelemetry.packet、handleBattleRelayActivity：main 全部已有（并多了 pinned control / markBattleMemberPhase）→ 取 main；box relay 版 handleBattleRelayActivity 丢弃。

## src/multi/state/SessionManager.ts（4 块）
- L26 import battle-contract：box 无 → 取 main。
- L1158/L1175 resolveBattleHandshakeIdentity：box 是不带 instanceId/isCurrentBattleClient 校验的旧版（#26 五重断线）→ 取 main（40ee8330 已吸收并加强）。
- L1684 armLevelNextDeadline：box 无 setImmediate 让步的旧版 → 取 main。
- 冲突外 box 合入的第二份 `private battleRelayMembershipChanged` 方法（重复定义）→ 删除。
- finalizeSent/battleRosterSeats/hasRoomConnections/clearLobbyRoomState 调用等 box 修复 main 均已有。

## src/lounge/state.ts（4 块）
- #32 lounge 加固（ReadyState 上限、名字截断、sendFrameReliably、一个 host 一个 lounge、disband 宽限）main 全部已有且更完整 → 取 main。
- 冲突外 box 合入的两行 `notify(...)`（位于 main 的 `if (!started)` 外，会对已开始的 lounge 也发解散帧）→ 删除。

## src/multi/http/lobby.ts（3 块）
- L8 import getRoomsHostedBy、L22 disbandIdleHostedLobbyRooms/isReturningMember、L128 create_room（mode15 门 4507 + 建房前清空闲房）：main 已有 disbandIdleHostedLobbyRooms，建房改为 lobby.create 命令（lobby-command-handlers 内同样以 host_created_new_room 清旧房），mode15 门 4507 也在 → 取 main。

## src/multi/tcp/lobby.ts（2 块）
- L592 / L633 测试服专属 NPC_COPY_HOST_PARTY（COM 座位复制房主当前编队）：main 无 → **移植到 main 形态**：保留 main 的 isNpcPartyAllowedInRoom 过滤循环与 npc.parties RPC；开关打开时 missingPartyCount=0（不抽池），party=structuredClone(hostMate.party)（仍过 isNpcPartyAllowedInRoom，不合法则跳过该座位，与 main 语义一致）。开关默认关闭，行为与 main 相同。
- 冲突外 box 合入的第二份 clearLobbyRoomState/getLobbyRoomStateForTests/seedLobbyRoomStateForTests（重复导出）→ 删除。

## src/multi/room/manager.ts（2 块）
- 两处 `assertRealtimeAuthority()`：box 侧为空 → 取 main。

## src/multi/five-boss/lobby-runtime.ts（2 块）
- 信号链 catch：box 是不记录 failedFiveBossSignals、不 retainRealtimeBusinessTail 的旧版 → 取 main。

## src/multi/tcp/handshake.ts（1 块）
- box 用本地 playerSocketAllowed；main 用 invokeRealtimeBusiness("player.authorize")（business-handlers 内仍调 playerSocketAllowed）并记录 sourceBattle → 取 main。

## src/multi/coordinator/embedded.ts（1 块）
- import battle-contract/room-start-claims/runtime-role：box 侧为空 → 取 main。

## src/multi/http/battle.ts（5 块）
- L62 import：box 要 embeddedMultiCoordinator/calculateFreeManaGrant/finish-receipt → 取 main（main 结算移入 MULTI_SETTLE_FINISH writer 命令，不再需要）。
- L471 acquireFinishExecution 键：box=buildFinishExecutionKey(multi, playerId, play_id)；main=`multi:${playerId}`（更粗，同玩家全部串行）→ 取 main。
- L482 / L667 多人 finish 主体（box：finish-receipt 回执重放、already_settled 快照重放、事务内 isMultiSettlementSettled 闩锁+重读玩家数值、finally 释放锁）：main 已用 player_operation_receipts 的 MULTI_FINISH_RECEIPT_OPERATION 做持久回执、quest_finish.single 互斥、play/quest/category 匹配校验、writer 事务内结算+回执、finally 释放锁 → 取 main（同一修复，main 形态）。
- L1267 content-type 头：取 main。
- 冲突外 box 合入的 `buildFinishExecutionKey`/`isMultiSettlementSettled`/`markMultiSettlementSettled`/`recordMultiSettlementResponse` import 与 buildFinishResponseCacheKey 第 4 参 `{ playerId }` → 删除（main 签名只有 3 参；按玩家去重已由持久回执覆盖）。

## 需复核
- http/battle.ts：已丢弃 box 的 finish-receipt.ts（src/data/domains/finish-receipt.ts）在多人 finish 的用法，以及 settlement-snapshot.ts 的 isMultiSettlementSettled/markMultiSettlementSettled、finish-response-cache.ts 的 buildFinishExecutionKey/playerId 键。这些库文件归其他 worker；若他们保留 box 版，这些导出在本文件里已无调用者（不报错，只是死代码）；若取 main，也不会与本文件冲突。另外请确认 #34 单人 finish 回执（quest_finish.single）在 main 的 player_operation_receipts 里写入，main 的多人 finish 依赖它做单/多互斥。
- tcp/lobby.ts NPC_COPY_HOST_PARTY：box 原实现用 legalNpcParty() 对房主编队做"裁剪成合法"；main 无该函数，改为 isNpcPartyAllowedInRoom 不合法即跳过座位。若测试服房主编队含该房不允许的装备，开关开启时 COM 座位会少于预期（box 版会剥掉装备后照样补位）。需要时再补一个裁剪函数。
- server.ts 全量取 main：box 的 clientAdmission().checkActivity 准入改由 main 的 coordinator/socket-admission 承担；测试服的准入名单（只放 com.leiting.wt 测试包）是否经由 socket-admission 仍生效，需在 175 上验证。
