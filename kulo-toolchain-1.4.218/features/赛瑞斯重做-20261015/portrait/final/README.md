# 赛瑞斯 129999 seris_dragon_king 立绘重做美术包(2026-10-15)

只产出文件,未写 store、未打包、未发布、未动设备/服务端/git。

## 输入(作者选定)
- 觉醒前 `_0`:`portrait/round2/gen/seiris_0_3_T2.png`(1086×1448)
- 觉醒后 `_1`:`portrait/round1/gen/seiris_1_6.png`(1086×1448)

## 做法(照抄 1.4.195 月狼那轮:`kulo-patch-toolkit/cursed_abyss/build/portrait195.py` + `立绘重设计-20261008/月狼替换包-20261009/derive.py`)
1. **抠图**:`wf_portrait_white_matte.py`(默认参数 core_tol 4 / aa 2,不点名任何封闭白块)。只删与画面四边连通的纯白,封闭白块与场景全部保留。
   审计(`work/report/seris_{0,1}_report.json`):`eaten_px=0`、`eaten_hard_px=0`、`leftover_bg_px=0`、`floating_white_px=0`(两张都是),封闭白块 28 / 62 块全部保留未删。
2. **full_shot**:抠好的母图直接用作 `full_shot_1440_1920_{0,1}.png`(1086×1448,与月狼同尺寸,四角透明)。
3. **图标**:月狼 derive.py 同法:按眼睛中点+头高定框,直接从母图裁(保留场景、透明保持透明,不填色、不加背景),
   再套官方形状蒙版 `alpha=min(原alpha, 官方蒙版)`(蒙版=5 个官方狼/独角兽角色同名图标 alpha 并集,与月狼同源)。
   落点:`_0` 眼中点 (538,215)、头高 300(正脸,横向居中 0.5);`_1` 眼 (595,385)、头高 245(侧脸朝右,沿用 0.62)。
   验收:蒙版为 0 处 alpha 全为 0(脚本内断言通过);尺寸与线上原图逐一断言一致。
4. **skill_cutin**:同法裁 1024×512(不套蒙版),并用 `wf_atf.build_cutin_atf(png, 原ATF)` 重编 **android 根 `.atf.deflate`(ETC1,11 级 mip)**——真机只读它。
   回解码 PSNR:RGB 29.0/29.8 dB、A 37.2/45.2 dB(AI 细鳞纹比官方低约 3dB,属正常)。
5. **图鉴格** `illustration_setting_sprite_sheet.png`:整图等比 fit 进原 region(_1 在 (0,0,360,372),_0 在 (0,373,359,365)),画布 361×806 不变,**atlas `.amf3.deflate` 不用改**。

## 产物
- `game/<逻辑路径>`:游戏存储态(PNG 魔数已改为小写 `\x89png`,与线上文件同),ATF 为 raw-deflate。可直接按逻辑路径替换。
- `png/`:同内容的标准 PNG,便于查看。
- `manifest.json`:每个文件的逻辑路径 → 本地文件 → sha256 → 是否替换已有文件(全部 27 个都是替换,无新增路径)→ 线上现存的根(及旧文件 sha256)。
  - PNG 线上同时存在于 `upload` 与 `medium_upload` 两根(两根旧字节本就不同),月狼那轮两根写同一份字节,这里也一样,**两根都要替换**。
  - `skill_cutin_{0,1}.atf.deflate` 存在于 `upload` 与 `android_upload`,两根都替换。本角色线上无 `ios_upload` 版本,未生成。
- `立绘图标预览.jpg`:透明处显示为洋红。
- `work/`:`build_seris.py`(可重跑)、抠图母图 `master/`、审计报告 `report/`、`tables.json`。

## 需要你改的表(三张,行级;外层其余行不动)
| 表 | 键 | 旧值 | 新值 |
|---|---|---|---|
| `master/generated/character_image.orderedmap` | `129999` → `0` | `515,284,1003,1568` | `462,294,1086,1448` |
| `master/generated/character_image.orderedmap` | `129999` → `1` | `495,189,1024,1536` | `405,124,1086,1448` |
| `master/generated/trimmed_image.orderedmap` | `character/seris_dragon_king/ui/full_shot_1440_1920_0` | `515,284,2000,2000` | `462,294,2000,2000` |
| `master/generated/trimmed_image.orderedmap` | `character/seris_dragon_king/ui/full_shot_1440_1920_1` | `495,189,2000,2000` | `405,124,2000,2000` |
| `master/character/full_shot_image_attribute.orderedmap` | `129999` → `0`/`1` | `1000,1000,1,1000,509` | 不变(`1000,1000,1,1000,509`) |

公式(portrait195):`x = 1000 − 眼x`,`y = 509 − 眼y`,夹到 `[0, 2000−w]`/`[0, 2000−h]`(本次都没触发夹紧),`character_image` 的 w,h = PNG 实际尺寸,`trimmed_image` 与 `character_image` 的 x,y 必须一致;脸锚因未夹紧恰好等于 (1000,509),`full_shot_image_attribute` 无需改。
`trimmed_image` 是扁平表(行=zlib CSV),`character_image`/`full_shot_image_attribute` 是嵌套表(只替内层 `0`/`1`)。

可选:`trimmed_image[character/seris_dragon_king/ui/skill_cutin_0]` 现为 `8,0,1024,512`(旧 cut-in 留下的显示偏移),新图按满幅 0,0 构图,月狼两格都是 `0,0`;改成 `0,0,1024,512` 更贴合,不改只差 8px。

## 未动的
- `skill_cutin_matched_0/1`、`skill_cutin_dragon`(及其 ATF):全表只有赛瑞斯有的死行,无官方代码路径读取,保持原样。
- illustration atlas、pivot/scale 列。
