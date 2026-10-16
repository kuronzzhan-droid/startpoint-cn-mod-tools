# 赛瑞斯重做 像素 round1 笔记（2026-10-15）

## 用户原稿处理
- 上传图 512×512 = 128×128 原画布做了 4× 放大（网格拟合误差 0.24，确认整数 4×），并带轻微压缩噪点。
- 处理：每 4×4 块取中心采样降回 128×128；从四角起泛洪，把外部白色抠成透明（身体里的白保留）；k-means 量化成 8 色。
- 正面 idle 帧 26×32 → `REF_user_front_idle.png`（量化后的版本：work/user_ref_128_q.png）。
- 用户调色板（量化后）：黑 #0d0d0e，白 #feffff/#f0f5fa，银 #d3deea/#99a1b7，蓝 #4675af/#354495，亮青 #6ca6e1。

## 生成任务（PixelLab）
| 任务 | 工具 | job id | 尺寸 | 输出 | 消耗 |
|---|---|---|---|---|---|
| 龙人形 Pro | create_image_pro | 1e6dc8ee-cc8c-4110-afec-937fa42d7c53 | 32×32 | 64 张候选 | 10 |
| 真龙形 Pro | create_image_pro | 34ad5208-336f-4144-804f-39f5c0666252 | 40×40 | 36 张候选 | 15 |
| 龙人形精修原稿 | edit_image（文字编辑，原稿×4） | 4550d08e-9368-4b14-a0c5-cc5944d68ae7 | 32×32 | 4 张（基本相同） | 10 |

所有候选：work/H_pro/c00-63、work/D_pro/d00-35、work/H_edit/e0-3；总览图：work/*_grid.png。

## 候选对照（下载索引：`https://api.pixellab.ai/mcp/images/<job>/download?index=N`）
- H1 = edit job 4550d08e，index 1（原稿精修：剪影最贴原稿，大头半身，带尾巴尖）
- H2 = pro job 1e6dc8ee，index 0
- H3 = pro job 1e6dc8ee，index 9
- H4 = pro job 1e6dc8ee，index 26
- H5 = pro job 1e6dc8ee，index 48（尾巴明显）
- H6 = pro job 1e6dc8ee，index 53（抬手姿势，尾巴明显）
- D1 = pro job 34ad5208，index 2（翼展宽，尾巴卷曲）
- D2 = 34ad5208，index 4（长卷角，尾巴卷曲）
- D3 = 34ad5208，index 16（尾巴螺旋）
- D4 = 34ad5208，index 18（双翼上举，V 形剪影）
- D5 = 34ad5208，index 26（紧凑，尾巴卷曲）
- D6 = 34ad5208，index 32（身体最结实）
- 这几项都是**图片任务，不是 PixelLab character**，所以还没有 character id。round2 选定后：用 `create_character(mode="v3", reference_image_url=<选中 PNG>)` 转成 character（龙用 body_type=quadruped 也不完全合适，龙可能更适合 animate_image / edit_image 批帧），再做 9 套标准战斗序列 + special_land/special_pose。

## 提示词
**龙人形 Pro**（seed 1015，参考图：原稿 32×32 标注 "character base: keep this exact silhouette, size, palette and black outline"；原稿 4 姿态表标注 "design details and palette"；官方安巴赫表下半部分标注 "art style: outline thickness, shading and pixel density"）：
> tiny chibi pixel sprite of a water dragon-king man, front view facing the viewer, idle standing pose, same design as the character base: white and silver scaled body, two small swept-back white horns with deep blue tips, spiky white crest around the head, deep blue mane and long deep blue robe panels at chest and hem, two small bright cyan eyes, small white tail tip peeking out at one side, chunky thick black outline, flat bright shading, mobile game battle sprite

**真龙形 Pro**（seed 1015，参考图：原稿 4 姿态表标注 palette/design language；官方安巴赫整张表标注 body/wing/scale/outline style, ignore swirl effects）：
> tiny pixel sprite of a small water dragon in flight, front view facing the viewer, idle hovering pose with wings spread, white and silver scaled body, deep blue mane on the neck, deep blue wing membranes with white wing bones, two swept-back horns, glowing bright cyan eyes, long tail curling below, chunky thick black outline, flat bright shading, mobile game battle sprite, same palette as the dragon-king man reference

**龙人形精修 edit**（seed 1015）：
> clean up this tiny dragon-king sprite while keeping its exact size, silhouette and white-silver and deep-blue palette: crisp continuous black outline, a readable face with two bright cyan eyes and a small snout, two clear swept-back white horns with deep blue tips, white spiky crest, deep blue robe stripes on chest and hem, and a small white tail tip curling out at the lower right side

## 观察
- Pro 版龙人形整体偏向**蓝袍为主**，原稿是**白身为主、蓝色点缀**。如果要更白，round2 可以把 H 候选拿来做 edit_image，提示 "more white body, blue only as accents"，或者把调色板换回原稿。
- edit 精修版（H1）剪影最忠实，但画成了大头半身、腿被吃掉；4 张输出几乎一样（同图同种子）。
- 龙的翼膜是深海军蓝；原稿蓝偏亮（#4675af）。可以按调色板映射换色（免费，本地做）。
- 龙身体约 30-38px，比官方安巴赫 idle（19×19）大。官方大剪影靠特效撑，这一档可读性够。

## 消耗
- 开始前：已用 20 / 剩 1980；结束后：已用 55 / 剩 1945 → **本轮 35 次生成**（$0 积分）。
