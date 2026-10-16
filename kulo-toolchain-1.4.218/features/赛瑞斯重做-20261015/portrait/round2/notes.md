# 赛瑞斯 S0-3 尾巴修正 round 2 (2026-10-15)

输入: round1 `gen/seiris_0_3.png`(作者选定)→ 复制为 `refs/seiris_0_3_src.png`,作为唯一参考图做图生图编辑。
问题: 尾巴像从抬起的小腿前方长出来、左脚踩在尾巴上。修正: 尾巴从脊椎末端/臀后长出,经画面左侧王座旁落地,沿台面卷到脚边;双脚踩石面。

产物: `gen/seiris_0_3_T1..T4.png`(均 1086×1448);联络表 `S0-3尾巴修正-候选.jpg`(原图 + T1-T4,3600×1090,约1.3MB);`sheet.py` 重出联络表。

## 管线(同 round1)
- 跑法: `JOBS_MOD=jobs_seris_r2 PAR=4 python run.py [T1,T2]`(run.py 复制自 round1,默认 JOBS_MOD 改为 jobs_seris_r2;已存在的输出会跳过,重抽先删 gen 里对应 png)。
- Codex CLI `codex exec -i refs/seiris_0_3_src.png -`,`-m gpt-6-astra`,`-s read-only`,reasoning medium;run.py 从日志里的 `~/.codex/generated_images/...png` 复制到 gen/。日志 `gen/T*.log`。
- 消耗: 4 张(预算 4),无重抽。tokens: T1 14,919 / T2 35,669 / T3 28,090 / T4 14,988,合计约 93.7k,ChatGPT/Codex 订阅额度,无 API 费用。

## 各变体尾巴走向与目测
- T1: 从左侧王座后落地,顺时针沿台面前沿弧向右脚 —— 最接近需求;右小腿后多出一小簇鳍尖(尾端疑似重复),细看可修。
- T2: 搭在左扶手外侧垂下,S 形落在台面左缘,尾尖在左脚旁。
- T3: 绕王座左侧外缘一大圈回到左前角,尾尖在左脚前。
- T4: 从座下穿到右侧,沿右前沿卷到右脚旁;左侧可见段很少。
- 共同变化: 模型把原来抬起的左腿放平成双脚落地(按要求"双脚踩石面"),所以腿部姿态与原图有差;脸、角、鬃毛、披风、三叉戟、王座、珊瑚、水、珍珠基本保持。

## 提示词(全部正面描述;run.py 另追加代理指令 'Generate exactly ONE image ... reply Generated: <path>')
共用前缀:
```
IMAGE EDIT of the attached image (image 1): Seiris, the silver-white water dragon king, seated on his white coral and silver throne. Reproduce image 1 faithfully at the same size (1086x1448) and the same framing: the same seated pose, the same front-facing dragon face with glowing cyan eyes, the same silver horns and deep-blue mane, the same hand at his chin, the same deep-blue and white robe, cape, silver shoulder plates and chest gem, the same silver trident held in his right hand on picture-right, the same coral throne, the same round platform of wet white stone, the same pearls, water ribbons and droplets, the same colours, crisp anime line art and flat cel shading, on the same plain white background. The one area that changes is the tail and the floor it occupies.

CORRECT ANATOMY OF THE TAIL: his long thick silver-white scaled tail with the deep-blue fin ridge grows from the base of his spine at the back of his hips, behind his body, and emerges beside the throne seat on picture-left, between the seat and the draped cape. It reads as one continuous tail from the hips to the fin-tipped end, with a smooth gradual taper. His raised leg on picture-left is fully a leg: the shin and the clawed foot on picture-left rest flat on the stone floor with all claws touching the stone, and the leg on picture-right stands on the stone floor in its current position. Both clawed feet stand on the bare wet stone of the platform. The area in front of the shin on picture-left shows the plain stone platform, pearls and water.

TAIL PATH FOR THIS VARIANT: 
```
各变体后缀:
- T1: the tail emerges from behind the seat on picture-left, sweeps down to the floor beside the throne base, and curls clockwise along the front edge of the platform, passing in front of the throne base below and beside his feet, its fin-tipped end resting on the stone near the foot on picture-right in a graceful crescent.
- T2: the tail emerges from behind the seat and drapes over the top of the throne's left armrest on picture-left, hangs down the outer side of the armrest, reaches the floor and lies in a relaxed S-curve on the stone at the picture-left edge of the platform, its fin-tipped end curling forward beside the foot on picture-left.
- T3: the tail emerges from behind the seat on picture-left and coils around the picture-left side of the throne, wrapping behind and around the throne's left side and base, then comes forward along the floor on picture-left in one large loop, its fin-tipped end resting on the stone at the front left corner of the platform, beside the foot on picture-left.
- T4: the tail passes beneath the throne seat, behind his legs, and emerges on the floor on picture-right, sweeping out to the right and curling forward along the front right edge of the platform beside the foot on picture-right, its fin-tipped end lifting gently at the front right corner; a short section of the tail base is visible behind the seat on picture-left where it leaves his hips.
