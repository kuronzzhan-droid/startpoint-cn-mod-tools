# 服务端路由 → handler 文件(自动生成 2026-10-14 19:13)

源:`D:\WF\startpoint-cn-kulo`(只读)。前缀来自 register(…, {prefix});`${apiPrefix}` = `/api/index.php`。
「写库线索」= 该文件 import 的 data/updaters、lib/persistence、data/domains 模块。手写说明见 [server-notes.md](server-notes.md)。

## 入口 src/cn-server.ts

### `/` — src/routes/cn/playerLogin.ts
- GET `/admin/player-login` — src/routes/cn/playerLogin.ts:82

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
写库线索: `domains/abyss-tower-progress`, `domains/character`, `domains/equipment`, `domains/party`, `domains/player`, `domains/quest`, `domains/quest_active`, `domains/rushEvent`, `domains/session`, `persistence-coordinator`
- POST `/load` — src/routes/cn/load.ts:133

### `/api/index.php/asset` — src/routes/cn/asset.ts
- POST `/api/index.php/asset/version_info` — src/routes/cn/asset.ts:288
- POST `/api/index.php/asset/get_path` — src/routes/cn/asset.ts:299

### `/` — src/routes/cn/takeOver.ts
写库线索: `domains/account`, `domains/character`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/take_over_register/get_take_over_setting` — src/routes/cn/takeOver.ts:304
- POST `/take_over_register/register_take_over_data` — src/routes/cn/takeOver.ts:319
- POST `/take_over/get_user_data_by_take_over_data` — src/routes/cn/takeOver.ts:342
- POST `/take_over/take_over_by_take_over_data` — src/routes/cn/takeOver.ts:356
- POST `/take_over/get_user_data_by_social_account` — src/routes/cn/takeOver.ts:398
- POST `/take_over/take_over_by_social_account` — src/routes/cn/takeOver.ts:400
- POST `/take_over_register/register_social_account` — src/routes/cn/takeOver.ts:402
- POST `/take_over_register/disable_social_account` — src/routes/cn/takeOver.ts:404

### `/api/index.php/tool` — src/routes/cn/tool.ts
写库线索: `domains/account`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/tool/get_header_response` — src/routes/cn/tool.ts:39
- POST `/api/index.php/tool/auth` — src/routes/cn/tool.ts:50
- POST `/api/index.php/tool/signup` — src/routes/cn/tool.ts:58

### `/api/index.php/reproduce` — src/routes/api/reproduce.ts
- POST `/api/index.php/reproduce/post` — src/routes/api/reproduce.ts:15

### `/api/index.php/tutorial` — src/routes/api/tutorial.ts
写库线索: `domains/mail`, `domains/player`, `domains/quest`, `domains/session`, `domains/tutorial`, `persistence-coordinator`
- POST `/api/index.php/tutorial/finish_trigger` — src/routes/api/tutorial.ts:39
- POST `/api/index.php/tutorial/update_step` — src/routes/api/tutorial.ts:83

### `/api/index.php/gacha` — src/routes/api/gacha.ts
写库线索: `domains/active_mission_counters`, `domains/gacha`, `domains/item`, `domains/mail`, `domains/option`, `domains/player`, `domains/player-operation-receipt`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/gacha/exchange_equipment` — src/routes/api/gacha.ts:117
- POST `/api/index.php/gacha/exchange_character` — src/routes/api/gacha.ts:199
- POST `/api/index.php/gacha/exec` — src/routes/api/gacha.ts:293

### `/api/index.php/party` — src/routes/api/party.ts
写库线索: `domains/active_mission_counters`, `domains/character`, `domains/equipment`, `domains/item`, `domains/party`, `domains/player`, `domains/publishedParty`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/party/publish` — src/routes/api/party.ts:592
- POST `/api/index.php/party/refer` — src/routes/api/party.ts:609
- POST `/api/index.php/party/edit` — src/routes/api/party.ts:669
- POST `/api/index.php/party/check_word` — src/routes/api/party.ts:854

### `/api/index.php/expod` — src/routes/api/expod.ts
写库线索: `domains/account`, `domains/active_mission_counters`, `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/expod/stack_to_exp` — src/routes/api/expod.ts:57
- POST `/api/index.php/expod/bulk_stack_to_exp` — src/routes/api/expod.ts:159
- POST `/api/index.php/expod/inject_exp` — src/routes/api/expod.ts:278

### `/api/index.php/story_quest` — src/routes/api/storyQuest.ts
写库线索: `domains/player`, `domains/quest`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/story_quest/finish` — src/routes/api/storyQuest.ts:84
- POST `/api/index.php/story_quest/finish_with_skip` — src/routes/api/storyQuest.ts:119

### `/api/index.php/option` — src/routes/api/option.ts
写库线索: `domains/option`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/option/update` — src/routes/api/option.ts:60
- POST `/api/index.php/option/update_in_battle` — src/routes/api/option.ts:62

### `/api/index.php/single_battle_quest` — src/routes/api/singleBattleQuest.ts
写库线索: `domains/abyss-tower-progress`, `domains/equipment`, `domains/item`, `domains/mail`, `domains/party`, `domains/player`, `domains/practice-battle-history`, `domains/quest_active`, `persistence-coordinator`, `persistence/command-names`
- POST `/api/index.php/single_battle_quest/finish` — src/routes/api/singleBattleQuest.ts:214
- POST `/api/index.php/single_battle_quest/abort` — src/routes/api/singleBattleQuest.ts:387
- POST `/api/index.php/single_battle_quest/start` — src/routes/api/singleBattleQuest.ts:522

### `/api/index.php/quest` — src/routes/api/quest.ts
写库线索: `domains/session`
- POST `/api/index.php/quest/get_recent_other_player_party` — src/routes/api/quest.ts:19

### `/api/index.php/attention` — src/routes/api/attention.ts
写库线索: `domains/character`, `domains/follow`, `domains/player`
- POST `/api/index.php/attention/check` — src/routes/api/attention.ts:40
- POST `/api/index.php/attention/action` — src/routes/api/attention.ts:150
- POST `/api/index.php/attention/logger` — src/routes/api/attention.ts:172

### `/api/index.php/character` — src/routes/api/character.ts
写库线索: `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/character/set_illustration_settings` — src/routes/api/character.ts:43
- POST `/api/index.php/character/over_limit` — src/routes/api/character.ts:84
- POST `/api/index.php/character/bulk_over_limit` — src/routes/api/character.ts:176
- POST `/api/index.php/character/add_character_from_town` — src/routes/api/character.ts:245

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
- POST `/api/index.php/equipment/upgrade` — src/routes/api/equipment.ts:92
- POST `/api/index.php/equipment/bulk_upgrade` — src/routes/api/equipment.ts:179
- POST `/api/index.php/equipment/set_protection` — src/routes/api/equipment.ts:272

### `/api/index.php/equipment` — src/routes/api/sell.ts
写库线索: `domains/equipment`, `domains/item`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/equipment/sell_equipment` — src/routes/api/sell.ts:45
- POST `/api/index.php/equipment/sell_stack` — src/routes/api/sell.ts:126
- POST `/api/index.php/equipment/bulk_sell_stack` — src/routes/api/sell.ts:210

### `/api/index.php/ex_boost` — src/routes/api/exBoost.ts
写库线索: `domains/account`, `domains/character`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/ex_boost/select` — src/routes/api/exBoost.ts:278
- POST `/api/index.php/ex_boost/draw` — src/routes/api/exBoost.ts:338
- POST `/api/index.php/ex_boost/first_draw` — src/routes/api/exBoost.ts:339

### `/api/index.php/box_gacha` — src/routes/api/boxGacha.ts
写库线索: `domains/account`, `domains/boxGacha`, `domains/equipment`, `domains/item`, `domains/party`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/box_gacha/reset` — src/routes/api/boxGacha.ts:146
- POST `/api/index.php/box_gacha/close` — src/routes/api/boxGacha.ts:218
- POST `/api/index.php/box_gacha/exec` — src/routes/api/boxGacha.ts:276
- POST `/api/index.php/box_gacha/get_box_list` — src/routes/api/boxGacha.ts:478

### `/api/index.php/shop` — src/routes/api/shop.ts
写库线索: `domains/account`, `domains/active_mission_counters`, `domains/degree`, `domains/equipment`, `domains/item`, `domains/player`, `domains/session`, `domains/shopPurchase`, `persistence-coordinator`
- POST `/api/index.php/shop/buy` — src/routes/api/shop.ts:325
- POST `/api/index.php/shop/get_sales_list` — src/routes/api/shop.ts:745
- POST `/api/index.php/shop/recover_stamina` — src/routes/api/shop.ts:873
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
- POST `/api/index.php/mission/get_mission_progress` — src/routes/api/mission.ts:38
- POST `/api/index.php/mission/update_mission_progress` — src/routes/api/mission.ts:212

### `/api/index.php/active_mission` — src/routes/api/activeMission.ts
写库线索: `domains/mail`, `domains/mission`, `domains/player`, `domains/quest`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/active_mission/receive` — src/routes/api/activeMission.ts:18

### `/api/index.php/Pass_card` — src/routes/api/passCard.ts
写库线索: `domains/mail`, `domains/pass-card`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/Pass_card/get_pass_card` — src/routes/api/passCard.ts:78
- POST `/api/index.php/Pass_card/receive_all` — src/routes/api/passCard.ts:101

### `/api/index.php/payment` — src/routes/api/payment.ts
写库线索: `domains/payment`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/payment/item_list` — src/routes/api/payment.ts:32
- POST `/api/index.php/payment/start` — src/routes/api/payment.ts:55
- POST `/api/index.php/payment/finish` — src/routes/api/payment.ts:102
- POST `/api/index.php/payment/report_purchase_result` — src/routes/api/payment.ts:227

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
- POST `/api/index.php/follow/lists` — src/routes/api/follow.ts:46
- POST `/api/index.php/follow/add` — src/routes/api/follow.ts:59
- POST `/api/index.php/follow/delete` — src/routes/api/follow.ts:74
- POST `/api/index.php/follow/delete_followed` — src/routes/api/follow.ts:84
- POST `/api/index.php/follow/bulk_edit` — src/routes/api/follow.ts:94
- POST `/api/index.php/follow/search_id` — src/routes/api/follow.ts:112
- POST `/api/index.php/follow/search_twitter` — src/routes/api/follow.ts:126

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
- POST `/api/index.php/player_history/index` — src/routes/api/playerHistory.ts:125
- POST `/api/index.php/player_history/edit` — src/routes/api/playerHistory.ts:169

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
- POST `/api/index.php/item/sell` — src/routes/api/item.ts:165

### `/api/index.php/lounge` — src/routes/api/lounge.ts
写库线索: `domains/character`, `domains/player`, `domains/session`
- POST `/api/index.php/lounge/get_list` — src/routes/api/lounge.ts:111
- POST `/api/index.php/lounge/create` — src/routes/api/lounge.ts:126
- POST `/api/index.php/lounge/prepare` — src/routes/api/lounge.ts:156
- POST `/api/index.php/lounge/select` — src/routes/api/lounge.ts:176
- POST `/api/index.php/lounge/search` — src/routes/api/lounge.ts:193
- POST `/api/index.php/lounge/restore` — src/routes/api/lounge.ts:217
- POST `/api/index.php/lounge/share` — src/routes/api/lounge.ts:235

### `/api/index.php/multi_special_exchange` — src/routes/api/multiSpecialExchange.ts
写库线索: `domains/campaign`, `domains/item`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/index.php/multi_special_exchange/exchange_character` — src/routes/api/multiSpecialExchange.ts:103

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
写库线索: `domains/character`, `domains/equipment`, `domains/item`, `domains/mail`, `domains/mission`, `domains/party`, `domains/player`, `domains/quest`, `persistence-coordinator`
- GET `/api/player/` — src/routes/web_api/player.ts:61
- GET `/api/player/:id/detail` — src/routes/web_api/player.ts:74
- GET `/api/player/save` — src/routes/web_api/player.ts:161
- POST `/api/player/save` — src/routes/web_api/player.ts:200
- POST `/api/player/:id/clear_ex_boost` — src/routes/web_api/player.ts:314
- POST `/api/player/:id/reset_parties` — src/routes/web_api/player.ts:325
- POST `/api/player/:id/clear_mail` — src/routes/web_api/player.ts:340
- POST `/api/player/:id/clear_receive_history` — src/routes/web_api/player.ts:350
- POST `/api/player/:id/repair_unison_unlock` — src/routes/web_api/player.ts:361
- POST `/api/player/:id/character` — src/routes/web_api/player.ts:400
- DELETE `/api/player/:id/character/:code` — src/routes/web_api/player.ts:421
- POST `/api/player/:id/item` — src/routes/web_api/player.ts:449
- DELETE `/api/player/:id/item/:itemId` — src/routes/web_api/player.ts:472
- DELETE `/api/player/:id/quest_progress/:section/:quest_id` — src/routes/web_api/player.ts:489
- DELETE `/api/player/:id/quest_progress` — src/routes/web_api/player.ts:504
- DELETE `/api/player/:id/drawn_quest/:category/:quest_id` — src/routes/web_api/player.ts:516
- DELETE `/api/player/:id/drawn_quest` — src/routes/web_api/player.ts:531
- POST `/api/player/:id/reset_challenge` — src/routes/web_api/player.ts:541
- DELETE `/api/player/:id/mail` — src/routes/web_api/player.ts:572
- POST `/api/player/:id/daily_reset` — src/routes/web_api/player.ts:587
- POST `/api/player/:id/weekly_reset` — src/routes/web_api/player.ts:617

### `/api/server` — src/routes/web_api/server.ts
写库线索: `domains/account`, `domains/admin-player`, `domains/character`, `domains/player`, `domains/session`, `persistence-coordinator`
- POST `/api/server/databaseBackup` — src/routes/web_api/server.ts:360
- GET `/api/server/status` — src/routes/web_api/server.ts:378
- GET `/api/server/currentTime` — src/routes/web_api/server.ts:446
- GET `/api/server/resetTime` — src/routes/web_api/server.ts:455
- GET `/api/server/time` — src/routes/web_api/server.ts:465
- GET `/api/server/clairvoyance/gacha` — src/routes/web_api/server.ts:502
- GET `/api/server/accounts` — src/routes/web_api/server.ts:513
- GET `/api/server/defaultSave` — src/routes/web_api/server.ts:607
- POST `/api/server/defaultSave` — src/routes/web_api/server.ts:612
- DELETE `/api/server/defaultSave` — src/routes/web_api/server.ts:639
- POST `/api/server/selectAccount` — src/routes/web_api/server.ts:647
- POST `/api/server/activateSave` — src/routes/web_api/server.ts:660
- POST `/api/server/newSave` — src/routes/web_api/server.ts:680
- POST `/api/server/deleteSave` — src/routes/web_api/server.ts:723
- POST `/api/server/deleteAccount` — src/routes/web_api/server.ts:758
- GET `/api/server/deleteUnnotedAccounts/status` — src/routes/web_api/server.ts:771
- POST `/api/server/deleteUnnotedAccounts` — src/routes/web_api/server.ts:779
- POST `/api/server/renameSave` — src/routes/web_api/server.ts:832
- POST `/api/server/cloneSave` — src/routes/web_api/server.ts:845
- POST `/api/server/account/rename` — src/routes/web_api/server.ts:897
- POST `/api/server/account/takeover-password/reset` — src/routes/web_api/server.ts:912
- POST `/api/server/device/rename` — src/routes/web_api/server.ts:938

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
写库线索: `domains/leaderboard`, `persistence-coordinator`
- GET `/api/leaderboards/` — src/routes/web_api/leaderboards.ts:35
- GET `/api/leaderboards/:key` — src/routes/web_api/leaderboards.ts:43
- POST `/api/leaderboards/:key/settle` — src/routes/web_api/leaderboards.ts:142
- POST `/api/leaderboards/:key/rollover` — src/routes/web_api/leaderboards.ts:151

### `/api/news` — src/routes/web_api/news.ts
写库线索: `domains/news`, `persistence-coordinator`
- GET `/api/news/` — src/routes/web_api/news.ts:45
- POST `/api/news/items` — src/routes/web_api/news.ts:47
- DELETE `/api/news/items/:id` — src/routes/web_api/news.ts:82
- PUT `/api/news/popup` — src/routes/web_api/news.ts:101
- POST `/api/news/popup/reset` — src/routes/web_api/news.ts:113

### `/api/server/diagnostics` — src/routes/web_api/diagnostics.ts
- GET `/api/server/diagnostics/realtime` — src/routes/web_api/diagnostics.ts:6
- POST `/api/server/diagnostics/realtime` — src/routes/web_api/diagnostics.ts:10

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
- POST `/load` — src/routes/api/index.ts:36

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

- src/cn-server.ts: POST `${apiPrefix}/assetintitle/version_info_in_title`:250, POST `${apiPrefix}/tool/check_social_link_enable`:261, POST `${apiPrefix}/tool/check_enable_gift`:266, POST `${apiPrefix}/tool/contact_active`:270, POST `${apiPrefix}/tool/custom_notify`:274, POST `${apiPrefix}/channels/channel_leiting_pay/query_unfinish_order`:278, POST `${apiPrefix}/channels/channel_leiting_pay/query_purcharge`:282, POST `${apiPrefix}/channels/channel_leiting_pay/set_unfinish_order_status`:286, POST `${apiPrefix}/episode_trial_reading/finish`:291, GET `/debug`:303, POST `/debug`:376, POST `/crash`:388
- src/lib/custom-cdn-resource-routes.ts: GET `/patch/cn/dummy/download/production/${root}/:prefix/:hash`:12
- src/lib/management-auth.ts: GET `/admin-login`:123, POST `/admin-login`:129, POST `/admin-logout`:147
- src/multi/http/battle.ts: POST `/start`:241, POST `/finish`:442, POST `/abort`:1038, POST `/play_continue`:1147
- src/multi/http/lobby.ts: POST `/create_room_failure`:76, POST `/get_rooms`:86, POST `/create_room`:137, POST `/search_room`:211, POST `/select_room`:256
- src/multi/http/room.ts: POST `/prepare`:75, POST `/summon`:130, POST `/restore_room`:181, POST `/share_room`:255, POST `/disband_room`:319
- src/multi/http/social.ts: POST `/verify_access_token`:13, POST `/micro_community`:53, POST `/publish_room`:62
