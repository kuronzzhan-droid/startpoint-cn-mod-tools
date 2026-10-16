# 赛瑞斯 S0-3 尾巴修正 round 2 (2026-10-15) — 图生图编辑,输入=round1 gen/seiris_0_3.png(作者选定)
# 提示词全部正面描述(作者规则:只写画面有的)。4 个变体只在尾巴走向上不同。
REFS = ["refs/seiris_0_3_src.png"]

BASE = """IMAGE EDIT of the attached image (image 1): Seiris, the silver-white water dragon king, seated on his white coral and silver throne. Reproduce image 1 faithfully at the same size (1086x1448) and the same framing: the same seated pose, the same front-facing dragon face with glowing cyan eyes, the same silver horns and deep-blue mane, the same hand at his chin, the same deep-blue and white robe, cape, silver shoulder plates and chest gem, the same silver trident held in his right hand on picture-right, the same coral throne, the same round platform of wet white stone, the same pearls, water ribbons and droplets, the same colours, crisp anime line art and flat cel shading, on the same plain white background. The one area that changes is the tail and the floor it occupies.

CORRECT ANATOMY OF THE TAIL: his long thick silver-white scaled tail with the deep-blue fin ridge grows from the base of his spine at the back of his hips, behind his body, and emerges beside the throne seat on picture-left, between the seat and the draped cape. It reads as one continuous tail from the hips to the fin-tipped end, with a smooth gradual taper. His raised leg on picture-left is fully a leg: the shin and the clawed foot on picture-left rest flat on the stone floor with all claws touching the stone, and the leg on picture-right stands on the stone floor in its current position. Both clawed feet stand on the bare wet stone of the platform. The area in front of the shin on picture-left shows the plain stone platform, pearls and water.

TAIL PATH FOR THIS VARIANT: """

VAR = {
 "T1": "the tail emerges from behind the seat on picture-left, sweeps down to the floor beside the throne base, and curls clockwise along the front edge of the platform, passing in front of the throne base below and beside his feet, its fin-tipped end resting on the stone near the foot on picture-right in a graceful crescent.",
 "T2": "the tail emerges from behind the seat and drapes over the top of the throne's left armrest on picture-left, hangs down the outer side of the armrest, reaches the floor and lies in a relaxed S-curve on the stone at the picture-left edge of the platform, its fin-tipped end curling forward beside the foot on picture-left.",
 "T3": "the tail emerges from behind the seat on picture-left and coils around the picture-left side of the throne, wrapping behind and around the throne's left side and base, then comes forward along the floor on picture-left in one large loop, its fin-tipped end resting on the stone at the front left corner of the platform, beside the foot on picture-left.",
 "T4": "the tail passes beneath the throne seat, behind his legs, and emerges on the floor on picture-right, sweeping out to the right and curling forward along the front right edge of the platform beside the foot on picture-right, its fin-tipped end lifting gently at the front right corner; a short section of the tail base is visible behind the seat on picture-left where it leaves his hips.",
}

JOBS = [dict(id=k, out=f"seiris_0_3_{k}.png", refs=REFS, prompt=BASE + v) for k, v in VAR.items()]
