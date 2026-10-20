"""220版约定、五重优先逐行证据、缺陷修复与测试对齐说明。"""
import json
import common as c

def jread(name):
    return json.loads((c.ROOT/'audit'/name).read_text('utf-8'))

def version_section():
    return ['','## 版本号约定','',
            '作者2026-10-16拍板：正式服从灰1.4.136一步到 **1.4.220**，与测试服对齐；测试服同时由1.4.219升到1.4.220。',
            '以后测试服从 **1.4.221** 往上推，正式服采纳时沿用测试服编号，**正式服永远不高于测试服**。本分享边depends_on仍为1.4.136，不要求灰安装测试服131–219历史链。',
            '第一轮1.4.137产物已移出当前交付，保存在本工作区历史目录，仅供审计，不参与本次manifest或安装。','']

def priority_section():
    five=jread('five-priority-220.json')
    rows=five['client_rules'];server=five.get('server_rules',[])
    lines=['','### 五重行保留我方值','',
           '长期规则例外：五重Boss HP、增益/buff、门票、奖励及相关配套行一律采用我方1.4.219终态，灰/kulo数据不得回写覆盖。普通行仍按三方规则合并。',
           f'客户端逐叶行保护{len(rows)}项，服务端逐叶路径保护{len(server)}项；下列逐行列出灰与我方不同的项。相同值也在附录机器清单中逐项列出并验证。',
           f"相对本任务实际CSV列级合并，强制优先规则额外改变{five['overrides_vs_default']}条五重行；第一轮实际包中的evil入口buff与灰预载已经共存。本轮新增明确保护及全量断言，不能据整行比较的冲突风险声称第一轮丢失修复。",
           '灰的五重evil炮弹预载已在我方216合入，保护终态同时核对保留该预载；本规则不整表覆盖。','']
    count=0
    for side,items in [('客户端',rows),('服务端',server)]:
        for r in items:
            if r.get('hui')==r.get('ours'):continue
            count+=1
            table=r.get('logical',r.get('file',r.get('member','未核实')))
            path=r.get('path',r.get('key_path',[]))
            lines += [f"#### {side} `{table}` / `{'/'.join(map(str,path))}`",'',
                      '```json',json.dumps({'表':table,'键':path,'灰值':r.get('hui'),'我方值':r.get('ours'),
                                           '最终':'我方值','依据':r.get('reason'),'来源边':r.get('source_edges',[])},
                                           ensure_ascii=False,indent=2),'```','']
    lines += [f'本节共{count}个灰/我方值不同的保护路径；完整机器证据见附录/five-priority-220.json。','',
              '### 凉月与碧：已核实缺陷修复优先','',
              (c.ROOT/'audit/defect-resolutions-220.md').read_text('utf-8'),'']
    return lines

def alignment_section():
    entry=json.loads((c.OUT/'manifest-entry-align-1.4.220.json').read_text('utf-8'))
    p=c.OUT/entry['archive']
    return ['','## 测试服1.4.219 → 1.4.220对齐边','',
            f"文件：`{p.name}`，{p.stat().st_size}字节；manifest：`manifest-entry-align-1.4.220.json`，depends_on=1.4.219、version=1.4.220。",'',
            '核对的是灰131–136相对共同祖先130的增量，与测试219逐表、逐嵌套叶行比较；灰新增而测试没有的才导入。测试已有的后续修复和五重终态保留测试值，不把旧缺陷回灌。',
            (c.ROOT/'audit/alignment-220.md').read_text('utf-8'),' ',
            '该边仅供测试服：把该ZIP加入测试服active，并追加测试对齐manifest条目、设置cdn_version=1.4.220；不能将正式136→220条目追加到测试219链。',
            '测试服既有GM/训练数据不因版本对齐导入正式服，也不在本条边中擅自删除。','']
