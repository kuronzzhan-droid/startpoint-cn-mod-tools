# -*- coding: utf-8 -*-
'泳装希尔媞 149996 ``wind_spgirl_swim`` 灰版资源补齐：13 条语音 + 剧情横幅（2026-09-27 第三轮 extra5 批次）。\n\n作者原话（2026-09-27 本会话，主会话逐字转述）：「对方补了资源」，附对方的四角色参考交付包\n``four-character-author-handoff-v2.zip``（``HANDOFF_SHA256``，resource_tail 1.4.121）。此前作者对灰服三角色的要求：\n「把这版替换我本地的,然后一并纳入调整」——核心导入已在本地 1.4.1054 完成（``wf_balance_20260927b_gray3``，\ncommit 183092fa），当时 ``gray3.NOT_IN_ARCHIVE["149996"]`` 记为「泳装语音未导入」（灰链 1.4.88 重编码版）。\n\n## 导入什么（``FILES``，14 个，逐个钉 sha256）\n交付包 ``<角色目录>/handoff/cdn/<tier>/<logical>`` 是灰服 CDN 存储态字节（MP3 帧头 0x7F、PNG 魔数小写 ``png``），\n``handoff/decoded/<logical>`` 是标准 MP3/PNG（``DECODED_SHA256``；``extract`` 时核对 ``wf_assets`` 解码 == decoded）。\n主会话逐文件比对（与 live 不同或 live 没有）后，泳装希尔媞只有这 14 个：\n- common 13 条语音：``voice/ally/{evolution,join}``、``voice/battle/{battle_start,outhole,power_flip,skill,win}_{0,1}``、\n  ``voice/battle/skill_ready``。与灰链归档 1.4.87→1.4.88 边（``GRAY_CHAIN_ZIP``）里的同名成员逐字节相同。\n- medium 1 张 ``ui/episode_banner_0.png``（live 没有；同样来自灰链 1.4.88）。\n交付包其余文件与 live 相同（主会话比对），不导入。\n\n## 实测结论（``revise`` 每次从钉住的来源字节重算，写进 notes）\n- **13 条语音的音频帧与 live 逐字节相同**：去掉 ID3v2 标签后 sha256 相同，帧数/码率/时长全同（MPEG-1 Layer III、\n  96 kbps CBR、44.1 kHz、单声道）。差异只在 ID3v2 标签尾部的零填充（live 恒 2048 字节，灰版 1941–2039 字节，\n  文件小 9–107 字节）；标签头与 TIT2 帧逐字节相同。所以「灰链 1.4.88 重编码」实际只是去掉部分标签填充，\n  导入后听感零变化，只让字节与灰服对齐。\n- 存储态严格校验（``mp3_facts``）：``wf_assets.mp3_encode(mp3_decode(x)) == x``（mp3_encode 的口径：CBR、\n  逐帧覆盖到文件尾），且探测 tail = 0。\n- 语音引用：``character_speech[149996]`` 的 kind 2 行 voice_path = ``ally/join``、kind 1 行 = ``ally/evolution``\n  （客户端 ``GeneralCharacterLogic.resolveVoicePath`` = ``character/<string_id>/voice/<相对路径>`` + ``.mp3``）；\n  11 条 battle 语音不在任何表里，是 ``CharacterShortVoiceLogic`` 的固定名/序号探测（win_/battle_start_/skill_/\n  power_flip_/outhole_ 序号池 + skill_ready）。string_id = character c0 = ``wind_spgirl_swim``。表不改。\n- 剧情横幅：解码 430×215 RGBA（8 bit），与 live 全部 502 张官方 ``episode_banner_0`` 同尺寸（``OFFICIAL_BANNER``），\n  存储态魔数与官方同为小写 ``png``。**没有任何表引用它**：live 2111 张 master 表（WF_PATHLIST_recovered 2116 条里\n  store 有的全部）递归解包后没有 ``episode_banner`` 字样；客户端 ``CharacterBaseImpl.getEpisodeBannerImagePath``\n  （as:206-209）按 image_prefix（character c8）硬编码 ``_0``，只有角色剧情列表（EpisodeCharacterSelect）和主页剧情\n  气泡用；149996 没有角色剧情（character_quest 无 1499960x 键）⇒ 导入后也不会显示，属休眠资源。\n  ``wf_character_requirements`` 把 episode_banner 归 excluded（不在 37 项硬门里）。\n\n## 交付包没带、未导入（notes.not_in_handoff）\n灰链 1.4.88 还同样去掉了 6 条 home 语音（``voice/home/{alk_niisama,…}``）的标签填充（音频帧同样与 live 相同），\n但交付包 v2 没带（对方导出器按通用名 ``home_0..9`` 探测，漏掉 speech 表注册的自定义名；报告 voice_counts 为空）。\n要逐字节对齐，可从灰链归档 1.4.88 取（``HOME_NOT_IN_HANDOFF`` 记了两边 sha256）；本模块不导入。\n\n## 返回（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）\n只有 ``files``：``{"<tier>:<logical>": "<HANDOFF_ROOT 下解出文件的绝对路径>"}``（14 个），外加\n``notes.file_sha256``（钉住字节；extra5 ``stage_batch`` 暂存后复核）。其余标准键全空。PACKAGES = []（无 flow 包，\nextra5 ``BarePlan``）。BEFORE = 14 个目标路径的 live ``file_sha256``（banner 为 None），任一漂移即拒绝；\n导入后再跑也会拒绝（fail closed）。另读三处只做门禁、不锁摘要：character_speech / character 两行（语音与横幅路径的\n引用），character_quest 1499960{1,2,3}（必须不存在）。\n\n源文件：``HANDOFF_ROOT``（默认仓库 ``work/gray3/handoff_v2``，``/work/`` 已 gitignore）下有就读它，没有就从钉哈希的\n``HANDOFF`` 压缩包直读；``files`` 输出只认 ``HANDOFF_ROOT``（先跑 ``python mod-tools/wf_balance_20260927c_swimassets.py extract``）。\n\n纯函数：``revise`` 只读 ``read()`` 与钉住哈希的来源，不写任何文件；不写 live/assets/.cdn/候选，不发布，不 git。\n'
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any, Callable
import zipfile
import zlib

import wf_assets as A

REPO = Path(__file__).resolve().parents[1]

CID = "149996"
CODE = "wind_spgirl_swim"
PACKAGES: list[str] = []                      # 无 flow 包（extra5 BarePlan）
PACKAGE_VERSION: dict[str, str] = {}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}

HANDOFF_NAME = "four-character-author-handoff-v2.zip"
#: 对方交付包（作者下载目录）；环境变量 WF_SWIM_HANDOFF_ARCHIVE 可覆盖。整包钉 HANDOFF_SHA256，成员逐个钉 FILES。
HANDOFF = Path(os.environ.get("WF_SWIM_HANDOFF_ARCHIVE", Path.home() / "Downloads" / HANDOFF_NAME))
HANDOFF_SHA256 = "00db9a563597bf5a132197ba7a32acd6681be4c5f7838dd529bbaf3781bfbce2"
HANDOFF_RESOURCE_TAIL = "1.4.121"
HANDOFF_DIR = "four-character-author-handoff-v2/149996-wind_spgirl_swim-reference-1.4.121/handoff"
#: 解出目录：默认仓库内 work/gray3/handoff_v2（/work/ 已 gitignore，不随会话清理）；环境变量 WF_SWIM_HANDOFF_ROOT
#: 可覆盖。布局 ``<root>/<tier>/<logical>``。
HANDOFF_ROOT = Path(os.environ.get("WF_SWIM_HANDOFF_ROOT", REPO / "work" / "gray3" / "handoff_v2"))
#: 灰链归档里同一批字节的出处（只作证据与测试对照；revise 不读）。
GRAY_CHAIN_ZIP = ("work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active/"
                  "pinball-1.4.87-1.4.88-1-0825-integrated-ginovi-spgirl-trio-rogue.zip")
GRAY_CHAIN_ZIP_SHA256 = "0ee61e86757833ff65d8ed6c34da1284fbe84b70c587a9c37da55a64a7ab96ce"
TIER_ROOTS = {"common": "upload", "medium": "medium_upload"}

SPEECH = "master/character/character_speech.orderedmap"
CHAR = "master/character/character.orderedmap"
CHARACTER_QUEST = "master/quest/character_quest.orderedmap"
#: 角色剧情键 = 角色 ID + 两位话数（官方 3 话：01-03）。
QUEST_KEYS = tuple(f"{CID}{n:02d}" for n in (1, 2, 3))
BANNER = f"medium:character/{CODE}/ui/episode_banner_0.png"
#: character_speech 里引用本次语音的行：kind → voice_path（kind 2 = Join、1 = Evolution）。
SPEECH_VOICES = {"2": "ally/join", "1": "ally/evolution"}
#: 客户端 CharacterShortVoiceLogic 按固定名/序号探测的 battle 语音前缀（as:29-83），不经任何表。
ENGINE_VOICE_PREFIXES = ("battle/win_", "battle/battle_start_", "battle/skill_", "battle/power_flip_",
                         "battle/outhole_", "battle/skill_ready")
#: live 全部官方 episode_banner（2026-09-27 实测：character 表 597 行的 code 里 502 个有 _0，全在 medium 根，
#: 全部 430×215 RGBA；没有任何 _1）。
OFFICIAL_BANNER = {"count": 502, "tier": "medium", "size": [430, 215], "mode": "RGBA", "slot_1_count": 0,
                   "examples": {"character/wind_spgirl/ui/episode_banner_0.png": [430, 215],
                                "character/black_wolf_knight_wt23/ui/episode_banner_0.png": [430, 215]}}
#: 表引用扫描（2026-09-27，一次性只读）：WF_PATHLIST_recovered.txt 的 2116 条 master/*.orderedmap 里 live store 有
#: 2111 张，逐张 unpack/zlib 递归解开，搜 b"episode_banner" 与 b"wind_spgirl_swim/ui/episode"：0 命中。
BANNER_TABLE_SCAN = {"pathlist_master_tables": 2116, "present_in_live": 2111, "hits": 0,
                     "needles": ["episode_banner", "wind_spgirl_swim/ui/episode"]}

# ---------------------------------------------------------------- 钉住的来源与 live 基线（生成，勿手改）
# BEGIN GENERATED
#: 交付包 handoff/cdn 的存储态字节："<tier>:<logical>" → sha256（= 灰链 1.4.88 同名成员）。
FILES = {
    "common:character/wind_spgirl_swim/voice/ally/evolution.mp3":
        "3a1d96444e017da11aadbf13addc6a0a9cf81c70a811a99464707b28c0932163",
    "common:character/wind_spgirl_swim/voice/ally/join.mp3":
        "68cce1ddcc61037fa56d58b89919155ad14920e29fa6b0e3f9bf6c6bb646f18a",
    "common:character/wind_spgirl_swim/voice/battle/battle_start_0.mp3":
        "e755292c89b9595136ba591cfe13b936b24ab54e3dec48874a403dd31accc9ba",
    "common:character/wind_spgirl_swim/voice/battle/battle_start_1.mp3":
        "42cf5b03233abf9e7d3bb0b75b6cc3702e580fbe0f0175c3c73c13ed613fae0b",
    "common:character/wind_spgirl_swim/voice/battle/outhole_0.mp3":
        "3cb463209c098b64431560692b9c5e30d03e1b313332b72b92cf47d2eaa18649",
    "common:character/wind_spgirl_swim/voice/battle/outhole_1.mp3":
        "89aa3970a2faae6604e17ca2b83a644e5e2d3b403e01878d79580af1bc15168d",
    "common:character/wind_spgirl_swim/voice/battle/power_flip_0.mp3":
        "831bc3d7c041892084201c48380fe3e5af862f36803ecc7c3603fe4daafb1371",
    "common:character/wind_spgirl_swim/voice/battle/power_flip_1.mp3":
        "b0ee8594abc68e24bc93778b1d13d7728ff1928a7a7a05d08e024126ea09d927",
    "common:character/wind_spgirl_swim/voice/battle/skill_0.mp3":
        "95d5333d6c8af7b5f2b4598d8f48610fef06ed0286be8815dfe3aad307b95be4",
    "common:character/wind_spgirl_swim/voice/battle/skill_1.mp3":
        "4cafc8bc444563390de4b8ee5fb9164e53442baf5c5dd0b1e390d42e89363d94",
    "common:character/wind_spgirl_swim/voice/battle/skill_ready.mp3":
        "3c1a758077a60f2da7bef1a5ba199a8d3989492aaa290a162adf5a7b11a04945",
    "common:character/wind_spgirl_swim/voice/battle/win_0.mp3":
        "6aadb787981601df0b496cf2033bda5f16a2e43a0ec35f28bf752a3036c5dffc",
    "common:character/wind_spgirl_swim/voice/battle/win_1.mp3":
        "bb8cf23b96931f210c865c7bcef0258470ea22310811b9d37c8cfe3bb7c094b6",
    "medium:character/wind_spgirl_swim/ui/episode_banner_0.png":
        "c575a309a384a9cac21f8b8500b5027122fb1e91ab19ad7aa31d7152fe18f3b3",
}

#: 交付包 handoff/decoded 的标准 MP3/PNG：member → sha256（extract 核对 wf_assets 解码 == 它）。
DECODED_SHA256 = {
    "common:character/wind_spgirl_swim/voice/ally/evolution.mp3":
        "e0083a4f819cfbd072ef331c7c9e4f482098ec83eae35791934fe204f5abb0ec",
    "common:character/wind_spgirl_swim/voice/ally/join.mp3":
        "cb68d951a7ab1c68f5030003f3bd0589e8903fce6fc2a0ce9e3fff991e1eac49",
    "common:character/wind_spgirl_swim/voice/battle/battle_start_0.mp3":
        "c9e7313a2cd406130045c5c9162c97e1d9d0cd27364af1c5a993f930545386c5",
    "common:character/wind_spgirl_swim/voice/battle/battle_start_1.mp3":
        "bf71a8fff65fcdd2000ad1f7884ba68aa792be79b5c4e20e7d38497a4a52052c",
    "common:character/wind_spgirl_swim/voice/battle/outhole_0.mp3":
        "fe7976ff5ee3ecbee0d6275c403d92ad77f5c9eac3517758943d98eacbf3e745",
    "common:character/wind_spgirl_swim/voice/battle/outhole_1.mp3":
        "e383b1752457e913b2defaab0f54ee068ff31464c26052af3b4bedc6119d6ec0",
    "common:character/wind_spgirl_swim/voice/battle/power_flip_0.mp3":
        "3103558075fd74aca49ccffbbe9d8192aa960266ca6cc202764915e0760e3d41",
    "common:character/wind_spgirl_swim/voice/battle/power_flip_1.mp3":
        "1ba46d176bed8bfa710665ebfdbbdff9e81af6750e258270754442678625a794",
    "common:character/wind_spgirl_swim/voice/battle/skill_0.mp3":
        "276782ff2fc4f5e1babbd75e07f2e76936e43cdcc400fad225ecb795e6d0784c",
    "common:character/wind_spgirl_swim/voice/battle/skill_1.mp3":
        "d2c0a6c4789c0ef258edf7d024df504b5665c910746afd416df54e19f35afc00",
    "common:character/wind_spgirl_swim/voice/battle/skill_ready.mp3":
        "8612e405c0e13e72cceff595b7579305f4c523790111913fce00001f6e480211",
    "common:character/wind_spgirl_swim/voice/battle/win_0.mp3":
        "44cc9ebe195dbdebe01bbcd6c43ba1f3010932bf02f3411e38f0d2eced6f1dfc",
    "common:character/wind_spgirl_swim/voice/battle/win_1.mp3":
        "29700fb34e99a52ee7ecbfb239a5a939818b03ee021befe48bf4e8dd9fe4eb99",
    "medium:character/wind_spgirl_swim/ui/episode_banner_0.png":
        "71dd713b6c3a2a2b577ea1bca22f49ef908362683e60c074afb7e58e1ca0ad2b",
}

#: live 输入基线（2026-09-27 本地链尾 1.4.1054 只读取数）：14 个目标路径的 file_sha256 摘要（banner live 缺失 = digest(None)）。
BEFORE = {
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/ally/evolution.mp3")):
        "3059f9ecb97ebc631e4f4351925e4b13f054163a4ccd851059efeba1708811e9",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/ally/join.mp3")):
        "187245a2470561247a2b250ec358197382c0b4eaba745ca59da8346b38c4c4ff",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/battle_start_0.mp3")):
        "8fe07fd7e13c1049a57f3851480e61501bf6492a3daa8992c6f0c565edc1a075",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/battle_start_1.mp3")):
        "8abc3783b9d26780ac3dba792ad04f232998397d76ba5e04191577c6f545b3be",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/outhole_0.mp3")):
        "27601987cadd44c250559e47991496845b3a64aa22db93bdd936cc0c9e3f037b",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/outhole_1.mp3")):
        "0e8b286731e3e674b6960bc976212e16dff87de99a89916a742ca700ff713c86",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/power_flip_0.mp3")):
        "1763fd838e92adec474ec70f9cca9652edeeb980fc7bb49496f804d7cae964ea",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/power_flip_1.mp3")):
        "af060e394455060f69ee7b9b2acf312136b5a90b8f23c552de90b92c749991b7",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/skill_0.mp3")):
        "5fcf40762ef634b89401e57d0e7188ec9a935fd845a2013507fb58eab711e88e",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/skill_1.mp3")):
        "57ea4f43e441cea4db58b1bfdb4f3597d24e3695d0c8d97c78e6cdb3d5981077",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/skill_ready.mp3")):
        "989e5286f4dc4fa34efa41c1c1378d86783f3a2081c776723013f9d921ae842f",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/win_0.mp3")):
        "b28798b13ef9f80916f060b3b0c64d72e9fc75b21e72d883f8da03ecb6eec059",
    ("file_sha256", ("common", "character/wind_spgirl_swim/voice/battle/win_1.mp3")):
        "4ed0218b822a1469278bcc133a80fd1f98b79c2a0df47ec81d5775ebde944a37",
    ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/episode_banner_0.png")):
        "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
}

#: live 旧版语音实测（mp3_facts；绑定 BEFORE 的 sha256，revise 读不到 live 字节，用它对照时长/帧/标签）。
LIVE_VOICE = {
    "common:character/wind_spgirl_swim/voice/ally/evolution.mp3":
        {"sha256": "25a25c4aa3938e6e5ede3c5c5aff78af7580e253ce6a6af223a55d74b77cefac", "bytes": 150062,
         "frames": 471, "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono",
         "duration_s": 12.3037, "id3v2_bytes": 2290, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "8dce8dca6f9da0da56e19cfd3c3006d13270e4fd70e3bf2ce4e9129e7ab6f719",
         "audio_sha256": "9c6ec2e7a07f4e6052f6e9567b33f83532e38e412f15a782a55df142ee5fa9c4"},
    "common:character/wind_spgirl_swim/voice/ally/join.mp3":
        {"sha256": "9f053522b46a105ceec81fb526c0c874ba12a77924d46df0f1323584bcbc412c", "bytes": 112443,
         "frames": 351, "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono",
         "duration_s": 9.169, "id3v2_bytes": 2288, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "e26e45af86be99fb15b8bb24b5ca655da615193f1c390e14b4cb9a1a1fd57286",
         "audio_sha256": "8b5aa1dfad650c4b81b7366b15581898e8cafd2c38d71da4645a403a30832782"},
    "common:character/wind_spgirl_swim/voice/battle/battle_start_0.mp3":
        {"sha256": "82d9876218fde7f5e2b540183a581ae7b8a9ca942f44eca1b5ba3394e8355298", "bytes": 23897, "frames": 69,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 1.8024,
         "id3v2_bytes": 2140, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "723888d6c217f387e01a109a780f775f117639924861c9d70917deb98db72d77",
         "audio_sha256": "543ae5cea2fd0f4e4def3e38734bb02ff5dd73142483f5844e910ea766a8ab19"},
    "common:character/wind_spgirl_swim/voice/battle/battle_start_1.mp3":
        {"sha256": "6bc2492693ddc30e26b2d295a1cc62625792a53854c9d4e03e3f12a52c4f8bbc", "bytes": 26716, "frames": 78,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 2.0376,
         "id3v2_bytes": 2138, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "61bcd59376ca37e1048ab85dc41de7adb6d7f61c765c43bc5d1bb75013cba849",
         "audio_sha256": "5a516acee540b6d83f4b017a55d9f98f4fe56b5630985d73fe77e0bed291adc2"},
    "common:character/wind_spgirl_swim/voice/battle/outhole_0.mp3":
        {"sha256": "686e8ae806f6ba4401c774aea8e1a30d0e21e5438c26f270c3d23b6e43cf1d9f", "bytes": 11348, "frames": 29,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 0.7576,
         "id3v2_bytes": 2130, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "2eb3ace3c6eb6f55a2f3351674e2dbed203fae8bd0cd829338561d994b69340f",
         "audio_sha256": "0f857e31972d5507decee80b442540b16f8b11adc5efaeda264daa3f65e7eea1"},
    "common:character/wind_spgirl_swim/voice/battle/outhole_1.mp3":
        {"sha256": "f693ab73bec9a83d9d65ff45b7924df610916301a0a5e4fbf8a231cae45317fa", "bytes": 19502, "frames": 55,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 1.4367,
         "id3v2_bytes": 2134, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "e5fd0e1716e8d9b93124c421eced6551690313d34c6aa604ad6c8803f009982a",
         "audio_sha256": "c907e8fc240ad25f7b1c28ae7317839f0ada8a4bb82baf31cb0e209c9b51fcff"},
    "common:character/wind_spgirl_swim/voice/battle/power_flip_0.mp3":
        {"sha256": "446488b15c5269f98d606f8de06729d61233063cf7fbe097b6cf47482dc2f854", "bytes": 11622, "frames": 30,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 0.7837,
         "id3v2_bytes": 2090, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "e6f308f05ed1ec8953adb78834a66f1f71ef88f5332f3a6bb7529c3cda284d2f",
         "audio_sha256": "9871415a05ae4e624470f94e46694369f941722d2cd2ce5e2e410216c20a77fe"},
    "common:character/wind_spgirl_swim/voice/battle/power_flip_1.mp3":
        {"sha256": "c56adfe5857bfca9d6916feb0ea5d605e54cc69a39e0adba554c40b81bd3a579", "bytes": 15401, "frames": 42,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 1.0971,
         "id3v2_bytes": 2108, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "b58b55cb448e3c43e9e5839e031806eb8057a515e2ef01e62e1439d3b32fae76",
         "audio_sha256": "f4d2759bdee3cba556ce2f0199db82a8e4190892f0433ce09fbedc023e56c7a4"},
    "common:character/wind_spgirl_swim/voice/battle/skill_0.mp3":
        {"sha256": "72d30d93b9008f643df195892573b699e31f1436a8094c6566ac700c0e23b2ef", "bytes": 24192, "frames": 70,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 1.8286,
         "id3v2_bytes": 2122, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "203298a0f01a421a596508c7794eaa74452bc2ee2c28de5ae5c407e8c408c673",
         "audio_sha256": "c7c3ecbc7f5026e06c71b33cd3f943e947af90554ae867c71bfbfebdd4ad7614"},
    "common:character/wind_spgirl_swim/voice/battle/skill_1.mp3":
        {"sha256": "2f92a43ecefb44149dc98a69f54f72f61b6abcb20790031e63784bf4cb07fd52", "bytes": 22929, "frames": 66,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 1.7241,
         "id3v2_bytes": 2112, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "9e3660555a5f91b8596ebd22c07dd70cda4040c9c3652558b886971d5661c918",
         "audio_sha256": "a938180a3248793d156d87ecd0128994248661ada2d5274c87d7f8767c1b6180"},
    "common:character/wind_spgirl_swim/voice/battle/skill_ready.mp3":
        {"sha256": "9da614e06d1ff4f6d0344956faea31aad89f2c24f4dba36c45be34a8a39377ea", "bytes": 10995, "frames": 28,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 0.7314,
         "id3v2_bytes": 2090, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "ab7b9538e5f09a6d892781240628f0bbe60a20584d615eb55bf1dda8fc6beae6",
         "audio_sha256": "727eea75b957066328be06049d7a2ee320be2ee796675a21f9bada213a2905d7"},
    "common:character/wind_spgirl_swim/voice/battle/win_0.mp3":
        {"sha256": "83d456c35e4839aa838bbe3dd2f55318025aa0ea71979b4fd8b32afffd672215", "bytes": 38923, "frames": 117,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 3.0563,
         "id3v2_bytes": 2120, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "73aba6330000b3e8e1204bd6a9f3ab2ee5603a9c4a5d92d7426532bde2fc7e84",
         "audio_sha256": "54c697a39ee322a6134603fb87278d78bd24908f5125272c713579b446ccdf2b"},
    "common:character/wind_spgirl_swim/voice/battle/win_1.mp3":
        {"sha256": "4c96792313502ef5729bfb412c955bfb8d4f485e5404fc471ef12b48956d3a64", "bytes": 44596, "frames": 135,
         "bitrate_kbps": 96, "sample_rate": 44100, "mpeg": "1", "channels": "mono", "duration_s": 3.5265,
         "id3v2_bytes": 2150, "id3v2_padding": 2048,
         "id3v2_head_frames_sha256": "0e5e4144b80451524016a50a1f5af017829d910573c369a225f06ac98f32f619",
         "audio_sha256": "18d3ca53b8e645fc9f35ad5c668a1249755b9d543628923505b505524a2be7c3"},
}

#: 交付包没带的 6 条 home 语音：灰链 1.4.88 与 live 两边字节（只报告，不导入）。
HOME_NOT_IN_HANDOFF = {
    "common:character/wind_spgirl_swim/voice/home/alk_niisama.mp3":
        {"live_sha256": "2cf310437c25bac57c44ee08c9bb703db2410e94ef089d6f1c4f8a47a3ab868e",
         "gray_chain_sha256": "c2c7b77e9a04af47e5a217f00aa89403fe47b03ad9bfa3952863b1f3e620d909",
         "live_bytes": 124024, "gray_chain_bytes": 123925, "duration_s": 10.1355, "audio_frames_identical": True},
    "common:character/wind_spgirl_swim/voice/home/kuga.mp3":
        {"live_sha256": "7bf37d787716123e4b744a2b2d228caa02d5eea5e0d0acdef4de7f1d09ba4c25",
         "gray_chain_sha256": "d5dd170816fb26dcd9603fd2e3b20b049f873b71dbc48001fe26b1ec128abf5f",
         "live_bytes": 182088, "gray_chain_bytes": 181955, "duration_s": 14.9682, "audio_frames_identical": True},
    "common:character/wind_spgirl_swim/voice/home/stella_nesamatachito.mp3":
        {"live_sha256": "cf42f98f672116fa6014504e6b83d6378dfddc0d058b7d3ef311990303107dba",
         "gray_chain_sha256": "22db9a5d598df6775555992ba311c91ddcd7c68236bc1f146e96f78ec1de69ed",
         "live_bytes": 124964, "gray_chain_bytes": 124865, "duration_s": 10.2139, "audio_frames_identical": True},
    "common:character/wind_spgirl_swim/voice/home/chikagorowa.mp3":
        {"live_sha256": "3ec56d69877ec4424fb6830e6910d7be6fa075de0b359eaf85e5996e43823c6e",
         "gray_chain_sha256": "ba666a81d6a6dfea5b072bf3566037885defa825c0ba5dc20f049df758e8dd3a",
         "live_bytes": 141600, "gray_chain_bytes": 141491, "duration_s": 11.5984, "audio_frames_identical": True},
    "common:character/wind_spgirl_swim/voice/home/konokenniwa.mp3":
        {"live_sha256": "a2bc933706f85df0fcbd238d241f46c8d4e30cf228837442e8ed538a4067467f",
         "gray_chain_sha256": "f89ab857c39afae57af0d2d0db04679cd1ec4b1af6db9b8f653a75651f0d20b2",
         "live_bytes": 153524, "gray_chain_bytes": 153411, "duration_s": 12.591, "audio_frames_identical": True},
    "common:character/wind_spgirl_swim/voice/home/udewo.mp3":
        {"live_sha256": "14fc5d910f3a3a5a283a9e59af830b8f5700d337b92157d585299d907a8db0a5",
         "gray_chain_sha256": "d3ef7621272cea49c9c2e702512c443963398138ca8132312709ef0a41bdc4a6",
         "live_bytes": 138439, "gray_chain_bytes": 138346, "duration_s": 11.3371, "audio_frames_identical": True},
}
# END GENERATED


class SwimAssetsError(ValueError):
    """来源或 live 输入与审查时不符、或资源校验失败：拒绝导入（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def split_member(member: str) -> tuple[str, str]:
    tier, logical = member.split(":", 1)
    return tier, logical


def is_voice(member: str) -> bool:
    return split_member(member)[1].endswith(".mp3")


# ---------------------------------------------------------------- 资源校验（纯函数）

def id3v2_size(data: bytes) -> int:
    """开头 ID3v2 标签总长（含 10 字节头；unsynchsafe），没有标签为 0。"""
    if data[:3] != b"ID3" or len(data) < 10:
        return 0
    raw = int.from_bytes(data[6:10], "big")
    size, mask = 0, 0x7F000000
    while mask:
        size >>= 1
        size |= raw & mask
        mask >>= 8
    return size + 10


def id3v2_layout(data: bytes) -> dict:
    """ID3v2 标签的三段：头 10 字节、帧区、尾部填充（全零）。"""
    total = id3v2_size(data)
    pos = 10
    while 0 < total and pos + 10 <= total and data[pos:pos + 4] != b"\0\0\0\0":
        pos += 10 + int.from_bytes(data[pos + 4:pos + 8], "big")
    padding = data[pos:total] if total else b""
    return {"total": total, "frames_bytes": max(pos - 10, 0) if total else 0, "padding": len(padding),
            "padding_zero": not padding.strip(b"\0"),
            "head_frames_sha256": hashlib.sha256(data[:6] + data[10:pos]).hexdigest() if total else None}


def mp3_facts(stored: bytes) -> dict:
    """存储态 MP3（帧头 0x7F）严格校验并量化。口径同 ``wf_assets.mp3_encode``：标准态重新编码必须逐字节回到存储态
    （CBR、逐帧覆盖到文件尾，否则 mp3_encode 抛错），另要求探测 tail = 0。"""
    standard = A.mp3_decode(stored)
    try:
        again = A.mp3_encode(standard)
    except ValueError as exc:
        raise SwimAssetsError(f"MP3 strict check failed: {exc}") from exc
    if again != stored:
        raise SwimAssetsError("MP3 storage round trip differs (decode → encode != stored bytes)")
    probe = A.mp3_probe(stored, 1023)
    if probe["frames"] == 0 or probe["tail"]:
        raise SwimAssetsError(f"MP3 frames do not cover the file: frames={probe['frames']} tail={probe['tail']}")
    if len(probe["bitrates"]) != 1 or len(probe["srates"]) != 1:
        raise SwimAssetsError(f"MP3 not CBR: {sorted(probe['bitrates'])} / {sorted(probe['srates'])}")
    head = id3v2_size(stored)
    header = int.from_bytes(stored[head:head + 4], "big")
    version = header >> 19 & 3
    samples = 1152 if version == 3 else 576
    (bitrate,), (rate,) = probe["bitrates"], probe["srates"]
    layout = id3v2_layout(stored)
    return {"bytes": len(stored), "frames": probe["frames"], "bitrate_kbps": bitrate // 1000, "sample_rate": rate,
            "mpeg": {3: "1", 2: "2", 0: "2.5"}[version],
            "channels": "mono" if header >> 6 & 3 == 3 else "stereo",
            "duration_s": round(probe["frames"] * samples / rate, 4),
            "id3v2_bytes": head, "id3v2_padding": layout["padding"],
            "id3v2_head_frames_sha256": layout["head_frames_sha256"],
            "audio_sha256": hashlib.sha256(stored[head:]).hexdigest()}


_PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_PNG_MODES = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}


def png_facts(stored: bytes) -> dict:
    """存储态 PNG（魔数小写 ``png``）严格校验：逐块 CRC、IHDR、IDAT 解压长度 = 行数 × (1 + 行字节)、每行滤波字节 0-4、
    IEND 后无尾随字节。只用标准库。"""
    if stored[:8] != A.PNG_FAKE:
        raise SwimAssetsError("PNG not in storage state (magic must be 89 'png')")
    data = A.png_decode(stored)
    pos, ihdr, idat, ended = 8, None, [], False
    while pos < len(data):
        if pos + 12 > len(data):
            raise SwimAssetsError("PNG truncated chunk")
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        if len(body) != length or len(crc) != 4 or zlib.crc32(kind + body) != int.from_bytes(crc, "big"):
            raise SwimAssetsError(f"PNG chunk CRC/length mismatch: {kind!r}")
        pos += 12 + length
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            ended = True
            break
    if ihdr is None or not idat or not ended or pos != len(data):
        raise SwimAssetsError("PNG structure incomplete (IHDR/IDAT/IEND or trailing bytes)")
    width, height, depth, color, _compression, _filter, interlace = ihdr
    if interlace != 0 or color not in _PNG_CHANNELS:
        raise SwimAssetsError(f"PNG unsupported layout: color={color} interlace={interlace}")
    pixels = zlib.decompress(b"".join(idat))
    stride = 1 + (width * _PNG_CHANNELS[color] * depth + 7) // 8
    if len(pixels) != height * stride or any(pixels[row * stride] > 4 for row in range(height)):
        raise SwimAssetsError("PNG pixel data length / filter bytes do not match IHDR")
    return {"bytes": len(stored), "size": [width, height], "bit_depth": depth, "mode": _PNG_MODES[color],
            "stored_magic": "png"}


# ---------------------------------------------------------------- 来源：解出目录 / 钉哈希的交付包

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cdn_member(member: str) -> str:
    tier, logical = split_member(member)
    return f"{HANDOFF_DIR}/cdn/{tier}/{logical}"


def decoded_member(member: str) -> str:
    return f"{HANDOFF_DIR}/decoded/{split_member(member)[1]}"


def open_handoff(archive: Path | str | None = None) -> zipfile.ZipFile:
    """按 HANDOFF_SHA256 核对整包后打开；不符即拒绝。"""
    path = Path(HANDOFF if archive is None else archive)
    if not path.is_file():
        raise SwimAssetsError(f"handoff archive not found: {path}")
    if _sha256_file(path) != HANDOFF_SHA256:
        raise SwimAssetsError(f"handoff archive sha256 mismatch: {path}")
    return zipfile.ZipFile(path)


def decode_standard(member: str, stored: bytes) -> bytes:
    return A.mp3_decode(stored) if is_voice(member) else A.png_decode(stored)


def extract(root: Path | str | None = None, archive: Path | str | None = None) -> int:
    """把钉哈希的交付包里这 14 个 cdn 成员解到 ``root``（默认 HANDOFF_ROOT，布局 ``<tier>/<logical>``）；逐个核 FILES，
    并核对 ``wf_assets`` 解码结果 == 包内 decoded 成员（DECODED_SHA256）。已相同的跳过，返回写入个数。
    只写 ``root`` 下的文件（默认仓库 work/gray3/handoff_v2，已 gitignore）；不碰 live/assets/.cdn/候选。"""
    root = HANDOFF_ROOT if root is None else Path(root)
    written = 0
    with open_handoff(archive) as zf:
        names = set(zf.namelist())
        for member in sorted(FILES):
            for name in (cdn_member(member), decoded_member(member)):
                if name not in names:
                    raise SwimAssetsError(f"handoff member missing: {name}")
            data = zf.read(cdn_member(member))
            if hashlib.sha256(data).hexdigest() != FILES[member]:
                raise SwimAssetsError(f"handoff member changed: {member}")
            decoded = zf.read(decoded_member(member))
            if hashlib.sha256(decoded).hexdigest() != DECODED_SHA256[member]:
                raise SwimAssetsError(f"handoff decoded member changed: {member}")
            if decode_standard(member, data) != decoded:
                raise SwimAssetsError(f"handoff cdn bytes do not decode to its decoded member: {member}")
            path = root.joinpath(*split_member(member))
            if path.is_file() and path.read_bytes() == data:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written += 1
    return written


class HandoffSource:
    """交付包成员：``root``（默认 HANDOFF_ROOT）下有就读它，没有就从钉哈希的 ``archive``（默认 HANDOFF）直接读；
    每次取字节都按 FILES 核 sha256（缺失/被改即拒绝）。``file_path`` 只认 ``root`` 下已解出的文件。"""

    def __init__(self, root: Path | str | None = None, archive: Path | str | None = None):
        self.root = HANDOFF_ROOT if root is None else Path(root)
        self.archive = HANDOFF if archive is None else Path(archive)
        self._zip: zipfile.ZipFile | None = None

    def path(self, tier: str, logical: str) -> Path:
        return self.root.joinpath(tier, logical)

    def raw(self, tier: str, logical: str) -> bytes:
        member = f"{tier}:{logical}"
        want = FILES.get(member)
        if want is None:
            raise SwimAssetsError(f"not a handoff import member: {member}")
        path = self.path(tier, logical)
        if path.is_file():
            data = path.read_bytes()
        elif self.archive.is_file():
            if self._zip is None:
                self._zip = open_handoff(self.archive)
            data = self._zip.read(cdn_member(member))
        else:
            raise SwimAssetsError(f"handoff member missing: {member} (neither {path} nor {self.archive}); restore "
                                  "the zip and run `python mod-tools/wf_balance_20260927c_swimassets.py extract`")
        if hashlib.sha256(data).hexdigest() != want:
            raise SwimAssetsError(f"handoff member changed: {member}")
        return data

    def file_path(self, tier: str, logical: str) -> str:
        path = self.path(tier, logical)
        if not path.is_file():
            raise SwimAssetsError(f"extracted member missing: {tier}:{logical} ({path}); "
                                  "run `python mod-tools/wf_balance_20260927c_swimassets.py extract` first")
        self.raw(tier, logical)                          # 落地字节同样核 sha256
        return str(path)


# ---------------------------------------------------------------- live 输入

def _baseline(read: Callable[[str, Any], Any]) -> None:
    for (kind, key), want in BEFORE.items():
        try:
            value = read(kind, key)
        except (KeyError, FileNotFoundError) as exc:
            raise SwimAssetsError(f"live input unreadable: {kind}:{key} ({exc!r}); file_sha256 needs the stage "
                                  "reader extension (extra5 make_read)") from exc
        if digest(value) != want:
            raise SwimAssetsError(f"unreviewed live baseline: {kind}:{key}")


def _references(read: Callable[[str, Any], Any]) -> dict:
    """语音/横幅路径的表引用门禁（不改表、不锁摘要）。"""
    try:
        speech = read("table", (SPEECH, CID))
        character = read("table", (CHAR, CID))
    except (KeyError, FileNotFoundError) as exc:
        raise SwimAssetsError(f"live input unreadable: {exc!r}") from exc
    if not character or len(character[0]) <= 8:
        raise SwimAssetsError("character row too short")
    string_id, image_prefix = character[0][0], character[0][8]
    if (string_id, image_prefix) != (CODE, CODE):
        raise SwimAssetsError(f"character c0/c8 must be {CODE}: {string_id!r}/{image_prefix!r}")
    paths = {row[0]: row[4] for row in speech if len(row) >= 5 and row[0] in SPEECH_VOICES}
    if paths != SPEECH_VOICES:
        raise SwimAssetsError(f"character_speech join/evolution voice_path drift: {paths}")
    speech_voices = {row[4] for row in speech if len(row) >= 5 and row[4] not in ("", "(None)")}
    quests = []
    for key in QUEST_KEYS:
        try:
            read("table", (CHARACTER_QUEST, key))
        except KeyError:
            continue
        quests.append(key)
    if quests:
        raise SwimAssetsError(f"character_quest rows appeared ({quests}): the episode banner would be displayed, "
                              "re-review before importing")
    return {"string_id": string_id, "image_prefix": image_prefix,
            "speech_rows": len(speech), "speech_voice_paths": sorted(speech_voices),
            "speech_row_digest": digest(speech), "character_quest_keys_absent": list(QUEST_KEYS)}


def _empty() -> dict:
    return {"ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {},
            "server_text": {}, "server_character": {}, "nested_table": {}, "presentation_table": {},
            "files": {}, "new_programs": []}


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any], source: Any = None) -> dict:
    """live（BEFORE 锁定的 14 个 file_sha256）→ 交付包里的 14 个文件。``source`` 默认 ``HandoffSource()``。"""
    _baseline(read)
    refs = _references(read)
    source = source if source is not None else HandoffSource()
    out = _empty()
    voices, banner = {}, None
    for member in sorted(FILES):
        tier, logical = split_member(member)
        data = source.raw(tier, logical)
        if hashlib.sha256(data).hexdigest() != FILES[member]:
            raise SwimAssetsError(f"handoff member changed: {member}")
        if is_voice(member):
            gray = mp3_facts(data)
            live = LIVE_VOICE[member]
            voices[member] = {
                "gray": gray, "live": deepcopy(live),
                "delta_bytes": gray["bytes"] - live["bytes"],
                "delta_frames": gray["frames"] - live["frames"],
                "delta_duration_s": round(gray["duration_s"] - live["duration_s"], 4),
                "audio_frames_identical": gray["audio_sha256"] == live["audio_sha256"],
                "id3v2_head_and_frames_identical": gray["id3v2_head_frames_sha256"] == live["id3v2_head_frames_sha256"],
                "id3v2_padding_delta": gray["id3v2_padding"] - live["id3v2_padding"],
                "referenced_by": ("character_speech" if logical.split("/voice/", 1)[1][:-4] in SPEECH_VOICES.values()
                                  else "engine fixed name (CharacterShortVoiceLogic)"),
            }
        else:
            banner = png_facts(data)
        out["files"][member] = source.file_path(tier, logical)
    if banner is None or banner["size"] != OFFICIAL_BANNER["size"] or banner["mode"] != OFFICIAL_BANNER["mode"]:
        raise SwimAssetsError(f"episode banner does not match the official banner shape: {banner}")
    out["notes"] = _notes(voices, banner, refs)
    return out


def _notes(voices: dict, banner: dict, refs: dict) -> dict:
    identical = sorted(m for m, v in voices.items() if v["audio_frames_identical"])
    return {
        "source": "mod-tools/wf_balance_20260927c_swimassets.py",
        "character": f"{CID} {CODE} 希尔媞「千刃共振」泳装",
        "author_request": ("「对方补了资源」（2026-09-27，附 four-character-author-handoff-v2.zip）；延续「把这版替换我本地的,"
                           "然后一并纳入调整」（gray3，1.4.1054 已导入表/DSL/美术，当时语音未导入）"),
        "handoff": {"path": str(HANDOFF), "sha256": HANDOFF_SHA256, "resource_tail": HANDOFF_RESOURCE_TAIL,
                    "directory": HANDOFF_DIR, "extracted_root": str(HANDOFF_ROOT), "imported_members": len(FILES),
                    "provenance": (f"与灰链归档 1.4.87→1.4.88 边（{GRAY_CHAIN_ZIP}，sha256 {GRAY_CHAIN_ZIP_SHA256}）"
                                   "里的同名 14 个成员逐字节相同")},
        "file_sha256": dict(FILES),
        "voices": {
            "count": len(voices),
            "audio_frames_identical": len(identical),
            "summary": ("13 条语音音频帧与 live 逐字节相同（去 ID3v2 标签后 sha256 相同；帧数/码率/时长全同，"
                        "MPEG-1 Layer III 96 kbps CBR 44.1 kHz 单声道）；差异只在 ID3v2 标签尾部零填充"
                        "（live 2048 字节 → 灰版 1941–2039），标签头与帧区逐字节相同。听感零变化，导入只让字节与灰服对齐"),
            "strict_check": "wf_assets.mp3_encode(mp3_decode(x)) == x（CBR、逐帧覆盖到文件尾）且 mp3_probe tail = 0",
            "by_member": voices,
        },
        "banner": {
            "member": BANNER, "facts": banner, "official": deepcopy(OFFICIAL_BANNER),
            "table_references": deepcopy(BANNER_TABLE_SCAN),
            "client": ("CharacterBaseImpl.getEpisodeBannerImagePath（as:206-209）= character/<image_prefix>/ui/episode_banner_0，"
                       "只有角色剧情列表 EpisodeCharacterSelect 与主页剧情气泡 HomeQuestButtonCharacterEpisodeBalloon 用"),
            "status": ("休眠：149996 没有角色剧情（character_quest 无 1499960{1,2,3}），导入后不会显示；"
                       "wf_character_requirements 归 excluded（不在 37 项硬门）"),
        },
        "references": refs,
        "tables_changed": "无（character_speech / character / character_quest 只读门禁）",
        "not_in_handoff": {
            "home_voices": deepcopy(HOME_NOT_IN_HANDOFF),
            "why": ("交付包 v2 的 voice 只有 13 条（报告 coverage.voice=13、voice_counts 为空；导出器按通用名 home_0..9 探测，"
                    "漏掉 speech 表注册的 6 条自定义名 home 语音）"),
            "gray_chain": ("灰链 1.4.88 对这 6 条做了同样的 ID3v2 填充裁剪，音频帧与 live 相同；要逐字节对齐可从 GRAY_CHAIN_ZIP 取，"
                           "本模块不导入"),
        },
        "relation_to_gray3": ("gray3.NOT_IN_ARCHIVE['149996'] 记的「19 条语音未导入」= 本模块 13 条 + not_in_handoff 6 条 home"),
        "risks": [
            "语音导入不改变可听内容（音频帧逐字节相同），只让字节与灰服对齐；发布会多铸 13 个 common 文件（约 0.5 MB）",
            "剧情横幅当前不被任何表或剧情引用，导入后不显示；将来若给 149996 加角色剧情，它才会出现在剧情列表",
            "HOME 6 条仍是我方字节（与灰服不逐字节相同，但音频相同）",
            "历史工作区 work/character_packs/xierti_swim（未被 active 引用）的包根与 build_voice/align_voice/"
            "install_to_live 等脚本持有这 13 条语音的旧字节，重跑或 flow 发布会把语音退回旧版，不得重跑",
        ],
        "stage_integration": [
            "read 需 file_sha256 种类：(tier, logical) → live 文件 sha256 或 None（extra5 make_read 已支持）；"
            "另读 table：character_speech/character 的 149996 行、character_quest 1499960{1,2,3}（KeyError = 不存在）",
            "files：BarePlan.emit(tier, logical, bytes)；tier ∈ common（13 条语音）/ medium（横幅）；"
            "stage_batch 按 notes.file_sha256 复核暂存字节",
            "无表、无 DSL、无候选（PACKAGES = []）",
        ],
        "runtime_verified": False,
    }


#: 多角色接口（extra5 stage_batch 按 UNITS 暂存；单条 ⇒ plan 名 swimassets--bare）。
UNITS = [dict(CID=CID, CODE=CODE, PACKAGES=list(PACKAGES), PACKAGE_VERSION=dict(PACKAGE_VERSION),
              CAPABILITIES=list(CAPABILITIES), REVIEWED_DRIFT=dict(REVIEWED_DRIFT), BEFORE=BEFORE,
              revise=revise)]


# ---------------------------------------------------------------- 命令行：解包

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="泳装希尔媞灰版资源补齐：从钉哈希的交付包解出 14 个文件")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("extract", help="把交付包里的 14 个 cdn 成员解到 HANDOFF_ROOT（默认 work/gray3/handoff_v2）")
    cmd.add_argument("--root", default=None)
    cmd.add_argument("--archive", default=None)
    args = parser.parse_args(argv)
    count = extract(args.root, args.archive)
    print(f"extracted {count} new/changed member(s) to {HANDOFF_ROOT if args.root is None else args.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
