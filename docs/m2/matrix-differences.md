# 机制矩阵逐条差异核对

基准为原 1.4.224 的 108 角色 `scan_raw.json`。重跑 224 的全部字段零差异，中文矩阵 CSV 逐字节相同。下表逐条列出 231 对基准的 110 个字段差异；完整 before/after 在 `work/m2/matrix/231/comparison.json`，逐版本定位在 `work/m2/matrix/step-differences.json`。

229 对基准为107个字段差异：104条 provenance，另有黑 desc_override、休尔特 awake_rows 与 pf_overrides。231为110个：105条 provenance和5条机制字段。三个版本的108个ID以及每个角色的注册能力集合均相同。

`provenance`只追踪 character、ability、leader、skill 四表，其变化包括名称/文案，不能当成新玩法。下表明确列出每个角色新增的版本标签；227标签来自面板文案批量修改。

| 角色 | 字段 | 逐条解释 |
|---|---|---|
| 119950 伊萨巴迪卡 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119951 奥尔塔尼亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119970 海茵莱特 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119989 碧安卡 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119990 玛格诺斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119991 妮可拉 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119992 米娅 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119993 红蝮蛇 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119994 哈宁红Z | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119995 炎枪见习兵 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119996 玛格诺斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119997 夏可缇 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 119998 金丝雀二号 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129950 伊劳德雷斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129951 斯拉姆冈 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129952 贝尔赛蒂亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129970 维尔努斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129990 海豹球 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129991 见岛勇希 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129992 杰拉尔 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129993 冰冻虎鲸 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129994 哈宁蓝Z | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129995 彷徨铠甲·水 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129996 蓝色海妖 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129997 克劳斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129998 水灵幽魂 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 129999 赛瑞斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139950 伊尔考普斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139951 普罗格雷奥 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139970 吉布西兹 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139985 露迪 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)、1.4.229(balance-1017c)；记录延伸，不代表能力增加。 |
| 139990 凯尔 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139991 黑 | desc_override | 1.4.225 黑的能力/队长行重排：outlaw_panther_moon_2 引用由4次减为3次，队长键由5次增为6次；仍是21条，desc_override 能力未增减。 |
| 139991 黑 | provenance | 四表逐边回放新增 1.4.225(balance-rose-1017b)、1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139992 夏琳 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139993 特克托 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139994 雷吉斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139995 稻穗 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139996 机枪魔块·雷 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139997 莉莉丝 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139998 拉姆斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 139999 史黛拉（夏日） | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 141099 休尔特 | awake_rows | 1.4.225 休尔特平衡后觉醒行27→32；1.4.229 再平衡后32→30，净增3条。觉醒系统与超限能力仍分别登记。 |
| 141099 休尔特 | pf_overrides | 1.4.225 休尔特队长表重排，722 PF覆盖从零基行7移到行6；PF键、levels=1,2,3、特效来源均未变。 |
| 141099 休尔特 | provenance | 四表逐边回放新增 1.4.225(balance-rose-1017b)、1.4.229(balance-1017c)；记录延伸，不代表能力增加。 |
| 149950 伊尔格拉乌 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149951 亚特摩西亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149970 克拉格 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149985 瑞西塔尔 | desc_override | 1.4.231 气绝设计修复减少 lich_halloween_4 的一行，引用计数11→10；desc_override 能力仍存在。 |
| 149985 瑞西塔尔 | provenance | 四表逐边回放新增 1.4.229(balance-1017c)、1.4.231(paralysis-design-fix)；记录延伸，不代表能力增加。 |
| 149986 罗尔夫 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149987 芙拉菲 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149988 盾牌座 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149989 希尔媞 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149990 白 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149991 疾风狂熊 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149992 彷徨铠甲·风 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149993 哈宁绿 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149994 风暴恶魔拉比 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149995 希耶提 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149996 希尔媞 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149997 墨斯伊克 | provenance | 四表逐边回放新增 1.4.225(balance-rose-1017b)、1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149998 风巨蜥 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 149999 杰拉德 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 151015 星川莉莉 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 151021 菲莉亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 151027 艾莉亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 151045 莉莉丝 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 151159 拉夫马诺 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159950 伊尔梅塔雷 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159951 杜梅欧 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159970 艾赞 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159985 塞里奥尔 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159991 稻穗 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159992 凉月 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159994 索恩 | desc_override | 1.4.231 气绝设计修复减少 tweyen_light_4 的一行，引用计数14→13；desc_override 能力仍存在。 |
| 159994 索恩 | provenance | 四表逐边回放新增 1.4.231(paralysis-design-fix)；记录延伸，不代表能力增加。 |
| 159995 丝缇涅尔 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159996 菲莉亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159997 泽赫尔 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159998 斩铁 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 159999 Sec-2600Li | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169950 伊尔昂斯拉 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169951 希亚特利欧 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169970 德古兰 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169978 碧 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169980 深渊之兽 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)、1.4.229(balance-1017c)；记录延伸，不代表能力增加。 |
| 169985 莫弥亚 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169988 澄波响 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169989 奈芙提姆 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169991 蕾贝卡 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169992 普莉姆拉 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169993 黑之下忍 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169994 白虎 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169995 魔王 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169996 西蒙 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169997 巴萨拉卡 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169998 拉芙 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 169999 基诺维 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179970 菲诺梅那 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179981 歼灭者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179982 步兵歼灭者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179983 僧正歼灭者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179984 异形歼灭者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179985 女帝歼灭者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179986 噬龙者 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 179999 罗尔夫 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 251017 莉莉丝 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 251053 萨莉哈 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
| 261089 阿鲁玛德乌斯 | provenance | 四表逐边回放新增 1.4.227(panel-text-standard)；记录延伸，不代表能力增加。 |
