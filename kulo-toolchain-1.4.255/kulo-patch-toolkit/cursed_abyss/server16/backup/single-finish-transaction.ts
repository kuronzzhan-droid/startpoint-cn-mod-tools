import { readFileSync } from "node:fs"
import path from "node:path"
import { existsSync } from "../../file-exists"
import { getRushEventFolderClearRewards } from "../../assets"
import { getCharactersEvolutionImgLevels, givePlayerCharactersExpSync } from "../../character"
import { getPlayerMailCountSync } from "../../../data/domains/mail"
import { givePlayerItemSync, getPlayerItemSync } from "../../../data/domains/item"
import {
    adjustPlayerExpPoolSync,
    getPlayerDailyChallengePointListSync,
    getPlayerSync,
    updatePlayerDailyChallengePointSync,
    updatePlayerSync,
} from "../../../data/domains/player"
import { deletePlayerActiveQuestSync } from "../../../data/domains/quest_active"
import { insertPlayerQuestProgressSync, updatePlayerQuestProgressSync } from "../../../data/domains/quest"
import { insertPlayerPracticeBattleHistorySync } from "../../../data/domains/practice-battle-history"
import {
    getPlayerCarnivalEventRecordsSync,
    migrateCarnivalEventFolderRecordsSync,
    upsertPlayerCarnivalEventRecordSync,
} from "../../../data/domains/carnivalEvent"
import { recordAbyssFloorFinishSync } from "../../../data/domains/abyss-records"
import { grantPlayerSoloTimeAttackDegreesSync } from "../../../data/domains/degree"
import {
    deletePlayerRushEventPlayedPartyListSync,
    getPlayerRushEventSync,
    insertPlayerRushEventClearedFolderSync,
    insertPlayerRushEventPlayedPartySync,
    updatePlayerRushEventSync,
} from "../../../data/domains/rushEvent"
import { getPlayerEquipmentListSync } from "../../../data/domains/equipment"
import {
    collectPartyCharacterIds,
    getAwakeBattleMissionIds,
    mergeMissionSettlementResponse,
    recordBattleMissionDimensionsSafe,
    settleAwakeMissionCandidates,
    settleMissionCategories,
    summarizeBattleStatistics,
} from "../../mission"
import {
    buildBattleMissionSettlementScopes,
    getBattleActiveMissionPatterns,
    recordMissionBattleFacts,
} from "../../mission/battle-facts"
import { reconcileActiveMissionFacts } from "../../mission/active-reconciliation"
import { trackSteamRobotChallengeMission } from "../../mission/steam-robot-challenge"
import { getContentSnapshot } from "../../../content/runtime/content-snapshot"
import { recordQuestRecommendedPartySafe } from "../recommended-party-history"
import { buildPracticeBattleHistoryRecord } from "../practice-battle-history"
import { givePlayerRewardSync, givePlayerRewardsSync, givePlayerScoreRewardsSync } from "../../quest"
import { handleRushEventFinish } from "./rush-handler"
import { handleRoguePerRoundDrops } from "./rogue-drops"
import { handleRaidEventFinish } from "./raid-handler"
import { handleCarnivalEventFinish } from "./carnival-handler"
import { grantCarnivalTotalScoreRewardsSync } from "./carnival-reward-handler"
import { handleDailyChallengePoint } from "./challenge-point"
import {
    collectScoreAttackMainCharacterIds,
    resolveNewScoreAttackBorderRewards,
    ScoreAttackBorderTier,
} from "./score-attack-handler"
import { finishLeaderboardQuestSync } from "../../leaderboard/service"
import { repairGauntletCompletionClassificationSync } from "../../gauntlet-completion-classification"
import { repairUnisonUnlockProgressSync } from "../../validate/unison-unlock"
import { getSerializedPlayerRushEventPlayedPartiesSync } from "../../rush"
import { grantFiveBossSoloRewardsSync } from "../../../multi/five-boss/solo-rewards"
import { getFiveBossSoloRewardMultiplierSync, saveFiveBossSoloReceiptSync } from "../../../multi/five-boss/solo-runtime"
import { getRushEventFolderMaxRounds } from "../../rush-event-folder-rounds"
import { getMaxStamina, getRankDegree } from "../../stamina"
import { MODE15_RUSH_EVENT_ID, settleMode15BattleSync } from "../../mode15-optional"
import { generateDataHeaders, getServerTime, realToVirtual } from "../../../utils"
import {
    createSingleSettlementBodyTimingCollector,
    type SingleSettlementBodyTiming,
} from "../../single-settlement-diagnostics"
import { gameVerboseLog } from "../../game-logging"
import { measureSettlementPhase } from "../../settlement-performance"
import { QuestCategory } from "../../types"
import type { BattleQuest, PlayerRewardResult } from "../../types"
import type { Player, PlayerQuestProgress } from "../../../data/types"
import type { ActiveQuest, FinishBody } from "../../../routes/api/singleBattleQuest"
import type { FinishContext } from "./types"
import eventChallengePointMap from "../../../../assets/event_challenge_point_map.json"

// Load carnival quest score data. The settlement used to read this table from
// the route module; because it can now run in the SQLite writer thread, the
// command module owns the copy instead of shipping the table with every request.
let carnivalScoreLookup: Record<string, { difficulty_score: number, time_limit_ms: number, folder_id: number, event_id: number }> = {}
try {
    const scorePath = path.join(process.cwd(), "assets", "carnival_event_quest_scores.json")
    if (existsSync(scorePath)) {
        carnivalScoreLookup = JSON.parse(readFileSync(scorePath, "utf-8"))
    }
} catch {} // Init failed silently; carnival scoring won't work

/**
 * Everything the single-battle finish transaction needs from the request
 * preparation phase. Every field is plain data: database rows, master data,
 * request body and derived numbers, so the whole argument object is safe to
 * structured-clone across the writer thread boundary.
 */
export interface SingleFinishTransactionArgs {
    playerId: number
    viewerId: number
    questCategory: QuestCategory
    questId: number
    questData: BattleQuest
    playerData: Player
    activeQuestData: ActiveQuest
    body: FinishBody
    clearTime: number
    clearRank: number | null
    questAccomplished: boolean
    /** Progress row read before the settlement; null means first clear. */
    questProgress: PlayerQuestProgress | null
    /** Five-boss solo runs settle through this generic path with own rewards. */
    fiveBossSoloQuest: boolean
    /** False when the active quest was rebuilt from a patched-client hint. */
    registered: boolean
    scoreAttackBorderTiers: ScoreAttackBorderTier[]
    beforeRankPoint: number
    newRankPoint: number
    manaObtained: number
    newMana: number
    newBoostPoint: number
    newBossBoostPoint: number
    useBoostPoint: boolean
    displayMode15ManaAsFieldDrop: boolean
    finishCacheKey: string | null
}

export interface SingleFinishTransactionResult {
    response: { data_headers: Record<string, unknown>, data: Record<string, any> }
    timing: SingleSettlementBodyTiming | null
}

/**
 * The single-battle finish transaction body.
 *
 * This function used to be an inline closure in the `/finish` handler. It runs
 * unchanged in-process when `CN_WRITER_THREAD` is off and inside the SQLite
 * writer thread when it is on, so it must not reference anything from the
 * request scope except the arguments above.
 */
export function settleSingleQuestFinishInTransaction(
    args: SingleFinishTransactionArgs,
): SingleFinishTransactionResult {
    const {
        playerId, viewerId, questCategory, questId, questData, playerData, activeQuestData, body,
        clearTime, clearRank, questAccomplished, questProgress,
        fiveBossSoloQuest, registered, scoreAttackBorderTiers, beforeRankPoint, newRankPoint,
        manaObtained, newMana, newBoostPoint, newBossBoostPoint, useBoostPoint,
        displayMode15ManaAsFieldDrop, finishCacheKey,
    } = args
    const questPreviouslyCompleted = questProgress !== null
    const isScoreAttackEvent = questCategory === QuestCategory.SCORE_ATTACK_EVENT
    const bodyTiming = createSingleSettlementBodyTimingCollector(questCategory, !!fiveBossSoloQuest)
    let bodySucceeded = false
    try {
        deletePlayerActiveQuestSync(playerId)
        const missionEvaluationTime = new Date(getServerTime() * 1000)

        let clearReward: PlayerRewardResult | null = null
        let sPlusClearReward: PlayerRewardResult | null = null
        const leaderId = body.statistics.party.characters[0]?.id
        if (questAccomplished) {
            recordAbyssFloorFinishSync({
                category: questCategory, questId, revision: activeQuestData.questTimeRevision,
                viewerId, elapsedTimeMs: clearTime, startedAtMs: activeQuestData.startedAtMs,
                nowMs: getServerTime() * 1000, accomplished: true,
                registered,
                matchingPlay: body.play_id === activeQuestData.playId
                    && Number(body.quest_id) === questId && Number(body.category) === questCategory,
                isMulti: activeQuestData.isMulti,
            })
            // update quest progress
            if (questPreviouslyCompleted) {
                // simply update the quest progress if it already exists.
                const updateData: any = {
                    questId: questId,
                    finished: true,
                    bestElapsedTimeMs: questProgress.bestElapsedTimeMs === undefined || questProgress.bestElapsedTimeMs === null ? clearTime : Math.min(clearTime, questProgress.bestElapsedTimeMs),
                    highScore: questProgress.highScore === undefined ? body.score : Math.max(body.score, questProgress.highScore),
                    leaderCharacterId: leaderId ?? null
                }
                if (clearRank !== null) {
                    updateData.clearRank = questProgress.clearRank === undefined ? clearRank : Math.max(clearRank, questProgress.clearRank)
                }
                updatePlayerQuestProgressSync(playerId, questCategory, updateData)
            } else {
                // insert if it doesn't already exist.
                const insertData: any = {
                    questId: questId,
                    finished: true,
                    bestElapsedTimeMs: clearTime,
                    highScore: body.score,
                    clearRank: clearRank ?? 5,
                    leaderCharacterId: leaderId ?? null
                }
                insertPlayerQuestProgressSync(playerId, questCategory, insertData)
            }

            // Legacy saves may be missing the 1-6-1 story completion row even
            // though a later main quest was cleared. Repair it immediately so
            // unison becomes available without requiring another login.
            if (questCategory === QuestCategory.MAIN && questId >= 1006001) {
                repairUnisonUnlockProgressSync(playerId)
            }

            if (questCategory === QuestCategory.SOLO_TIME_ATTACK_EVENT) {
                const newDegreeIds = grantPlayerSoloTimeAttackDegreesSync(playerId, questId, clearTime)
                if (newDegreeIds.length > 0) {
                    console.log(`[DEGREE] solo time attack granted: player=${playerId} quest=${questId} elapsed=${clearTime} degrees=${newDegreeIds.join(",")}`)
                }
            }
        }

        // update player
        const oldRkDegree = getRankDegree(beforeRankPoint)
        const newDegreeId = getRankDegree(newRankPoint)
        const didLevelUp = newDegreeId > oldRkDegree
        updatePlayerSync({
            id: playerId,
            freeMana: newMana,
            rankPoint: newRankPoint,
            boostPoint: newBoostPoint,
            bossBoostPoint: newBossBoostPoint,
            totalManaObtained: (playerData.totalManaObtained ?? 0) + manaObtained,
            maxComboAchieved: Math.max(playerData.maxComboAchieved ?? 0, (body as any).statistics?.max_combo_count ?? 0),
            ...(didLevelUp ? { stamina: playerData.stamina + getMaxStamina(newDegreeId), staminaHealTime: new Date() } : {}),
        })
        if (adjustPlayerExpPoolSync(playerId, questData.poolExpReward, 'single_battle_base_reward') === null) {
            throw new Error(`Failed to grant single battle EXP to player ${playerId}`)
        }
        clearReward = !isScoreAttackEvent && !questPreviouslyCompleted && questData.clearReward !== undefined
            ? givePlayerRewardSync(playerId, questData.clearReward)
            : null
        const isExpertSingleEvent = questCategory === QuestCategory.EXPERT_SINGLE_EVENT
        const shouldGrantSPlusReward = isExpertSingleEvent
            ? questProgress?.sPlusRewardReceived !== true
            : questProgress?.clearRank !== 5
        sPlusClearReward = !isScoreAttackEvent && (clearRank === 5)
            && shouldGrantSPlusReward && (questData.sPlusReward !== undefined)
            ? givePlayerRewardSync(playerId, questData.sPlusReward)
            : null
        if (isExpertSingleEvent && sPlusClearReward !== null) {
            updatePlayerQuestProgressSync(playerId, questCategory, {
                questId,
                sPlusRewardReceived: true,
            })
            console.log(`[EXPERT_SINGLE_EVENT] SS reward granted: player=${playerId} quest=${questId} item=14040 count=3`)
        }
        if (didLevelUp) {
            playerData.stamina = playerData.stamina + getMaxStamina(newDegreeId)
            playerData.staminaHealTime = new Date()
            console.log(`[BATTLE-FINISH] player ${playerId} leveled up: ${oldRkDegree} -> ${newDegreeId}, stamina refilled`)
        }

        // Consume daily challenge point
        const dailyChallengePointList = handleDailyChallengePoint({
            questCategory,
            eventId: questData.eventId,
            playerId,
            challengePointMap: eventChallengePointMap as Record<string, number>,
            getEntries: (pid) => getPlayerDailyChallengePointListSync(pid),
            updatePoint: (pid, id, pt) => updatePlayerDailyChallengePointSync(pid, id, pt),
        })

        // 五重单人使用独立奖励计划，不再叠加 1099001 的旧 score reward 组
        // （其中包含猫头鹰货币及其稀有池）。多人专用结算也不走这条普通奖励链。
        const effectiveScoreRewardGroupId = fiveBossSoloQuest
            ? undefined
            : questData.scoreRewardGroupId
        const effectiveScoreRewardGroup = fiveBossSoloQuest
            ? undefined
            : questData.scoreRewardGroup
        // reward score rewards
        if (isScoreAttackEvent) {
            gameVerboseLog(() => `[SCORE_ATTACK] questId=${questId} body={score:${body.score}, elapsed:${body.elapsed_time_ms}, accomplished:${body.is_accomplished}, addMana:${body.add_mana}, continue:${body.continue_count}}`)
            gameVerboseLog(() => `[SCORE_ATTACK] questData={localQuest:${questData.scoreAttackQuestId}, bRank:${questData.bRankScore}, aRank:${questData.aRankScore}, sRank:${questData.sRankScore}, ssRank:${questData.ssRankScore}, rankPt:${questData.rankPointReward}, charExp:${questData.characterExpReward}, mana:${questData.manaReward}, poolExp:${questData.poolExpReward}}`)
        }
        gameVerboseLog(() => `[BATTLE] scoreReward groupId=${effectiveScoreRewardGroupId ?? (fiveBossSoloQuest ? 'skipped-five-boss-solo' : 'null')} groupLen=${effectiveScoreRewardGroup?.length ?? 'null'} questId=${questId} category=${questCategory}`)
        const scoreRewardsResult = givePlayerScoreRewardsSync(
            playerId,
            effectiveScoreRewardGroupId,
            effectiveScoreRewardGroup,
            useBoostPoint,
            questData.element,
            { questId, mode: "solo" },
        )
        let scoreAttackEventData: { reward_ids: number[], main_character_ids: Record<string, number> } | null = null
        if (isScoreAttackEvent) {
            const previousHighScore = questProgress?.highScore ?? 0
            const mainCharacterIds = collectScoreAttackMainCharacterIds(body.statistics.party.characters)
            const resolved = resolveNewScoreAttackBorderRewards(
                scoreAttackBorderTiers,
                previousHighScore,
                body.score,
            )
            for (const [itemIdText, count] of Object.entries(resolved.itemCounts)) {
                scoreRewardsResult.items[itemIdText] = givePlayerItemSync(playerId, Number(itemIdText), count)
            }
            scoreAttackEventData = {
                reward_ids: resolved.rewardIds,
                main_character_ids: mainCharacterIds,
            }
            gameVerboseLog(() => `[SCORE_ATTACK] borderRewards: event=${questData.eventId} folder=${questData.folderId} oldScore=${previousHighScore} newScore=${body.score} crossed=${resolved.rewardIds.length} items=${JSON.stringify(resolved.itemCounts)}`)
            gameVerboseLog(() => `[SCORE_ATTACK] afterReward: dropIds=${JSON.stringify(scoreRewardsResult.drop_score_reward_ids)}, drops=${scoreRewardsResult.drop_score_reward_ids.length}, items=${JSON.stringify(scoreRewardsResult.items)}, equipList=${scoreRewardsResult.equipment_list?.length ?? 0}`)
            gameVerboseLog(() => `[SCORE_ATTACK] response: accomplished=${questAccomplished}, clearRank=${clearRank}, score=${body.score}, elapsed=${body.elapsed_time_ms}, items=${JSON.stringify(scoreRewardsResult.items)}, clientCategory=${questCategory}`)
        }

        // reward character exp
        bodyTiming.step("battle_facts")
        const bodyPartyStatistics = body.statistics.party
        const partyCharacterIds = [...bodyPartyStatistics.characters, ...bodyPartyStatistics.unison_characters]

        if (questCategory === QuestCategory.PRACTICE) {
            insertPlayerPracticeBattleHistorySync(buildPracticeBattleHistoryRecord({
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
                equipmentList: getPlayerEquipmentListSync(playerId),
            }))
        }

        // Build finish context for mission trackers
        const finishCtx: FinishContext = {
            playerId, questCategory, questId,
            questAccomplished,
            clearTime: body.elapsed_time_ms,
            clearRank,
            party: body.statistics.party as any,
            statistics: (body as any).statistics,
            player: playerData,
            questPreviouslyCompleted,
            questProgress,
            partySlot: activeQuestData.partySlot ?? playerData.partySlot,
        }

        // Mission progress is recorded once by recordMissionBattleFacts below.
        const singleBattleParty = collectPartyCharacterIds(finishCtx.party)
        recordBattleMissionDimensionsSafe({
            type: "battle_finish",
            playerId,
            questCategory,
            questId,
            accomplished: questAccomplished,
            mode: "single",
            clearRank,
            clearTimeMs: clearTime,
            score: Number(body.score) || 0,
            ...singleBattleParty,
            statistics: summarizeBattleStatistics(finishCtx.statistics),
        })
        const missionBattleFacts = recordMissionBattleFacts(finishCtx, missionEvaluationTime)
        if (questData.fixedParty === undefined) {
            recordQuestRecommendedPartySafe(finishCtx)
        }
        const steamRobotMissionId = trackSteamRobotChallengeMission({
            playerId,
            questCategory,
            questId,
            questAccomplished,
            clearRank,
            statistics: finishCtx.statistics,
        })
        if (steamRobotMissionId !== null) {
            console.log(`[MISSION] steam robot challenge cleared: player=${playerId} quest=${questId} mission=${steamRobotMissionId}`)
        }
        const partyCharacterIdsArray: number[] = []
        bodyTiming.step("experience")
        for (const value of partyCharacterIds.values()) {
            if (value !== null && value.id !== null) partyCharacterIdsArray.push(value.id);
        }
        const addExpAmount = questData.characterExpReward

        const rewardCharacterExpResult = givePlayerCharactersExpSync(
            playerId,
            partyCharacterIdsArray,
            addExpAmount,
            questData.fixedParty !== undefined
        )

        bodyTiming.step("mode_rewards")
        const dataHeaders = generateDataHeaders({
            viewer_id: viewerId
        })

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
            && questCategory === QuestCategory.RUSH_EVENT
            && questData.rushEventId === MODE15_RUSH_EVENT_ID
            && (mode15BoundaryStage === 4
                || mode15BoundaryStage === 9
                || mode15BoundaryStage === 14);
        const rushPartiesBeforeBoundaryAdvance = withholdMode15BoundaryAdvance
            ? getSerializedPlayerRushEventPlayedPartiesSync(playerId, MODE15_RUSH_EVENT_ID)
            : null;

        // handle event quest-specific data & rewards
        const { rushEventData, rushEventRewardsResult } = handleRushEventFinish({
            questCategory,
            questAccomplished,
            questData,
            clearTime,
            party: bodyPartyStatistics,
            playerId,
            questId,
            getEvoLevels: (pid, chars) => getCharactersEvolutionImgLevels(pid, chars),
            getFolderMaxRounds: getRushEventFolderMaxRounds,
            getRushEvent: (pid, eid) => getPlayerRushEventSync(pid, eid),
            updateRushEvent: (pid, data) => updatePlayerRushEventSync(pid, data),
            // Never save a content-less marker. The legacy result/quest UI
            // dereferences the first character of every recorded party; a row
            // made entirely of NULL values becomes character id 0 and crashes
            // immediately after boundary floors such as stage 5.
            insertParty: (pid, eid, p) => insertPlayerRushEventPlayedPartySync(pid, eid, p),
            insertClearedFolder: (pid, eid, fid) => insertPlayerRushEventClearedFolderSync(pid, eid, fid),
            deletePartyList: (pid, eid, bt) => deletePlayerRushEventPlayedPartyListSync(pid, eid, bt),
            getSerializedParties: (pid, eid) => getSerializedPlayerRushEventPlayedPartiesSync(pid, eid),
            getFolderRewards: (eid, fid) => getRushEventFolderClearRewards(eid, fid),
            giveRewards: (pid, r) => givePlayerRewardsSync(pid, r),
        })
        const abyssEnduranceDegrees = finishLeaderboardQuestSync({
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
                    : getRushEventFolderMaxRounds(
                        questData.rushEventId,
                        questData.rushEventFolderId,
                    ),
            },
            accomplished: questAccomplished,
            clientBattleMs: clearTime,
            party: {
                characterIds: bodyPartyStatistics.characters.map(value => value?.id ?? null),
                unisonCharacterIds: bodyPartyStatistics.unison_characters.map(value => value?.id ?? null),
                equipmentIds: bodyPartyStatistics.equipments.map(value => value?.id ?? null),
                abilitySoulIds: bodyPartyStatistics.ability_soul_ids,
                evolutionImgLevels: getCharactersEvolutionImgLevels(
                    playerId,
                    bodyPartyStatistics.characters.map(value => value?.id ?? null),
                ),
                unisonEvolutionImgLevels: getCharactersEvolutionImgLevels(
                    playerId,
                    bodyPartyStatistics.unison_characters.map(value => value?.id ?? null),
                ),
            },
        })
        if (
            questAccomplished
            && questCategory === QuestCategory.RUSH_EVENT
            && questData.rushEventId !== undefined
            && repairGauntletCompletionClassificationSync(
                playerId,
                questData.rushEventId,
            )
        ) {
            console.log(
                `[RUSH] completed classification repaired: `
                + `player=${playerId} event=${questData.rushEventId}`,
            )
        }

        if (rushEventData !== null && rushPartiesBeforeBoundaryAdvance !== null) {
            rushEventData.rush_battle_played_party_list = rushPartiesBeforeBoundaryAdvance.folderParties
            rushEventData.endless_battle_played_party_list = rushPartiesBeforeBoundaryAdvance.endlessParties
            console.log(
                `[MODE15] deferred Rush result visibility: player=${playerId} stage=${mode15BoundaryStage}`,
            )
        }

        const rogueFolderMaxRounds: Record<number, number> = {}
        if (
            questData.rushEventId !== undefined
            && questData.rushEventFolderId !== undefined
        ) {
            rogueFolderMaxRounds[questData.rushEventFolderId] =
                getRushEventFolderMaxRounds(
                    questData.rushEventId,
                    questData.rushEventFolderId,
                )
        }
        const rogueDrops = handleRoguePerRoundDrops({
            questCategory,
            questAccomplished,
            playerId,
            questData,
            folderMaxRounds: rogueFolderMaxRounds,
            partyCharacterIds: partyCharacterIdsArray,
        })
        if (
            rogueDrops !== null
            && rushEventData !== null
            && rogueDrops.showInRewardList
        ) {
            rushEventData.rush_battle_reward_list = [
                ...rushEventData.rush_battle_reward_list,
                ...rogueDrops.rewardListEntries,
            ]
        }

        // Record played party for RAID_EVENT
        const raidEventData = handleRaidEventFinish({
            questCategory,
            questAccomplished,
            activeEventId: activeQuestData.eventId,
            playId: activeQuestData.playId,
            party: bodyPartyStatistics,
            playerId,
            questId,
            getEvoLevelsFn: (pid, chars) => getCharactersEvolutionImgLevels(pid, chars),
            insertPartyFn: (pid, eid, p) => insertPlayerRushEventPlayedPartySync(pid, eid, p),
        })

        // handle carnival event score & records
        const carnivalInfo = carnivalScoreLookup[String(questId)]
        if (carnivalInfo) migrateCarnivalEventFolderRecordsSync(carnivalInfo.event_id)
        const carnivalEventData = handleCarnivalEventFinish({
            questCategory,
            questAccomplished,
            questId,
            battleScore: body.score,
            clearTime,
            party: bodyPartyStatistics,
            playerId,
            carnivalLookup: carnivalScoreLookup,
            getRecordsFn: (pid, eid) => getPlayerCarnivalEventRecordsSync(pid, eid),
            upsertFn: (pid, eid, fid, score, chars, unisons) => upsertPlayerCarnivalEventRecordSync(pid, eid, fid, score, chars, unisons),
        })

        let carnivalRewardsResult: PlayerRewardResult | null = null
        if (carnivalEventData && carnivalInfo) {
            const totalBestScore = getPlayerCarnivalEventRecordsSync(playerId, carnivalInfo.event_id)
                .reduce((sum, record) => sum + (record.bestScore ?? 0), 0)
            const granted = grantCarnivalTotalScoreRewardsSync(playerId, carnivalInfo.event_id, totalBestScore)
            carnivalEventData.reward_ids = granted.rewardIds
            carnivalEventData.new_degree_ids = granted.newDegreeIds
            carnivalRewardsResult = granted.rewards
        }

        const mode15RewardsResult = settleMode15BattleSync(
            playerId,
            questCategory,
            questId,
            questAccomplished,
        )

        const fiveBossSolo = fiveBossSoloQuest && questAccomplished
            ? grantFiveBossSoloRewardsSync({ playerId, firstClear: !questProgress?.finished,
                rewardMultiplier: getFiveBossSoloRewardMultiplierSync(playerId, activeQuestData.playId) }) : null
        const itemList = {
            ...(fiveBossSolo?.items ?? {}),
            ...(activeQuestData.entryItemId ? { [activeQuestData.entryItemId]: getPlayerItemSync(playerId, activeQuestData.entryItemId) ?? 0 } : {}),
            ...(clearReward?.items ?? {}),
            ...(sPlusClearReward?.items ?? {}),
            ...scoreRewardsResult.items,
            ...(rushEventRewardsResult?.items ?? {}),
            ...(rogueDrops?.rewardResult.items ?? {}),
            ...(carnivalRewardsResult?.items ?? {}),
            ...(mode15RewardsResult?.items ?? {})
        }
        const characterList = [
            ...rewardCharacterExpResult.character_list as unknown as Record<string, unknown>[],
            ...((clearReward?.character_list || []) as Record<string, unknown>[]),
            ...((sPlusClearReward?.character_list || []) as Record<string, unknown>[]),
            ...(scoreRewardsResult.character_list as Record<string, unknown>[]),
            ...((rogueDrops?.rewardResult.character_list || []) as unknown as Record<string, unknown>[]),
            ...((rogueDrops?.expCharacterList || []) as unknown as Record<string, unknown>[]),
            ...((carnivalRewardsResult?.character_list || []) as Record<string, unknown>[]),
            ...((mode15RewardsResult?.character_list || []) as Record<string, unknown>[]),
        ]
        bodyTiming.step("missions")
        const missionSettlement = measureSettlementPhase("single", "mission", () => (
            settleMissionCategories(
                playerId,
                buildBattleMissionSettlementScopes(
                    missionBattleFacts,
                    Object.keys(itemList).map(Number),
                    steamRobotMissionId === null ? [] : [steamRobotMissionId],
                    partyCharacterIdsArray,
                ),
                missionEvaluationTime,
            )
        ))
        bodyTiming.step("awake")
        const awakeMissionSettlement = measureSettlementPhase("single", "awake_mission", () => (
            settleAwakeMissionCandidates(
                playerId,
                questAccomplished
                    ? getAwakeBattleMissionIds(
                        partyCharacterIdsArray,
                        missionBattleFacts.awakeMissionIds,
                    )
                    : [],
                missionEvaluationTime,
            )
        ))
        bodyTiming.step("active")
        const activeMissionSettlement = measureSettlementPhase("single", "active_mission", () => (
            reconcileActiveMissionFacts({
                playerId,
                repository: getContentSnapshot().repository,
                now: missionEvaluationTime,
                patterns: getBattleActiveMissionPatterns(questCategory),
            })
        ))
        bodyTiming.step("response")
        const finalPlayerData = getPlayerSync(playerId)
        const responseData: Record<string, any> = {
                "user_info": {
                    "free_mana": finalPlayerData?.freeMana ?? newMana,
                    "exp_pool": finalPlayerData?.expPool ?? rewardCharacterExpResult.exp_pool,
                    "exp_pooled_time": getServerTime(playerData.expPooledTime),
                    "free_vmoney": finalPlayerData?.freeVmoney ?? playerData.freeVmoney,
                    "rank_point": newRankPoint,
                    "degree_id": playerData.degreeId ?? 1,
                    "stamina": playerData.stamina,
                    "stamina_heal_time": realToVirtual(playerData.staminaHealTime),
                    "boost_point": newBoostPoint,
                    "boss_boost_point": newBossBoostPoint
                },
                "add_exp_list": [
                    ...rewardCharacterExpResult.add_exp_list,
                    ...(rogueDrops?.addExpList || []),
                ],
                "character_list": characterList,
                "bond_token_status_list": {
                    ...rewardCharacterExpResult.bond_token_status_list,
                    ...(rogueDrops?.bondTokenStatusList || {}),
                },
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
                    ...(clearReward?.joined_character_id_list || []),
                    ...(sPlusClearReward?.joined_character_id_list || []),
                    ...scoreRewardsResult.joined_character_id_list,
                    ...(carnivalRewardsResult?.joined_character_id_list || []),
                    ...(mode15RewardsResult?.joined_character_id_list || [])
                ],
                "before_rank_point": beforeRankPoint,
                "clear_rank": clearRank ?? 5,
                "drop_score_reward_ids": scoreRewardsResult.drop_score_reward_ids,
                "drop_rare_reward_ids": scoreRewardsResult.drop_rare_reward_ids,
                "drop_additional_reward_ids": [
                    ...(fiveBossSolo?.dropAdditionalRewardIds ?? []),
                    ...(rogueDrops?.additionalRewardEntries ?? []),
                    ...(mode15RewardsResult?.mode15_additional_reward_ids ?? []),
                ],
                "drop_periodic_reward_ids": [],
                "equipment_list": [
                    ...scoreRewardsResult.equipment_list,
                    ...(clearReward?.equipment_list || []),
                    ...(sPlusClearReward?.equipment_list || []),
                    ...(rushEventRewardsResult?.equipment_list || []),
                    ...(rogueDrops?.rewardResult.equipment_list || []),
                    ...(carnivalRewardsResult?.equipment_list || []),
                    ...(mode15RewardsResult?.equipment_list || []),
                    ...(fiveBossSolo?.equipment_list ?? [])
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
                "user_daily_challenge_point_list": dailyChallengePointList ?? [],
                "presigned_quest_category": []
        }
        if (raidEventData?.new_degree_ids.length) {
            responseData.degree_list = raidEventData.new_degree_ids.map(degreeId => ({
                viewer_id: viewerId,
                degree_id: degreeId,
            }))
        }
        if (abyssEnduranceDegrees.length) {
            responseData.degree_list = [
                ...(responseData.degree_list ?? []),
                ...abyssEnduranceDegrees.map(degreeId => ({ viewer_id: viewerId, degree_id: degreeId })),
            ]
        }
        mergeMissionSettlementResponse(responseData, missionSettlement, viewerId)
        // Awake settlement re-publishes completed special unlocks itself,
        // including already-persisted rows whose earlier response was lost.
        mergeMissionSettlementResponse(responseData, awakeMissionSettlement, viewerId)
        if (activeMissionSettlement.length > 0) {
            responseData.active_mission_list = activeMissionSettlement
        }
        responseData.mail_arrived = getPlayerMailCountSync(playerId, true) > 0
        const response = { data_headers: dataHeaders, data: responseData }
        if (fiveBossSoloQuest) saveFiveBossSoloReceiptSync(playerId, activeQuestData.playId, finishCacheKey, response)
        bodySucceeded = true
        return { response, timing: bodyTiming.result(true) }
    } finally {
        // A rolled-back body has no caller to report to; drop its sample.
        if (!bodySucceeded) bodyTiming.result(false)
    }
}
