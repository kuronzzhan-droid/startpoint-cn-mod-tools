# master 表 → 客户端读取类(自动生成 2026-10-14 19:35)

表名由 `pinball/master/generated/<Camel>Table.as` 反推 snake_case(近似,数字/缩写可能不准)。
列解析在同目录 `<Camel>Values.as` 的 `parseAtN`(N=列号)。只列 generated 以外引用 Table/Values 的类,最多 8 个。

| 表(推断) | Camel | 读取类数 | 主要读取类 |
|---|---|---|---|
| ability | Ability | 2 | `boot_ffc6`, `AbilityLogic` |
| ability_default_statue_group | AbilityDefaultStatueGroup | 1 | `boot_ffc6` |
| ability_soul | AbilitySoul | 2 | `boot_ffc6`, `AbilitySoulAbilityLogic` |
| ability_soul_stance_detail | AbilitySoulStanceDetail | 2 | `boot_ffc6`, `SimilarAbilitySoulAsyncSearcher` |
| ability_statue_group | AbilityStatueGroup | 2 | `boot_ffc6`, `OwnedManaNodeLogic` |
| access_count_mode | AccessCountMode | 2 | `boot_ffc6`, `ConfigLogic` |
| achievement | Achievement | 3 | `boot_ffc6`, `AchievementLogic`, `AchievementRepository` |
| action_skill | ActionSkill | 5 | `boot_ffc6`, `TerrainHandler`, `ActionSkillLogic`, `DialogCharacterSkillDescriptionVariationTranslator`, `LearnWindow` |
| action_skill_gauge_thresholds | ActionSkillGaugeThresholds | 2 | `boot_ffc6`, `SkillWeightGaugeLevelRepository` |
| active_mission | ActiveMission | 5 | `boot_ffc6`, `ActiveMissionLogic`, `ActiveMissionRepository`, `ActiveMissionScene`, `RealIncentiveActiveMissionScene` |
| active_mission_event | ActiveMissionEvent | 3 | `boot_ffc6`, `ActiveMissionEventLogic`, `ActiveMissionRepository` |
| active_mission_reward | ActiveMissionReward | 3 | `boot_ffc6`, `ActiveMissionLogic`, `ActiveMissionStageLogic` |
| additional_reward | AdditionalReward | 4 | `boot_ffc6`, `AdditionalRewardLogic`, `AdditionalRewardRepository`, `QuestRewardKindTools` |
| adjust_event | AdjustEvent | 2 | `boot_ffc6`, `GlobalLogic` |
| advent_event | AdventEvent | 4 | `boot_ffc6`, `AdventEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| advent_event_quest | AdventEventQuest | 5 | `boot_ffc6`, `AdventEventLogic`, `AdventEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| advice_text | AdviceText | 2 | `boot_ffc6`, `AdviceTextRepository` |
| advice_text_quest_group | AdviceTextQuestGroup | 2 | `boot_ffc6`, `AdviceTextRepository` |
| android_payment | AndroidPayment | 3 | `boot_ffc6`, `PaymentLogic`, `OperationUserManipulateDialog` |
| assist_atk_curve | AssistAtkCurve | 3 | `boot_ffc6`, `AssistYakumonoSource`, `AssistCharacterFactory` |
| assist_cutin | AssistCutin | 4 | `boot_ffc6`, `AssistYakumonoSource`, `AssistCharacterFactory`, `SoundTestScene` |
| assist_hp_curve | AssistHpCurve | 2 | `boot_ffc6`, `AssistCharacterFactory` |
| assist_multiball | AssistMultiball | 3 | `boot_ffc6`, `AssistCharacterFactory`, `SoundTestScene` |
| assist_multiball_level | AssistMultiballLevel | 2 | `boot_ffc6`, `AssistCharacterFactory` |
| assist_yakumono | AssistYakumono | 4 | `boot_ffc6`, `TerrainHandler`, `AssistYakumonoSource`, `SoundTestScene` |
| assist_yakumono_level | AssistYakumonoLevel | 2 | `boot_ffc6`, `AssistYakumonoSource` |
| assistant_mission_list | AssistantMissionList | 4 | `boot_ffc6`, `LittleAssistantItemLogic`, `LittleAssistantLogic`, `LittleAssistantScene` |
| atk_basic_curve | AtkBasicCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| atk_correction_curve | AtkCorrectionCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| attention_config | AttentionConfig | 2 | `boot_ffc6`, `AttentionConfigLogic` |
| attention_enable_scene | AttentionEnableScene | 2 | `boot_ffc6`, `AttentionConfigLogic` |
| attention_group | AttentionGroup | 1 | `boot_ffc6` |
| attention_priority | AttentionPriority | 1 | `boot_ffc6` |
| banner_image | BannerImage | 1 | `boot_ffc6` |
| battle_bgm_group | BattleBgmGroup | 3 | `boot_ffc6`, `BattleBgmGroupLogic`, `BattleQuestBaseImpl` |
| battle_no_daily_challenge_point_return | BattleNoDailyChallengePointReturn | 2 | `boot_ffc6`, `BattleQuestBaseImpl` |
| battle_no_stamina_return | BattleNoStaminaReturn | 2 | `boot_ffc6`, `BattleQuestBaseImpl` |
| bgm_asset | BgmAsset | 7 | `boot_ffc6`, `AssetPathCollectionBuilder`, `SoundAssetCache`, `Builder_pinball_master_generated_BgmAssetValues_pinball_sound_production_bgm_BgmResource`, `SoundTestScene`, `BgmChannel`, `BgmResource` |
| board_open_condition | BoardOpenCondition | 2 | `boot_ffc6`, `BattleCharacterLogic` |
| bond_token_exchange | BondTokenExchange | 5 | `boot_ffc6`, `BondTokenExchangeProductLogic`, `BondTokenExchangeProductRepository`, `ExchangeBondTokenDummyRemote`, `ExchangeGetBondTokenExchangeListDummyRemote` |
| boss_battle_chapter | BossBattleChapter | 2 | `boot_ffc6`, `QuestRepository` |
| boss_battle_multi_pickup_event | BossBattleMultiPickupEvent | 3 | `boot_ffc6`, `BossBattleRepository`, `BossBattleMultiPickupEventLogic` |
| boss_battle_multi_pickup_event_schedule | BossBattleMultiPickupEventSchedule | 3 | `boot_ffc6`, `BossBattleMultiPickupEventLogic`, `BossBattleMultiPickupEventScheduleLogic` |
| boss_battle_quest | BossBattleQuest | 6 | `boot_ffc6`, `BossBattleQuestLogic`, `BossBattleStageNodeLogic`, `QuestRepository`, `QuestRewardKindTools`, `MultiBattleQuestSelectRoomDummyRemote` |
| boss_battle_stage_node | BossBattleStageNode | 4 | `boot_ffc6`, `BossBattleChapterLogic`, `BossBattleStageNodeLogic`, `QuestRepository` |
| boss_battle_stage_node_group | BossBattleStageNodeGroup | 3 | `boot_ffc6`, `BossBattleRepository`, `BossBattleStageNodeGroupLogic` |
| boss_coin_shop | BossCoinShop | 4 | `boot_ffc6`, `ShopProductRepository`, `OperationShopManipulateDialog`, `LittleAssistantScene` |
| boss_coin_shop_category | BossCoinShopCategory | 4 | `boot_ffc6`, `BossCoinShopCategoryLogic`, `ShopProductRepository`, `OperationShopManipulateDialog` |
| boss_coin_shop_select_item_campaign | BossCoinShopSelectItemCampaign | 4 | `boot_ffc6`, `BossCoinShopSelectItemCampaignLogic`, `ShopProductRepository`, `OperationShopManipulateDialog` |
| boss_coin_shop_select_item_campaign_lineup | BossCoinShopSelectItemCampaignLineup | 2 | `boot_ffc6`, `BossCoinShopSelectItemCampaignLogic` |
| boss_level | BossLevel | 22 | `boot_ffc6`, `GeneralBossSource`, `ConductorSource`, `KrakenSource`, `OrochiExHeadSource`, `OrochiExSource`, `OrochiSource`, `FireSpherePhase1CrystalSource` |
| boss_weak_point_marker_set | BossWeakPointMarkerSet | 19 | `boot_ffc6`, `GeneralBossSource`, `FunnelSource`, `ConductorSource`, `KrakenSource`, `FireSpherePhase1CrystalSource`, `FireSpherePhase4MicronucleusSource`, `FireSphereSource` |
| both_boss_group | BothBossGroup | 2 | `boot_ffc6`, `BothBossMapRepository` |
| both_boss_map | BothBossMap | 2 | `boot_ffc6`, `BothBossMapLogic` |
| box | Box | 2 | `boot_ffc6`, `BoxGachaRepository` |
| box_gacha | BoxGacha | 2 | `boot_ffc6`, `BoxGachaRepository` |
| box_reward | BoxReward | 2 | `boot_ffc6`, `BoxGachaRepository` |
| box_reward_lineup_old | BoxRewardLineupOld | 1 | `boot_ffc6` |
| box_reward_old | BoxRewardOld | 1 | `boot_ffc6` |
| breakable_block | BreakableBlock | 3 | `boot_ffc6`, `TerrainHandler`, `BreakableBlockSource` |
| breakable_block_level | BreakableBlockLevel | 2 | `boot_ffc6`, `BreakableBlockSource` |
| breakable_block_state | BreakableBlockState | 2 | `boot_ffc6`, `BreakableBlockSource` |
| carnival_event | CarnivalEvent | 4 | `boot_ffc6`, `CarnivalEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| carnival_event_quest | CarnivalEventQuest | 5 | `boot_ffc6`, `CarnivalEventQuestFolderLogic`, `CarnivalEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| carnival_event_quest_folder | CarnivalEventQuestFolder | 4 | `boot_ffc6`, `CarnivalEventLogic`, `CarnivalEventQuestFolderLogic`, `CarnivalEventQuestLogic` |
| carnival_event_total_score_reward | CarnivalEventTotalScoreReward | 3 | `boot_ffc6`, `CarnivalEventTotalScoreRewardLogic`, `CarnivalEventTotalScoreRewardRepository` |
| challenge_dungeon_event | ChallengeDungeonEvent | 4 | `boot_ffc6`, `ChallengeDungeonEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| challenge_dungeon_event_quest | ChallengeDungeonEventQuest | 5 | `boot_ffc6`, `ChallengeDungeonEventLogic`, `ChallengeDungeonEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| character | Character | 19 | `boot_ffc6`, `GenerateAbilityDescription`, `GeneralCharacterLogic`, `BattlePartyTools`, `FixedPartyLogic`, `GlobalLogic`, `OperationAchievementDialog`, `GachaExecDummyRemote` |
| character_awake_event | CharacterAwakeEvent | 4 | `boot_ffc6`, `GeneralCharacterLogic`, `CharacterAwakeEventLogic`, `OperationAchievementDialog` |
| character_awake_mission | CharacterAwakeMission | 5 | `boot_ffc6`, `CharacterAwakeEventLogic`, `CharacterAwakeMissionLogic`, `MissionRepository`, `OperationAchievementDialog` |
| character_awake_mission_reward | CharacterAwakeMissionReward | 3 | `boot_ffc6`, `CharacterAwakeEventLogic`, `CharacterAwakeMissionLogic` |
| character_awake_status | CharacterAwakeStatus | 2 | `boot_ffc6`, `CharacterAwakeStatusLogic` |
| character_election | CharacterElection | 3 | `boot_ffc6`, `CharacterElectionLogic`, `CharacterElectionRepository` |
| character_election_exclude | CharacterElectionExclude | 2 | `boot_ffc6`, `CharacterElectionLogic` |
| character_election_order | CharacterElectionOrder | 2 | `boot_ffc6`, `CharacterElectionLogic` |
| character_exchange_rate | CharacterExchangeRate | 4 | `boot_ffc6`, `CharacterGachaOddsLogic`, `GachaOddsCharacterLogic`, `GachaExchangeCharacterScene` |
| character_gacha_sound | CharacterGachaSound | 4 | `boot_ffc6`, `AssetResolver`, `GeneralJoinCharacterSource`, `JoinMovie` |
| character_image | CharacterImage | 2 | `boot_ffc6`, `GeneralCharacterLogic` |
| character_level | CharacterLevel | 2 | `boot_ffc6`, `CharacterLevelLogic` |
| character_quest | CharacterQuest | 3 | `boot_ffc6`, `CharacterQuestLogic`, `QuestRepository` |
| character_special_ui | CharacterSpecialUi | 2 | `boot_ffc6`, `CharacterSpecialUiRepository` |
| character_speech | CharacterSpeech | 3 | `boot_ffc6`, `Speech`, `CharacterSpeechRepository` |
| character_stance_detail | CharacterStanceDetail | 2 | `boot_ffc6`, `SimilarCharacterAsyncSearcher` |
| character_status | CharacterStatus | 2 | `boot_ffc6`, `CharacterBaseStatusLogic` |
| character_tag | CharacterTag | 3 | `boot_ffc6`, `OrCharacterGroup_Impl_`, `CharacterTagLogic` |
| character_text | CharacterText | 3 | `boot_ffc6`, `GeneralCharacterLogic`, `OperationAchievementDialog` |
| clear_reward | ClearReward | 2 | `boot_ffc6`, `QuestClearRewardLogic` |
| collect_item_event | CollectItemEvent | 5 | `boot_ffc6`, `CollectItemEventLogic`, `CollectItemEventRepository`, `OperationAchievementDialog`, `OperationShopManipulateDialog` |
| collect_item_event_mission | CollectItemEventMission | 9 | `boot_ffc6`, `CollectItemEventLogic`, `CollectItemEventMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote`, `CollectItemEventMissionScene` |
| collect_item_event_mission_reward | CollectItemEventMissionReward | 7 | `boot_ffc6`, `CollectItemEventLogic`, `CollectItemEventMissionLogic`, `CollectItemEventMissionStageLogic`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote`, `LittleAssistantScene` |
| collect_item_event_quest_relation | CollectItemEventQuestRelation | 2 | `boot_ffc6`, `CollectItemEventLogic` |
| collect_item_event_reward_relation | CollectItemEventRewardRelation | 2 | `boot_ffc6`, `CollectItemEventRewardRelationLogic` |
| concerted_boss_interrupt | ConcertedBossInterrupt | 3 | `boot_ffc6`, `ConcertedBossSource`, `ConcertedBoss` |
| concerted_boss_watch | ConcertedBossWatch | 3 | `boot_ffc6`, `ConcertedBossSource`, `ConcertedBoss` |
| conductor | Conductor | 3 | `boot_ffc6`, `ZoneSourceValues`, `ConductorSource` |
| config | Config | 2 | `boot_ffc6`, `ConfigLogic` |
| custom_ability_power_up_string | CustomAbilityPowerUpString | 4 | `boot_ffc6`, `CustomAbilityPowerUpStringTools`, `AbilityDescriptionTools`, `AbilityDescriptionStringfier_Impl_` |
| custom_ability_string | CustomAbilityString | 4 | `boot_ffc6`, `AbilityDescriptionGenerator`, `AbilityDescriptionTools`, `InstantAbilityDescriptionGenerator` |
| daily_challenge_point | DailyChallengePoint | 4 | `boot_ffc6`, `DailyChallengePointLogic`, `DummyRemote`, `OperationUserManipulateDialog` |
| daily_challenge_point_campaign | DailyChallengePointCampaign | 2 | `boot_ffc6`, `DailyChallengePointCampaignLogic` |
| daily_exp_mana_event | DailyExpManaEvent | 3 | `boot_ffc6`, `DailyExpManaEventLogic`, `QuestRepository` |
| daily_exp_mana_event_quest | DailyExpManaEventQuest | 6 | `boot_ffc6`, `DailyExpManaEventLogic`, `DailyExpManaEventQuestLogic`, `QuestRepository`, `LoadedDataTools`, `OperationQuestManipulateTools` |
| daily_exp_mana_event_quest_odds | DailyExpManaEventQuestOdds | 3 | `boot_ffc6`, `DailyExpManaEventQuestLogic`, `LoadedDataTools` |
| daily_mission | DailyMission | 6 | `boot_ffc6`, `DailyMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote`, `MissionNameReportTestCase` |
| daily_mission_reward | DailyMissionReward | 5 | `boot_ffc6`, `DailyMissionLogic`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote`, `LittleAssistantScene` |
| daily_week_event | DailyWeekEvent | 3 | `boot_ffc6`, `DailyWeekEventLogic`, `QuestRepository` |
| daily_week_event_quest | DailyWeekEventQuest | 6 | `boot_ffc6`, `DailyWeekEventLogic`, `DailyWeekEventQuestLogic`, `QuestRepository`, `LoadedDataTools`, `OperationQuestManipulateTools` |
| daily_week_event_quest_odds | DailyWeekEventQuestOdds | 3 | `boot_ffc6`, `DailyWeekEventQuestLogic`, `LoadedDataTools` |
| degree | Degree | 2 | `boot_ffc6`, `DegreeLogic` |
| degree_category | DegreeCategory | 2 | `boot_ffc6`, `DegreeCategoryLogic` |
| degree_mission | DegreeMission | 5 | `boot_ffc6`, `DegreeMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote` |
| degree_mission_reward | DegreeMissionReward | 4 | `boot_ffc6`, `DegreeMissionLogic`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote` |
| direct_instant_item | DirectInstantItem | 3 | `boot_ffc6`, `TerrainHandler`, `DirectInstantItemSource` |
| element_particle_emitter | ElementParticleEmitter | 10 | `boot_ffc6`, `ActionEffect`, `ElementParticleManagerView`, `BattleSceneViewOrder`, `BattleView`, `BattleViewOrder`, `BattleViewOrderImpl`, `EmptyBattleSceneViewOrder` |
| encyclopedia | Encyclopedia | 3 | `boot_ffc6`, `EncyclopediaRepository`, `DummyEncyclopediaRepository` |
| encyclopedia_tag | EncyclopediaTag | 3 | `boot_ffc6`, `EncyclopediaRepository`, `DummyEncyclopediaRepository` |
| encyclopedia_tag_quest_relation | EncyclopediaTagQuestRelation | 2 | `boot_ffc6`, `DummyEncyclopediaRepository` |
| encyclopedia_triggered_tutorial_story | EncyclopediaTriggeredTutorialStory | 2 | `boot_ffc6`, `EncyclopediaRepository` |
| enemy_ability | EnemyAbility | 1 | `boot_ffc6` |
| equipment | Equipment | 6 | `boot_ffc6`, `GenerateAbilityDescription`, `GeneralEquipmentLogic`, `DummyRemote`, `OperationItemManipulateDialog`, `GachaExecDummyRemote` |
| equipment_craft_point_exchange | EquipmentCraftPointExchange | 2 | `boot_ffc6`, `EquipmentCraftPointExchangeLogic` |
| equipment_dissolve_rate | EquipmentDissolveRate | 2 | `boot_ffc6`, `EquipmentDissolveRateLogic` |
| equipment_enhancement | EquipmentEnhancement | 2 | `boot_ffc6`, `EquipmentEnhancementLogic` |
| equipment_enhancement_ability | EquipmentEnhancementAbility | 2 | `boot_ffc6`, `EquipmentEnhancementAbilityLogic` |
| equipment_enhancement_config | EquipmentEnhancementConfig | 2 | `boot_ffc6`, `EquipmentEnhancementConfigLogic` |
| equipment_enhancement_shop | EquipmentEnhancementShop | 4 | `boot_ffc6`, `EquipmentEnhancementShopProductLogic`, `ShopProductRepository`, `OperationShopManipulateDialog` |
| equipment_enhancement_shop_category | EquipmentEnhancementShopCategory | 3 | `boot_ffc6`, `EquipmentEnhancementShopCategoryLogic`, `ShopProductRepository` |
| equipment_enhancement_status | EquipmentEnhancementStatus | 2 | `boot_ffc6`, `EquipmentEnhancementStatusLogic` |
| equipment_exchange_rate | EquipmentExchangeRate | 3 | `boot_ffc6`, `EquipmentGachaOddsLogic`, `GachaExchangeEquipmentScene` |
| equipment_gacha_movie_probability | EquipmentGachaMovieProbability | 2 | `boot_ffc6`, `GachaExecDummyRemote` |
| equipment_gacha_odds | EquipmentGachaOdds | 3 | `EquipmentGachaOddsLogic`, `GachaOddsEquipmentLogic`, `GachaOddsTools` |
| equipment_quest_search | EquipmentQuestSearch | 2 | `boot_ffc6`, `ItemHowToGetQuestSearcher` |
| equipment_stance_detail | EquipmentStanceDetail | 2 | `boot_ffc6`, `SimilarEquipmentAsyncSearcher` |
| equipment_status | EquipmentStatus | 2 | `boot_ffc6`, `EquipmentStatusLogic` |
| escape_swift | EscapeSwift | 2 | `boot_ffc6`, `EscapeSwiftLogic` |
| event_aggregation_time | EventAggregationTime | 1 | `boot_ffc6` |
| event_folder | EventFolder | 3 | `boot_ffc6`, `EventFolderLogic`, `QuestRepository` |
| event_folder_events | EventFolderEvents | 3 | `boot_ffc6`, `EventFolderLogic`, `QuestRepository` |
| event_item_shop | EventItemShop | 4 | `boot_ffc6`, `ShopProductRepository`, `OperationShopManipulateDialog`, `LittleAssistantScene` |
| event_list | EventList | 3 | `boot_ffc6`, `EventListLogic`, `OperationQuestManipulateTools` |
| event_mission | EventMission | 6 | `boot_ffc6`, `EventMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote`, `MissionNameReportTestCase` |
| event_mission_reward | EventMissionReward | 5 | `boot_ffc6`, `EventMissionLogic`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote`, `LittleAssistantScene` |
| event_shop_select_item_campaign | EventShopSelectItemCampaign | 4 | `boot_ffc6`, `EventShopSelectItemCampaignLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| event_shop_select_item_campaign_lineup | EventShopSelectItemCampaignLineup | 2 | `boot_ffc6`, `EventShopSelectItemCampaignLogic` |
| evolution_status | EvolutionStatus | 2 | `boot_ffc6`, `CharacterEvolutionStatusLogic` |
| ex_ability | ExAbility | 6 | `boot_ffc6`, `GenerateAbilityDescription`, `ExAbilityLogic`, `ExBoostRepository`, `ExBoostDrawDummyRemote`, `ExBoostFirstDrawDummyRemote` |
| ex_boost | ExBoost | 5 | `boot_ffc6`, `ExBoostLogic`, `ExBoostMasterTools`, `ExBoostRepository`, `OwnedItemRepository` |
| ex_boost_config | ExBoostConfig | 2 | `boot_ffc6`, `ExBoostLogic` |
| ex_boost_icon_ribbon | ExBoostIconRibbon | 2 | `boot_ffc6`, `ExBoostLogic` |
| ex_boost_item_acquisition | ExBoostItemAcquisition | 2 | `boot_ffc6`, `ExBoostItemAcquisitionRepository` |
| ex_boost_odds | ExBoostOdds | 2 | `ExBoostMasterTools`, `ExBoostOddsLogic` |
| ex_chapter | ExChapter | 4 | `boot_ffc6`, `ExChapterLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| ex_quest | ExQuest | 4 | `boot_ffc6`, `ExQuestLogic`, `ExStageNodeLogic`, `QuestRepository` |
| ex_stage_node | ExStageNode | 4 | `boot_ffc6`, `ExChapterLogic`, `ExStageNodeLogic`, `QuestRepository` |
| ex_stage_node_position | ExStageNodePosition | 2 | `boot_ffc6`, `ExChapterLogic` |
| ex_status | ExStatus | 5 | `boot_ffc6`, `ExBoostRepository`, `ExStatusLogic`, `ExBoostDrawDummyRemote`, `ExBoostFirstDrawDummyRemote` |
| executable_instant_item | ExecutableInstantItem | 4 | `boot_ffc6`, `TerrainHandler`, `ZoneSourceValues`, `ExecutableInstantItemSource` |
| executable_instant_item_atk_curve | ExecutableInstantItemAtkCurve | 2 | `boot_ffc6`, `ExecutableInstantItemSource` |
| executable_instant_item_level | ExecutableInstantItemLevel | 2 | `boot_ffc6`, `ExecutableInstantItemSource` |
| experience_conversion_rate | ExperienceConversionRate | 2 | `boot_ffc6`, `GeneralCharacterLogic` |
| expert_single_event | ExpertSingleEvent | 3 | `boot_ffc6`, `ExpertSingleEventLogic`, `QuestRepository` |
| expert_single_event_campaign | ExpertSingleEventCampaign | 3 | `boot_ffc6`, `ExpertSingleEventCampaignLogic`, `ExpertSingleEventLogic` |
| expert_single_event_quest | ExpertSingleEventQuest | 5 | `boot_ffc6`, `ExpertSingleEventQuestFolderLogic`, `ExpertSingleEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| expert_single_event_quest_folder | ExpertSingleEventQuestFolder | 3 | `boot_ffc6`, `ExpertSingleEventLogic`, `ExpertSingleEventQuestFolderLogic` |
| feature_announcement | FeatureAnnouncement | 3 | `boot_ffc6`, `FeatureAnnouncementLogic`, `FeatureAnnouncementRepository` |
| feature_banner | FeatureBanner | 4 | `boot_ffc6`, `FeatureBannerLogic`, `FeatureBannerRepository`, `FixedFeatureBannerValues` |
| feature_banner_dialog | FeatureBannerDialog | 8 | `boot_ffc6`, `FeatureBannerDialog`, `ChangeSceneLinkFlow`, `ChangeSceneLinkKind`, `LinkSceneTool`, `MiscFeatureBannerCarouselLogic`, `SpecialFeatureBannerCarouselLogic`, `LittleAssistantScene` |
| feature_banner_misc | FeatureBannerMisc | 3 | `boot_ffc6`, `FeatureBannerMiscLogic`, `FeatureBannerMiscRepository` |
| feature_banner_secondary | FeatureBannerSecondary | 3 | `boot_ffc6`, `FeatureBannerSecondaryLogic`, `FeatureBannerSecondaryRepository` |
| feature_guide_dialog | FeatureGuideDialog | 3 | `boot_ffc6`, `FeatureGuideDialogLogic`, `FeatureGuideDialogRepository` |
| field | Field | 13 | `boot_ffc6`, `AssetResolver`, `BattleQuestBaseImpl`, `BattleQuestPeek`, `RaidEventAnimationSource`, `RaidEventTotalDamageDialog`, `FieldImpl`, `TerrainParser` |
| field_data | FieldData | 2 | `boot_ffc6`, `BattleQuestBaseImpl` |
| fire_sphere | FireSphere | 3 | `boot_ffc6`, `ZoneSourceValues`, `FireSphereSource` |
| fire_sphere_phase1_crystal | FireSpherePhase1Crystal | 3 | `boot_ffc6`, `ZoneSourceValues`, `FireSpherePhase1CrystalSource` |
| fire_sphere_phase4_micronucleus | FireSpherePhase4Micronucleus | 3 | `boot_ffc6`, `ZoneSourceValues`, `FireSpherePhase4MicronucleusSource` |
| fix_hp_basic_curve | FixHpBasicCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| fixed_party | FixedParty | 2 | `boot_ffc6`, `FixedPartyLogic` |
| flipper_skin | FlipperSkin | 4 | `boot_ffc6`, `BattleAssetPathCollectionBuilder`, `FlipperSkinLogic`, `BattleEquipmentLogic` |
| floor | Floor | 2 | `boot_ffc6`, `BattleQuestBaseImpl` |
| full_shot_image_attribute | FullShotImageAttribute | 3 | `boot_ffc6`, `GeneralCharacterLogic`, `FullShotImageAttributeTools` |
| funnel_level | FunnelLevel | 3 | `boot_ffc6`, `FunnelSource`, `TentacleSource` |
| gacha | Gacha | 3 | `boot_ffc6`, `GachaLogic`, `GachaRepository` |
| gacha_campaign | GachaCampaign | 2 | `boot_ffc6`, `GachaCampaignLogic` |
| gacha_feature_content | GachaFeatureContent | 3 | `boot_ffc6`, `GachaFeatureContentLogic`, `GachaLogic` |
| gacha_odds | GachaOdds | 3 | `CharacterGachaOddsLogic`, `GachaOddsCharacterLogic`, `GachaOddsTools` |
| gacha_rarity_odds | GachaRarityOdds | 2 | `GachaOddsTools`, `GachaRarityOddsLogic` |
| gacha_skill_preview | GachaSkillPreview | 2 | `boot_ffc6`, `GachaSkillPreviewTools` |
| gacha_ticket_type | GachaTicketType | 1 | `boot_ffc6` |
| game_system_unlock | GameSystemUnlock | 3 | `boot_ffc6`, `GameSystemUnlockConditionMessageImpl`, `GameSystemUnlockRepository` |
| game_system_unlock_condition | GameSystemUnlockCondition | 2 | `boot_ffc6`, `GameSystemUnlockRepository` |
| gender | Gender | 3 | `boot_ffc6`, `OrCharacterGroup_Impl_`, `GenderLogic` |
| general_boss | GeneralBoss | 5 | `boot_ffc6`, `ActionDslHandler`, `ZoneSourceValues`, `GeneralBossSource`, `DebugEnemyStatusLocalStore_Impl_` |
| general_boss_state | GeneralBossState | 3 | `boot_ffc6`, `GeneralBossSource`, `DebugEnemyStatusLocalStore_Impl_` |
| general_boss_variable | GeneralBossVariable | 2 | `boot_ffc6`, `GeneralBossSource` |
| general_enemy_watch | GeneralEnemyWatch | 6 | `boot_ffc6`, `ZoneSourceValues`, `GeneralBossSource`, `GeneralEnemyWatchTableTools`, `FunnelSource`, `BreakableBlockSource` |
| general_event_type | GeneralEventType | 2 | `boot_ffc6`, `GeneralEventTypeTools` |
| general_funnel | GeneralFunnel | 4 | `boot_ffc6`, `ActionDslHandler`, `FunnelSource`, `DebugEnemyStatusLocalStore_Impl_` |
| general_funnel_state | GeneralFunnelState | 3 | `boot_ffc6`, `FunnelSource`, `DebugEnemyStatusLocalStore_Impl_` |
| general_funnel_variable | GeneralFunnelVariable | 2 | `boot_ffc6`, `FunnelSource` |
| general_shop | GeneralShop | 4 | `boot_ffc6`, `GeneralShopProductLogic`, `ShopProductRepository`, `OperationShopManipulateDialog` |
| general_zako | GeneralZako | 4 | `boot_ffc6`, `ActionDslHandler`, `ZoneSourceValues`, `ZakoSource` |
| general_zako_state | GeneralZakoState | 2 | `boot_ffc6`, `ZakoSource` |
| general_zako_variable | GeneralZakoVariable | 2 | `boot_ffc6`, `ZakoSource` |
| growth_fund | GrowthFund | 3 | `boot_ffc6`, `GrowthFundItemLogic`, `GrowthFundLogic` |
| hard_multi_event | HardMultiEvent | 4 | `boot_ffc6`, `HardMultiEventLogic`, `QuestRepository`, `DummyAttentionRandomizer` |
| hard_multi_event_quest | HardMultiEventQuest | 6 | `boot_ffc6`, `HardMultiEventLogic`, `HardMultiEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools`, `MultiBattleQuestSelectRoomDummyRemote` |
| help | Help | 3 | `boot_ffc6`, `HelpDataLogic`, `HelpRepository` |
| hit_hp_basic_curve | HitHpBasicCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| hit_hp_correction_curve | HitHpCorrectionCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| holy_sphere | HolySphere | 3 | `boot_ffc6`, `ZoneSourceValues`, `HolySphereSource` |
| icon_tag | IconTag | 6 | `boot_ffc6`, `CommonLogicAssetContainer`, `ILogicAssetContainer`, `LogicAssetContainer`, `ViewAssetContainer`, `InlineIconContainer` |
| induce | Induce | 2 | `boot_ffc6`, `InduceRepository` |
| instant_item_odds | InstantItemOdds | 3 | `boot_ffc6`, `ZoneSourceValues`, `InstantItemOdds` |
| ios_payment | IosPayment | 1 | `boot_ffc6` |
| item | Item | 10 | `boot_ffc6`, `OwnedOverLimitLogic`, `ItemLogic`, `OwnedAbilitySoulRepository`, `OwnedItemRepository`, `StaminaRecoveryItemRepository`, `DummyRemote`, `OwnedEquipmentDetailWithProtectionFlow` |
| item_bonus_select | ItemBonusSelect | 3 | `boot_ffc6`, `ItemLogic`, `OwnedEquipmentDetailWithProtectionFlow` |
| item_quest_search | ItemQuestSearch | 2 | `boot_ffc6`, `ItemHowToGetQuestSearcher` |
| kraken | Kraken | 4 | `boot_ffc6`, `ZoneSourceValues`, `KrakenSource`, `TentacleSource` |
| leader_ability | LeaderAbility | 2 | `boot_ffc6`, `LeaderAbilityLogic` |
| level_cap | LevelCap | 2 | `boot_ffc6`, `CharacterLevelLogic` |
| level_required_mana_node | LevelRequiredManaNode | 2 | `boot_ffc6`, `GeneralManaNodeLogic` |
| link_scene | LinkScene | 2 | `boot_ffc6`, `LittleAssistantScene` |
| login_bonus | LoginBonus | 4 | `boot_ffc6`, `LoginBonusLogic`, `LoginBonusRepository`, `OperationLoginBonusDialog` |
| main_chapter | MainChapter | 6 | `boot_ffc6`, `AssetResolver`, `MainChapterLogic`, `QuestRepository`, `OperationQuestManipulateTools`, `QuestSelectTestScene` |
| main_quest | MainQuest | 4 | `boot_ffc6`, `MainQuestLogic`, `MainStageNodeLogic`, `QuestRepository` |
| main_stage_node | MainStageNode | 7 | `boot_ffc6`, `AssetResolver`, `EncyclopediaRepository`, `MainChapterLogic`, `MainStageNodeLogic`, `QuestRepository`, `QuestSelectTestScene` |
| main_stage_node_position | MainStageNodePosition | 2 | `boot_ffc6`, `MainChapterLogic` |
| mana_board | ManaBoard | 5 | `boot_ffc6`, `GeneralManaNodeLogic`, `ManaBoardNodeLocationProvider`, `GeneralCharacterLogic`, `OwnedCharacterLogic` |
| mana_board2_open_condition | ManaBoard2OpenCondition | 2 | `boot_ffc6`, `GeneralCharacterLogic` |
| mana_node | ManaNode | 7 | `boot_ffc6`, `GeneralManaNodeLogic`, `FixedCharacterTools`, `GeneralCharacterLogic`, `BattlePartyTools`, `DummyRemote`, `OwnedCharacterSearcherTest` |
| mana_node_awake | ManaNodeAwake | 3 | `boot_ffc6`, `GeneralManaNodeLogic`, `OwnedManaNodeLogic` |
| mana_shop | ManaShop | 4 | `boot_ffc6`, `ManaShopProductLogic`, `ShopProductRepository`, `OperationShopManipulateDialog` |
| mission_client_check | MissionClientCheck | 4 | `TypePackerResource2`, `boot_ffc6`, `MissionClientCheckInfo`, `MissionClientCheck` |
| mission_display_tag | MissionDisplayTag | 1 | `boot_ffc6` |
| multi_special_exchange_campaign | MultiSpecialExchangeCampaign | 3 | `boot_ffc6`, `MultiSpecialExchangeCampaignLogic`, `MultiSpecialExchangeCampaignRepository` |
| multi_special_exchange_campaign_character | MultiSpecialExchangeCampaignCharacter | 2 | `boot_ffc6`, `MultiSpecialExchangeCampaignLogic` |
| multiball | Multiball | 5 | `boot_ffc6`, `ActionDslHandler`, `ActionDslAssetResolver`, `DebugMultiballStatsManager`, `MultiballFactory` |
| multiball_atk_curve | MultiballAtkCurve | 2 | `boot_ffc6`, `MultiballFactory` |
| multiball_group | MultiballGroup | 8 | `boot_ffc6`, `AbilityDescriptionTools`, `DuringAbilityDescriptionGenerator`, `InstantAbilityDescriptionGenerator`, `AbilityDescriptionStringfier_Impl_`, `AbilitySlotImpl`, `BattleAbilityTriggerImpl`, `MultiballCountHandler` |
| multiball_hp_curve | MultiballHpCurve | 2 | `boot_ffc6`, `MultiballFactory` |
| multiball_level | MultiballLevel | 2 | `boot_ffc6`, `MultiballFactory` |
| news_setting | NewsSetting | 2 | `boot_ffc6`, `ConfigLogic` |
| notification | Notification | 2 | `boot_ffc6`, `NotificationLogic` |
| obtainable_instant_item | ObtainableInstantItem | 3 | `TypePackerResource2`, `boot_ffc6`, `ObtainableInstantItemSource` |
| orochi | Orochi | 3 | `boot_ffc6`, `ZoneSourceValues`, `OrochiSource` |
| orochi_ex | OrochiEx | 3 | `boot_ffc6`, `ZoneSourceValues`, `OrochiExSource` |
| orochi_ex_head | OrochiExHead | 3 | `boot_ffc6`, `ZoneSourceValues`, `OrochiExHeadSource` |
| orochi_weak_point_marker_set | OrochiWeakPointMarkerSet | 2 | `boot_ffc6`, `OrochiSource` |
| party_atk_curve | PartyAtkCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| party_attribute_ribbon_config | PartyAttributeRibbonConfig | 2 | `boot_ffc6`, `PartyRibbonSummarizer` |
| party_config | PartyConfig | 2 | `boot_ffc6`, `PartyConfigLogic` |
| party_group_color | PartyGroupColor | 2 | `boot_ffc6`, `PartyGroupColorRepository` |
| party_hp_curve | PartyHpCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| party_status_gauge_threshold | PartyStatusGaugeThreshold | 2 | `boot_ffc6`, `PartyStatusGaugeThresholdLogic` |
| pass_card_daily_mission | PassCardDailyMission | 5 | `boot_ffc6`, `PassCardDailyMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote` |
| pass_card_daily_mission_reward | PassCardDailyMissionReward | 3 | `boot_ffc6`, `PassCardDailyMissionLogic`, `MissionChangeMissionCompleteDummyRemote` |
| pass_card_event | PassCardEvent | 5 | `boot_ffc6`, `PassCardEventRepository`, `PassCardScene`, `PassCardScenePeek`, `PassCardView` |
| pass_card_event_mission | PassCardEventMission | 5 | `boot_ffc6`, `PassCardEventMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote` |
| pass_card_event_mission_reward | PassCardEventMissionReward | 3 | `boot_ffc6`, `PassCardEventMissionLogic`, `MissionChangeMissionCompleteDummyRemote` |
| pass_card_reward | PassCardReward | 3 | `boot_ffc6`, `PassCardEventRepository`, `PassCardRewardLogic` |
| pass_card_week_mission | PassCardWeekMission | 5 | `boot_ffc6`, `PassCardWeekMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote` |
| pass_card_week_mission_reward | PassCardWeekMissionReward | 3 | `boot_ffc6`, `PassCardWeekMissionLogic`, `MissionChangeMissionCompleteDummyRemote` |
| periodic_reward | PeriodicReward | 3 | `boot_ffc6`, `PeriodicRewardGroupLogic`, `PeriodicRewardLogic` |
| periodic_reward_point | PeriodicRewardPoint | 3 | `boot_ffc6`, `PeriodicRewardPointLogic`, `OperationHardMultiEventDialog` |
| phase_quest_reward | PhaseQuestReward | 2 | `boot_ffc6`, `BattlePhaseResultLogic` |
| player | Player | 2 | `boot_ffc6`, `PlayerRepository` |
| player_character | PlayerCharacter | 2 | `boot_ffc6`, `PlayerRepository` |
| player_character_mana_node | PlayerCharacterManaNode | 2 | `boot_ffc6`, `PlayerRepository` |
| player_default_name | PlayerDefaultName | 2 | `boot_ffc6`, `PlayerDefaultNameRepository` |
| player_history | PlayerHistory | 3 | `boot_ffc6`, `PlayerHistoryLogic`, `PlayerHistoryRepository` |
| player_history_card_background | PlayerHistoryCardBackground | 3 | `boot_ffc6`, `PlayerHistoryCardBackgroundLogic`, `PlayerHistoryRepository` |
| player_history_challenge_single_boss | PlayerHistoryChallengeSingleBoss | 3 | `boot_ffc6`, `PlayerHistoryChallengeSingleBossLogic`, `PlayerHistoryRepository` |
| player_history_topic | PlayerHistoryTopic | 3 | `boot_ffc6`, `PlayerHistoryRepository`, `PlayerHistoryTopicLogic` |
| player_item | PlayerItem | 2 | `boot_ffc6`, `PlayerRepository` |
| player_party | PlayerParty | 2 | `boot_ffc6`, `PlayerRepository` |
| player_party_raid_event | PlayerPartyRaidEvent | 1 | `boot_ffc6` |
| player_rank | PlayerRank | 5 | `boot_ffc6`, `PlayerLogic`, `DummyRemote`, `RealRemote`, `OperationUserManipulateDialog` |
| power_flip_action | PowerFlipAction | 2 | `boot_ffc6`, `PowerFlipLogic` |
| practice_quest | PracticeQuest | 3 | `boot_ffc6`, `PracticeQuestLogic`, `QuestRepository` |
| practice_quest_folder | PracticeQuestFolder | 3 | `boot_ffc6`, `PracticeQuestFolderLogic`, `PracticeRootLogic` |
| premium_login_bonus | PremiumLoginBonus | 2 | `boot_ffc6`, `LoginBonusProcessor` |
| premium_login_bonus_config | PremiumLoginBonusConfig | 3 | `boot_ffc6`, `PremiumLoginBonusMailedItemDialog`, `LoginBonusProcessor` |
| quest_category | QuestCategory | 2 | `boot_ffc6`, `QuestCategoryLogic` |
| quest_rank | QuestRank | 5 | `boot_ffc6`, `CommonQuestBase`, `QuestLogic`, `QuestRepository`, `HudAttentionNotification` |
| quest_set | QuestSet | 3 | `boot_ffc6`, `OrdinaryQuestBase`, `AdventEventQuestLogic` |
| race | Race | 3 | `boot_ffc6`, `OrCharacterGroup_Impl_`, `RaceLogic` |
| raid_event | RaidEvent | 4 | `boot_ffc6`, `RaidEventAnimationSource`, `RaidEventLogic`, `QuestRepository` |
| raid_event_config | RaidEventConfig | 2 | `boot_ffc6`, `LogicAssetContainer` |
| raid_event_overall_reward | RaidEventOverallReward | 3 | `boot_ffc6`, `RaidEventLogic`, `RaidEventOverallRewardLogic` |
| raid_event_quest | RaidEventQuest | 6 | `boot_ffc6`, `RaidEventLogic`, `RaidEventQuestFolderLogic`, `RaidEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| raid_event_quest_folder | RaidEventQuestFolder | 3 | `boot_ffc6`, `RaidEventLogic`, `RaidEventQuestFolderLogic` |
| raid_event_ranking_aggregation_schedule | RaidEventRankingAggregationSchedule | 1 | `boot_ffc6` |
| raid_event_ranking_reward | RaidEventRankingReward | 1 | `boot_ffc6` |
| ranking_event | RankingEvent | 3 | `boot_ffc6`, `RankingEventLogic`, `QuestRepository` |
| ranking_event_rank_asset | RankingEventRankAsset | 2 | `boot_ffc6`, `RankingEventRankLogic` |
| ranking_event_ranking_reward | RankingEventRankingReward | 3 | `boot_ffc6`, `RankingEventLogic`, `RankingEventRankLogic` |
| ranking_event_single_quest | RankingEventSingleQuest | 5 | `boot_ffc6`, `RankingEventLogic`, `RankingEventSingleQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| rare_score_reward | RareScoreReward | 3 | `boot_ffc6`, `RareScoreRewardGroupLogic`, `RareScoreRewardLogic` |
| real_incentive_mission_ingame_reward | RealIncentiveMissionIngameReward | 2 | `boot_ffc6`, `RealIncentiveActiveMissionScene` |
| real_incentive_mission_real_reward | RealIncentiveMissionRealReward | 2 | `boot_ffc6`, `RealIncentiveActiveMissionScene` |
| reason | Reason | 2 | `boot_ffc6`, `MailReasonLogic` |
| regular_mission | RegularMission | 6 | `boot_ffc6`, `RegularMissionLogic`, `MissionRepository`, `OperationAchievementDialog`, `MissionChangeMissionCompleteDummyRemote`, `MissionNameReportTestCase` |
| regular_mission_reward | RegularMissionReward | 4 | `boot_ffc6`, `RegularMissionLogic`, `DummyMissionRepository`, `MissionChangeMissionCompleteDummyRemote` |
| reward_campaign | RewardCampaign | 2 | `boot_ffc6`, `CampaignRepository` |
| reward_element_map | RewardElementMap | 2 | `boot_ffc6`, `RewardResolver` |
| rich_text_css | RichTextCss | 1 | `boot_ffc6` |
| rich_text_html | RichTextHtml | 1 | `boot_ffc6` |
| room_config | RoomConfig | 3 | `boot_ffc6`, `CommonLogicAssetContainer`, `LogicAssetContainer` |
| rush_event | RushEvent | 4 | `boot_ffc6`, `RushEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| rush_event_battle_quest_correction | RushEventBattleQuestCorrection | 2 | `boot_ffc6`, `RushEventQuestLogic` |
| rush_event_config | RushEventConfig | 2 | `boot_ffc6`, `LogicAssetContainer` |
| rush_event_quest | RushEventQuest | 5 | `boot_ffc6`, `RushEventQuestFolderLogic`, `RushEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| rush_event_quest_folder | RushEventQuestFolder | 3 | `boot_ffc6`, `RushEventLogic`, `RushEventQuestFolderLogic` |
| rush_event_ranking_aggregation_schedule | RushEventRankingAggregationSchedule | 1 | `boot_ffc6` |
| rush_event_ranking_reward | RushEventRankingReward | 1 | `boot_ffc6` |
| scenario_command | ScenarioCommand | 7 | `ScenarioCommandSource`, `StoryQuestBaseImpl`, `SoundTestScene`, `DebugStorySelectTools`, `ScenarioCommand`, `ScenarioCommandCollection`, `DebugStorySeek` |
| score_attack_border_reward | ScoreAttackBorderReward | 3 | `boot_ffc6`, `ScoreAttackBorderRewardLogic`, `ScoreAttackBorderRewardRepository` |
| score_attack_event | ScoreAttackEvent | 4 | `boot_ffc6`, `ScoreAttackEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| score_attack_event_quest | ScoreAttackEventQuest | 6 | `boot_ffc6`, `ScoreAttackEventLogic`, `ScoreAttackEventQuestFolderLogic`, `ScoreAttackEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| score_attack_event_quest_damage_check | ScoreAttackEventQuestDamageCheck | 3 | `boot_ffc6`, `ScoreAttackEventBattleQuestLogic`, `DamageCheckGaugeImpl` |
| score_attack_event_quest_field_effect | ScoreAttackEventQuestFieldEffect | 3 | `boot_ffc6`, `ScoreAttackEventBattleQuestLogic`, `ActionEvaluator` |
| score_attack_event_quest_field_value | ScoreAttackEventQuestFieldValue | 3 | `boot_ffc6`, `ModifiedFieldValueOverrideLogic`, `ScoreAttackEventBattleQuestLogic` |
| score_attack_event_quest_folder | ScoreAttackEventQuestFolder | 3 | `boot_ffc6`, `ScoreAttackEventLogic`, `ScoreAttackEventQuestFolderLogic` |
| score_attack_event_quest_funnel_zako | ScoreAttackEventQuestFunnelZako | 6 | `boot_ffc6`, `EnemySourceBase`, `StandardEnemySource`, `FunnelZakoOverrideLogic`, `ScoreAttackEventBattleQuestLogic`, `DebugEnemyStatusLocalStore_Impl_` |
| score_attack_event_quest_hit_check | ScoreAttackEventQuestHitCheck | 6 | `boot_ffc6`, `HitCountCheckOverrideLogic`, `ScoreAttackEventBattleQuestLogic`, `OrochiEx`, `OrochiExHead`, `HitCountCheck` |
| score_bonus | ScoreBonus | 4 | `boot_ffc6`, `FinalScore`, `ScoreSource`, `ScoreCalculatorImpl` |
| score_reward | ScoreReward | 3 | `boot_ffc6`, `CommonScoreRewardLogic`, `ScoreRewardGroupLogic` |
| screen_color_effect_preset | ScreenColorEffectPreset | 2 | `boot_ffc6`, `ScenarioScreenColorEffectPresetLogic` |
| shop_cost_item_schedule | ShopCostItemSchedule | 3 | `boot_ffc6`, `ShopCostItemScheduleLogic`, `ShopCostItemScheduleRepository` |
| shop_pickup_schedule | ShopPickupSchedule | 2 | `boot_ffc6`, `ShopPickupScheduleRepository` |
| short_prologue_contents | ShortPrologueContents | 2 | `boot_ffc6`, `ShortPrologueContentRepository` |
| side_story_config | SideStoryConfig | 2 | `boot_ffc6`, `EventTopScene` |
| side_story_event_list | SideStoryEventList | 2 | `boot_ffc6`, `SideStoryEventListLogic` |
| skill_invoker | SkillInvoker | 3 | `boot_ffc6`, `TerrainHandler`, `SkillInvokerSource` |
| skill_invoker_atk_curve | SkillInvokerAtkCurve | 2 | `boot_ffc6`, `SkillInvokerSource` |
| skill_invoker_level | SkillInvokerLevel | 2 | `boot_ffc6`, `SkillInvokerSource` |
| skill_preview_character | SkillPreviewCharacter | 5 | `boot_ffc6`, `GachaSkillPreviewTools`, `CharacterDetail`, `CharacterInformationScene`, `CharacterDetailCore` |
| skill_preview_quest | SkillPreviewQuest | 2 | `boot_ffc6`, `SkillPreviewQuestLogic` |
| skill_replace_string | SkillReplaceString | 5 | `boot_ffc6`, `AbilityDescriptionGenerator`, `AbilityDescriptionTools`, `InstantAbilityDescriptionGenerator`, `ActionSkillLogic` |
| solo_time_attack_clear_time_reward | SoloTimeAttackClearTimeReward | 3 | `boot_ffc6`, `SoloTimeAttackRewardLogic`, `SoloTimeAttackRewardRepository` |
| solo_time_attack_event | SoloTimeAttackEvent | 3 | `boot_ffc6`, `SoloTimeAttackEventLogic`, `QuestRepository` |
| solo_time_attack_event_quest | SoloTimeAttackEventQuest | 5 | `boot_ffc6`, `SoloTimeAttackEventLogic`, `SoloTimeAttackEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| sound_effect_asset | SoundEffectAsset | 5 | `boot_ffc6`, `AssetPathCollectionBuilder`, `SoundAssetCache`, `SoundTestScene`, `ProductionSoundSection` |
| special_exchange_campaign | SpecialExchangeCampaign | 3 | `boot_ffc6`, `SpecialExchangeCampaignLogic`, `SpecialExchangeCampaignRepository` |
| special_exchange_campaign_character | SpecialExchangeCampaignCharacter | 2 | `boot_ffc6`, `SpecialExchangeCampaignLogic` |
| special_exchange_campaign_equipment | SpecialExchangeCampaignEquipment | 2 | `boot_ffc6`, `SpecialExchangeCampaignLogic` |
| special_pack_shop | SpecialPackShop | 4 | `boot_ffc6`, `ShopProductRepository`, `SpecialPackShopProductLogic`, `OperationShopManipulateDialog` |
| special_pack_shop_recommend | SpecialPackShopRecommend | 2 | `boot_ffc6`, `ShopProductRepository` |
| stamina_campaign | StaminaCampaign | 2 | `boot_ffc6`, `CampaignRepository` |
| stance | Stance | 2 | `boot_ffc6`, `StanceLogic` |
| stance_detail_ability_soul_tier | StanceDetailAbilitySoulTier | 2 | `boot_ffc6`, `SimilarAbilitySoulAsyncSearcher` |
| stance_detail_best_status | StanceDetailBestStatus | 1 | `boot_ffc6` |
| stance_detail_character_feature | StanceDetailCharacterFeature | 1 | `boot_ffc6` |
| stance_detail_character_roll | StanceDetailCharacterRoll | 1 | `boot_ffc6` |
| stance_detail_concept | StanceDetailConcept | 1 | `boot_ffc6` |
| stance_detail_equipment_best_status | StanceDetailEquipmentBestStatus | 1 | `boot_ffc6` |
| stance_detail_equipment_limitation | StanceDetailEquipmentLimitation | 3 | `boot_ffc6`, `SimilarAbilitySoulAsyncSearcher`, `SimilarEquipmentAsyncSearcher` |
| stance_detail_equipment_roll | StanceDetailEquipmentRoll | 1 | `boot_ffc6` |
| stance_detail_equipment_tier | StanceDetailEquipmentTier | 2 | `boot_ffc6`, `SimilarEquipmentAsyncSearcher` |
| standard_boss | StandardBoss | 3 | `boot_ffc6`, `ZoneSourceValues`, `StandardBossSource` |
| standard_funnel | StandardFunnel | 3 | `boot_ffc6`, `ActionDslHandler`, `StandardFunnelSource` |
| star_crumb_exchange | StarCrumbExchange | 3 | `boot_ffc6`, `StarCrumbExchangeProductLogic`, `StarCrumbExchangeProductRepository` |
| star_crumb_exchange_cost | StarCrumbExchangeCost | 2 | `boot_ffc6`, `StarCrumbExchangeProductLogic` |
| star_grain_shop | StarGrainShop | 4 | `boot_ffc6`, `ShopProductRepository`, `StarGrainShopProductLogic`, `OperationShopManipulateDialog` |
| stars_gacha_campaign | StarsGachaCampaign | 3 | `boot_ffc6`, `StarsGachaCampaignLogic`, `StarsGachaCampaignRepository` |
| start_dash_exchange_campaign | StartDashExchangeCampaign | 3 | `boot_ffc6`, `StartDashExchangeCampaignLogic`, `StartDashExchangeCampaignRepository` |
| start_dash_exchange_campaign_exclude_character | StartDashExchangeCampaignExcludeCharacter | 2 | `boot_ffc6`, `StartDashExchangeCampaignLogic` |
| start_dash_exchange_campaign_term | StartDashExchangeCampaignTerm | 1 | `boot_ffc6` |
| start_tutorial_shortened_step | StartTutorialShortenedStep | 3 | `boot_ffc6`, `StartTutorialRepository`, `TutorialUpdateStepDummyRemote` |
| start_tutorial_step | StartTutorialStep | 3 | `boot_ffc6`, `StartTutorialRepository`, `TutorialUpdateStepDummyRemote` |
| story_character | StoryCharacter | 4 | `boot_ffc6`, `ScenarioCommandSource`, `StoryQuestBaseImpl`, `StoryCharacterLogic` |
| story_event | StoryEvent | 4 | `boot_ffc6`, `StoryEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| story_event_single_quest | StoryEventSingleQuest | 5 | `boot_ffc6`, `StoryEventLogic`, `StoryEventSingleQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| story_join_character | StoryJoinCharacter | 2 | `boot_ffc6`, `StoryJoinCharacterRepository` |
| switched_action_skill | SwitchedActionSkill | 4 | `boot_ffc6`, `ActionSkillLogic`, `DialogCharacterSkillDescriptionVariationTranslator`, `LearnWindow` |
| talky_yakumono | TalkyYakumono | 2 | `boot_ffc6`, `TalkyYakumonoSource` |
| talky_yakumono_speech_group | TalkyYakumonoSpeechGroup | 3 | `boot_ffc6`, `SpeechGroupSource`, `TalkyYakumonoImpl` |
| tentacle | Tentacle | 2 | `boot_ffc6`, `TentacleSource` |
| thunder_sphere | ThunderSphere | 3 | `boot_ffc6`, `ZoneSourceValues`, `ThunderSphereSource` |
| thunder_sphere_micronucleus | ThunderSphereMicronucleus | 3 | `boot_ffc6`, `ZoneSourceValues`, `ThunderSphereMicronucleusSource` |
| thunder_sphere_phase3_crystal | ThunderSpherePhase3Crystal | 3 | `boot_ffc6`, `ZoneSourceValues`, `ThunderSpherePhase3CrystalSource` |
| thunder_sphere_phase4_crystal | ThunderSpherePhase4Crystal | 3 | `boot_ffc6`, `ZoneSourceValues`, `ThunderSpherePhase4CrystalSource` |
| tips | Tips | 2 | `boot_ffc6`, `LoadingTipsManager` |
| tips_loading_transition | TipsLoadingTransition | 2 | `boot_ffc6`, `ConfigLogic` |
| touyakiren_ceo | TouyakirenCeo | 3 | `boot_ffc6`, `ZoneSourceValues`, `TouyakirenCeoSource` |
| tower_dungeon_event | TowerDungeonEvent | 3 | `boot_ffc6`, `TowerDungeonEventLogic`, `QuestRepository` |
| tower_dungeon_event_quest | TowerDungeonEventQuest | 5 | `boot_ffc6`, `TowerDungeonEventLogic`, `TowerDungeonEventQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| town_bgm | TownBgm | 3 | `boot_ffc6`, `AlbumDetailScene`, `AlbumScene` |
| town_bgm_set_list | TownBgmSetList | 5 | `boot_ffc6`, `AlbumDetailScene`, `AlbumDetailScenePeek`, `AlbumDetailView`, `AlbumScene` |
| town_content | TownContent | 3 | `boot_ffc6`, `TownContentLogic`, `TownContentRepository` |
| tp_basic_curve | TpBasicCurve | 2 | `boot_ffc6`, `EnemySourceBase` |
| treasure_shop | TreasureShop | 4 | `boot_ffc6`, `ShopProductRepository`, `GlobalDebugCommandInterpreter`, `OperationShopManipulateDialog` |
| treasure_shop_discount_rate | TreasureShopDiscountRate | 2 | `boot_ffc6`, `DiscountRateRepository` |
| treasure_vault_exchange_campaign | TreasureVaultExchangeCampaign | 3 | `boot_ffc6`, `TreasureVaultExchangeCampaignLogic`, `TreasureVaultExchangeCampaignRepository` |
| treasure_vault_exchange_campaign_equipment | TreasureVaultExchangeCampaignEquipment | 2 | `boot_ffc6`, `TreasureVaultExchangeCampaignLogic` |
| triggered_tutorial | TriggeredTutorial | 4 | `boot_ffc6`, `QuestRepository`, `TriggeredTutorialLogic`, `TriggeredTutorialRepository` |
| triggered_tutorial_specific_condition | TriggeredTutorialSpecificCondition | 2 | `boot_ffc6`, `TriggeredTutorialSpecificConditionRepository` |
| triggered_tutorial_specific_contents | TriggeredTutorialSpecificContents | 1 | `boot_ffc6` |
| triggered_tutorial_specific_trigger | TriggeredTutorialSpecificTrigger | 1 | `boot_ffc6` |
| trimmed_image | TrimmedImage | 2 | `boot_ffc6`, `TrimmedImageRepository` |
| tutorial_gacha | TutorialGacha | 3 | `boot_ffc6`, `GachaRepository`, `TutorialGachaLogic` |
| tutorial_quest | TutorialQuest | 4 | `boot_ffc6`, `QuestRepository`, `StartTutorialRepository`, `TutorialQuestLogic` |
| tutorial_tips | TutorialTips | 2 | `boot_ffc6`, `LoadingTipsManager` |
| ui_string | UiString | 4 | `boot_ffc6`, `AssetResolver`, `CommonLogicAssetContainer`, `LogicAssetContainer` |
| unique_condition | UniqueCondition | 2 | `boot_ffc6`, `UniqueConditionLogic` |
| upskill | Upskill | 3 | `boot_ffc6`, `DialogCharacterSkillDescriptionVariationTranslator`, `LearnWindow` |
| upskill_text | UpskillText | 3 | `boot_ffc6`, `ActionSkillUpDescriptionExtractor`, `LearnWindow` |
| video_dialog_contents | VideoDialogContents | 2 | `boot_ffc6`, `VideoDialogContentsLogic` |
| voice_asset | VoiceAsset | 5 | `boot_ffc6`, `CommonLogicAssetContainer`, `SoundAssetCache`, `SoundTestScene`, `ProductionSoundSection` |
| water_sphere | WaterSphere | 3 | `boot_ffc6`, `ZoneSourceValues`, `WaterSphereSource` |
| water_sphere_micronucleus | WaterSphereMicronucleus | 3 | `boot_ffc6`, `ZoneSourceValues`, `WaterSphereMicronucleusSource` |
| weekly_mission | WeeklyMission | 4 | `boot_ffc6`, `MissionRepository`, `WeeklyMissionLogic`, `OperationAchievementDialog` |
| weekly_mission_reward | WeeklyMissionReward | 2 | `boot_ffc6`, `WeeklyMissionLogic` |
| weight_saving_mode | WeightSavingMode | 2 | `boot_ffc6`, `ApplicationOptionLogic` |
| wind_sphere | WindSphere | 3 | `boot_ffc6`, `ZoneSourceValues`, `WindSphereSource` |
| wind_sphere_micronucleus | WindSphereMicronucleus | 3 | `boot_ffc6`, `ZoneSourceValues`, `WindSphereMicronucleusSource` |
| world_story_event | WorldStoryEvent | 4 | `boot_ffc6`, `WorldStoryEventLogic`, `QuestRepository`, `OperationShopManipulateDialog` |
| world_story_event_boss_battle_quest | WorldStoryEventBossBattleQuest | 5 | `boot_ffc6`, `WorldStoryEventBossBattleQuestLogic`, `WorldStoryEventLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| world_story_event_quest | WorldStoryEventQuest | 5 | `boot_ffc6`, `WorldStoryEventLogic`, `WorldStoryEventSingleQuestLogic`, `QuestRepository`, `OperationQuestManipulateTools` |
| zako_level | ZakoLevel | 2 | `boot_ffc6`, `ZakoSource` |
| zone | Zone | 2 | `boot_ffc6`, `ZoneMapTools` |
| zone_action | ZoneAction | 3 | `boot_ffc6`, `ZoneMapTools`, `QuestRepository` |
