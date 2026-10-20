"""第三轮训练恢复、GM只带本体的中文交付章节。"""
import json
import common as c

def read(name):return json.loads((c.ROOT/'audit'/name).read_text('utf-8'))

def sections():
    policy=read('inclusion-policy-r3.json')
    lines=['','## GM武器只带数据，正式服不开放获取','',
           '作者2026-10-16 17:14拍板：“新木桩和武器带上吧反正正式服不开放gm武器获取”。本轮收入GM5990001–5990006的武器本体、文本、图标引用、属性/强化/魂珠使用配套及GM DSL。',
           '只恢复定义和正常显示/使用所需数据，不新增商店商品、掉落、奖励、任务、兑换、邮件或礼包发放项。item_ids/equipment_ids等是识别注册，代码不会仅因注册就自动生成玩家商店商品或卡池候选。',
           '已有管理后台通过显式操作人工授予道具/邮件的能力属于既有管理功能；本包未新增任何邮件/礼包条目，未自动授予任何账号，也未把后台操作开放给玩家。','',
           '### 收入哪些客户端行和资源','']
    notes=c.ROOT/'audit/gm-client-r3.md'
    if not notes.exists():notes=c.OUT/'附录/客户端准入第三轮.md'
    lines.append(notes.read_text('utf-8'))
    lines+=['','### 收入哪些服务端行','',
            (c.ROOT/'audit/gm-server-r3.md').read_text('utf-8'),'',
            '## 剔除清单：仅GM武器获取途径','',
            f"本轮客户端刻意不收的获取途径表键{len(policy['excluded_rows'])}项、独立成员{len(policy['excluded_members'])}项。输入源中若没有获取条目，明确记0，不虚构被剔除行。训练副本和GM本体已不在剔除清单。",'',
            '### 获取途径独立审查','',
            (c.ROOT/'audit/gm-route-review-r3.md').read_text('utf-8'),'',
            '### 混合行处理','',
            '遇到获取途径与正常内容同一行且无法安全分离时，不收该行并记录阻塞。本轮已审计范围未发现这种混合行；未通过修改检查器或静默覆盖处理。','',
            '## 训练木桩全部恢复','',
            '恢复21个训练副本1103–1123及目录、Boss/等级、Zone/Field、地形、DSL、训练道具/等级和图集配套；包括后补的wf_dummy_skill_charge_half等级行。终态取我方219，逐键读回核对，完整清单见上述客户端准入章节及附录/inclusion-policy-r3.json。','']
    return lines
