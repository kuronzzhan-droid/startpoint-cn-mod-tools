"""汇总本次实测证据，生成给灰的中文说明和最终report。"""
import json
from pathlib import Path
import shutil
import common as c
from report_priority_sections import version_section, priority_section, alignment_section
from report_inclusion_r3 import sections as inclusion_sections

def read(p):
    return json.loads(Path(p).read_text('utf-8-sig'))

def main():
    annex=c.OUT/'附录';annex.mkdir(exist_ok=True)
    evidence=['inputs.json','client-conflicts.json','client-members.json','client-merged-tables.json',
              'client-verification.json','text-normalizations.json','apk-dependencies.md',
              'apk-dependencies.json','server-audit.json','server-audit.md','server-verification.json',
              'server-source-supplement.json','prepush-audit.md','five-priority-220.json','five-priority-220.md',
              'defect-resolutions-220.json','defect-resolutions-220.md','alignment-220.json',
              'alignment-220.md','priority-applied-220.json','five-server-verification.json',
              'inclusion-policy-r3.json','inclusion-verification-r3.json','gm-client-r3.md',
              'gm-server-r3.json','gm-server-r3.md','gm-route-review-r3.json','gm-route-review-r3.md',
              'gm-route-source-r3.json','review-r3.json','review-r3.md']
    for name in evidence:
        source=c.ROOT/'audit'/name
        if source.exists():shutil.copyfile(source,annex/name)
    report=read(c.OUT/'report.json');entry=read(c.OUT/'manifest-entry-1.4.220.json')
    pre_note=annex/'prepush-audit.md'
    if pre_note.exists():
        text=(pre_note.read_text('utf-8')
              .replace('本次13个新包',f"本次{len(entry['chain'])}个新包")
              .replace('cdn_version137','cdn_version1.4.220')
              .replace('新137包','新220包'))
        pre_note.write_text(text,'utf-8')
    client=read(annex/'client-verification.json');server=read(annex/'server-audit.json')
    prepush=read(c.OUT/'prepush-summary.json');policy=read(annex/'exclusions.json')
    align_pre=read(c.OUT/'prepush-align-summary.json')
    five=read(annex/'five-priority-220.json')
    defects=read(annex/'defect-resolutions-220.json')
    groups=read(annex/'function-groups.json');conflicts=read(annex/'client-conflicts.json')
    norms=read(annex/'text-normalizations.json');schedule=read(annex/'schedule.json')
    gm_server=read(annex/'gm-server-r3.json')
    assert prepush['returncode']==0 and prepush['counts']['ERROR']==0, 'prepush尚未通过'
    assert align_pre['returncode']==0 and align_pre['counts']['ERROR']==0, '测试对齐prepush尚未通过'
    report.update({'from':'1.4.136','to':'1.4.220','since':'1.4.219',
                   'conflicts':len(conflicts)+server['conflict_count'], 'server_conflicts':server['conflict_count'],
                   'server_files':server['file_count'],'server_entries':server['entry_count'],
                   'round':3,'author_decision':'2026-10-16 17:14 木桩与GM本体收入，正式服不开放GM获取',
                   'exclusions':{'category':'仅GM武器获取途径','client_table_keys':len(policy['excluded_rows']),
                                 'client_members':len(policy['excluded_members']),'server_entries':server['excluded_count']},
                   'inclusions':{'training_quests':len(policy['restored_quests']),
                                 'training_table_keys':len(policy['restored_dummy_rows']),
                                 'training_members':len(policy['restored_dummy_members']),
                                 'gm_weapons':policy['gm_weapon_ids'],'gm_body_table_keys':len(policy['gm_body_rows']),
                                 'gm_body_members':len(policy['gm_body_members']),
                                 'gm_server_rows':gm_server['included_count']},
                   'schedule_quests':schedule['count'],'prepush':prepush['counts'],
                   'alignment':{'from':'1.4.219','to':'1.4.220','audit':'附录/alignment-220.json',
                                'prepush':align_pre['counts']},
                   'priority':{'five_client_rows':len(five['client_rules']),
                               'five_server_paths':len(five.get('server_rules',[])),
                               'five_changed_vs_default_column_merge':five['overrides_vs_default'],
                               'defect_fixes':sum(r['resolution']=='ours' for r in defects['rules'])},
                   'normalizations':norms,'client_verification':{'checks':len(client['checks']),'passed':True},
                   'runtime_validation':'未核实；本任务禁止启动服务器/设备，只有离线与静态验证',
                   'remaining_deployment_requirements':['灰决定72副本开放排期','灰移植超限服务端源码并编译/运行验证',
                                                        '核实灰客户端含所需APK补丁并实机验证']})
    c.write_json(c.OUT/'report.json',report)
    server_note=f"# 服务端第三轮审计\n\n固定灰基线{report['hui_ref']}，目标136→220。{server['file_count']}文件/{server['entry_count']}操作，冲突{server['conflict_count']}，获取途径排除{server['excluded_count']}。\n\n"+(annex/'gm-server-r3.md').read_text('utf-8')
    for name in ['server-audit.md','服务端审计.md']:(annex/name).write_text(server_note,'utf-8')
    lines=['# 给灰的 1.4.136 → 1.4.220 分享包说明（第三轮）','',
      '这是离线交付包，以灰的链尾 **1.4.136** 为目标基线，将我方 **1.4.219 终态**相对共同祖先 **1.4.130** 的数据增量三方合并成一条新边。',
      f"灰基线固定为 `Ku1o/startpoint-cn-kulo` 的 `{report['hui_ref']}`，原清单88项；我方清单172项（含禁用候选），实际重放131–219共89条启用边/105包。灰分叉后重放6条边/8包。",'',
      '**交付状态：离线构建、读回校验和 prepush 已通过；未部署、未安装、未启动任何服务端或设备。** 超限必须配套服务端源码和APK补丁，数据行本身不实现超限接口。新增72个决战副本保留来源时间，需由灰重新排期。',
      '', '## 包、锚点与完整性','',
      f"共 **{len(entry['chain'])}包、{report['members']}个唯一成员、{report['merged_tables']}张改动表**；每包≤5MiB。成员沿用灰的 `production/upload|medium_upload|android_upload/.../<hash>` 格式，没有引入APK、keystore、签名或.so。",'',
      '| 序号 | 文件 | 字节 | MiB | 成员数 |','|---|---|---:|---:|---:|']
    for i,x in enumerate(entry['archive_integrity'],1):
        lines.append(f"| {i} | `{x['name']}` | {x['size']} | {x['size']/1048576:.4f} | {x['members']} |")
    lines[lines.index('## 包、锚点与完整性'):lines.index('## 包、锚点与完整性')]=version_section()
    lines+=['',f"每包同名 `.integrity.json` 给出包SHA-256、成员清单、成员SHA-256，以及合并表的逐嵌套行路径和前后值。`manifest-entry-1.4.220.json` 的chain列全{len(entry['chain'])}个包，archive_integrity齐全；仅将它作为一个条目追加，不替换灰的既有patches。",'',
            '## 收入的功能与对象','',
            '以下按来源功能分组；重叠内容以最终三方结果为准，灰已有且值相同的成员不重复发包，中间数值不逐边叠加。凉月和碧的冲突例外见后文。各来源边/表/对象完整索引在 `附录/function-groups.json`。']
    for g in groups:
        lines+=['',f"### {g['group']}",'']
        chars='、'.join(f"{x['name']}（{x['id']}）" for x in g['characters'])
        if '皇后像素' in g['group']:
            chars='女帝歼灭者（179985）；成员内AMF路径明确为character/epuration_empress_playable/pixelart/'
        weapons='、'.join(f"{x['name']}（{x['id']}）" for x in g['weapons'])
        lines.append('角色：'+(chars or '该组脚本未直接改角色行；仅美术资源对应角色ID的部分未核实。'))
        lines.append('武器/魂珠：'+(weapons or '本组无新增武器；商店配套另见下段。'))
        if '主线 Boss' in g['group']:
            lines.append('副本：'+ '、'.join(x['quest_id'] for x in schedule['playable_quests'])+'；共72项，领主武装54把。')
        if '超限' in g['group']:lines.append('瓦格纳111183、护花使龙/休尔特141099的120级状态、觉醒/等级任务、10000320超限结晶与10000302悖论之核、技能/台座/图标配套；瓦格纳特效取我方219还原去黑底终态。')
        if '赛瑞斯' in g['group']:lines.append('赛瑞斯129999双形态、Fever箭头换道具、Unique条件1299901–1299909与PF override；底层PF仍为Lv3，选用Lv4动作，禁止改成真实档位4。')
        if '凉月' in g['group']:lines.append('凉月159992美术与获取语音保留灰的有效终态；我方213对能力1599921、1599922和队长技159992的4个空值列修复，经核查灰仍为原缺陷值，本次采用我方修复。')
        if '禁忌' in g['group']:lines.append('商店category98：8000101–8000124、5910101–5910129、5920001共54件魂珠；作者终态价格999禁忌星铁，保留。GM5990001–5990006不在该商店。')
        if '中秋' in g['group']:lines.append('活动与MOD卡池相关资源/收尾按来源终态保留；没有新增可玩quest ID需要另计排期，具体卡池对象ID未核实。')
    lines+=['','实际交付差异涉及的角色（含平衡、文案、语音等，并非均为新角色）：',
            '、'.join(f"{x['name']}（{x['id']}）" for x in client['affected_characters'])+'。','']
    lines+=inclusion_sections()
    (annex/'排除明细.md').write_text('# 第三轮剔除清单：仅GM武器获取途径\n\n当前源数据没有实际GM获取途径行可排除：客户端0表键/0资源，服务端0行；不虚构排除项。\n\n训练木桩与GM本体全部收入，逐行清单见客户端准入第三轮.md、gm-server-r3.md。路线核查与管理员边界见gm-route-review-r3.md。\n','utf-8')
    lines+=['','## 需重新排期的决战副本','']
    sched=(annex/'副本排期.md').read_text('utf-8')
    lines.append(sched.split('\n',1)[1])
    lines+=['','## APK 补丁依赖表','',
            (annex/'apk-dependencies.md').read_text('utf-8').split('## 功能与依赖',1)[1].split('## 编号与方法对照',1)[0],
            '完整方法映射、38份本地证据及已知错误的适用边界见 [APK依赖审计](附录/apk-dependencies.md)。用户提到PR #43的目录在本地origin/main未找到，PR当前状态未联网核实；不等同灰已部署。','',
            '## 合并冲突清单与处理方式','',
            f"客户端 **{len(conflicts)}处**，服务端 **{server['conflict_count']}处**。普通冲突默认保留灰；五重相关行强制采用我方，已核实的凉月/碧缺陷修复也采用我方。下列列出双方完整值及最终处理。",'']
    for i,x in enumerate(conflicts,1):
        lines += [f"### 冲突 {i}：`{x['logical']}` / `{'/'.join(x['path']) or '整成员'}`",'',
                  f"处理：{x['resolution']}；依据见resolution_reason和缺陷核查章节。以下为完整值；二进制值是SHA-256。",'',
                  '```json',json.dumps(x,ensure_ascii=False,indent=2),'```','']
    lines+=priority_section()
    lines+=alignment_section()
    lines+=['碧169978的角色、文本、状态和六条能力仍逐项等于灰；立绘切换PNG与atlas成对采用我方217修复，灰原20帧通用图集没有界面所需2帧。凉月3行能力/队长技采用我方213修复，获取语音保持灰。以上为静态核查及读回，真实客户端运行未核实。', '',
            '### 为通过自检进行的文案一致性修复','',
            '首轮原始三方结果 prepush ERROR2：我方219的杰拉德149999资料表第1/2档描述与实际action_skill不同。本包只把客户端character_text的c5/c7同步到white_wolf_gerald第1/2档c1，未改技能效果。服务端149999资料与灰相同且不在本次entries，维持基线。具体前后值如下：','',
            '```json',json.dumps(norms,ensure_ascii=False,indent=2),'```','',
            '服务端有1项我方删除意图（boss_coin_shop_item_category_map键202045），按只增/按键合并规则保留灰状态；这不是双方同值冲突。','',
            '## 服务端数据与安装步骤','',
            f"`server-entries.json` 包含 **{server['file_count']}文件、{server['entry_count']}个键/ID条目**，基线为上述灰origin/main。应用脚本默认只核对，先对所有文件的目标键检查，任一原值不符拒绝整个批次；不整文件替换，保留原换行、BOM与非目标区域。",'',
            '1. 灰先在自己的副本核对当前链尾为1.4.136、目标键基线匹配，并备份。确认下列源码/APK前提和72项副本排期；来源时间未被本包修改，若直接上链会沿用这些时间。',
            '2. 在灰的开发副本移植 [超限服务端源码补充](服务端源码补充/说明.md)，完成其适用单测/编译及运行验证。附件7文件的原上下文和结果字节已在内存核对，未在本任务编译或运行。',
            '3. 在交付目录执行（由灰在自己的目标上操作；本任务未执行到外部目录）：','',
            '```powershell',"$env:PYTHONIOENCODING='utf-8'",r'python .\apply_server_entries.py --assets <灰仓库的assets绝对路径>',
            r'python .\apply_server_entries.py --assets <灰仓库的assets绝对路径> --apply','```','',
            f"4. 将{len(entry['chain'])}个ZIP全部放入灰assets/asset-patch/active；追加manifest-entry，设置cdn_version为1.4.220。第三轮替换第二轮同名包时必须同时更新全部ZIP、integrity与条目，不可混用旧SHA。旁边integrity作为审计附件，包内不嵌入元数据。",
            '5. 核实灰APK包含依赖表所列补丁、APK内置经验/等级表和台座图集；跨端/同房也要兼容。按灰既有运维流程部署、重启和验证；本包不附APK或签名材料。',
            '6. 在灰部署副本再次运行prepush，并验证角色详情、超限双扣、赛瑞斯Fever/PF、凉月、碧和新副本。前述步骤是给接收者的说明，不代表本任务已部署或获授权外发。','',
            '## 本次自检结果','',
            f"原版 `wf_prepush_check.py --since 1.4.136`：**ERROR {prepush['counts']['ERROR']} / WARN {prepush['counts']['WARN']} / INFO {prepush['counts']['INFO']}**，退出码{prepush['returncode']}。无allowlist降级；chain/text/companion/level四项均执行。完整输出 `prepush.txt`、`prepush.json`；输入命令与源码hash见prepush-summary和prepush-chain-source。",'',
            f"测试对齐边 `--since 1.4.219`：**ERROR {align_pre['counts']['ERROR']} / WARN {align_pre['counts']['WARN']} / INFO {align_pre['counts']['INFO']}**，退出码{align_pre['returncode']}。证据为prepush-align.txt/json及prepush-align-summary.json。",'',
            '检查视图在本工作区内重放灰全链+220；3个历史LFS指针从本地对象读取并逐SHA/size验证，未联网。chain使用固定灰源码中4个真实纯函数，经TypeScript AST原文提取转译，避免启动服务端依赖；合法链、重复序号、序号缺口和缺文件自测通过。',
            'WARN是完整发现记录，不等同无风险：包含灰已存或我方历史终态文案差异、历史物品伴随项、等级/变量遗留项。新增错误未被allowlist或修改检查器隐藏。',
            '第三轮比第二轮新增6条WARN，均为5990001–5990006魂珠缺少item_quest_search展示行，客户端获取途径页为空；本轮按不开放GM获取的决定保留空页，不为消除WARN新增获取信息或奖励行。',
            '客户端关键读回通过：瓦格纳111183的120级4500/1060、护花使龙141099的120级、赛瑞斯129999技能/能力、瓦格纳队长技、基诺维169999平衡行等于我方终态；碧169978角色/文本/状态/六能力等于灰，立绘两成员等于我方217；凉月3行能力/队长技等于我方213，获取语音等于灰。',
            f"ZIP大小上限、CRC、成员无重复、包SHA和每成员SHA逐项通过；训练及GM本体共{client['inclusion_verification']['restored_table_keys_verified']}个原排除表键、{client['inclusion_verification']['restored_members_verified']}份原排除资源已读回核对。GM本体引用允许保留，未分类GM引用及GM获取途径引用均为0。服务端{server['file_count']}文件{server['entry_count']}条在工作区副本完成dry-run和apply，逐字节等于合并视图；脏键/重复应用/重复JSON键拒绝、CRLF/BOM与无关数据保留测试通过。",
            '真实客户端、服务端编译/运行、同房联机以及灰端已装补丁情况：**未核实**，本任务按硬规则未触碰服务器/模拟器/adb。','',
            '## 重跑构建','',
            '需要本机任务指定的只读来源、Python与现有TypeScript；固定输入清单在build/source-lock.json和附录/inputs.json。脚本所有缓存/临时文件只写本工作区，关闭pycache，不执行Git写操作或联网。原始输入路径未随包复制（避免重复分发整条历史链）。',
            '```powershell',"$env:PYTHONIOENCODING='utf-8'","$env:PYTHONDONTWRITEBYTECODE='1'",r'python .\build\build_all.py','```','',
            '需要灰决定/完成：72副本排期、服务端源码移植与编译/运行验证、APK能力核实与实机/联机验证。本次离线包的构建和必要静态自检已完成。','']
    (c.OUT/'说明.md').write_text('\n'.join(lines),'utf-8')
    print('说明与report已生成；prepush',prepush['counts'])

if __name__=='__main__':main()
