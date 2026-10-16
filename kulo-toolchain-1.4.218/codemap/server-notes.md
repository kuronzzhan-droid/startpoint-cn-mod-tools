# startpoint-cn-kulo 服务端速查（查表用，非手册）

路径相对 `D:\WF\startpoint-cn-kulo`（下称 kulo）。盒子专用补丁不在 kulo 里，在盒子快照 `D:\WF\bughunt-20261014\boxtree\`（下称 boxtree，路径同 kulo 的 `src/...`），见第 3 节。路由全表/环境变量表由脚本另出，这里不重复。

## 1. 持久化层

### 1.1 总图
- 库：单个 SQLite `wdfp_data.db`，目录 `DATA_DIR`（缺省 `<repo>/.database`），`src/data/index.ts:18-20`；版本迁移钩子 `init/updateBefore/updateAfter` 在 `src/data/index.ts:6-11,43-48`，实现在 `src/data/initializers/*`、`src/data/updaters/wdfpData.ts:37(updateBeforeInit) / :72(updateAfterInit)`。
- 取连接：`getDb()` `src/data/db.ts:23`（惰性）；写线程用 `setDbOverride()` `src/data/db.ts:18` 换成自己的连接，让同一份 domain 代码在两边跑。
- `src/data/domains/*.ts`：每个领域一个文件，函数名约定 `getXxxSync / insertXxxSync / updateXxxSync`，直接用 better-sqlite3 同步语句。路由只调这些，少数例外手写 SQL（如 `lib/player-login.ts`）。
- `src/data/readers/load-snapshot.ts`：只读拼装器（角色/编队/关卡进度 `readPlayer*Sync`，被 `domains/character.ts quest.ts party.ts` 复用；`readLoadSnapshot :215` 目前无外部调用）。
- `src/data/utils/serialize-player.ts / serialize-entities.ts / client-player-snapshot.ts`：落库行 与 客户端 `/load` 包格式互转。
- `src/data/snapshots/player-snapshot.ts`：玩家存档 V2 快照（备份/回滚/导出/测试服模板）。`PLAYER_SNAPSHOT_V2_TABLES :64`、`createPlayerSaveSnapshotV2Sync :321`、`validatePlayerSaveSnapshotV2Sync :369`、`restorePlayerSaveSnapshotV2Sync :484`、覆盖度断言 `assertPlayerSnapshotCoverageSync :242`。使用方：`routes/web_api/player.ts:237,243`、`routes/web_api/server.ts:860`、`workers/player-save-export-worker.ts:30`。

### 1.2 事务入口（四种）
全部在 `src/lib/persistence-coordinator.ts`：
| 函数 | 位置 | 用途 |
|---|---|---|
| `runPersistenceTransaction(ctx, op, {afterCommit})` | :148 | 异步，主线程内同步闭包。先 `yieldToEventLoop`，再 `withPlayerWriteQueue(playerId)`（有 playerId）或 `enqueueGlobalWrite`，再 `runImmediateTransactionWithRetry`（BEGIN IMMEDIATE，忙则重试）。绝大多数路由用它。 |
| `runPersistenceTransactionSync(ctx, op)` | :384 | 同步兼容口；已在事务里则 `db.transaction(op)()`=savepoint。domain 内部嵌套、命令体内部都用它。 |
| `runWriterCommand(name, args, ctx)` | :256 | 按名字把“整段读-改-写”交给写线程（`CN_WRITER_THREAD=1`），关闭时在主进程内走同一注册函数。已命令化的只有 5 条。 |
| `runPersistenceSqlCommand` | :207 | 纯 SQL 语句数组，交给 `workers/sqlite-persistence-worker.ts`（`SQLITE_PERSISTENCE_WORKER`）；低频。 |
- `PersistenceDomain`（:23）：account/player/single-quest/multi-settlement/mail/mission/gacha/shop/event/leaderboard/admin/maintenance。ctx 形如 `{domain, playerId, operation}`；有 `playerId` 的写按玩家串行（`src/lib/sqlite-write-coordinator.ts:19 withPlayerWriteQueue`，重试 `:49 runImmediateTransactionWithRetry`，忙判断 `:13`）。
- 优雅停机：`drainPersistence :415`、`drainPlayerWriteQueues`(sqlite-write-coordinator.ts:39)。

### 1.3 命令/写线程机制
- 命令名常量+参数类型：`src/lib/persistence/command-names.ts`（只有类型依赖，防循环）：`mission.settle_categories`、`single.refresh_quest_progress`、`multi.cleanup_active_quest`、`multi.record_battle_facts`、`single.settle_finish`。
- 注册表：`src/lib/persistence/command-registry.ts:49 registerWriterCommand / :57 getWriterCommand`；handler 签名 `(args, ctx{afterCommit})`，参数/结果须 structuredClone 安全；非持久副作用必须放 `ctx.afterCommit`（提交后才执行）。
- 命令绑定：`src/lib/persistence/commands.ts`（副作用导入，主进程与写线程都要 import；5 条 `registerWriterCommand` 在 :27/:36/:45/:54/:90，体内用 `runPersistenceTransactionSync`）。
- 客户端：`src/lib/persistence/writer-client.ts`：`startSqliteWriter :330`（`cn-server.ts:608` 调用）、`executeSqliteWriterCommand :345`（队列 `waiting[]`，满=`SQLITE_WRITER_QUEUE_FULL`）、`drainSqliteWriter :427`、`stopSqliteWriter :452`、`sqliteWriterStats :407`。配置 `writer-config.ts:36-50`：`CN_WRITER_THREAD` 缺省关；`SQLITE_WRITER_FALLBACK` 缺省关；队列 512、in-flight 32、群提交窗口 2ms/64 条、命令超时 30s、重启 5 次。
- 写线程：`src/workers/sqlite-writer-worker.ts`：`executeBatch :130`（一批共用 `BEGIN IMMEDIATE :151`/`COMMIT :196`，每条命令一个 savepoint，失败只 `ROLLBACK TO :184` 该条；COMMIT 前 structuredClone 校验 :176；afterCommit 在提交后跑 :228）；`handleMessage :293`。主线程时钟偏移经 `pushTimeOffset` 同步给写线程。
- 其它线程：`workers/sqlite-checkpoint-worker.ts`（WAL 检查点/截断）、`sqlite-persistence-worker.ts`（SQL 数组命令）、`player-save-export-worker.ts`（导出 V2 快照）、`cn-response-worker.ts`（/load 回包编码，`lib/cn-response-worker-pool.ts`）、`quest-npc-party-pool-worker.ts`（NPC 队伍池预热）、`admin-account-cleanup-worker.ts`。
- 幂等回执：`data/domains/player-operation-receipt.ts`（`getPlayerOperationReceiptSync(playerId, operation, requestKey)`，gacha 兑换用）；/finish 响应缓存 `lib/finish-response-cache.ts`。

### 1.4 handler 区域 对应 数据域 / 业务模块 / 事务函数
| 区域 | 路由文件 | 主要 domain / 业务模块 | 事务 |
|---|---|---|---|
| 登录/注册 | `routes/cn/playerLogin.ts`、`lib/player-login.ts` | `domains/account.ts session.ts player.ts` | `runPersistenceTransactionSync` domain=account（`player-login.ts:210 register / :227 login / :245 logout`） |
| /load 进主城 | `routes/cn/load.ts:133` | `domains/player.ts`(dailyReset/pooledExp) + 各 `getPlayerXxxSync` + `data/utils/serialize-*` | `runPersistenceTransaction` domain=player op=`load_maintenance`(`load.ts:162`)；主体读取不在事务内 |
| 单人关 start/finish/abort | `routes/api/singleBattleQuest.ts:522/:214/:387` | `domains/quest.ts quest_active.ts`；`lib/quest/finish/*`（rush/raid/score-attack/carnival handler） | start=`runPersistenceTransaction`(:682)；finish=**`runWriterCommand(SINGLE_REFRESH_QUEST_PROGRESS :335, SINGLE_SETTLE_FINISH :363)`**，体在 `lib/quest/finish/single-finish-transaction.ts: settleSingleQuestFinishInTransaction` |
| 剧情 finish | `routes/api/storyQuest.ts:84/:119` | `domains/quest.ts` | `runPersistenceTransaction`(storyQuest.ts:40) |
| 多人 finish/abort | `multi/http/battle.ts:442/:1038` | `lib/mission/battle-facts.ts`、`multi/settlement.ts`、`multi/settlement-snapshot.ts` | **`runWriterCommand(MULTI_RECORD_BATTLE_FACTS :793, MULTI_CLEANUP_ACTIVE_QUEST :1008)`**；奖励段仍 `runPersistenceTransaction` |
| boss 战/五重 | `multi/http/five-boss-battle.ts`、`multi/five-boss/*` | `domains/fiveBossGauntletRun.ts`(`startMemberSync :336 / recordMemberBattleSignalSync :481 / settleMemberSync :566 / abortMemberSync :667`)、`initializers/five-boss-gauntlet.ts` | domain=event；`five-boss/lobby-runtime.ts:106`、`solo-runtime.ts:43/50`、`continue-runtime.ts:140/147` |
| 抽卡 | `routes/api/gacha.ts`(draw :380；兑换 :158/:240) | `lib/gacha*.ts`、`domains/gacha.ts`、`lib/gacha-exec-plan.ts` | `runPersistenceTransaction` domain=gacha；带 requestKey 回执幂等 |
| 盒抽 | `routes/api/boxGacha.ts`(box_exec :347, reset :180, close :252) | `domains/boxGacha.ts` | `runPersistenceTransaction` domain=gacha |
| 角色 魔力/羁绊/突破 | `routes/api/character/mana.ts`、`bond.ts`、`character.ts`(over_limit :118, bulk :195) | `domains/character.ts`、`lib/mana.ts`、`lib/character-awake-*.ts` | `runPersistenceTransaction`（mana.ts:122/183/403；bond.ts:50/112） |
| 编队 | `routes/api/party.ts`(edit :767)、`partyGroup.ts`(:58) | `domains/party.ts publishedParty.ts`、`lib/party-group-persistence.ts` | `runPersistenceTransaction` |
| 商店/道具/出售 | `routes/api/shop.ts`(purchase :685, bulk :1268, stamina :937, 强化 :581)、`item.ts`(:130)、`sell.ts` | `domains/item.ts shopPurchase.ts equipment.ts`、`lib/item-sell.ts`、`lib/shop-sales.ts` | `runPersistenceTransaction` domain=shop/player；余额先读后写（见坑 6） |
| 任务/成就 mission | `routes/api/mission.ts`(:239)、`activeMission.ts` | `domains/mission.ts active_mission_*`、`lib/mission/*`(`settlement.ts:285/:314/:321`) | `runWriterCommand(MISSION_SETTLE_CATEGORIES)`(settlement.ts:314) + domain=mission 事务 |
| 深渊/rush/塔 | `routes/api/rushEvent.ts`(select_folder :359, battle/start :794, reset :872/885, reward :983) | `domains/rushEvent.ts abyss-*.ts`、`lib/rush.ts abyss-modes.ts`、`lib/quest/finish/rush-handler.ts` | `runPersistenceTransaction` domain=event |
| 排行榜 | `routes/api/rankingEvent.ts`、`routes/web_api/leaderboards.ts` | `domains/leaderboard.ts`、`lib/leaderboard/{service,settlement,rewards,availability}.ts`；定时器 `leaderboardSettlementScheduler`(cn-server.ts:624) | domain=leaderboard（`service.ts:147`、`settlement.ts:346/:477`、`domains/leaderboard.ts:248`） |
| 邮件/奖励 | `routes/api/mail.ts`(:223)、`web_api/mail.ts` | `domains/mail.ts`、`lib/daily-vmoney-mail.ts` | domain=mail |
| 管理后台 | `routes/web_api/{player,server,mail,news,leaderboards,seeds,diagnostics}.ts`、`routes/web/*` | `domains/admin-player.ts player-repair.ts`、`lib/admin-*.ts`、快照 `data/snapshots` | domain=admin（`web_api/player.ts:305-463`：admin_add_character/set_item 等） |

## 2. 联机（src/multi）
入口 `multi/index.ts`（barrel）；HTTP 注册 `multi/http/register.ts`；TCP 端口 `SESSION_PORT` 缺省 8003（`tcp/server.ts:26`）。
- `tcp/server.ts`：8003 监听、分帧（`\0` 分隔 JSON）、握手超时/帧上限/背压常量(:34-42)、准入 `clientAdmission().checkActivity`(:149,:186)、`startSessionServer :51`。
- `tcp/handshake.ts`：进房/进战斗握手 `handleHandshake :34`，建 SessionClient、buildRealParty。
- `tcp/lobby.ts`（1316 行）：大厅帧 `handleMessage :1282`（Enter/Ready/ChangeParty/StartBattle/Bye）；全员就绪开战 `checkAllReadyAndStart :344`；人机补位 `handleEnterComs :396`、`recruitNpcMatesForRoom :673`。
- `tcp/battle.ts`：战斗帧。Notify(SceneReady/LevelNext/Finalize/Measurement/Heartbeat) 在 `handleBattleNotify`；Broadcast 转 `relayToBattleRoom([2,connId,data])`，Send 转 `[3,connId,msg]`（`handleBattleMessage`）。
- `tcp/relay.ts:9 relayToBattleRoom`：**帧转发核心**。服务器不跑战斗逻辑、不做锁步校验，仅把一个客户端的 Broadcast/Send 序列化一次，发给 `sessionManager.snapshotBattleRelayRecipients()` 冻结的收件人；每台设备自己模拟全员。
- `tcp/reliable-send.ts`：带背压/重连代次的发送封装；`tcp/chain-diagnostic.ts`、`disconnect-diagnostics.ts`：诊断。
- `state/SessionManager.ts`（1551 行）：房间/战斗客户端索引、栅栏（SceneReady/LevelNext 屏障 `markSceneReady`/`beginBattleLevelNext`）、重连、座位过期。`state/ClientStateMachine.ts`：客户端状态。
- `coordinator/embedded.ts:28 EmbeddedMultiCoordinator`：房间状态迁移（LOBBY/BATTLE/SETTLING…）。
- `room/manager.ts`：房间表 `createRoom :103 / getRoom :147 / disbandRoom :270`；`room/admission.ts` 入场判定；`room/serializer.ts`、`sharing.ts`。
- `http/lobby.ts`（create/search/select/get_rooms）、`http/room.ts`（prepare/summon/restore/share/disband）、`http/social.ts`（verify_access_token/publish_room）。
- **结算**：`http/battle.ts`：`/start :241`、`/finish :442`（逐玩家：冻结快照 -> 奖励 -> `MULTI_RECORD_BATTLE_FACTS` -> 缓存响应 -> `transitionMultiSettlementSnapshot(RETURN_PENDING)` -> `MULTI_CLEANUP_ACTIVE_QUEST`）、`/abort :1038`、`/play_continue :1147`。`settlement.ts:132 mergeMultiSettlementResults` 合并各人结果；`settlement-snapshot.ts` 战斗实例快照生命周期 BATTLE/SETTLING/RETURN_PENDING/LOBBY(:5)；另 `rescue-fragment-reward.ts`、`party-snapshot.ts`。
- NPC：`ai-fill.ts`（超时补人机，`MULTI_AI_FILL_TIMEOUT_MS` 缺省 120000，:15）、`npc/*`（队伍池 `player-party-pool.ts`、`quest-party-pool-*`、`builder.ts`、`controller.ts`）、`recruitment.ts`（随机招募）、`guest-eligibility.ts`、`mode15-room-gate.ts`。
- 五重：`five-boss/*`（`contract.ts` 常量、`battle-runtime.ts`、`rewards.ts`、`solo-*.ts`、`lobby-runtime.ts`、`connection-diagnostic.ts`）。

## 3. 测试盒专用补丁（不在 kulo main；以 boxtree 为准）
盒子 `C:\startpoint-test`（175.178.160.158）。`diff -rq kulo/src boxtree/src` 差约 50 个文件，下列是盒子专用或未进 PR 的。
| 项 | boxtree 位置 | 作用 | 开关 / 缺省 |
|---|---|---|---|
| 测试员登录 | `src/lib/player-login.ts:207-263`（`testerLogin / createTesterAccount`；`registerPlayerLogin`、`loginPlayer` 首行判断） | 统一密码登录；账号名不存在就自动建号并 `restorePlayerSaveSnapshotV2Sync(模板)`，名字=账号名（前 12 字）。已有账号也只校验统一密码，不校验各自密码 | `TEST_SERVER_SHARED_PASSWORD` 且 `TEST_SERVER_TEMPLATE_SAVE`（V2 快照 JSON，如 `config/tester-template.json`）都设才生效；缺省关=正常注册/登录 |
| 客户端准入 | kulo 就有：`src/lib/client-admission.ts`（HMAC 挑战/证明，`installClientAdmission :187`，preHandler 只管 `/api/index.php/*` 与 `/player-auth/*`；TCP 在 `multi/tcp/server.ts:149,186`）；配置 `config/client-admission.json`(`enforce`、`builds[]`) 与 `config/client-admission.keys.json`（密钥，勿外传） | 只放行名单内 build id；不符返回 result_code 516 + `CLIENT_ADMISSION_REQUIRED`。盒子配置只放测试包 build `android-181-testserver-wt-v17b-20261007`（包名 com.leiting.wt）；boxtree 版另加 `[ADMISSION-DIAG]` 诊断行 | `CLIENT_ADMISSION_CONFIG` / `CLIENT_ADMISSION_KEYS` 可改路径；kulo 内置 config 现为 `enforce:true` + 3 个公网 build |
| 分流下载 | `src/routes/cn/asset.ts:36-48,347-349`（`buildDiffList` 内选补丁包 base） | 版本 <= `LOCAL_PATCH_AFTER` 的 diff 走 `CDN_BASE_URL`（Cloudflare 镜像）；更新的 asset-patch 或 `LOCAL_PATCH_FILES` 列出的文件名走 `LOCAL_PATCH_BASE_URL`（本机） | `CDN_BASE_URL`、`LOCAL_PATCH_BASE_URL`、`LOCAL_PATCH_AFTER`(如 1.4.130)、`LOCAL_PATCH_FILES`(逗号分隔)；缺省全空=全部走原 baseUrl |
| 单人分数缩放 | kulo 已有：`src/lib/quest/finish/single-finish-transaction.ts:157-166`；boxtree :183-191 | `body.score = floor(score*SINGLE_SCORE_SCALE)`，只影响记录分/分数奖励/排行（客户端单人 boss 额外 x2 时间倍率，与联机对齐）；SCORE_ATTACK 排除 | `SINGLE_SCORE_SCALE` 缺省 **0.5**，=1 关闭。kulo 现状对所有非分数挑战类别缩放；`bughunt-20261014/handoff/0003*.patch` 收窄为 BOSS_BATTLE(2)+WORLD_STORY_EVENT_BOSS_BATTLE(19)，降临活动不缩放 |
| 战斗中继子进程 | `src/multi/tcp/battle-relay/{bridge,child,protocol}.ts`；开关 `bridge.ts:20 battleRelayProcessEnabled`，接线 `tcp/server.ts:21,311` | 握手后把战斗 socket 交给子进程转发，主进程持 `RelayProxySocket`，隔离主线程卡顿；崩溃最多重启 `MULTI_BATTLE_RELAY_MAX_RESTARTS`(5)，超过则留在进程内 | `MULTI_BATTLE_RELAY_PROCESS=1` 才开，缺省关（kulo 无此目录） |
| 战斗遥测 | `src/multi/battle-telemetry.ts`（`battleTelemetry :303`；钩子 `coordinator/embedded.ts:71-72 begin/end`、`tcp/battle.ts:88 packet`、`SessionManager.ts:394/455/1435`） | 每场联机战斗结束输出一行 `[MULTI-BATTLE]` 摘要（包数、最长静默、背压、断线原因、事件循环延迟），近期摘要进管理诊断接口(`routes/web_api/diagnostics.ts`) | `MULTI_BATTLE_TELEMETRY` 缺省 **true**（`battle-telemetry.ts:75-77`）；热路径只加计数器，不碰 SQLite |
| 人机复制房主 | `src/multi/tcp/lobby.ts:427-461`（`recruitNpcMatesForRoomAttempt` 内） | 每个 COM 用 `structuredClone(hostMate.party)`（过 `legalNpcParty`），不抽玩家队伍池、不读 `room.npc_party_by_com_id` 缓存（`missingPartyCount` 强制 0） | `NPC_COPY_HOST_PARTY=1`，缺省关。开启后 five-boss-integration「COM parties stable」断言预期失败；不进 kulo PR |
| 其它盒子 env（非代码补丁） | — | `MULTI_AI_FILL_TIMEOUT_MS=0` 人机立刻补位；`CN_LOAD_HTTP_COMPRESSION=gzip`(/load 回包 2.16MB 变 153KB，`lib/cn-load-http-compression.ts:38`，缺省 off)；`SQLITE_SYNCHRONOUS=NORMAL`、`SQLITE_DIAGNOSTICS=true` | 详见 memory `wf-test-server-175.md` |

参考：`D:\WF\bughunt-20261014\findings\codex_score_scale_report.md`（类别映射表）、`handoff\0001-0003*.patch`、`D:\WF\startpoint-cn\out\性能与漏洞审计-20261009\总报告.md`。

## 4. 服务端专用数据文件
- 静态主数据 = 仓库内 JSON：`assets/*.json`，由 `src/lib/assets.ts:1-41` 静态 `import` 汇总（关卡/奖励/商店/抽卡/魔力盘/boss 币商店等），取数函数 `getMainQuestSync :253`、`getBoxGachaSync :632`、`getGachaSync :660`、`getGenericShopItemsSync :721`。合并“基础 + cnmod + rank_p5b”的表在 `src/lib/content-master.ts:26-32`（`serverCharacters / cdnCharacters / cdnCharacterTexts / degreeDefinitions / serverGachas / serverManaNodes`）。运行期内容快照：`src/content/runtime/content-snapshot.ts`、`lib/custom-cdn-resource-routes.ts`。
- `assets/cdndata/*`：CDN 镜像副本（character/gacha/boss_coin_shop/player_rank 等）。
- **`assets/cdndata/character_text.json`（+ `character_text_rank_p5b.json`）= 服务端专用**，只在 `content-master.ts:5-6,29` 合并成 `cdnCharacterTexts`，读取方仅两处：`src/lib/admin-clairvoyance.ts:2,85`（管理员千里眼角色文案）与 `src/lib/mission/active-loadout-battle-facts.ts:6,58-72`（任务战斗事实按文案里的称号/标签等判定）。不下发客户端；游戏内技能说明在客户端 action_skill，改此文件不改游戏内文案。盒子上的该文件比构建器版多 159992 且为 CRLF，只合改动条目，别整文件覆盖。
- `CDN_DIR`（缺省 `.cdn`，相对仓库根）：客户端资源/补丁镜像，读点 `cn-server.ts:469`、`server.ts:153`、`routes/cn/asset.ts:250`、`routes/api/asset.ts:99`、`routes/web_api/server.ts:380`、`unzip_cdn.ts:29`、`validate_cdn.ts:10`。补丁包目录 `asset-patch/active`，manifest 按 mtime 热加载：纯资源补丁免重启，服务端 JSON/代码需重启。
- `DATA_DIR`（缺省 `.database`）：`wdfp_data.db`、`active_account.json`（含 `timeOffset` 虚拟时钟，`data/activeAccount.ts:12`）、`default_save.json`（`data/defaultSave.ts:10-13`）、备份(`lib/admin-database-backup.ts:20`)。`storage-maintenance.ts:19` 为维护脚本。

## 5. 坑（均有证据）
1. **`src/lib/persistence/commands.ts:97` 联机 EXP 条件取反**：`givePlayerCharactersExpSync(..., !args.fixedParty)` kulo 仍是旧的（同文件 :76 的推荐队伍 `if (!args.fixedParty)` 才对）。修复见 handoff `0001-…skip-co-op-character-EXP-only-for-fixed-p.patch`，改为 `args.fixedParty`。
2. **`single-finish-transaction.ts:246` `clearReward !== undefined`**：值为 `null`（未解析奖励）时仍调用发奖，HTTP 500；应 `!= null`（handoff 0002）。
3. **`SINGLE_SCORE_SCALE` 直接改写请求 `body.score`**（`single-finish-transaction.ts:161-165`），默认 0.5 且对所有非分数挑战类别生效；命令被重试/复用同一 args 会二次缩放（`findings/server_hunches.md`）。
4. **`CN_WRITER_THREAD` 缺省关（`writer-config.ts:48`）、`SQLITE_WRITER_FALLBACK` 缺省关（:49）**：开了写线程但线程挂掉，命令直接抛 `SQLITE_WRITER_UNAVAILABLE`，不静默回落。新增命令必须同时在 `command-names.ts` 加常量并在 `commands.ts` 注册，主进程与写线程两边都要 import `commands.ts`。
5. **命令结果必须 structuredClone 安全**，否则写线程在 COMMIT 前回滚（`sqlite-writer-worker.ts:176`）；非持久副作用只能走 `afterCommit`。
6. **商店/回体/出售“事务外读余额、事务内写绝对值”并发双花**（`routes/api/shop.ts:346-684`，批量买 `:1051/:1077` 限购可绕）；`sell.ts:66-84,234`、`item.ts:56-104`、`equipment.ts:203` 重复 id 致奖励翻倍（审计 20261009 的 E1-E5；盒子 #30/#31 已修，kulo 本地不一定带）。
7. **`QUEST_FINISH_STRICT` 未设**（`lib/quest/finish/active-quest-resolver.ts:40-42`）：不调 /start 也能 /finish，`add_mana` 由客户端给。
8. **单人/多人 /finish 二次发奖**：响应缓存被挤掉或换写法后可重领（审计 E6/E7；盒子 #34 用 `player_operation_receipts` 回执堵住，`FINISH_RESPONSE_CACHE_TTL_MS` 下限 5000）。
9. **进程无 `unhandledRejection` 兜底**（kulo 全仓 grep 为 0；boxtree 有 `src/lib/process-guards.ts`）；`multi/tcp/server.ts` listen 后无常驻 error 监听（审计 N1/N7）。
10. **五重 LevelNext/Finalize 每包一个写事务**（`multi/five-boss/lobby-runtime.ts:94-133`，事务在 :106），无去重（审计 N5）。
11. **`multi/tcp/lobby.ts:36,342`** 房间解散不清 `autoStartingRooms`，复用房号可能永不自动开战（N4）；`tcp/handshake.ts:54-96` 未知 connection_id 跳过会话校验（N6）。
12. **`assets/cdndata/boss_coin_shop.json` 与服务端 `assets/boss_coin_shop.json` 不一致**（镜像缺 75 行自制 594xxxxxx，71 行价格不同）：客户端表缺行则 C8601；boss 币商店 `/buy` 不校验 availableFrom/Until（`shop.ts:363,403` 只管 EVENT_ITEM/TREASURE_EQUIPMENT）。
13. **服务器时间被钉死**（`active_account.json timeOffset`；盒子定 2025-07-29 起走）；改时钟要停服改文件。
14. **`src/multi/http/battle.ts` 是 CRLF**，其余 src 为 LF：整文件 merge/patch 会变一个大冲突；`rc=$?` 要紧跟 `git merge-file`。
15. **out/ 过期**：`out/` 被 .gitignore，改 src 不 tsc 就跑旧代码；盒子 4G 内存 tsc 会 OOM，须本机编好 out/ 再传；`single-finish-transaction.js` 在 bughunt repo/out 里曾被手改（hunches）。
16. **准入密钥在 SWF 里有两份**（含 HMAC 编译折叠副本），换 build key 必须全体替换；`config/client-admission.keys.json` 不得入库/外传。
17. **盒子敏感项**：`TEST_SERVER_SHARED_PASSWORD`、管理密码、准入密钥只存盒子 `.env` 和本机 `.wf-testserver`，勿写进聊天或仓库；管理后台无密码=锁死。
