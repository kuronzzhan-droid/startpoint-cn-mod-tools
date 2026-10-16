# 赛瑞斯 129999 原创像素特效（2026-10-15）

## 结论
- 做了 5 个特效族、9 个特效，外加 1 枚固有状态图标。全部原创，水色板锁 12 色，Lv4 加红雷（红色板 8 色）。
- 全部放在 `battle/effect/skill_unique/seris_dragon_king/<子目录>/`，图集 `<子目录>/<子目录>.png`，帧名两段式。
- 图集总占用 **0.396 Mpx**。旧赛瑞斯特效 layer0 **1.101 Mpx** + layer1 **1.346 Mpx**。新的只有旧的 36%（只比 layer0），layer1 归零。
- 每张图集都在官方 skill_unique 中位数附近，最大 97k px，低于官方 p90（217k）。
- 落盘文件回读重渲染，和模型渲染逐像素一致。静态门禁全过（见「校验」）。
- 花费：RetroDiffusion $0.21（3 次 vfx，$38.296 → $38.086）。PixelLab 0 次（1945 → 1945）。
- 没碰 live 表、设备、服务器、git。接线参数在 `dsl_hooks.json`，要在 `build/seris_rework.py` / `seris_pf.py` 里改（我没改）。

## 交付物
| 路径 | 内容 |
|---|---|
| `fx/<族>/game/...` | 游戏格式文件：png（存储态魔数 `\x89png`）、atlas/parts/timeline（AMF3 + raw deflate） |
| `fx/drop_manifest.json` | 29 个文件，`{logical, local, roots:["upload"], sha256, size, replaces_existing}` |
| `fx/dsl_hooks.json` | 每条 ShowEffect 的完整节点，可以直接替换或插入 |
| `fx/preview/*.gif` | 暗底预览（0.4 倍，竖屏 1080×1920）。框线是敌带 y250-1230，圆圈是假想敌和球 |
| `fx/特效总览.png` | 各特效 4 张关键帧 |
| `fx/<族>/<族>_sheet_preview.png` | 图集明文 PNG |
| `fx/icon/` | 固有状态图标，另附 4 倍预览 |
| `fx/_src/rd/` | RD 原始输出：ring / splash / redbolt |
| `fx/_scripts/` | 生产脚本：`run.py` 一键重建，`verify_decode.py` 回读门禁 |

## 五个族
| 族 | 特效 | 用途 | 帧数（主体+收尾） | 构成 |
|---|---|---|---|---|
| tide | seris_tide | 人形技能『苍海潮涌』 | 32+12 | 浪峰 4 列平铺（3 帧轮换）、水体渐变、水流纹；第 8/12/16 帧三根潮柱，配 RD 水花、泡沫环、飞沫，第 3 根加白闪 |
| breath | seris_breath | 龙形技能三段吐息 | 36+10 | 原点就是龙口。可平铺水柱（3 相位逐帧下流）、口部白闪、RD 漩涡环、下行螺旋环、末端水花、飞沫 |
| breath | seris_flight | 真龙升空 | start 16 / loop 48 / end 20 | 用新龙形像素（final_USER_DB special 帧 1/38/50），10 倍。背后是压扁的 RD 漩涡环。loop 无缝，寿命直写 220 |
| dash | seris_dash | 冲刺 629『龙翼冲撞』 | 22+8 | 双水翼（同一张图镜像）3 帧合拢扑击，第 3 帧爆开：白闪 + RD 水花 + 泡沫环 + 飞沫 |
| lv4 | seris_lv4_human | PF Lv4『苍海怒涛』龙人形 | 60+14 | 先落 3 道红雷，然后巨浪漫过全场，浪内连落 10 道红雷，浪峰上爬红电，第 30 帧起四处拍落 |
| lv4 | seris_lv4_dragon | PF Lv4 真龙形 | 60+14 | 在龙人形版之上加第二道浪、13 道红雷，第 22 帧加中央红雷柱，配龙吼 |
| lv4 | seris_red_bolt | 弹板 Lv4 就绪红电 / 拍板时球上红电 | 10+4 | 短红雷 + 红闪 + 火花 |
| transform | seris_transform | 进 Fever 化龙（审计新增） | 36+10 | 漩涡环包住本体，潮柱冲天，正好遮住换形那一帧，然后爆散 |
| transform | seris_revert | Fever 结束回龙人（审计新增，可选） | 24+8 | 漩涡环收拢落地，溅起水冠。和化龙共用像素，零新增图集 |

- timeline 统一是 `neutral(once)` 主体 + `end(once)` 收尾淡出。寿命到点或被终止都会跳到 end 播完，不会当场消失。
- SE 全部取官方 timeline 原文路径，门禁校验它们都在官方 416 条集合里：
  - 潮涌：`se_water_giant_tidal_wave` / `se_splash_slam` / `se_water_large_explosion`
  - 龙息：`se_violent_swirling_water` + `se_water_large_explosion`
  - 升空：`se_dragon_flying` + `se_dragon_roar`
  - 冲撞：`se_water_strike` + `se_splash_slam`
  - Lv4：`se_thunderbolt_single` / `se_water_giant_tidal_wave` / `se_lightning_attack_volume1` / `se_water_large_explosion`，龙形加 `se_dragon_roar`
  - 化龙：`se_splash_launch` + `se_dragon_roar`
  - 回龙人：`se_wave_splash`
  - SE 的触发帧是按画面估的，没量包络，真机要听一遍。

## DSL 挂法（完整节点见 dsl_hooks.json）
| 特效 | 树 | ShowEffect 参数 |
|---|---|---|
| 潮涌 | seris_dragon_king / _2：替换「全体演出」 | subject -1，SuperForesideOfCharacter，LifetimeDirectly 32，AB，(0,0,0)，true/true，scale 1.0（和旧版同位） |
| 升空 | matched / matched_2 / ability_skill_seris_breath：替换「龙形升空演出」 | -1，SuperForeside，LifetimeDirectly 220，AB，(0,0,0.0)，scale 1.0。龙身烘在 parts 里 y=-830 |
| 吐息 ×3 | 同上：替换「龙息第1/2/3段」（Wait 40/95/150 不动） | -1，SuperForeside，PlayOnlyFirstSequence，AB，**x=0,y=-740**（原点放到龙口），rot 0.0，true/true，scale 1.0/1.3/1.6 |
| 化龙 | ability_skill_seris_breath：根 Block 第 0 条插入 | -17，ForesideOfCharacter，PlayOnlyFirstSequence，AB，(0,0,0.0)，true/true，1.0。**必须在 `water_only()` 之后插**，因为它会删掉路径含 "transform" 的 ShowEffect |
| 冲撞 | dash_h / dash_d：替换 dash_tree 里那条 | subject 0（FindNearSubjects 绑的敌人），ForesideOfCharacter，PlayOnlyFirstSequence，AB，(0,0,0)，**false/false**（创建帧快照，敌人死了也能播完），scale 人形 1.0 / 龙形 1.35 |
| Lv4 | override_seris_human_lv4 / dragon_lv4 的 lv3 树：`PF.compose(lv4=True)` 之后插在 Suppress 后面 | -1，SuperForeside，LifetimeDirectly 60，AB，(0,0,0.0)，false/false，1.0（分 human/dragon 两条路径）。再插一条 `seris_red_bolt`：-18，PlayOnlyFirstSequence，false/false，1.0。这条同时让红电跟 Lv4 树一起预载 |
| 弹板红电（APK） | `BattleFlipperImpl.update` 的 HitEffect 路径 | `battle/effect/skill_unique/seris_dragon_king/lv4/seris_red_bolt`。只有赛瑞斯是队长、Lv4 行存在时才预载，补丁判 Lv4 就绪的条件正好一样 |
| 回龙人（可选） | 新 629 树 `ability_skill_seris_revert`，只有一条 ShowEffect（-17，Foreside，PlayOnlyFirstSequence） | 能力 1299993 加第 7 行：触发 184、kind 629。这是新数据通路，要金丝雀 |
| 固有图标 | `battle/common/unique_condition/unique_seris_dragon_king.png` | 原位替换 48×48。改成官方样式：白边圆角方、蓝渐变底、白色龙首加浪纹（旧的是圆形徽章，不合官方） |

## 图集预算（layer0，按 (w+2)×(h+2) 计）
| 资产 | 尺寸 | 占用 px | 何时加载 |
|---|---|---|---|
| **新** tide | 357×250 | 90,468 | 常驻（技能树） |
| **新** breath | 289×302 | 88,464 | 常驻 |
| **新** dash | 204×190 | 39,552 | 常驻（能力 629） |
| **新** transform | 221×358 | 80,280 | 常驻（629 龙息） |
| **新** lv4 | 302×318 | 97,280 | 仅队长（722/419 预载） |
| **新合计** | | **396,044**（常驻 298,764） | 占 4096² 的 2.36% |
| 旧 seris_human_royal_tide_ring | 294×588 | 174,640 | 常驻 |
| 旧 seris_dragon_flight | 1024×128 | 133,380 | 常驻 |
| 旧 seris_dragon_frozen_thunder_breath | 512×512 | 264,196 | 常驻 |
| 旧 seris_human_shooting_powerflip | 512×512 | 264,196 | 仅队长 |
| 旧 seris_dragon_special_powerflip | 512×512 | 264,196 | 仅队长 |
| **旧 layer0 合计** | | **1,100,608** | |
| 旧 uncommon/layer1 seris_dragon_king_transform | 1138×1179 | 1,346,340（layer1） | 常驻 |
| 参考：主仓旧口径 skill_unique/seris_dragon_king（1.4.256 裁后） | 1980×879 | 1,746,142 | kulo 视图里这张是 1138×1179，现役 DSL 不引用 |

- 官方对照（pathlist 内 370 张 skill_unique 目录图集）：中位 82,039 / p90 216,840 / 最大 947,249。新 5 张在 39k–97k 之间，没有一张过 p90，长宽比都 ≤1.62，没有细长列阻塞件。
- 官方角色 layer0 中位约 0.17 Mpx（卡片口径）。赛瑞斯新特效 0.40 Mpx，以前是 1.10（layer0）+ 1.35（layer1）。像素线新 sprite_sheet 246×80，旧的是 468×665。
- 卡顿：单帧可见面片峰值最大 71（潮涌），龙形 Lv4 是 54。官方特殊 PF 是 325，魔王修后是 564，远低于这两个。
- 放大倍率：小件 2–3 倍（像素风），渐变水体件按设计拉伸（卡片允许），龙身 10 倍（角色像素是 6 倍）。parts 矩阵数最多 1698（官方最大 3815），单 graphics 段数最多 383（官方最大 795），都在官方先例范围内。

## 审计：缺什么、补了什么
**已补（本批交付）**
1. 化龙爆发 `seris_transform`。进 Fever 时 629 自动龙息会跑，挂在它第 0 条，零数据新增。旧化龙演出（uncommon/layer1，1.35 Mpx）已经被 rework 摘掉，没有替代就等于化龙无演出。
2. 回龙人 `seris_revert`。Fever 结束只删固有 22，没有 DSL 在跑，所以要另加 629 行。像素和化龙共用，零图集成本。数据通路标为可选，需要金丝雀。
3. 升空换新龙。旧 `seris_dragon_flight` 用的是旧龙形像素，换完小人之后会和本体对不上。新版取新龙形帧。
4. Lv4 人形 / 龙形两版，同一张图集别名，龙形版多一道浪和中央红雷柱。
5. 弹板红电 `seris_red_bolt`。设计稿 §6 说「纯红闪电要另画随角色预载的特效」，这就是那张。Lv4 树里挂一条同时解决预载。
6. 固有状态图标「龙王显现」，按官方样式重画。

**建议不做**
- 龙形 / 人形 PF 合成里的官方五类型特效不换。官方 PF 的黄 / 绿 / 青是档位色语义，而且这些特效已经由公共件和官方族预载。换成自制要多 0.5 Mpx 以上，还会抹掉档位信息。Lv4 专属演出已经单独做了。
- 弹板本体红帧不做。这个改动在公共图集 layer0，全战斗共享，设计稿已否决，APK 染色足够。
- 冲刺本身的拖尾不做。冲刺是引擎原生演出，DSL 改不到。

**发布前提醒**
- 旧的 tide_ring / flight / frozen_thunder_breath 三个目录在新 DSL 接线后就零引用了，图集不再预载。文件留着就行（CDN 删不掉，也不该删）。
- 老 `skill_unique/seris_dragon_king/seris_dragon_king.png`（1138×1179）这次仍然零引用。新特效都在子目录，不会把它拉进预载。
- 主仓 `mod-tools/wf_offline_content.py` 有 `WORKSPACE_PROGRAM_EFFECTS` 精确集合闸门。如果离线整包走主仓工具，要把新路径同步进去。
- 没上真机的有：SE 时机、龙息 y=-740 的口位、冲撞 tracking false/false、回龙人 629 通路、APK HitEffect 播放 end 段的行为。

## 校验（`_scripts/verify_decode.py` 全过）
- 只用落盘文件（解混淆 PNG + atlas + parts + timeline）重渲染每个特效的 5 个关键帧，和模型渲染逐像素一致。
- 结构检查：
  - 键序 = 官方：parts `i,g,m,a,o,t,c,s`，timeline 六键，atlas `n,w,h,x,y`
  - 帧名两段式，基名 = parts 文件名
  - 每个图集 rect 都有 alpha==0 像素。水体渐变件是纯色，走白名单
  - 段起点 + 关键帧总长 ≤ g.t（防 #1125）
  - 每帧每图并发数 ≤ a（实例池宁多勿崩）
  - timeline 末帧 == g.t
  - SE 路径都在官方集合内
- AMF3 编码器先用旧 tide_ring 和官方 powerflip_attack_special_three 做过逐字节往返验证。
- RD 件按 alpha 质心统一画布归中（循环件漂移 ≤1px），并重新吸进锁定色板。

---

## 降噪轮（10-15 作者：「当前音效有点多和吵」）

### 结论
- 每个动作最多一声，并且降低音量。平时 PF 只保留特殊型那一套（set+clear），PF Lv4 只剩一声。
- 方式：把其余四种官方 PF 特效做成静音副本，放在 `seris_dragon_king/pfq_*/`。图集多 139,016 px，只在赛瑞斯当队长时加载。新特效加副本合计 535,060 px，仍低于旧版 layer0 的 1,100,608。
- 音量用 timeline 声音条目的 `volume` 字段。客户端 `flatomo/timeline/Playhead.as:174` 的逻辑：`volume != -1` 时增益 = `volume × 0.1`，`-1` 时为 1.0。官方 1658 条全写 -1。现役赛瑞斯旧化龙特效写的是 9，真机正常播放。

### 每个动作的 SE 条数（上界；格斗连打按最多命中次数计）
| 动作 | 1.4.209 | 本轮 | 本轮保留的 SE |
|---|---|---|---|
| 人形技能 苍海潮涌 | 3 | 1 | se_wave_splash，音量 0.6 |
| 龙形技能（升空+三段吐息） | 8 | 1 | 第 1 段 se_water_short_splash，音量 0.7；第 2/3 段改用 `seris_breath_mute` |
| 进 Fever：化龙+自动龙息 | 10 | 1 | 化龙 se_splash_launch，音量 0.6；自动龙息整棵静音 |
| 冲刺 龙翼冲撞 | 2 | 1 | se_water_short_splash，音量 0.5（冲刺频繁，压得最低） |
| Fever 结束 回龙人 | 1 | 0 | — |
| PF Lv1 / Lv2 / Lv3 龙人形 | 3 / 3 / 3 | 2 / 2 / 2 | 官方特殊型 set + clear |
| PF Lv1 / Lv2 / Lv3 真龙形 | 9 / 10 / 13 | 2 / 2 / 2 | 同上 |
| PF Lv4 龙人形 | 7 | 1 | se_thunderbolt_single，音量 0.8 |
| PF Lv4 真龙形 | 18 | 1 | 同上 |

- 升空、红电（弹板 HitEffect 和球上红电）、回龙人都没有声音。
- 明细在 `_scripts/se_count.json`，脚本是 `_scripts/se_count.py`。
- 1.4.209 版的旧 SE 配置备份在 `_scripts/build_fx_loud_backup.py`。

### 官方 PF 的 SE 在哪里、为什么一次拍板响好几套
- 五种 PF 的 DSL 里没有任何声音命令。声音全部写在官方特效 timeline 的 `sounds` 里，ShowEffect 一播就响。合成 PF 同时播 2 到 5 种类型的特效，所以叠成 2 到 5 套。
- 真龙形 Lv3 一次拍板最多 13 声：
  - 剑：spin + smash（smash 在 end 段）
  - 拳：连打 lash_a × 6 + finish
  - 射击 1 声
  - 辅助 1 声
  - 特殊：set + clear
- 弹板本体的充能音、角色类型（c6）决定的原生 PF 演出、每次伤害的命中水花（`hit/normal_damage/splash` 自带 se_water_short_splash）由引擎触发，DSL 管不到，不在本轮范围。

### 方案比较
| 方案 | 做法 | 图集成本 | 问题 |
|---|---|---|---|
| A | 只复制 parts+timeline，继续引用官方图集的帧名 | 0 | 官方 sheet 要靠别的引用才会加载。剑、辅助两个目录没有无声的兄弟特效可以挂着保活，缺了就是「纹理尚未加载」。太脆，不用 |
| **B（采用）** | 整目录静音副本：png 原字节复制，atlas/parts 只改目录前缀，timeline 清空 sounds | +139,016 px（剑 37,023 / 拳 38,610 / 射击 12,415 / 辅助 19,118 / 特殊 31,850） | 自包含，不依赖官方目录是否加载 |
| C | DSL 层静音 | 0 | ShowEffect 没有音量参数，DSL 也没有静音命令。唯一的 DSL 办法是删掉其他类型的 ShowEffect，画面会跟着没掉。不用 |

### 落地文件
- `fx/pf_quiet/game/.../pfq_{spin,fight,beam,support,special}/`：58 个文件，已并入 `drop_manifest.json`（现共 89 条）。
- `fx/pf_quiet/path_map.json`：官方路径到静音副本的映射，24 条。
- `build/seris_pf_quiet.py`：seris_pf.py 的副本，唯一区别是 `compose()` 末尾多了一步 `quiet_paths()`。
  - Lv1-3 保留特殊型的官方路径，其余换成静音副本。
  - Lv4 全部换成静音副本。
  - 已验证：把路径映射回去后，和 `seris_pf.compose()` 的结果逐项相等，判定、伤害、寿命都没动。
- `build/seris_rework_quiet.patch`：两处改动，请审后应用。
  1. `import seris_pf as PF` 改成 `import seris_pf_quiet as PF`。
  2. `fx_dragon(transform=True)` 的第 1 段改用 `breath_1_auto`（静音）。
- `dsl_hooks.json` 已更新：breath_2/3 改指 `seris_breath_mute`，新增 `breath_1_auto`。rework 直接读这个文件，这两处不用改代码就会生效。不打 patch 的话，进 Fever 会响 2 声（化龙 + 自动龙息第 1 段）。
- 本族文件的 sha 会变：所有 timeline 变了，breath 图集多了 mute 的别名条目（零像素），另新增 `seris_breath_mute` 两个文件。需要重新出包。

### 校验
- `verify_pfq.py`：
  - 副本 png 与官方逐字节一致。
  - atlas 除 n 外逐字段一致，parts 除 i[].p 外一致，timeline 除 sounds 外一致。
  - 每条 i[].p 都能在新 atlas 里找到。
- `verify_decode.py` 全部通过，SE 路径都在官方集合内。
- 没上真机的：volume 实际听感（是否还要再压）、特殊型 set 音是否仍嫌吵。若嫌吵，可以把 `KEEP_SOUND` 改成 `()` 并给 special 也走静音副本，这样每次拍板 0 声，只剩引擎原生的弹板/命中音。
