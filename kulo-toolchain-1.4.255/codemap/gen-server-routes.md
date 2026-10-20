# 服务端路由 → handler 文件(自动生成 2026-10-19 22:35)

源:`D:\WF\ghmain`(只读)。前缀来自 register(…, {prefix});`${apiPrefix}` = `/api/index.php`。
「写库线索」= 该文件 import 的 data/updaters、lib/persistence、data/domains 模块。手写说明见 [server-notes.md](server-notes.md)。

## 入口 src/cn-server.ts

### `/` — src/routes/cn/playerLogin.ts
写库线索: `persistence-admission`
- GET `/admin/player-login` — src/routes/cn/playerLogin.ts:123

### `/` — src/routes/cn/abyssRecords.ts
写库线索: `domains/abyss-records`

### `/` — src/routes/cn/versionCheck.ts
- GET `/shijtswy/version/client_release_android.dis` — src/routes/cn/versionCheck.ts:32
- GET `/shijtswy/version/client_release_ios.dis` — src/routes/cn/versionCheck.ts:38

### `/` — src/routes/cn/ios-leiting.ts
- GET `/area/config.json` — src/routes/cn/ios-leiting.ts:74
- GET `/protocols/leiting/switch/switch.txt` — src/routes/cn/ios-leiting.ts:81
- GET `/myip` — src/routes/cn/ios-leiting.ts:85
- POST `/logmonitor/api/advert!getNewConfig.action` — src/routes/cn/ios-leiting.ts:89
- GET `/api/skan/query_detail` — src/routes/cn/ios-leiting.ts:93
- GET `/wf/210009_config_20200415.json` — src/routes/cn/ios-leiting.ts:109
- POST `/sync_data` — src/routes/cn/ios-leiting.ts:118

### `/api/index.php` — src/routes/cn/leitingAuth.ts
- POST `/api/index.php/channels/channel_leiting/leiting_login` — src/routes/cn/leitingAuth.ts:19
- POST `/api/index.php/channels/channel_leiting/leiting_antiaddiction_login` — src/routes/cn/leitingAuth.ts:41
- POST `/api/index.php/channels/channel_leiting/leiting_antiaddiction_logout` — src/routes/cn/leitingAuth.ts:58
- POST `/api/index.php/channels/channel_leiting/leiting_update` — src/routes/cn/leitingAuth.ts:67

### `/` — src/routes/cn/load.ts
写库线索: `domains/abyss-tower-progress`, `domains/character`, `domains/equipment`, `domains/party`, `domains/player`, `domains/quest`, `domains/quest_active`, `domains/rushEvent`, `domains/session`, `persistence-admission`
- POST `/load` — src/routes/cn/load.ts:135

### `/api/index.php/asset` — src/routes/cn/asset.ts
- POST `/api/index.php/asset/version_info` — src/routes/cn/asset.ts:408
- POST `/api/index.php/asset/get_path` — src/routes/cn/asset.ts:419

### `/` — src/routes/cn/takeOver.ts
写库线索: `domains/account`, `domains/character`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/take_over_register/get_take_over_setting` — src/routes/cn/takeOver.ts:341
- POST `/take_over_register/register_take_over_data` — src/routes/cn/takeOver.ts:356
- POST `/take_over/get_user_data_by_take_over_data` — src/routes/cn/takeOver.ts:379
- POST `/take_over/take_over_by_take_over_data` — src/routes/cn/takeOver.ts:393
- POST `/take_over/get_user_data_by_social_account` — src/routes/cn/takeOver.ts:435
- POST `/take_over/take_over_by_social_account` — src/routes/cn/takeOver.ts:437
- POST `/take_over_register/register_social_account` — src/routes/cn/takeOver.ts:439
- POST `/take_over_register/disable_social_account` — src/routes/cn/takeOver.ts:441

### `/api/index.php/tool` — src/routes/cn/tool.ts
写库线索: `domains/account`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/tool/get_header_response` — src/routes/cn/tool.ts:43
- POST `/api/index.php/tool/auth` — src/routes/cn/tool.ts:54
- POST `/api/index.php/tool/signup` — src/routes/cn/tool.ts:62

### `/api/index.php/reproduce` — src/routes/api/reproduce.ts
- POST `/api/index.php/reproduce/post` — src/routes/api/reproduce.ts:15

### `/api/index.php/tutorial` — src/routes/api/tutorial.ts
写库线索: `domains/mail`, `domains/player`, `domains/quest`, `domains/session`, `domains/tutorial`, `persistence-coordinator`
- POST `/api/index.php/tutorial/finish_trigger` — src/routes/api/tutorial.ts:39
- POST `/api/index.php/tutorial/update_step` — src/routes/api/tutorial.ts:83

### `/api/index.php/gacha` — src/routes/api/gacha.ts
写库线索: `domains/active_mission_counters`, `domains/gacha`, `domains/item`, `domains/mail`, `domains/option`, `domains/player`, `domains/player-operation-receipt`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/gacha/exchange_equipment` — src/routes/api/gacha.ts:128
- POST `/api/index.php/gacha/exchange_character` — src/routes/api/gacha.ts:210
- POST `/api/index.php/gacha/exec` — src/routes/api/gacha.ts:304

### `/api/index.php/party` — src/routes/api/party.ts
写库线索: `domains/active_mission_counters`, `domains/character`, `domains/equipment`, `domains/item`, `domains/party`, `domains/player`, `domains/publishedParty`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/party/publish` — src/routes/api/party.ts:593
- POST `/api/index.php/party/refer` — src/routes/api/party.ts:610
- POST `/api/index.php/party/edit` — src/routes/api/party.ts:670
- POST `/api/index.php/party/check_word` — src/routes/api/party.ts:884

### `/api/index.php/expod` — src/routes/api/expod.ts
写库线索: `domains/account`, `domains/active_mission_counters`, `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/expod/stack_to_exp` — src/routes/api/expod.ts:58
- POST `/api/index.php/expod/bulk_stack_to_exp` — src/routes/api/expod.ts:160
- POST `/api/index.php/expod/inject_exp` — src/routes/api/expod.ts:279

### `/api/index.php/story_quest` — src/routes/api/storyQuest.ts
写库线索: `domains/player`, `domains/quest`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/story_quest/finish` — src/routes/api/storyQuest.ts:84
- POST `/api/index.php/story_quest/finish_with_skip` — src/routes/api/storyQuest.ts:119

### `/api/index.php/option` — src/routes/api/option.ts
写库线索: `domains/option`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/option/update` — src/routes/api/option.ts:60
- POST `/api/index.php/option/update_in_battle` — src/routes/api/option.ts:62

### `/api/index.php/single_battle_quest` — src/routes/api/singleBattleQuest.ts
写库线索: `domains/abyss-tower-progress`, `domains/equipment`, `domains/item`, `domains/mail`, `domains/party`, `domains/player`, `domains/player-operation-receipt`, `domains/practice-battle-history`, `domains/quest_active`, `persistence-coordinator`
- POST `/api/index.php/single_battle_quest/finish` — src/routes/api/singleBattleQuest.ts:221
- POST `/api/index.php/single_battle_quest/abort` — src/routes/api/singleBattleQuest.ts:453
- POST `/api/index.php/single_battle_quest/start` — src/routes/api/singleBattleQuest.ts:599

### `/api/index.php/quest` — src/routes/api/quest.ts
写库线索: `domains/session`
- POST `/api/index.php/quest/get_recent_other_player_party` — src/routes/api/quest.ts:19

### `/api/index.php/attention` — src/routes/api/attention.ts
写库线索: `domains/character`, `domains/follow`, `domains/player`
- POST `/api/index.php/attention/check` — src/routes/api/attention.ts:41
- POST `/api/index.php/attention/action` — src/routes/api/attention.ts:134
- POST `/api/index.php/attention/logger` — src/routes/api/attention.ts:156

### `/api/index.php/character` — src/routes/api/character.ts
写库线索: `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/character/set_illustration_settings` — src/routes/api/character.ts:44
- POST `/api/index.php/character/over_limit` — src/routes/api/character.ts:85
- POST `/api/index.php/character/bulk_over_limit` — src/routes/api/character.ts:184
- POST `/api/index.php/character/add_character_from_town` — src/routes/api/character.ts:253

### `/api/index.php/character` — src/routes/api/character/mana.ts
写库线索: `domains/active_mission_counters`, `domains/character`, `domains/character_awake`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/character/learn_mana_node` — src/routes/api/character/mana.ts:36
- POST `/api/index.php/character/awake_mana_node` — src/routes/api/character/mana.ts:254

### `/api/index.php/character` — src/routes/api/character/bond.ts
写库线索: `domains/character`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/character/receive_bond_token` — src/routes/api/character/bond.ts:36
- POST `/api/index.php/character/open_mana_board` — src/routes/api/character/bond.ts:86

### `/api/index.php/party_group` — src/routes/api/partyGroup.ts
写库线索: `domains/account`, `domains/party`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/party_group/edit` — src/routes/api/partyGroup.ts:26

### `/api/index.php/equipment` — src/routes/api/equipment.ts
写库线索: `domains/equipment`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/equipment/upgrade` — src/routes/api/equipment.ts:93
- POST `/api/index.php/equipment/bulk_upgrade` — src/routes/api/equipment.ts:191
- POST `/api/index.php/equipment/set_protection` — src/routes/api/equipment.ts:288

### `/api/index.php/equipment` — src/routes/api/sell.ts
写库线索: `domains/equipment`, `domains/item`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/equipment/sell_equipment` — src/routes/api/sell.ts:88
- POST `/api/index.php/equipment/sell_stack` — src/routes/api/sell.ts:152
- POST `/api/index.php/equipment/bulk_sell_stack` — src/routes/api/sell.ts:217

### `/api/index.php/ex_boost` — src/routes/api/exBoost.ts
写库线索: `domains/account`, `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/ex_boost/select` — src/routes/api/exBoost.ts:285
- POST `/api/index.php/ex_boost/draw` — src/routes/api/exBoost.ts:345
- POST `/api/index.php/ex_boost/first_draw` — src/routes/api/exBoost.ts:346

### `/api/index.php/box_gacha` — src/routes/api/boxGacha.ts
写库线索: `domains/account`, `domains/boxGacha`, `domains/equipment`, `domains/item`, `domains/party`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/box_gacha/reset` — src/routes/api/boxGacha.ts:176
- POST `/api/index.php/box_gacha/close` — src/routes/api/boxGacha.ts:247
- POST `/api/index.php/box_gacha/exec` — src/routes/api/boxGacha.ts:319
- POST `/api/index.php/box_gacha/get_box_list` — src/routes/api/boxGacha.ts:500

### `/api/index.php/shop` — src/routes/api/shop.ts
写库线索: `domains/account`, `domains/active_mission_counters`, `domains/degree`, `domains/equipment`, `domains/item`, `domains/player`, `domains/session`, `domains/shopPurchase`, `persistence-coordinator`
- POST `/api/index.php/shop/buy` — src/routes/api/shop.ts:325
- POST `/api/index.php/shop/get_sales_list` — src/routes/api/shop.ts:698
- POST `/api/index.php/shop/recover_stamina` — src/routes/api/shop.ts:826
- POST `/api/index.php/shop/get_campaign_lineup_id` — src/routes/api/shop.ts:1368
- POST `/api/index.php/shop/set_campaign_lineup_id` — src/routes/api/shop.ts:1382

### `/api/index.php/exchange` — src/routes/api/exchange.ts
写库线索: `domains/character`, `domains/equipment`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/exchange/star_crumb` — src/routes/api/exchange.ts:27

### `/api/index.php/encyclopedia` — src/routes/api/encyclopedia.ts
写库线索: `domains/encyclopedia`, `domains/item`, `domains/session`
- POST `/api/index.php/encyclopedia/read_keyword` — src/routes/api/encyclopedia.ts:36
- POST `/api/index.php/encyclopedia/unlock_keyword` — src/routes/api/encyclopedia.ts:72
- POST `/api/index.php/encyclopedia/index` — src/routes/api/encyclopedia.ts:143

### `/api/index.php/mail` — src/routes/api/mail.ts
写库线索: `domains/character`, `domains/degree`, `domains/equipment`, `domains/item`, `domains/mail`, `domains/player`, `domains/player-operation-receipt`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/mail/index` — src/routes/api/mail.ts:281
- POST `/api/index.php/mail/receive` — src/routes/api/mail.ts:315
- POST `/api/index.php/mail/receive_all` — src/routes/api/mail.ts:372

### `/api/index.php/ranking_event` — src/routes/api/rankingEvent.ts
写库线索: `domains/quest`, `domains/session`
- POST `/api/index.php/ranking_event/get_summary` — src/routes/api/rankingEvent.ts:75
- POST `/api/index.php/ranking_event/receive_reward` — src/routes/api/rankingEvent.ts:115

### `/api/index.php/mission` — src/routes/api/mission.ts
写库线索: `domains/mail`, `domains/mission`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/mission/get_mission_progress` — src/routes/api/mission.ts:37
- POST `/api/index.php/mission/update_mission_progress` — src/routes/api/mission.ts:211

### `/api/index.php/active_mission` — src/routes/api/activeMission.ts
写库线索: `domains/mail`, `domains/mission`, `domains/player`, `domains/quest`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/active_mission/receive` — src/routes/api/activeMission.ts:19

### `/api/index.php/Pass_card` — src/routes/api/passCard.ts
写库线索: `domains/mail`, `domains/pass-card`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/Pass_card/get_pass_card` — src/routes/api/passCard.ts:78
- POST `/api/index.php/Pass_card/receive_all` — src/routes/api/passCard.ts:101

### `/api/index.php/payment` — src/routes/api/payment.ts
写库线索: `domains/payment`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/payment/item_list` — src/routes/api/payment.ts:34
- POST `/api/index.php/payment/start` — src/routes/api/payment.ts:57
- POST `/api/index.php/payment/finish` — src/routes/api/payment.ts:104
- POST `/api/index.php/payment/report_purchase_result` — src/routes/api/payment.ts:251

### `/api/index.php/news` — src/routes/api/news.ts
写库线索: `domains/news`, `domains/session`
- POST `/api/index.php/news/index` — src/routes/api/news.ts:175
- POST `/api/index.php/news/get_info` — src/routes/api/news.ts:176
- POST `/api/index.php/news/system_index` — src/routes/api/news.ts:177
- POST `/api/index.php/news/get_system_info` — src/routes/api/news.ts:178
- POST `/api/index.php/news/latest_forced` — src/routes/api/news.ts:179
- POST `/api/index.php/news/latest_forced_system` — src/routes/api/news.ts:181

### `/api/index.php/event/raid` — src/routes/api/raidEvent.ts
写库线索: `domains/character`, `domains/mail`, `domains/party`, `domains/player`, `domains/rushEvent`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/event/raid/summary` — src/routes/api/raidEvent.ts:71
- POST `/api/index.php/event/raid/get_boss` — src/routes/api/raidEvent.ts:167
- POST `/api/index.php/event/raid/ranking_reward` — src/routes/api/raidEvent.ts:203
- POST `/api/index.php/event/raid/party` — src/routes/api/raidEvent.ts:242
- POST `/api/index.php/event/raid/ranking` — src/routes/api/raidEvent.ts:335
- POST `/api/index.php/event/raid/ranking/party` — src/routes/api/raidEvent.ts:357
- POST `/api/index.php/event/raid/battle/start` — src/routes/api/raidEvent.ts:377
- POST `/api/index.php/event/raid/select_folder` — src/routes/api/raidEvent.ts:454
- POST `/api/index.php/event/raid/reset` — src/routes/api/raidEvent.ts:482

### `/api/index.php/event/rush` — src/routes/api/rushEvent.ts
写库线索: `domains/abyss-tower-progress`, `domains/account`, `domains/character`, `domains/party`, `domains/player`, `domains/rushEvent`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/event/rush/summary` — src/routes/api/rushEvent.ts:198
- POST `/api/index.php/event/rush/select_folder` — src/routes/api/rushEvent.ts:280
- POST `/api/index.php/event/rush/ranking` — src/routes/api/rushEvent.ts:404
- POST `/api/index.php/event/rush/ranking/played_party` — src/routes/api/rushEvent.ts:476
- POST `/api/index.php/event/rush/aggregated_time` — src/routes/api/rushEvent.ts:531
- POST `/api/index.php/event/rush/party` — src/routes/api/rushEvent.ts:565
- POST `/api/index.php/event/rush/leaderboard` — src/routes/api/rushEvent.ts:649
- POST `/api/index.php/event/rush/battle/start` — src/routes/api/rushEvent.ts:693
- POST `/api/index.php/event/rush/reset` — src/routes/api/rushEvent.ts:842
- POST `/api/index.php/event/rush/reward` — src/routes/api/rushEvent.ts:942
- POST `/api/index.php/event/rush/endless_battle` — src/routes/api/rushEvent.ts:1011

### `/api/index.php/carnival_event` — src/routes/api/carnivalEvent.ts
写库线索: `domains/carnivalEvent`, `domains/party`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/carnival_event/index` — src/routes/api/carnivalEvent.ts:116
- POST `/api/index.php/carnival_event/get_party` — src/routes/api/carnivalEvent.ts:167

### `/api/index.php/contents_guide` — src/routes/api/contentsGuide.ts
写库线索: `domains/player`, `domains/session`
- POST `/api/index.php/contents_guide/start` — src/routes/api/contentsGuide.ts:29

### `/api/index.php/profile` — src/routes/api/profile.ts
写库线索: `domains/degree`, `domains/option`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/profile/get_my_profile` — src/routes/api/profile.ts:50
- POST `/api/index.php/profile/get_profile` — src/routes/api/profile.ts:106
- POST `/api/index.php/profile/get_last_login_region` — src/routes/api/profile.ts:146
- POST `/api/index.php/profile/get_degree_list` — src/routes/api/profile.ts:170
- POST `/api/index.php/profile/update_degree` — src/routes/api/profile.ts:209
- POST `/api/index.php/profile/update_profile_settings` — src/routes/api/profile.ts:270
- POST `/api/index.php/profile/update_comment` — src/routes/api/profile.ts:323
- POST `/api/index.php/profile/rename` — src/routes/api/profile.ts:360

### `/api/index.php/follow` — src/routes/api/follow.ts
写库线索: `domains/follow`, `domains/session`
- POST `/api/index.php/follow/lists` — src/routes/api/follow.ts:47
- POST `/api/index.php/follow/add` — src/routes/api/follow.ts:60
- POST `/api/index.php/follow/delete` — src/routes/api/follow.ts:75
- POST `/api/index.php/follow/delete_followed` — src/routes/api/follow.ts:85
- POST `/api/index.php/follow/bulk_edit` — src/routes/api/follow.ts:95
- POST `/api/index.php/follow/search_id` — src/routes/api/follow.ts:123
- POST `/api/index.php/follow/search_twitter` — src/routes/api/follow.ts:137

### `/api/index.php/sns` — src/routes/api/sns.ts
写库线索: `domains/session`
- POST `/api/index.php/sns/get` — src/routes/api/sns.ts:23
- POST `/api/index.php/sns/update_twitter` — src/routes/api/sns.ts:36

### `/api/index.php/history` — src/routes/api/history.ts
写库线索: `domains/mail`, `domains/practice-battle-history`, `domains/session`
- POST `/api/index.php/history/receive` — src/routes/api/history.ts:10
- POST `/api/index.php/history/practice_battle` — src/routes/api/history.ts:48
- POST `/api/index.php/history/score_attack_event_battle` — src/routes/api/history.ts:70

### `/api/index.php/player_history` — src/routes/api/playerHistory.ts
写库线索: `domains/character`, `domains/degree`, `domains/player`, `domains/player-history`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/player_history/index` — src/routes/api/playerHistory.ts:126
- POST `/api/index.php/player_history/edit` — src/routes/api/playerHistory.ts:170

### `/api/index.php/comic` — src/routes/api/comic.ts
写库线索: `domains/session`
- GET `/api/index.php/comic/image` — src/routes/api/comic.ts:49
- POST `/api/index.php/comic/get_list` — src/routes/api/comic.ts:97

### `/api/index.php/quest` — src/routes/api/questUnlock.ts
写库线索: `domains/item`, `domains/player`, `domains/quest`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/quest/unlock` — src/routes/api/questUnlock.ts:20

### `/api/index.php/item` — src/routes/api/item.ts
写库线索: `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/item/use_item` — src/routes/api/item.ts:25
- POST `/api/index.php/item/sell` — src/routes/api/item.ts:186

### `/api/index.php/lounge` — src/routes/api/lounge.ts
写库线索: `domains/character`, `domains/player`, `domains/session`
- POST `/api/index.php/lounge/get_list` — src/routes/api/lounge.ts:129
- POST `/api/index.php/lounge/create` — src/routes/api/lounge.ts:152
- POST `/api/index.php/lounge/prepare` — src/routes/api/lounge.ts:183
- POST `/api/index.php/lounge/select` — src/routes/api/lounge.ts:201
- POST `/api/index.php/lounge/search` — src/routes/api/lounge.ts:218
- POST `/api/index.php/lounge/restore` — src/routes/api/lounge.ts:245
- POST `/api/index.php/lounge/share` — src/routes/api/lounge.ts:264

### `/api/index.php/multi_special_exchange` — src/routes/api/multiSpecialExchange.ts
写库线索: `domains/campaign`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/multi_special_exchange/exchange_character` — src/routes/api/multiSpecialExchange.ts:121

### `/api/index.php/how_to_get` — src/routes/api/howToGet.ts
写库线索: `domains/degree`, `domains/session`, `domains/shopPurchase`
- POST `/api/index.php/how_to_get/get_list` — src/routes/api/howToGet.ts:31

### `/` — src/routes/web/index.ts
- GET `/` — src/routes/web/index.ts:11
- GET `/seeds` — src/routes/web/index.ts:19

### `/player` — src/routes/web/player.ts
写库线索: `domains/account`, `domains/character`, `domains/equipment`, `domains/item`, `domains/player`, `domains/quest`, `domains/session`
- GET `/player/` — src/routes/web/player.ts:42
- GET `/player/:playerId` — src/routes/web/player.ts:169

### `/` — src/routes/web/mail.ts
- GET `/mail` — src/routes/web/mail.ts:9

### `/api` — src/routes/web_api/index.ts

### `/api/player` — src/routes/web_api/player.ts
写库线索: `domains/character`, `domains/equipment`, `domains/item`, `domains/mail`, `domains/mission`, `domains/party`, `domains/player`, `domains/quest`, `persistence-admission`, `persistence-coordinator`
- GET `/api/player/` — src/routes/web_api/player.ts:66
- GET `/api/player/:id/detail` — src/routes/web_api/player.ts:79
- GET `/api/player/save` — src/routes/web_api/player.ts:166
- POST `/api/player/save` — src/routes/web_api/player.ts:206
- POST `/api/player/:id/clear_ex_boost` — src/routes/web_api/player.ts:329
- POST `/api/player/:id/reset_parties` — src/routes/web_api/player.ts:340
- POST `/api/player/:id/clear_mail` — src/routes/web_api/player.ts:355
- POST `/api/player/:id/clear_receive_history` — src/routes/web_api/player.ts:365
- POST `/api/player/:id/repair_unison_unlock` — src/routes/web_api/player.ts:376
- POST `/api/player/:id/character` — src/routes/web_api/player.ts:415
- DELETE `/api/player/:id/character/:code` — src/routes/web_api/player.ts:436
- POST `/api/player/:id/item` — src/routes/web_api/player.ts:464
- DELETE `/api/player/:id/item/:itemId` — src/routes/web_api/player.ts:487
- DELETE `/api/player/:id/quest_progress/:section/:quest_id` — src/routes/web_api/player.ts:504
- DELETE `/api/player/:id/quest_progress` — src/routes/web_api/player.ts:519
- DELETE `/api/player/:id/drawn_quest/:category/:quest_id` — src/routes/web_api/player.ts:531
- DELETE `/api/player/:id/drawn_quest` — src/routes/web_api/player.ts:546
- POST `/api/player/:id/reset_challenge` — src/routes/web_api/player.ts:556
- DELETE `/api/player/:id/mail` — src/routes/web_api/player.ts:587
- POST `/api/player/:id/daily_reset` — src/routes/web_api/player.ts:602
- POST `/api/player/:id/weekly_reset` — src/routes/web_api/player.ts:632

### `/api/server` — src/routes/web_api/server.ts
写库线索: `domains/account`, `domains/admin-player`, `domains/character`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/server/databaseBackup` — src/routes/web_api/server.ts:430
- GET `/api/server/status` — src/routes/web_api/server.ts:448
- GET `/api/server/currentTime` — src/routes/web_api/server.ts:516
- GET `/api/server/resetTime` — src/routes/web_api/server.ts:525
- GET `/api/server/time` — src/routes/web_api/server.ts:535
- GET `/api/server/clairvoyance/gacha` — src/routes/web_api/server.ts:572
- GET `/api/server/accounts` — src/routes/web_api/server.ts:583
- GET `/api/server/defaultSave` — src/routes/web_api/server.ts:677
- POST `/api/server/defaultSave` — src/routes/web_api/server.ts:682
- DELETE `/api/server/defaultSave` — src/routes/web_api/server.ts:709
- POST `/api/server/selectAccount` — src/routes/web_api/server.ts:717
- POST `/api/server/activateSave` — src/routes/web_api/server.ts:730
- POST `/api/server/newSave` — src/routes/web_api/server.ts:750
- POST `/api/server/deleteSave` — src/routes/web_api/server.ts:793
- POST `/api/server/deleteAccount` — src/routes/web_api/server.ts:828
- GET `/api/server/deleteUnnotedAccounts/status` — src/routes/web_api/server.ts:841
- POST `/api/server/deleteUnnotedAccounts` — src/routes/web_api/server.ts:849
- POST `/api/server/renameSave` — src/routes/web_api/server.ts:906
- POST `/api/server/cloneSave` — src/routes/web_api/server.ts:919
- POST `/api/server/account/rename` — src/routes/web_api/server.ts:971
- POST `/api/server/account/takeover-password/reset` — src/routes/web_api/server.ts:986
- POST `/api/server/device/rename` — src/routes/web_api/server.ts:1012

### `/api/mail` — src/routes/web_api/mail.ts
写库线索: `domains/account`, `domains/mail`, `domains/player`, `persistence-coordinator`
- GET `/api/mail/daily` — src/routes/web_api/mail.ts:91
- POST `/api/mail/daily/run` — src/routes/web_api/mail.ts:108
- POST `/api/mail/send` — src/routes/web_api/mail.ts:123
- GET `/api/mail/history` — src/routes/web_api/mail.ts:261

### `/api/lookup` — src/routes/web_api/lookup.ts
- GET `/api/lookup/characters` — src/routes/web_api/lookup.ts:63
- GET `/api/lookup/items` — src/routes/web_api/lookup.ts:67
- GET `/api/lookup/equipment` — src/routes/web_api/lookup.ts:71
- GET `/api/lookup/quests` — src/routes/web_api/lookup.ts:75

### `/api/leaderboards` — src/routes/web_api/leaderboards.ts
写库线索: `domains/leaderboard`, `persistence-admission`, `persistence-coordinator`
- GET `/api/leaderboards/` — src/routes/web_api/leaderboards.ts:46
- GET `/api/leaderboards/:key` — src/routes/web_api/leaderboards.ts:54
- POST `/api/leaderboards/:key/settle` — src/routes/web_api/leaderboards.ts:158
- POST `/api/leaderboards/:key/rollover` — src/routes/web_api/leaderboards.ts:170

### `/api/news` — src/routes/web_api/news.ts
写库线索: `domains/news`, `persistence-coordinator`
- GET `/api/news/` — src/routes/web_api/news.ts:45
- POST `/api/news/items` — src/routes/web_api/news.ts:47
- DELETE `/api/news/items/:id` — src/routes/web_api/news.ts:82
- PUT `/api/news/popup` — src/routes/web_api/news.ts:101
- POST `/api/news/popup/reset` — src/routes/web_api/news.ts:113

### `/api/server/diagnostics` — src/routes/web_api/diagnostics.ts
- GET `/api/server/diagnostics/realtime` — src/routes/web_api/diagnostics.ts:6
- GET `/api/server/diagnostics/battles` — src/routes/web_api/diagnostics.ts:12
- POST `/api/server/diagnostics/realtime` — src/routes/web_api/diagnostics.ts:17

### `/api/seeds` — src/routes/web_api/seeds.ts
- GET `/api/seeds/stats` — src/routes/web_api/seeds.ts:36
- GET `/api/seeds/list` — src/routes/web_api/seeds.ts:60
- POST `/api/seeds/mode` — src/routes/web_api/seeds.ts:69
- POST `/api/seeds/tag` — src/routes/web_api/seeds.ts:76
- POST `/api/seeds/test-seed` — src/routes/web_api/seeds.ts:86
- DELETE `/api/seeds/test-seed` — src/routes/web_api/seeds.ts:93

### `/api/mod-admin` — src/routes/api/modAdmin.ts
- GET `/api/mod-admin/ping` — src/routes/api/modAdmin.ts:5

## 入口 src/server.ts

### `/` — src/routes/api/index.ts
写库线索: `domains/boxGacha`, `domains/campaign`, `domains/character`, `domains/equipment`, `domains/gacha`, `domains/item`, `domains/mission`, `domains/option`, `domains/party`, `domains/player`
- POST `/load` — src/routes/api/index.ts:38

### `/api/index.php/asset` — src/routes/api/asset.ts
- POST `/api/index.php/asset/version_info` — src/routes/api/asset.ts:179
- POST `/api/index.php/asset/get_path` — src/routes/api/asset.ts:245

### `/api/index.php/tool` — src/routes/api/tool.ts
写库线索: `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/tool/get_header_response` — src/routes/api/tool.ts:23
- POST `/api/index.php/tool/signup` — src/routes/api/tool.ts:36

### `/openapi/service` — src/routes/openapi.ts
写库线索: `domains/account`, `domains/player`, `domains/session`
- POST `/openapi/service/v3/util/country/get` — src/routes/openapi.ts:122
- POST `/openapi/service/v4/device/accessToken/create` — src/routes/openapi.ts:128
- POST `/openapi/service/v3/zat/login` — src/routes/openapi.ts:137
- POST `/openapi/service/v3/push/token/register` — src/routes/openapi.ts:224
- POST `/openapi/service/v3/agreement/getForLogin` — src/routes/openapi.ts:232
- POST `/openapi/service/v3/player/heartbeat` — src/routes/openapi.ts:266
- POST `/openapi/service/v4/auth/loginDevice` — src/routes/openapi.ts:271

### `/infodesk` — src/routes/infodesk.ts
- GET `/infodesk/v2/appGroup` — src/routes/infodesk.ts:5
- GET `/infodesk/v2/app` — src/routes/infodesk.ts:67

## 未经 register 链解析到的路由文件

- src/cn-server.ts: POST `${apiPrefix}/assetintitle/version_info_in_title`:273, POST `${apiPrefix}/tool/check_social_link_enable`:284, POST `${apiPrefix}/tool/check_enable_gift`:289, POST `${apiPrefix}/tool/contact_active`:293, POST `${apiPrefix}/tool/custom_notify`:297, POST `${apiPrefix}/channels/channel_leiting_pay/query_unfinish_order`:301, POST `${apiPrefix}/channels/channel_leiting_pay/query_purcharge`:305, POST `${apiPrefix}/channels/channel_leiting_pay/set_unfinish_order_status`:309, POST `${apiPrefix}/episode_trial_reading/finish`:314, GET `/debug`:372, POST `/debug`:378, POST `/crash`:385
- src/lib/custom-cdn-resource-routes.ts: GET `/patch/cn/dummy/download/production/${root}/:prefix/:hash`:12
- src/lib/management-auth.ts: GET `/admin-login`:166, POST `/admin-login`:172, POST `/admin-logout`:190
- src/multi/http/battle.ts: POST `/start`:215, POST `/finish`:420, POST `/abort`:679, POST `/play_continue`:794
- src/multi/http/lobby.ts: POST `/create_room_failure`:53, POST `/get_rooms`:57, POST `/create_room`:74, POST `/search_room`:92, POST `/select_room`:106
- src/multi/http/room.ts: POST `/prepare`:73, POST `/summon`:87, POST `/restore_room`:98, POST `/share_room`:106, POST `/disband_room`:118
- src/multi/http/social.ts: POST `/verify_access_token`:14, POST `/micro_community`:56, POST `/publish_room`:65
