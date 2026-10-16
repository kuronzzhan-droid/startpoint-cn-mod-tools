# 赛瑞斯像素小人 · 官方母本整套换色（2026-10-15）

方法：官方小人整套（sprite_sheet.png + atlas + frame + timeline，main 和 special 两套）按**精确 RGB** 逐色替换，帧几何、图集坐标、时间轴、帧号全部不动，只把条目名里的 `character/<母本>/` 改成 `character/seris_dragon_king/`。frame.scale 回到官方 6（旧自制版是 1.26，大帧）。没有调用任何生成接口，零消耗。

## 0. 用户原稿是不是官方/自制小人？

- 上传图是 **2× 放大**（2×2 块零混合，偏移 0,0），1× 原尺寸：正面/背面 13×16，下排两张 17×16、17×17。还原图：`work/ref64.png`、`work/ref_fig0-3.png`。
- 拿 4 个人形与全部 593 套像素表（官方+自制，含杰拉德 white_wolf_gerald、现版赛瑞斯）的每一帧做比对，比的是剪影 IoU + 黑/中/亮三档结构，允许水平镜像。**没有精确或近似精确的匹配**：结构一致率最高只有 0.51（high_priestess 80 帧，剪影 0.90），白狼杰拉德、黑狼骑士都没进前列。
- 结论：原稿是**用户自己画的原创 13×16 小人**，不是官方件，也不是官方件换色。剪影最接近的男性兽人是白虎 white_tiger（正面+背面合计剪影 1.64，男性第 1）；下排宽肩姿态的剪影接近 ice_dragon / wind_dragon 的背面走路帧（0.75 / 0.82）。

## 1. 候选与选择

| ID | 母本 | 说明 | 产出 |
|---|---|---|---|
| **HA** | `alk_3halfanv` | Alk(3.5周年) 151165 ★5 光 Undead,Dragon 角+龙翼 | 整套换色 main+special |
| **HB** | `white_tiger` | 白虎 white_tiger ★4(id10) 雷 Human,Beast 白鬃兽人 | 整套换色 main+special |
| **DA** | `ice_dragon` | 安巴赫 ice_dragon 121105 ★5 水 Dragon | 整套换色 main+special |
| **DB** | `wind_dragon` | 休尔特 wind_dragon 141008 ★5 风 Dragon | 整套换色 main+special |
| HC | `black_wolf_knight` | 黑狼骑士 111007 ★5 火 Human,Beast(杰拉德母本) | 仅预览 |
| HD | `white_tiger_2anv` | 白虎2周年 131086 ★5 雷 Human,Beast | 仅预览 |
| HE | `light_ballot23` | light_ballot23 151153 ★5 光 Dragon 人形龙(非标时间轴) | 仅预览 |
| DC | `fire_dragon` | 瓦格纳 fire_dragon 111001 ★5 火 Dragon | 仅预览 |
| DD | `darkness_dragon` | 暗龙 darkness_dragon 261089 ★5 暗 Dragon | 仅预览 |

龙人形：
- **HA alk_3halfanv（推荐）**：唯一一个**男性 + Dragon 种族 + 标准时间轴**的官方人形（Undead,Dragon，★5，special 齐）。头上有角，下摆是龙翼，正好做「龙人」：肤色 → 白鳞，白发 → 深蓝鬃毛（背面成大片蓝，接近原稿背面），紫灰外套 → 银白袍，粉色龙翼 → 深蓝翼膜。时间轴 neutral 1-2 … revive 387-428，和黑狼骑士/杰拉德同一套。
- **HB white_tiger（备选）**：剪影最像原稿（尖顶白鬃 + 宽肩袍子），白毛本身就合适。缺点：这一行的 id 是 `10`、c2=4（★4），时间轴是**敌人/boss 版**（skill_ready 51-286 共 236 帧，另带 wince/stun/attack/dead 七段），技能演出偏长；没有角。
- 其余人形候选：HC 黑狼骑士（杰拉德母本，剪影有耳无角）、HD 白虎2周年（白蓝配色现成，但剪影最远）、HE light_ballot23（人形龙，时间轴非标 skill 75-134，身形细长）。

真龙形：
- **DA ice_dragon 安巴赫（推荐）**：水属性 ★5，本身就是白银身体 + 冰蓝特效，改动最少：淡紫翼膜/冠 → 深蓝，琥珀眼 → 青色，技能特效（冰/水）原样保留。
- **DB wind_dragon 休尔特（备选）**：灰黑身体 → 银白，黄绿翼缘 → 蓝，风特效 → 水色。剪影更宽更凶；特效换色后看起来像碎水块，不如 DA 自然。
- DC 瓦格纳、DD 暗龙只作参考（火/暗特效换水色工作量大，剪影也不比 DA 合适）。

## 2. 调色板映射（精确 RGB → RGB；alpha 不变；表里没有的颜色一律不动）

赛瑞斯色卡（取自原稿量化色）：白 #feffff/#f0f5fa，银 #d3deea/#99a1b7，蓝 #4675af/#354495，亮蓝 #6ca6e1，眼睛青 (100,230,255)。黑描边 (0,0,0)、影子 (0,0,0,a51)、幽灵灰、入棺洋红这些系统色都不动。

### HA alk_3halfanv

- 身体：
  - `(235, 211, 208)` → `(240, 245, 250)`　（main 202px / special 188px）
  - `(218, 178, 173)` → `(211, 222, 234)`　（main 133px / special 127px）
  - `(241, 236, 227)` → `(254, 255, 255)`　（main 37px / special 25px）
  - `(243, 243, 255)` → `(108, 166, 225)`　（main 561px / special 511px）
  - `(210, 206, 240)` → `(70, 117, 175)`　（main 74px / special 35px）
  - `(187, 177, 218)` → `(70, 117, 175)`　（main 3px / special 1px）
  - `(163, 148, 202)` → `(53, 68, 149)`　（main 204px / special 204px）
  - `(179, 141, 207)` → `(53, 68, 149)`　（main 61px / special 56px）
  - `(147, 100, 185)` → `(40, 46, 110)`　（main 76px / special 77px）
  - `(118, 82, 158)` → `(40, 46, 110)`　（main 16px / special 14px）
  - `(116, 105, 141)` → `(225, 232, 242)`　（main 63px / special 59px）
  - `(103, 91, 131)` → `(211, 222, 234)`　（main 263px / special 227px）
  - `(93, 83, 117)` → `(182, 192, 210)`　（main 111px / special 95px）
  - `(78, 71, 103)` → `(153, 161, 183)`　（main 6px / special 0px）
  - `(71, 59, 102)` → `(153, 161, 183)`　（main 25px / special 25px）
  - `(69, 71, 84)` → `(120, 130, 160)`　（main 123px / special 101px）
  - `(40, 41, 62)` → `(40, 46, 110)`　（main 117px / special 94px）
  - `(32, 33, 52)` → `(28, 36, 90)`　（main 79px / special 44px）
  - `(46, 21, 74)` → `(28, 36, 90)`　（main 15px / special 12px）
  - `(216, 78, 131)` → `(70, 117, 175)`　（main 291px / special 264px）
  - `(160, 40, 25)` → `(53, 68, 149)`　（main 25px / special 23px）
  - `(82, 51, 49)` → `(40, 46, 110)`　（main 30px / special 20px）
  - `(53, 0, 0)` → `(30, 150, 220)`　（main 50px / special 47px）
  - `(67, 152, 168)` → `(70, 117, 175)`　（main 63px / special 57px）
  - `(0, 120, 124)` → `(53, 68, 149)`　（main 24px / special 23px）
  - `(35, 101, 114)` → `(40, 46, 110)`　（main 21px / special 18px）
  - `(60, 91, 108)` → `(53, 68, 149)`　（main 44px / special 37px）
  - `(89, 115, 146)` → `(70, 117, 175)`　（main 19px / special 10px）
  - `(148, 196, 255)` → `(108, 166, 225)`　（main 23px / special 21px）
  - `(252, 240, 200)` → `(225, 250, 255)`　（main 76px / special 77px）
  - `(248, 223, 141)` → `(150, 225, 255)`　（main 55px / special 53px）
  - `(142, 100, 46)` → `(70, 117, 175)`　（main 14px / special 15px）
  - `(69, 42, 7)` → `(28, 36, 90)`　（main 18px / special 18px）
- 特效/special：
  - `(160, 136, 224)` → `(70, 160, 230)`　（main 2306px / special 2306px）
  - `(45, 48, 67)` → `(20, 50, 110)`　（main 2150px / special 2368px）
  - `(70, 31, 60)` → `(14, 60, 150)`　（main 2185px / special 2185px）
  - `(255, 255, 213)` → `(225, 250, 255)`　（main 1945px / special 1945px）
  - `(255, 226, 144)` → `(150, 225, 255)`　（main 1492px / special 1492px）
  - `(255, 212, 64)` → `(54, 192, 255)`　（main 1422px / special 1422px）
  - `(224, 94, 164)` → `(14, 128, 255)`　（main 1246px / special 1318px）
  - `(255, 156, 32)` → `(14, 156, 255)`　（main 1308px / special 1308px）
  - `(50, 53, 67)` → `(20, 60, 120)`　（main 965px / special 965px）
  - `(27, 29, 40)` → `(10, 30, 80)`　（main 971px / special 971px）
  - `(53, 160, 184)` → `(43, 212, 255)`　（main 599px / special 599px）
  - `(197, 192, 208)` → `(210, 241, 255)`　（main 411px / special 411px）
  - `(255, 158, 0)` → `(0, 174, 255)`　（main 78px / special 78px）

### HB white_tiger

- 身体：
  - `(242, 245, 255)` → `(240, 245, 250)`　（main 972px / special 617px）
  - `(255, 255, 255)` → `(254, 255, 255)`　（main 2712px / special 2026px）
  - `(216, 218, 229)` → `(211, 222, 234)`　（main 94px / special 50px）
  - `(199, 203, 208)` → `(70, 117, 175)`　（main 122px / special 45px）
  - `(186, 189, 195)` → `(182, 192, 210)`　（main 49px / special 46px）
  - `(181, 184, 192)` → `(153, 161, 183)`　（main 1023px / special 641px）
  - `(145, 153, 165)` → `(120, 130, 160)`　（main 89px / special 3px）
  - `(81, 91, 101)` → `(70, 117, 175)`　（main 293px / special 158px）
  - `(51, 51, 63)` → `(53, 68, 149)`　（main 81px / special 31px）
  - `(58, 50, 42)` → `(40, 46, 110)`　（main 3px / special 2px）
  - `(96, 114, 90)` → `(70, 117, 175)`　（main 148px / special 48px）
  - `(52, 90, 48)` → `(53, 68, 149)`　（main 570px / special 386px）
  - `(0, 48, 0)` → `(28, 36, 90)`　（main 443px / special 247px）
  - `(207, 77, 0)` → `(100, 230, 255)`　（main 64px / special 36px）
  - `(168, 79, 0)` → `(40, 46, 110)`　（main 36px / special 21px）
  - `(233, 149, 0)` → `(108, 166, 225)`　（main 19px / special 10px）
  - `(86, 0, 0)` → `(40, 40, 90)`　（main 83px / special 35px）
  - `(203, 142, 158)` → `(225, 232, 242)`　（main 73px / special 35px）
- 特效/special：
  - `(238, 233, 218)` → `(150, 225, 255)`　（main 1375px / special 1230px）
  - `(242, 240, 235)` → `(225, 250, 255)`　（main 544px / special 544px）
  - `(226, 226, 224)` → `(110, 200, 245)`　（main 262px / special 262px）
  - `(216, 213, 198)` → `(70, 160, 230)`　（main 350px / special 237px）
  - `(103, 13, 0)` → `(20, 60, 140)`　（main 20px / special 20px）
  - `(207, 126, 0)` → `(60, 200, 255)`　（main 6px / special 6px）
  - `(143, 143, 137)` → `(80, 120, 170)`　（main 1px / special 1px）

### DA ice_dragon

- 身体：
  - `(241, 239, 251)` → `(240, 245, 250)`　（main 2401px / special 4355px）
  - `(219, 241, 251)` → `(240, 245, 250)`　（main 142px / special 196px）
  - `(219, 219, 235)` → `(211, 222, 234)`　（main 33px / special 12px）
  - `(161, 163, 179)` → `(182, 192, 210)`　（main 76px / special 174px）
  - `(154, 157, 163)` → `(153, 161, 183)`　（main 93px / special 130px）
  - `(128, 139, 163)` → `(120, 130, 160)`　（main 7px / special 3px）
  - `(81, 83, 96)` → `(84, 95, 130)`　（main 61px / special 26px）
  - `(212, 212, 251)` → `(108, 166, 225)`　（main 148px / special 30px）
  - `(183, 186, 251)` → `(70, 117, 175)`　（main 44px / special 225px）
  - `(154, 159, 251)` → `(53, 68, 149)`　（main 4px / special 0px）
  - `(109, 109, 172)` → `(40, 46, 110)`　（main 16px / special 6px）
  - `(107, 156, 251)` → `(70, 117, 175)`　（main 141px / special 180px）
  - `(74, 143, 251)` → `(53, 68, 149)`　（main 236px / special 457px）
  - `(130, 165, 246)` → `(70, 117, 175)`　（main 21px / special 0px）
  - `(143, 172, 246)` → `(108, 166, 225)`　（main 32px / special 48px）
  - `(94, 165, 251)` → `(70, 117, 175)`　（main 3px / special 0px）
  - `(181, 217, 251)` → `(108, 166, 225)`　（main 26px / special 9px）
  - `(161, 222, 255)` → `(108, 166, 225)`　（main 117px / special 2088px）
  - `(60, 51, 150)` → `(40, 46, 110)`　（main 74px / special 94px）
  - `(255, 179, 0)` → `(100, 230, 255)`　（main 37px / special 47px）
  - `(72, 33, 0)` → `(20, 60, 140)`　（main 19px / special 0px）
- 特效/special：
  - `(202, 209, 251)` → `(150, 190, 235)`　（main 530px / special 1242px）
  - `(166, 169, 242)` → `(70, 117, 175)`　（main 489px / special 1354px）
  - `(183, 208, 244)` → `(150, 190, 235)`　（main 0px / special 87px）
  - `(161, 186, 231)` → `(70, 117, 175)`　（main 0px / special 57px）

### DB wind_dragon

- 身体：
  - `(114, 117, 128)` → `(240, 245, 250)`　（main 219px / special 141px）
  - `(117, 114, 120)` → `(225, 232, 242)`　（main 48px / special 77px）
  - `(98, 96, 96)` → `(211, 222, 234)`　（main 421px / special 1310px）
  - `(157, 161, 174)` → `(211, 222, 234)`　（main 47px / special 899px）
  - `(154, 159, 159)` → `(153, 161, 183)`　（main 22px / special 34px）
  - `(67, 63, 63)` → `(153, 161, 183)`　（main 132px / special 69px）
  - `(45, 45, 45)` → `(120, 130, 160)`　（main 46px / special 42px）
  - `(143, 143, 143)` → `(225, 232, 242)`　（main 4px / special 15px）
  - `(243, 235, 213)` → `(254, 255, 255)`　（main 190px / special 507px）
  - `(184, 187, 189)` → `(254, 255, 255)`　（main 43px / special 4px）
  - `(221, 240, 125)` → `(108, 166, 225)`　（main 176px / special 614px）
  - `(110, 205, 181)` → `(70, 117, 175)`　（main 66px / special 742px）
  - `(43, 125, 112)` → `(53, 68, 149)`　（main 85px / special 623px）
  - `(145, 145, 174)` → `(70, 117, 175)`　（main 41px / special 34px）
  - `(34, 38, 49)` → `(28, 36, 90)`　（main 19px / special 6px）
  - `(63, 67, 115)` → `(100, 230, 255)`　（main 101px / special 175px）
- 特效/special：
  - `(74, 98, 130)` → `(28, 60, 130)`　（main 3268px / special 3268px）
  - `(236, 220, 77)` → `(60, 200, 255)`　（main 1965px / special 1965px）
  - `(229, 254, 136)` → `(150, 235, 255)`　（main 1717px / special 1717px）
  - `(35, 213, 149)` → `(14, 128, 255)`　（main 1389px / special 1389px）
  - `(201, 201, 228)` → `(210, 241, 255)`　（main 728px / special 1263px）
  - `(189, 178, 255)` → `(170, 215, 255)`　（main 0px / special 1389px）
  - `(120, 96, 213)` → `(53, 68, 149)`　（main 0px / special 899px）
  - `(255, 170, 250)` → `(180, 235, 255)`　（main 0px / special 938px）
  - `(159, 151, 236)` → `(108, 166, 225)`　（main 0px / special 668px）
  - `(175, 175, 213)` → `(211, 222, 234)`　（main 0px / special 691px）
  - `(223, 210, 255)` → `(225, 240, 255)`　（main 0px / special 152px）
  - `(159, 130, 236)` → `(70, 117, 175)`　（main 0px / special 141px）
  - `(88, 74, 88)` → `(40, 50, 90)`　（main 0px / special 798px）
  - `(120, 93, 120)` → `(60, 80, 130)`　（main 0px / special 273px）
  - `(133, 112, 130)` → `(120, 130, 160)`　（main 0px / special 167px）
  - `(194, 183, 191)` → `(211, 222, 234)`　（main 0px / special 185px）

## 3. 文件（可直接放入 `character/seris_dragon_king/pixelart/`）

所有 `.png` 都是 **store 形态**（魔数写成小写 `\x89png`，和 store/补丁包里的一样）；`_preview_*.png` 是普通 PNG，只用来看，**不要发布**。`.deflate` 是 raw deflate(-15) + AMF3，已逐个解回校验。

**推荐组合 = HA + DA：**

| 放到 | 来源 |
|---|---|
| `pixelart/sprite_sheet.png` | `sets/HA_alk_3halfanv/main/sprite_sheet.png` |
| `pixelart/sprite_sheet.atlas.amf3.deflate` | `sets/HA_alk_3halfanv/main/sprite_sheet.atlas.amf3.deflate` |
| `pixelart/pixelart.frame.amf3.deflate` | `sets/HA_alk_3halfanv/main/pixelart.frame.amf3.deflate` |
| `pixelart/pixelart.timeline.amf3.deflate` | `sets/HA_alk_3halfanv/main/pixelart.timeline.amf3.deflate` |
| `pixelart/special_sprite_sheet.png` | `dual_form/HA+DA/special/special_sprite_sheet.png` |
| `pixelart/special_sprite_sheet.atlas.amf3.deflate` | `dual_form/HA+DA/special/special_sprite_sheet.atlas.amf3.deflate` |
| `pixelart/special.frame.amf3.deflate` | `dual_form/HA+DA/special/special.frame.amf3.deflate` |
| `pixelart/special.timeline.amf3.deflate` | `dual_form/HA+DA/special/special.timeline.amf3.deflate` |

其他组合：`dual_form/{HA+DB, HB+DA, HB+DB}/special` 配对应的 `sets/H?_*/main`。**main 和 special 必须成对替换**：special 里 9 段战斗序列的绝对帧号是照着 main 时间轴抄的。

`sets/<ID>_<母本>/{main,special}` 是每个母本单独换色的完整 8 件（几何完全不动）。其中 `sets/D*/main` 就是真龙的原始战斗表；`sets/H*/special` 是人形的获取演出换色，双形态方案里**用不到**（special 槽给了龙），留着备用：如果想让获取演出显示人形，就要把 dual 里追加的那两段换成它。

### 文件清单（大小 / md5）

- `dual_form/HA+DA/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　361B　8844f23647f0
  - special_sprite_sheet.atlas.amf3.deflate　1454B　03012d012c46
  - special_sprite_sheet.png　39820B　165b875de96d
- `dual_form/HA+DB/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　361B　e8a0e29f5d28
  - special_sprite_sheet.atlas.amf3.deflate　1271B　27d3450f1888
  - special_sprite_sheet.png　46661B　26b22ce56216
- `dual_form/HB+DA/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　417B　d47fbeefa50d
  - special_sprite_sheet.atlas.amf3.deflate　1458B　46f94289c774
  - special_sprite_sheet.png　39820B　165b875de96d
- `dual_form/HB+DB/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　419B　7efa2eb8ba50
  - special_sprite_sheet.atlas.amf3.deflate　1270B　57910b5a541c
  - special_sprite_sheet.png　46661B　26b22ce56216
- `sets/DA_ice_dragon/main/`
  - pixelart.frame.amf3.deflate　79B　76226d41cddc
  - pixelart.timeline.amf3.deflate　331B　612c74fc5e03
  - sprite_sheet.atlas.amf3.deflate　1091B　7c4e0d877962
  - sprite_sheet.png　21857B　9ca95f329bd5
- `sets/DA_ice_dragon/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　108B　cca6857f8aa7
  - special_sprite_sheet.atlas.amf3.deflate　674B　e3fb92c659b2
  - special_sprite_sheet.png　39778B　5f780012eb4b
- `sets/DB_wind_dragon/main/`
  - pixelart.frame.amf3.deflate　79B　76226d41cddc
  - pixelart.timeline.amf3.deflate　331B　3a1492726e1d
  - sprite_sheet.atlas.amf3.deflate　935B　8e6b5c96b430
  - sprite_sheet.png　13273B　f82048b41526
- `sets/DB_wind_dragon/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　108B　6c9f7fa00e7f
  - special_sprite_sheet.atlas.amf3.deflate　610B　067f3ccebb72
  - special_sprite_sheet.png　50877B　29e52f27b9ce
- `sets/HA_alk_3halfanv/main/`
  - pixelart.frame.amf3.deflate　79B　76226d41cddc
  - pixelart.timeline.amf3.deflate　331B　3a1492726e1d
  - sprite_sheet.atlas.amf3.deflate　1210B　b7b7be24f81c
  - sprite_sheet.png　24199B　d513eb799e30
- `sets/HA_alk_3halfanv/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　109B　11bed09b10c1
  - special_sprite_sheet.atlas.amf3.deflate　628B　a8a542057c43
  - special_sprite_sheet.png　29512B　f8322561b05e
- `sets/HB_white_tiger/main/`
  - pixelart.frame.amf3.deflate　79B　76226d41cddc
  - pixelart.timeline.amf3.deflate　471B　a161e36eae64
  - sprite_sheet.atlas.amf3.deflate　1565B　2bcf8b631fb7
  - sprite_sheet.png　14601B　880146f1c08e
- `sets/HB_white_tiger/special/`
  - special.frame.amf3.deflate　84B　c47df2c5cc91
  - special.timeline.amf3.deflate　109B　58a8840db13d
  - special_sprite_sheet.atlas.amf3.deflate　640B　f96f02bc0158
  - special_sprite_sheet.png　9022B　e1c929c7c506

## 4. 双形态 special 槽：现状 vs 需要

客户端机制（见 wf-special-slot-dual-form）：`MemberView.draw` 用人形 Playhead 的**绝对帧号**去 `gotoAndStop` 龙形 special 动画，所以龙形的 9 段战斗序列必须和人形 main 时间轴**同帧号**；另外 special 槽本来是 ★4+ 获取演出槽，`special_land` / `special_pose` 缺一段就会硬 throw，必须追加在后面。

| | 现版 seris（store131） | 新版 HA+DA |
|---|---|---|
| main 时间轴 | neutral 1-48, walk_back 49-80, walk_front 81-112, skill_ready 113-142, kachidoki 143-192, into_coffin 193-222, ghost_raise 223-262, ghost_neutral 263-298, revive 299-338；scale 1.26 | alk 原样：1-2 / 3-26 / 27-50 / 51-110 / 111-158 / 159-200 / 201-225 / 226-386 / 387-428；scale 6 |
| special 时间轴 | 同上 9 段 + special_land 339-434 + special_pose 435-482；scale 1.26 | 同上 9 段（与 main 逐帧号一致） + **special_land 429-613 + special_pose 614-668**（安巴赫原版获取演出，+428 平移）；scale 6 |
| special 图集 | 92 条，575×1351 | 161 条，1022×247（重新紧排、去重、不旋转） |
| circles/points | 与 main 相同 | 抄 alk main 的 unit_body/hp_gauge |

重排规则（龙 → 人形帧号）：同名序列逐帧对应；龙序列比人形长 → 等比压缩（安巴赫 skill_ready 66 帧压进 60 帧）；龙序列较短 → loop 取模循环，once/pass 播完停在最后一帧。special_land 第 1 帧放一个 1×1 透明帧，和官方一样开头空白（否则会停在 revive 的最后一帧）。`neutral` 第 1 帧没有图，这和所有官方表一样（首个关键帧是 2）。

HB 组合：白虎 main 最大帧号是 747（带敌人段），所以 special_land 从 748 开始；special 里只镜像 9 个标准段（队员只会播这 9 段）。

## 5. 预览

- `候选总览-官方母本.png`：每个候选一行，官方/赛瑞斯上下对照，1× 条 + 4× idle/walk/back + skill_ready 关键帧（大帧 2×）。
- `preview/<ID>_<母本>.gif`：neutral → walk_front → walk_back → skill_ready，按时间轴帧序（60fps 合并同帧），中灰底，官方|赛瑞斯并排。
- `preview/dual_<组合>_battle_mirror.gif`：人形 main 和龙形 special 在**同一绝对帧号**并排播放，用来核对镜像对齐。`dual_<组合>_join_movie.gif`：追加的 special_land+special_pose。

## 6. 装配注意

- 这批只产出文件，没碰数据表、设备、git、服务端。上链要走正常 wf_publish 铸边；8 个文件要一起换。
- scale 从 1.26 变成 6 以后，旧的大帧 render-scale 补丁就不需要了。
- 这套补丁会在 rarity≥4 时预载 special，还会在 Unique 22 存在时换成 special 动画。新 special 满足 9 段同构 + land/pose 两段，契约没有变。
- 生产脚本：`scripts/`（common/frames/maps/build/preview/verify/notes.py）。重跑顺序：build → preview → verify → notes。WF_TIP=206 的视图在 build 目录 base149。
