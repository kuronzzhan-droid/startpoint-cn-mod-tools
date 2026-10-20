"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.settleSingleQuestFinishInTransaction = void 0;
const node_fs_1 = require("node:fs");
const node_path_1 = __importDefault(require("node:path"));
const file_exists_1 = require("../../file-exists");
const assets_1 = require("../../assets");
const character_1 = require("../../character");
const mail_1 = require("../../../data/domains/mail");
const item_1 = require("../../../data/domains/item");
const player_1 = require("../../../data/domains/player");
const quest_active_1 = require("../../../data/domains/quest_active");
const quest_1 = require("../../../data/domains/quest");
const practice_battle_history_1 = require("../../../data/domains/practice-battle-history");
const carnivalEvent_1 = require("../../../data/domains/carnivalEvent");
const abyss_records_1 = require("../../../data/domains/abyss-records");
const degree_1 = require("../../../data/domains/degree");
const rushEvent_1 = require("../../../data/domains/rushEvent");
const equipment_1 = require("../../../data/domains/equipment");
const mission_1 = require("../../mission");
const battle_facts_1 = require("../../mission/battle-facts");
const active_reconciliation_1 = require("../../mission/active-reconciliation");
const steam_robot_challenge_1 = require("../../mission/steam-robot-challenge");
const content_snapshot_1 = require("../../../content/runtime/content-snapshot");
const recommended_party_history_1 = require("../recommended-party-history");
const practice_battle_history_2 = require("../practice-battle-history");
const quest_2 = require("../../quest");
const rush_handler_1 = require("./rush-handler");
const rogue_drops_1 = require("./rogue-drops");
const raid_handler_1 = require("./raid-handler");
const carnival_handler_1 = require("./carnival-handler");
const carnival_reward_handler_1 = require("./carnival-reward-handler");
const challenge_point_1 = require("./challenge-point");
const score_attack_handler_1 = require("./score-attack-handler");
const service_1 = require("../../leaderboard/service");
const gauntlet_completion_classification_1 = require("../../gauntlet-completion-classification");
const unison_unlock_1 = require("../../validate/unison-unlock");
const rush_1 = require("../../rush");
const solo_rewards_1 = require("../../../multi/five-boss/solo-rewards");
const solo_runtime_1 = require("../../../multi/five-boss/solo-runtime");
const rush_event_folder_rounds_1 = require("../../rush-event-folder-rounds");
const stamina_1 = require("../../stamina");
const mode15_optional_1 = require("../../mode15-optional");
const utils_1 = require("../../../utils");
const single_settlement_diagnostics_1 = require("../../single-settlement-diagnostics");
const game_logging_1 = require("../../game-logging");
const settlement_performance_1 = require("../../settlement-performance");
const types_1 = require("../../types");
const event_challenge_point_map_json_1 = __importDefault(require("../../../../assets/event_challenge_point_map.json"));
// Load carnival quest score data. The settlement used to read this table from
// the route module; because it can now run in the SQLite writer thread, the
// command module owns the copy instead of shipping the table with every request.
let carnivalScoreLookup = {};
try {
    const scorePath = node_path_1.default.join(process.cwd(), "assets", "carnival_event_quest_scores.json");
    if ((0, file_exists_1.existsSync)(scorePath)) {
        carnivalScoreLookup = JSON.parse((0, node_fs_1.readFileSync)(scorePath, "utf-8"));
    }
}
catch (_a) { } // Init failed silently; carnival scoring won't work
/**
 * The single-battle finish transaction body.
 *
 * This function used to be an inline closure in the `/finish` handler. It runs
 * unchanged in-process when `CN_WRITER_THREAD` is off and inside the SQLite
 * writer thread when it is on, so it must not reference anything from the
 * request scope except the arguments above.
 */
function settleSingleQuestFinishInTransaction(args) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x, _y, _z;
    const { playerId, viewerId, questCategory, questId, questData, playerData, activeQuestData, body, clearTime, clearRank, questAccomplished, questProgress, fiveBossSoloQuest, registered, scoreAttackBorderTiers, beforeRankPoint, newRankPoint, manaObtained, newMana, newBoostPoint, newBossBoostPoint, useBoostPoint, displayMode15ManaAsFieldDrop, finishCacheKey, } = args;
    const questPreviouslyCompleted = questProgress !== null;
    const isScoreAttackEvent = questCategory === types_1.QuestCategory.SCORE_ATTACK_EVENT;
    const bodyTiming = (0, single_settlement_diagnostics_1.createSingleSettlementBodyTimingCollector)(questCategory, !!fiveBossSoloQuest);
    let bodySucceeded = false;
    try {
        (0, quest_active_1.deletePlayerActiveQuestSync)(playerId);
        const missionEvaluationTime = new Date((0, utils_1.getServerTime)() * 1000);
        let clearReward = null;
        let sPlusClearReward = null;
        const leaderId = (_a = body.statistics.party.characters[0]) === null || _a === void 0 ? void 0 : _a.id;
        if (questAccomplished) {
            (0, abyss_records_1.recordAbyssFloorFinishSync)({
                category: questCategory, questId, revision: activeQuestData.questTimeRevision,
                viewerId, elapsedTimeMs: clearTime, startedAtMs: activeQuestData.startedAtMs,
                nowMs: (0, utils_1.getServerTime)() * 1000, accomplished: true,
                registered,
                matchingPlay: body.play_id === activeQuestData.playId
                    && Number(body.quest_id) === questId && Number(body.category) === questCategory,
                isMulti: activeQuestData.isMulti,
            });
            // update quest progress
            if (questPreviouslyCompleted) {
                // simply update the quest progress if it already exists.
                const updateData = {
                    questId: questId,
                    finished: true,
                    bestElapsedTimeMs: questProgress.bestElapsedTimeMs === undefined || questProgress.bestElapsedTimeMs === null ? clearTime : Math.min(clearTime, questProgress.bestElapsedTimeMs),
                    highScore: questProgress.highScore === undefined ? body.score : Math.max(body.score, questProgress.highScore),
                    leaderCharacterId: leaderId !== null && leaderId !== void 0 ? leaderId : null
                };
                if (clearRank !== null) {
                    updateData.clearRank = questProgress.clearRank === undefined ? clearRank : Math.max(clearRank, questProgress.clearRank);
                }
                (0, quest_1.updatePlayerQuestProgressSync)(playerId, questCategory, updateData);
            }
            else {
                // insert if it doesn't already exist.
                const insertData = {
                    questId: questId,
                    finished: true,
                    bestElapsedTimeMs: clearTime,
                    highScore: body.score,
                    clearRank: clearRank !== null && clearRank !== void 0 ? clearRank : 5,
                    leaderCharacterId: leaderId !== null && leaderId !== void 0 ? leaderId : null
                };
                (0, quest_1.insertPlayerQuestProgressSync)(playerId, questCategory, insertData);
            }
            // Legacy saves may be missing the 1-6-1 story completion row even
            // though a later main quest was cleared. Repair it immediately so
            // unison becomes available without requiring another login.
            if (questCategory === types_1.QuestCategory.MAIN && questId >= 1006001) {
                (0, unison_unlock_1.repairUnisonUnlockProgressSync)(playerId);
            }
            if (questCategory === types_1.QuestCategory.SOLO_TIME_ATTACK_EVENT) {
                const newDegreeIds = (0, degree_1.grantPlayerSoloTimeAttackDegreesSync)(playerId, questId, clearTime);
                if (newDegreeIds.length > 0) {
                    console.log(`[DEGREE] solo time attack granted: player=${playerId} quest=${questId} elapsed=${clearTime} degrees=${newDegreeIds.join(",")}`);
                }
            }
        }
        // update player
        const oldRkDegree = (0, stamina_1.getRankDegree)(beforeRankPoint);
        const newDegreeId = (0, stamina_1.getRankDegree)(newRankPoint);
        const didLevelUp = newDegreeId > oldRkDegree;
        (0, player_1.updatePlayerSync)(Object.assign({ id: playerId, freeMana: newMana, rankPoint: newRankPoint, boostPoint: newBoostPoint, bossBoostPoint: newBossBoostPoint, totalManaObtained: ((_b = playerData.totalManaObtained) !== null && _b !== void 0 ? _b : 0) + manaObtained, maxComboAchieved: Math.max((_c = playerData.maxComboAchieved) !== null && _c !== void 0 ? _c : 0, (_e = (_d = body.statistics) === null || _d === void 0 ? void 0 : _d.max_combo_count) !== null && _e !== void 0 ? _e : 0) }, (didLevelUp ? { stamina: playerData.stamina + (0, stamina_1.getMaxStamina)(newDegreeId), staminaHealTime: new Date() } : {})));
        if ((0, player_1.adjustPlayerExpPoolSync)(playerId, questData.poolExpReward, 'single_battle_base_reward') === null) {
            throw new Error(`Failed to grant single battle EXP to player ${playerId}`);
        }
        clearReward = !isScoreAttackEvent && !questPreviouslyCompleted && questData.clearReward !== undefined
            ? (0, quest_2.givePlayerRewardSync)(playerId, questData.clearReward)
            : null;
        const isExpertSingleEvent = questCategory === types_1.QuestCategory.EXPERT_SINGLE_EVENT;
        const shouldGrantSPlusReward = isExpertSingleEvent
            ? (questProgress === null || questProgress === void 0 ? void 0 : questProgress.sPlusRewardReceived) !== true
            : (questProgress === null || questProgress === void 0 ? void 0 : questProgress.clearRank) !== 5;
        sPlusClearReward = !isScoreAttackEvent && (clearRank === 5)
            && shouldGrantSPlusReward && (questData.sPlusReward !== undefined)
            ? (0, quest_2.givePlayerRewardSync)(playerId, questData.sPlusReward)
            : null;
        if (isExpertSingleEvent && sPlusClearReward !== null) {
            (0, quest_1.updatePlayerQuestProgressSync)(playerId, questCategory, {
                questId,
                sPlusRewardReceived: true,
            });
            console.log(`[EXPERT_SINGLE_EVENT] SS reward granted: player=${playerId} quest=${questId} item=14040 count=3`);
        }
        if (didLevelUp) {
            playerData.stamina = playerData.stamina + (0, stamina_1.getMaxStamina)(newDegreeId);
            playerData.staminaHealTime = new Date();
            console.log(`[BATTLE-FINISH] player ${playerId} leveled up: ${oldRkDegree} -> ${newDegreeId}, stamina refilled`);
        }
        // Consume daily challenge point
        const dailyChallengePointList = (0, challenge_point_1.handleDailyChallengePoint)({
            questCategory,
            eventId: questData.eventId,
            playerId,
            challengePointMap: event_challenge_point_map_json_1.default,
            getEntries: (pid) => (0, player_1.getPlayerDailyChallengePointListSync)(pid),
            updatePoint: (pid, id, pt) => (0, player_1.updatePlayerDailyChallengePointSync)(pid, id, pt),
        });
        // 五重单人使用独立奖励计划，不再叠加 1099001 的旧 score reward 组
        // （其中包含猫头鹰货币及其稀有池）。多人专用结算也不走这条普通奖励链。
        const effectiveScoreRewardGroupId = fiveBossSoloQuest
            ? undefined
            : questData.scoreRewardGroupId;
        const effectiveScoreRewardGroup = fiveBossSoloQuest
            ? undefined
            : questData.scoreRewardGroup;
        // reward score rewards
        if (isScoreAttackEvent) {
            (0, game_logging_1.gameVerboseLog)(() => `[SCORE_ATTACK] questId=${questId} body={score:${body.score}, elapsed:${body.elapsed_time_ms}, accomplished:${body.is_accomplished}, addMana:${body.add_mana}, continue:${body.continue_count}}`);
            (0, game_logging_1.gameVerboseLog)(() => `[SCORE_ATTACK] questData={localQuest:${questData.scoreAttackQuestId}, bRank:${questData.bRankScore}, aRank:${questData.aRankScore}, sRank:${questData.sRankScore}, ssRank:${questData.ssRankScore}, rankPt:${questData.rankPointReward}, charExp:${questData.characterExpReward}, mana:${questData.manaReward}, poolExp:${questData.poolExpReward}}`);
        }
        (0, game_logging_1.gameVerboseLog)(() => { var _a; return `[BATTLE] scoreReward groupId=${effectiveScoreRewardGroupId !== null && effectiveScoreRewardGroupId !== void 0 ? effectiveScoreRewardGroupId : (fiveBossSoloQuest ? 'skipped-five-boss-solo' : 'null')} groupLen=${(_a = effectiveScoreRewardGroup === null || effectiveScoreRewardGroup === void 0 ? void 0 : effectiveScoreRewardGroup.length) !== null && _a !== void 0 ? _a : 'null'} questId=${questId} category=${questCategory}`; });
        const scoreRewardsResult = (0, quest_2.givePlayerScoreRewardsSync)(playerId, effectiveScoreRewardGroupId, effectiveScoreRewardGroup, useBoostPoint, questData.element, { questId, mode: "solo" });
        let scoreAttackEventData = null;
        if (isScoreAttackEvent) {
            const previousHighScore = (_f = questProgress === null || questProgress === void 0 ? void 0 : questProgress.highScore) !== null && _f !== void 0 ? _f : 0;
            const mainCharacterIds = (0, score_attack_handler_1.collectScoreAttackMainCharacterIds)(body.statistics.party.characters);
            const resolved = (0, score_attack_handler_1.resolveNewScoreAttackBorderRewards)(scoreAttackBorderTiers, previousHighScore, body.score);
            for (const [itemIdText, count] of Object.entries(resolved.itemCounts)) {
                scoreRewardsResult.items[itemIdText] = (0, item_1.givePlayerItemSync)(playerId, Number(itemIdText), count);
            }
            scoreAttackEventData = {
                reward_ids: resolved.rewardIds,
                main_character_ids: mainCharacterIds,
            };
            (0, game_logging_1.gameVerboseLog)(() => `[SCORE_ATTACK] borderRewards: event=${questData.eventId} folder=${questData.folderId} oldScore=${previousHighScore} newScore=${body.score} crossed=${resolved.rewardIds.length} items=${JSON.stringify(resolved.itemCounts)}`);
            (0, game_logging_1.gameVerboseLog)(() => { var _a, _b; return `[SCORE_ATTACK] afterReward: dropIds=${JSON.stringify(scoreRewardsResult.drop_score_reward_ids)}, drops=${scoreRewardsResult.drop_score_reward_ids.length}, items=${JSON.stringify(scoreRewardsResult.items)}, equipList=${(_b = (_a = scoreRewardsResult.equipment_list) === null || _a === void 0 ? void 0 : _a.length) !== null && _b !== void 0 ? _b : 0}`; });
            (0, game_logging_1.gameVerboseLog)(() => `[SCORE_ATTACK] response: accomplished=${questAccomplished}, clearRank=${clearRank}, score=${body.score}, elapsed=${body.elapsed_time_ms}, items=${JSON.stringify(scoreRewardsResult.items)}, clientCategory=${questCategory}`);
        }
        // reward character exp
        bodyTiming.step("battle_facts");
        const bodyPartyStatistics = body.statistics.party;
        const partyCharacterIds = [...bodyPartyStatistics.characters, ...bodyPartyStatistics.unison_characters];
        if (questCategory === types_1.QuestCategory.PRACTICE) {
            (0, practice_battle_history_1.insertPlayerPracticeBattleHistorySync)((0, practice_battle_history_2.buildPracticeBattleHistoryRecord)({
                playerId,
                playId: activeQuestData.playId,
                categoryId: questCategory,
                questId,
                finishKind: questAccomplished ? 0 : 1,
                createdAt: new Date(),
                elapsedTimeMs: clearTime,
                score: body.score,
                clearRank: questAccomplished ? clearRank : null,
                party: bodyPartyStatistics,
                statistics: body.statistics,
                equipmentList: (0, equipment_1.getPlayerEquipmentListSync)(playerId),
            }));
        }
        // Build finish context for mission trackers
        const finishCtx = {
            playerId, questCategory, questId,
            questAccomplished,
            clearTime: body.elapsed_time_ms,
            clearRank,
            party: body.statistics.party,
            statistics: body.statistics,
            player: playerData,
            questPreviouslyCompleted,
            questProgress,
            partySlot: (_g = activeQuestData.partySlot) !== null && _g !== void 0 ? _g : playerData.partySlot,
        };
        // Mission progress is recorded once by recordMissionBattleFacts below.
        const singleBattleParty = (0, mission_1.collectPartyCharacterIds)(finishCtx.party);
        (0, mission_1.recordBattleMissionDimensionsSafe)(Object.assign(Object.assign({ type: "battle_finish", playerId,
            questCategory,
            questId, accomplished: questAccomplished, mode: "single", clearRank, clearTimeMs: clearTime, score: Number(body.score) || 0 }, singleBattleParty), { statistics: (0, mission_1.summarizeBattleStatistics)(finishCtx.statistics) }));
        const missionBattleFacts = (0, battle_facts_1.recordMissionBattleFacts)(finishCtx, missionEvaluationTime);
        if (questData.fixedParty === undefined) {
            (0, recommended_party_history_1.recordQuestRecommendedPartySafe)(finishCtx);
        }
        const steamRobotMissionId = (0, steam_robot_challenge_1.trackSteamRobotChallengeMission)({
            playerId,
            questCategory,
            questId,
            questAccomplished,
            clearRank,
            statistics: finishCtx.statistics,
        });
        if (steamRobotMissionId !== null) {
            console.log(`[MISSION] steam robot challenge cleared: player=${playerId} quest=${questId} mission=${steamRobotMissionId}`);
        }
        const partyCharacterIdsArray = [];
        bodyTiming.step("experience");
        for (const value of partyCharacterIds.values()) {
            if (value !== null && value.id !== null)
                partyCharacterIdsArray.push(value.id);
        }
        const addExpAmount = questData.characterExpReward;
        const rewardCharacterExpResult = (0, character_1.givePlayerCharactersExpSync)(playerId, partyCharacterIdsArray, addExpAmount, questData.fixedParty !== undefined);
        bodyTiming.step("mode_rewards");
        const dataHeaders = (0, utils_1.generateDataHeaders)({
            viewer_id: viewerId
        });
        // At the three solo-to-multiplayer boundaries, do not expose the
        // just-written Rush round in *this* generic quest-result response.
        // The legacy client uses that response to decide whether to draw
        // "Continue challenge"; exposing it would make the 5/10/15
        // placeholder open as a normal single-player Rush quest.
        //
        // The real marker is still persisted by the handler.  Pressing OK
        // returns to the Rush page, whose subsequent summary load receives
        // the real marker and correctly exposes the multiplayer Boss.
        const mode15BoundaryStage = Number(questId) % 1000;
        const withholdMode15BoundaryAdvance = questAccomplished
            && questCategory === types_1.QuestCategory.RUSH_EVENT
            && questData.rushEventId === mode15_optional_1.MODE15_RUSH_EVENT_ID
            && (mode15BoundaryStage === 4
                || mode15BoundaryStage === 9
                || mode15BoundaryStage === 14);
        const rushPartiesBeforeBoundaryAdvance = withholdMode15BoundaryAdvance
            ? (0, rush_1.getSerializedPlayerRushEventPlayedPartiesSync)(playerId, mode15_optional_1.MODE15_RUSH_EVENT_ID)
            : null;
        // handle event quest-specific data & rewards
        const { rushEventData, rushEventRewardsResult } = (0, rush_handler_1.handleRushEventFinish)({
            questCategory,
            questAccomplished,
            questData,
            clearTime,
            party: bodyPartyStatistics,
            playerId,
            questId,
            getEvoLevels: (pid, chars) => (0, character_1.getCharactersEvolutionImgLevels)(pid, chars),
            getFolderMaxRounds: rush_event_folder_rounds_1.getRushEventFolderMaxRounds,
            getRushEvent: (pid, eid) => (0, rushEvent_1.getPlayerRushEventSync)(pid, eid),
            updateRushEvent: (pid, data) => (0, rushEvent_1.updatePlayerRushEventSync)(pid, data),
            // Never save a content-less marker. The legacy result/quest UI
            // dereferences the first character of every recorded party; a row
            // made entirely of NULL values becomes character id 0 and crashes
            // immediately after boundary floors such as stage 5.
            insertParty: (pid, eid, p) => (0, rushEvent_1.insertPlayerRushEventPlayedPartySync)(pid, eid, p),
            insertClearedFolder: (pid, eid, fid) => (0, rushEvent_1.insertPlayerRushEventClearedFolderSync)(pid, eid, fid),
            deletePartyList: (pid, eid, bt) => (0, rushEvent_1.deletePlayerRushEventPlayedPartyListSync)(pid, eid, bt),
            getSerializedParties: (pid, eid) => (0, rush_1.getSerializedPlayerRushEventPlayedPartiesSync)(pid, eid),
            getFolderRewards: (eid, fid) => (0, assets_1.getRushEventFolderClearRewards)(eid, fid),
            giveRewards: (pid, r) => (0, quest_2.givePlayerRewardsSync)(pid, r),
        });
        const abyssEnduranceDegrees = (0, service_1.finishLeaderboardQuestSync)({
            playerId,
            quest: {
                category: questCategory,
                eventId: questData.rushEventId,
                folderId: questData.rushEventFolderId,
                round: questData.rushEventRound,
                questId,
                totalRounds: questData.rushEventId === undefined
                    || questData.rushEventFolderId === undefined
                    ? 0
                    : (0, rush_event_folder_rounds_1.getRushEventFolderMaxRounds)(questData.rushEventId, questData.rushEventFolderId),
            },
            accomplished: questAccomplished,
            clientBattleMs: clearTime,
            party: {
                characterIds: bodyPartyStatistics.characters.map(value => { var _a; return (_a = value === null || value === void 0 ? void 0 : value.id) !== null && _a !== void 0 ? _a : null; }),
                unisonCharacterIds: bodyPartyStatistics.unison_characters.map(value => { var _a; return (_a = value === null || value === void 0 ? void 0 : value.id) !== null && _a !== void 0 ? _a : null; }),
                equipmentIds: bodyPartyStatistics.equipments.map(value => { var _a; return (_a = value === null || value === void 0 ? void 0 : value.id) !== null && _a !== void 0 ? _a : null; }),
                abilitySoulIds: bodyPartyStatistics.ability_soul_ids,
                evolutionImgLevels: (0, character_1.getCharactersEvolutionImgLevels)(playerId, bodyPartyStatistics.characters.map(value => { var _a; return (_a = value === null || value === void 0 ? void 0 : value.id) !== null && _a !== void 0 ? _a : null; })),
                unisonEvolutionImgLevels: (0, character_1.getCharactersEvolutionImgLevels)(playerId, bodyPartyStatistics.unison_characters.map(value => { var _a; return (_a = value === null || value === void 0 ? void 0 : value.id) !== null && _a !== void 0 ? _a : null; })),
            },
        });
        if (questAccomplished
            && questCategory === types_1.QuestCategory.RUSH_EVENT
            && questData.rushEventId !== undefined
            && (0, gauntlet_completion_classification_1.repairGauntletCompletionClassificationSync)(playerId, questData.rushEventId)) {
            console.log(`[RUSH] completed classification repaired: `
                + `player=${playerId} event=${questData.rushEventId}`);
        }
        if (rushEventData !== null && rushPartiesBeforeBoundaryAdvance !== null) {
            rushEventData.rush_battle_played_party_list = rushPartiesBeforeBoundaryAdvance.folderParties;
            rushEventData.endless_battle_played_party_list = rushPartiesBeforeBoundaryAdvance.endlessParties;
            console.log(`[MODE15] deferred Rush result visibility: player=${playerId} stage=${mode15BoundaryStage}`);
        }
        const rogueFolderMaxRounds = {};
        if (questData.rushEventId !== undefined
            && questData.rushEventFolderId !== undefined) {
            rogueFolderMaxRounds[questData.rushEventFolderId] =
                (0, rush_event_folder_rounds_1.getRushEventFolderMaxRounds)(questData.rushEventId, questData.rushEventFolderId);
        }
        const rogueDrops = (0, rogue_drops_1.handleRoguePerRoundDrops)({
            questCategory,
            questAccomplished,
            playerId,
            questData,
            folderMaxRounds: rogueFolderMaxRounds,
            partyCharacterIds: partyCharacterIdsArray,
        });
        if (rogueDrops !== null
            && rushEventData !== null
            && rogueDrops.showInRewardList) {
            rushEventData.rush_battle_reward_list = [
                ...rushEventData.rush_battle_reward_list,
                ...rogueDrops.rewardListEntries,
            ];
        }
        // Record played party for RAID_EVENT
        const raidEventData = (0, raid_handler_1.handleRaidEventFinish)({
            questCategory,
            questAccomplished,
            activeEventId: activeQuestData.eventId,
            playId: activeQuestData.playId,
            party: bodyPartyStatistics,
            playerId,
            questId,
            getEvoLevelsFn: (pid, chars) => (0, character_1.getCharactersEvolutionImgLevels)(pid, chars),
            insertPartyFn: (pid, eid, p) => (0, rushEvent_1.insertPlayerRushEventPlayedPartySync)(pid, eid, p),
        });
        // handle carnival event score & records
        const carnivalInfo = carnivalScoreLookup[String(questId)];
        if (carnivalInfo)
            (0, carnivalEvent_1.migrateCarnivalEventFolderRecordsSync)(carnivalInfo.event_id);
        const carnivalEventData = (0, carnival_handler_1.handleCarnivalEventFinish)({
            questCategory,
            questAccomplished,
            questId,
            battleScore: body.score,
            clearTime,
            party: bodyPartyStatistics,
            playerId,
            carnivalLookup: carnivalScoreLookup,
            getRecordsFn: (pid, eid) => (0, carnivalEvent_1.getPlayerCarnivalEventRecordsSync)(pid, eid),
            upsertFn: (pid, eid, fid, score, chars, unisons) => (0, carnivalEvent_1.upsertPlayerCarnivalEventRecordSync)(pid, eid, fid, score, chars, unisons),
        });
        let carnivalRewardsResult = null;
        if (carnivalEventData && carnivalInfo) {
            const totalBestScore = (0, carnivalEvent_1.getPlayerCarnivalEventRecordsSync)(playerId, carnivalInfo.event_id)
                .reduce((sum, record) => { var _a; return sum + ((_a = record.bestScore) !== null && _a !== void 0 ? _a : 0); }, 0);
            const granted = (0, carnival_reward_handler_1.grantCarnivalTotalScoreRewardsSync)(playerId, carnivalInfo.event_id, totalBestScore);
            carnivalEventData.reward_ids = granted.rewardIds;
            carnivalEventData.new_degree_ids = granted.newDegreeIds;
            carnivalRewardsResult = granted.rewards;
        }
        const mode15RewardsResult = (0, mode15_optional_1.settleMode15BattleSync)(playerId, questCategory, questId, questAccomplished);
        const fiveBossSolo = fiveBossSoloQuest && questAccomplished
            ? (0, solo_rewards_1.grantFiveBossSoloRewardsSync)({ playerId, firstClear: !(questProgress === null || questProgress === void 0 ? void 0 : questProgress.finished),
                rewardMultiplier: (0, solo_runtime_1.getFiveBossSoloRewardMultiplierSync)(playerId, activeQuestData.playId) }) : null;
        const itemList = Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, ((_h = fiveBossSolo === null || fiveBossSolo === void 0 ? void 0 : fiveBossSolo.items) !== null && _h !== void 0 ? _h : {})), (activeQuestData.entryItemId ? { [activeQuestData.entryItemId]: (_j = (0, item_1.getPlayerItemSync)(playerId, activeQuestData.entryItemId)) !== null && _j !== void 0 ? _j : 0 } : {})), ((_k = clearReward === null || clearReward === void 0 ? void 0 : clearReward.items) !== null && _k !== void 0 ? _k : {})), ((_l = sPlusClearReward === null || sPlusClearReward === void 0 ? void 0 : sPlusClearReward.items) !== null && _l !== void 0 ? _l : {})), scoreRewardsResult.items), ((_m = rushEventRewardsResult === null || rushEventRewardsResult === void 0 ? void 0 : rushEventRewardsResult.items) !== null && _m !== void 0 ? _m : {})), ((_o = rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.rewardResult.items) !== null && _o !== void 0 ? _o : {})), ((_p = carnivalRewardsResult === null || carnivalRewardsResult === void 0 ? void 0 : carnivalRewardsResult.items) !== null && _p !== void 0 ? _p : {})), ((_q = mode15RewardsResult === null || mode15RewardsResult === void 0 ? void 0 : mode15RewardsResult.items) !== null && _q !== void 0 ? _q : {}));
        const characterList = [
            ...rewardCharacterExpResult.character_list,
            ...((clearReward === null || clearReward === void 0 ? void 0 : clearReward.character_list) || []),
            ...((sPlusClearReward === null || sPlusClearReward === void 0 ? void 0 : sPlusClearReward.character_list) || []),
            ...scoreRewardsResult.character_list,
            ...((rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.rewardResult.character_list) || []),
            ...((rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.expCharacterList) || []),
            ...((carnivalRewardsResult === null || carnivalRewardsResult === void 0 ? void 0 : carnivalRewardsResult.character_list) || []),
            ...((mode15RewardsResult === null || mode15RewardsResult === void 0 ? void 0 : mode15RewardsResult.character_list) || []),
        ];
        bodyTiming.step("missions");
        const missionSettlement = (0, settlement_performance_1.measureSettlementPhase)("single", "mission", () => ((0, mission_1.settleMissionCategories)(playerId, (0, battle_facts_1.buildBattleMissionSettlementScopes)(missionBattleFacts, Object.keys(itemList).map(Number), steamRobotMissionId === null ? [] : [steamRobotMissionId], partyCharacterIdsArray), missionEvaluationTime)));
        bodyTiming.step("awake");
        const awakeMissionSettlement = (0, settlement_performance_1.measureSettlementPhase)("single", "awake_mission", () => ((0, mission_1.settleAwakeMissionCandidates)(playerId, questAccomplished
            ? (0, mission_1.getAwakeBattleMissionIds)(partyCharacterIdsArray, missionBattleFacts.awakeMissionIds)
            : [], missionEvaluationTime)));
        bodyTiming.step("active");
        const activeMissionSettlement = (0, settlement_performance_1.measureSettlementPhase)("single", "active_mission", () => ((0, active_reconciliation_1.reconcileActiveMissionFacts)({
            playerId,
            repository: (0, content_snapshot_1.getContentSnapshot)().repository,
            now: missionEvaluationTime,
            patterns: (0, battle_facts_1.getBattleActiveMissionPatterns)(questCategory),
        })));
        bodyTiming.step("response");
        const finalPlayerData = (0, player_1.getPlayerSync)(playerId);
        const responseData = {
            "user_info": {
                "free_mana": (_r = finalPlayerData === null || finalPlayerData === void 0 ? void 0 : finalPlayerData.freeMana) !== null && _r !== void 0 ? _r : newMana,
                "exp_pool": (_s = finalPlayerData === null || finalPlayerData === void 0 ? void 0 : finalPlayerData.expPool) !== null && _s !== void 0 ? _s : rewardCharacterExpResult.exp_pool,
                "exp_pooled_time": (0, utils_1.getServerTime)(playerData.expPooledTime),
                "free_vmoney": (_t = finalPlayerData === null || finalPlayerData === void 0 ? void 0 : finalPlayerData.freeVmoney) !== null && _t !== void 0 ? _t : playerData.freeVmoney,
                "rank_point": newRankPoint,
                "degree_id": (_u = playerData.degreeId) !== null && _u !== void 0 ? _u : 1,
                "stamina": playerData.stamina,
                "stamina_heal_time": (0, utils_1.realToVirtual)(playerData.staminaHealTime),
                "boost_point": newBoostPoint,
                "boss_boost_point": newBossBoostPoint
            },
            "add_exp_list": [
                ...rewardCharacterExpResult.add_exp_list,
                ...((rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.addExpList) || []),
            ],
            "character_list": characterList,
            "bond_token_status_list": Object.assign(Object.assign({}, rewardCharacterExpResult.bond_token_status_list), ((rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.bondTokenStatusList) || {})),
            "rewards": {
                "overflow_pool_exp": 0,
                "converted_pool_exp": 0,
                "reward_pool_exp": questData.poolExpReward,
                // Rush result panels do not render reward_mana in the
                // acquired-item area.  Mode15 presents the same credited
                // amount through the native field-mana slot so the Mana
                // icon and quantity are visible; user_info.free_mana
                // remains authoritative and the award is not duplicated.
                "reward_mana": displayMode15ManaAsFieldDrop ? 0 : questData.manaReward,
                "field_mana": body.add_mana
                    + (displayMode15ManaAsFieldDrop ? questData.manaReward : 0)
            },
            "old_high_score": questProgress === null ? 0 : questProgress.highScore || 0,
            "joined_character_id_list": [
                ...((clearReward === null || clearReward === void 0 ? void 0 : clearReward.joined_character_id_list) || []),
                ...((sPlusClearReward === null || sPlusClearReward === void 0 ? void 0 : sPlusClearReward.joined_character_id_list) || []),
                ...scoreRewardsResult.joined_character_id_list,
                ...((carnivalRewardsResult === null || carnivalRewardsResult === void 0 ? void 0 : carnivalRewardsResult.joined_character_id_list) || []),
                ...((mode15RewardsResult === null || mode15RewardsResult === void 0 ? void 0 : mode15RewardsResult.joined_character_id_list) || [])
            ],
            "before_rank_point": beforeRankPoint,
            "clear_rank": clearRank !== null && clearRank !== void 0 ? clearRank : 5,
            "drop_score_reward_ids": scoreRewardsResult.drop_score_reward_ids,
            "drop_rare_reward_ids": scoreRewardsResult.drop_rare_reward_ids,
            "drop_additional_reward_ids": [
                ...((_v = fiveBossSolo === null || fiveBossSolo === void 0 ? void 0 : fiveBossSolo.dropAdditionalRewardIds) !== null && _v !== void 0 ? _v : []),
                ...((_w = rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.additionalRewardEntries) !== null && _w !== void 0 ? _w : []),
                ...((_x = mode15RewardsResult === null || mode15RewardsResult === void 0 ? void 0 : mode15RewardsResult.mode15_additional_reward_ids) !== null && _x !== void 0 ? _x : []),
            ],
            "drop_periodic_reward_ids": [],
            "equipment_list": [
                ...scoreRewardsResult.equipment_list,
                ...((clearReward === null || clearReward === void 0 ? void 0 : clearReward.equipment_list) || []),
                ...((sPlusClearReward === null || sPlusClearReward === void 0 ? void 0 : sPlusClearReward.equipment_list) || []),
                ...((rushEventRewardsResult === null || rushEventRewardsResult === void 0 ? void 0 : rushEventRewardsResult.equipment_list) || []),
                ...((rogueDrops === null || rogueDrops === void 0 ? void 0 : rogueDrops.rewardResult.equipment_list) || []),
                ...((carnivalRewardsResult === null || carnivalRewardsResult === void 0 ? void 0 : carnivalRewardsResult.equipment_list) || []),
                ...((mode15RewardsResult === null || mode15RewardsResult === void 0 ? void 0 : mode15RewardsResult.equipment_list) || []),
                ...((_y = fiveBossSolo === null || fiveBossSolo === void 0 ? void 0 : fiveBossSolo.equipment_list) !== null && _y !== void 0 ? _y : [])
            ],
            "category_id": body.category,
            "start_time": dataHeaders['servertime'],
            "is_multi": "single",
            "quest_name": "",
            "item_list": itemList,
            "rush_event": rushEventData,
            "raid_event": raidEventData,
            "carnival_event": carnivalEventData,
            "score_attack_event": scoreAttackEventData,
            "user_daily_challenge_point_list": dailyChallengePointList !== null && dailyChallengePointList !== void 0 ? dailyChallengePointList : [],
            "presigned_quest_category": []
        };
        if (raidEventData === null || raidEventData === void 0 ? void 0 : raidEventData.new_degree_ids.length) {
            responseData.degree_list = raidEventData.new_degree_ids.map(degreeId => ({
                viewer_id: viewerId,
                degree_id: degreeId,
            }));
        }
        if (abyssEnduranceDegrees.length) {
            responseData.degree_list = [
                ...((_z = responseData.degree_list) !== null && _z !== void 0 ? _z : []),
                ...abyssEnduranceDegrees.map(degreeId => ({ viewer_id: viewerId, degree_id: degreeId })),
            ];
        }
        (0, mission_1.mergeMissionSettlementResponse)(responseData, missionSettlement, viewerId);
        // Awake settlement re-publishes completed special unlocks itself,
        // including already-persisted rows whose earlier response was lost.
        (0, mission_1.mergeMissionSettlementResponse)(responseData, awakeMissionSettlement, viewerId);
        if (activeMissionSettlement.length > 0) {
            responseData.active_mission_list = activeMissionSettlement;
        }
        responseData.mail_arrived = (0, mail_1.getPlayerMailCountSync)(playerId, true) > 0;
        const response = { data_headers: dataHeaders, data: responseData };
        if (fiveBossSoloQuest)
            (0, solo_runtime_1.saveFiveBossSoloReceiptSync)(playerId, activeQuestData.playId, finishCacheKey, response);
        bodySucceeded = true;
        return { response, timing: bodyTiming.result(true) };
    }
    finally {
        // A rolled-back body has no caller to report to; drop its sample.
        if (!bodySucceeded)
            bodyTiming.result(false);
    }
}
exports.settleSingleQuestFinishInTransaction = settleSingleQuestFinishInTransaction;
