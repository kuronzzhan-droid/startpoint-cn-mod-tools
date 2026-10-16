from common import *
import glob, hashlib, json, shutil
from maps import MOTHERS, EXTRA_CANDIDATES
usage = json.load(open(OUT + '/palette_usage.json', encoding='utf8'))
L = []
A = L.append
A('# 赛瑞斯像素小人 · 官方母本整套换色（2026-10-15）\n')
A('方法：官方小人整套（sprite_sheet.png + atlas + frame + timeline，main 和 special 两套）按**精确 RGB** 逐色替换，帧几何、图集坐标、时间轴、帧号全部不动，只把条目名里的 `character/<母本>/` 改成 `character/seris_dragon_king/`。frame.scale 回到官方 6（旧自制版是 1.26，大帧）。没有调用任何生成接口，零消耗。\n')
A('## 0. 用户原稿是不是官方/自制小人？\n')
A('- 上传图是 **2× 放大**（2×2 块零混合，偏移 0,0），1× 原尺寸：正面/背面 13×16，下排两张 17×16、17×17。还原图：`work/ref64.png`、`work/ref_fig0-3.png`。')
A('- 拿 4 个人形与全部 593 套像素表（官方+自制，含杰拉德 white_wolf_gerald、现版赛瑞斯）的每一帧做比对，比的是剪影 IoU + 黑/中/亮三档结构，允许水平镜像。**没有精确或近似精确的匹配**：结构一致率最高只有 0.51（high_priestess 80 帧，剪影 0.90），白狼杰拉德、黑狼骑士都没进前列。')
A('- 结论：原稿是**用户自己画的原创 13×16 小人**，不是官方件，也不是官方件换色。剪影最接近的男性兽人是白虎 white_tiger（正面+背面合计剪影 1.64，男性第 1）；下排宽肩姿态的剪影接近 ice_dragon / wind_dragon 的背面走路帧（0.75 / 0.82）。\n')
A('## 1. 候选与选择\n')
A('| ID | 母本 | 说明 | 产出 |')
A('|---|---|---|---|')
for m, md in MOTHERS.items():
    A(f"| **{md['id']}** | `{m}` | {md['name']} | 整套换色 main+special |")
for c, i, n in EXTRA_CANDIDATES:
    A(f'| {i} | `{c}` | {n} | 仅预览 |')
A('')
A('龙人形：')
A('- **HA alk_3halfanv（推荐）**：唯一一个**男性 + Dragon 种族 + 标准时间轴**的官方人形（Undead,Dragon，★5，special 齐）。头上有角，下摆是龙翼，正好做「龙人」：肤色 → 白鳞，白发 → 深蓝鬃毛（背面成大片蓝，接近原稿背面），紫灰外套 → 银白袍，粉色龙翼 → 深蓝翼膜。时间轴 neutral 1-2 … revive 387-428，和黑狼骑士/杰拉德同一套。')
A('- **HB white_tiger（备选）**：剪影最像原稿（尖顶白鬃 + 宽肩袍子），白毛本身就合适。缺点：这一行的 id 是 `10`、c2=4（★4），时间轴是**敌人/boss 版**（skill_ready 51-286 共 236 帧，另带 wince/stun/attack/dead 七段），技能演出偏长；没有角。')
A('- 其余人形候选：HC 黑狼骑士（杰拉德母本，剪影有耳无角）、HD 白虎2周年（白蓝配色现成，但剪影最远）、HE light_ballot23（人形龙，时间轴非标 skill 75-134，身形细长）。')
A('\n真龙形：')
A('- **DA ice_dragon 安巴赫（推荐）**：水属性 ★5，本身就是白银身体 + 冰蓝特效，改动最少：淡紫翼膜/冠 → 深蓝，琥珀眼 → 青色，技能特效（冰/水）原样保留。')
A('- **DB wind_dragon 休尔特（备选）**：灰黑身体 → 银白，黄绿翼缘 → 蓝，风特效 → 水色。剪影更宽更凶；特效换色后看起来像碎水块，不如 DA 自然。')
A('- DC 瓦格纳、DD 暗龙只作参考（火/暗特效换水色工作量大，剪影也不比 DA 合适）。\n')
A('## 2. 调色板映射（精确 RGB → RGB；alpha 不变；表里没有的颜色一律不动）\n')
A('赛瑞斯色卡（取自原稿量化色）：白 #feffff/#f0f5fa，银 #d3deea/#99a1b7，蓝 #4675af/#354495，亮蓝 #6ca6e1，眼睛青 (100,230,255)。黑描边 (0,0,0)、影子 (0,0,0,a51)、幽灵灰、入棺洋红这些系统色都不动。\n')
for m, md in MOTHERS.items():
    A(f"### {md['id']} {m}\n")
    for title, mp in (('身体', md['body']), ('特效/special', md['fx'])):
        if not mp:
            A(f'- {title}：无（保持官方原色）'); continue
        A(f'- {title}：')
        for src, dst in mp.items():
            n1 = usage.get(f"{md['id']}_{m}_main", {}).get(str(src), 0)
            n2 = usage.get(f"{md['id']}_{m}_special", {}).get(str(src), 0)
            A(f'  - `{src}` → `{dst}`　（main {n1}px / special {n2}px）')
    A('')
A('## 3. 文件（可直接放入 `character/seris_dragon_king/pixelart/`）\n')
A('所有 `.png` 都是 **store 形态**（魔数写成小写 `\\x89png`，和 store/补丁包里的一样）；`_preview_*.png` 是普通 PNG，只用来看，**不要发布**。`.deflate` 是 raw deflate(-15) + AMF3，已逐个解回校验。\n')
A('**推荐组合 = HA + DA：**\n')
A('| 放到 | 来源 |')
A('|---|---|')
for f in ['sprite_sheet.png', 'sprite_sheet.atlas.amf3.deflate', 'pixelart.frame.amf3.deflate', 'pixelart.timeline.amf3.deflate']:
    A(f'| `pixelart/{f}` | `sets/HA_alk_3halfanv/main/{f}` |')
for f in ['special_sprite_sheet.png', 'special_sprite_sheet.atlas.amf3.deflate', 'special.frame.amf3.deflate', 'special.timeline.amf3.deflate']:
    A(f'| `pixelart/{f}` | `dual_form/HA+DA/special/{f}` |')
A('\n其他组合：`dual_form/{HA+DB, HB+DA, HB+DB}/special` 配对应的 `sets/H?_*/main`。**main 和 special 必须成对替换**：special 里 9 段战斗序列的绝对帧号是照着 main 时间轴抄的。\n')
A('`sets/<ID>_<母本>/{main,special}` 是每个母本单独换色的完整 8 件（几何完全不动）。其中 `sets/D*/main` 就是真龙的原始战斗表；`sets/H*/special` 是人形的获取演出换色，双形态方案里**用不到**（special 槽给了龙），留着备用：如果想让获取演出显示人形，就要把 dual 里追加的那两段换成它。\n')
A('### 文件清单（大小 / md5）\n')
for d in sorted(glob.glob(OUT + '/sets/*/*') + glob.glob(OUT + '/dual_form/*/special')):
    d = d.replace('\\', '/')
    A(f"- `{d.split('official_mother/')[1]}/`")
    for f in sorted(os.listdir(d)):
        if f.startswith('_preview'): continue
        b = open(f'{d}/{f}', 'rb').read()
        A(f'  - {f}　{len(b)}B　{hashlib.md5(b).hexdigest()[:12]}')
A('\n## 4. 双形态 special 槽：现状 vs 需要\n')
A('客户端机制（见 wf-special-slot-dual-form）：`MemberView.draw` 用人形 Playhead 的**绝对帧号**去 `gotoAndStop` 龙形 special 动画，所以龙形的 9 段战斗序列必须和人形 main 时间轴**同帧号**；另外 special 槽本来是 ★4+ 获取演出槽，`special_land` / `special_pose` 缺一段就会硬 throw，必须追加在后面。\n')
A('| | 现版 seris（store131） | 新版 HA+DA |')
A('|---|---|---|')
A('| main 时间轴 | neutral 1-48, walk_back 49-80, walk_front 81-112, skill_ready 113-142, kachidoki 143-192, into_coffin 193-222, ghost_raise 223-262, ghost_neutral 263-298, revive 299-338；scale 1.26 | alk 原样：1-2 / 3-26 / 27-50 / 51-110 / 111-158 / 159-200 / 201-225 / 226-386 / 387-428；scale 6 |')
A('| special 时间轴 | 同上 9 段 + special_land 339-434 + special_pose 435-482；scale 1.26 | 同上 9 段（与 main 逐帧号一致） + **special_land 429-613 + special_pose 614-668**（安巴赫原版获取演出，+428 平移）；scale 6 |')
A('| special 图集 | 92 条，575×1351 | 161 条，1022×247（重新紧排、去重、不旋转） |')
A('| circles/points | 与 main 相同 | 抄 alk main 的 unit_body/hp_gauge |')
A('\n重排规则（龙 → 人形帧号）：同名序列逐帧对应；龙序列比人形长 → 等比压缩（安巴赫 skill_ready 66 帧压进 60 帧）；龙序列较短 → loop 取模循环，once/pass 播完停在最后一帧。special_land 第 1 帧放一个 1×1 透明帧，和官方一样开头空白（否则会停在 revive 的最后一帧）。`neutral` 第 1 帧没有图，这和所有官方表一样（首个关键帧是 2）。\n')
A('HB 组合：白虎 main 最大帧号是 747（带敌人段），所以 special_land 从 748 开始；special 里只镜像 9 个标准段（队员只会播这 9 段）。\n')
A('## 5. 预览\n')
A('- `候选总览-官方母本.png`：每个候选一行，官方/赛瑞斯上下对照，1× 条 + 4× idle/walk/back + skill_ready 关键帧（大帧 2×）。')
A('- `preview/<ID>_<母本>.gif`：neutral → walk_front → walk_back → skill_ready，按时间轴帧序（60fps 合并同帧），中灰底，官方|赛瑞斯并排。')
A('- `preview/dual_<组合>_battle_mirror.gif`：人形 main 和龙形 special 在**同一绝对帧号**并排播放，用来核对镜像对齐。`dual_<组合>_join_movie.gif`：追加的 special_land+special_pose。\n')
A('## 6. 装配注意\n')
A('- 这批只产出文件，没碰数据表、设备、git、服务端。上链要走正常 wf_publish 铸边；8 个文件要一起换。')
A('- scale 从 1.26 变成 6 以后，旧的大帧 render-scale 补丁就不需要了。')
A('- 这套补丁会在 rarity≥4 时预载 special，还会在 Unique 22 存在时换成 special 动画。新 special 满足 9 段同构 + land/pose 两段，契约没有变。')
A('- 生产脚本：`scripts/`（common/frames/maps/build/preview/verify/notes.py）。重跑顺序：build → preview → verify → notes。WF_TIP=206 的视图在 build 目录 base149。')
open(OUT + '/notes.md', 'w', encoding='utf8').write('\n'.join(L) + '\n')
# archive scripts + ref crops
os.makedirs(OUT + '/scripts', exist_ok=True); os.makedirs(OUT + '/work', exist_ok=True)
for f in ['common.py', 'frames.py', 'maps.py', 'build.py', 'preview.py', 'verify.py', 'notes.py', 'pal.py', 'loc.py', 'match2.py', 'rank.py']:
    shutil.copy(f'{SR}/{f}', f'{OUT}/scripts/{f}')
for f in ['ref64.png', 'ref_fig0.png', 'ref_fig1.png', 'ref_fig2.png', 'ref_fig3.png', 'rank.json']:
    shutil.copy(f'{SR}/{f}', f'{OUT}/work/{f}')
print('notes ok')
