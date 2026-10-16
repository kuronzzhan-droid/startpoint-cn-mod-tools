"""歼灭者试点:以机兵降临讨伐(节点60)为模板,生成主线boss的boss战关卡。"""
import sys,io,os,csv,zlib,hashlib,json,copy,zipfile,shutil
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
sys.path.insert(0,r'D:\WF\startpoint-cn-kulo\tools\fantasy-gauntlet-mod-tools')
import wf_quest_lib as q, wf_dsl
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'out')
STORE=os.environ['WF_TARGET_STORE']
NODE='80'; QBASE=1080000; KEY='mod_mainboss_epuration'
TERRAIN='battle/terrain/multi_normal_quest/mod_main_boss/boss_battle_epuration'
MAIN=('9','5','2'); MAIN_MID='9005002'; MAIN_FIELD='main_9_5_2'
NAME='歼灭者'; THUMB='quest/thumbnail/world_9/battle_9_5_2'; BGM='world09_battle_epuration_boss'; ELEMENT='5'
def csvrow(s): return next(csv.reader([s]))
def csvjoin(r):
    b=io.StringIO(); csv.writer(b,lineterminator='').writerow(r); return b.getvalue()
def hrel(lp):
    h=hashlib.sha1((lp+q.SALT).encode()).hexdigest(); return f'production/upload/{h[:2]}/{h[2:]}'
files={}
# 1 boss_battle_quest
bb=q.load_table('master/quest/boss_battle_quest.orderedmap')
assert NODE not in bb['1'], 'node exists'
tmpl=bb['1']['60']; new={}
for k,v in tmpl.items():
    r=csvrow(v); n=int(k)
    r[0]=str(QBASE+n); r[2]=f'{NAME} ::quest_rank::'; r[3]=THUMB; r[5]='2000-01-01 00:00:00'
    if n==1: r[7:12]=['0',*MAIN,MAIN_MID]
    else: r[7:12]=['2','1',NODE,str(n-1),str(QBASE+n-1)]
    r[72]=ELEMENT; r[109]=KEY; r[110]=BGM
    new[k]=csvjoin(r)
    assert csvrow(new[k])==r
bb['1'][NODE]=new
files['master/quest/boss_battle_quest.orderedmap']=q.build_node(bb)
# 2 stage node
sn=q.load_table('master/quest/boss_battle_stage_node.orderedmap')
r=csvrow(sn['1']['60']); r[1]=f'{NAME}讨伐'; r[3]='(None)'; r[11]=THUMB
sn['1'][NODE]=csvjoin(r)
files['master/quest/boss_battle_stage_node.orderedmap']=q.build_node(sn)
# 3 field + zone
fd=q.load_table('master/battle/field_data.orderedmap'); assert KEY not in fd
fr=csvrow(fd[MAIN_FIELD]); fd[KEY]=csvjoin([fr[0],TERRAIN,KEY])
files['master/battle/field_data.orderedmap']=q.build_node(fd)
zn=q.load_table('master/battle/zone.orderedmap'); assert KEY not in zn
zn[KEY]=copy.deepcopy(zn[MAIN_FIELD])
files['master/battle/zone.orderedmap']=q.build_node(zn)
# 4 terrain: main terrain + 6 more coffins (co-op needs 9)
src=fr[1]+'.amf3.deflate'; h=hrel(src).split('upload/')[1]
raw=open(f'{STORE}/{h}','rb').read(); d=zlib.decompress(raw,-15); t=wf_dsl.parse_dsl(d)['tree']
layer=t['layers'][0]; objs=layer['objects']
coffins=[o for o in objs if o['type']=='COFFIN']; assert len(coffins)==3
nid=max(o['id'] for o in objs)+1
EXTRA=[(130.5,62.174),(150.334,64.1739),(105.962,58.9548),(184.296,83.219),(181.5,133.0),(132.008,181.719)]
pos=objs.index(coffins[-1])+1
for i,(x,y) in enumerate(EXTRA):
    c=copy.deepcopy(coffins[0]); c['id']=nid+i; c['x']=x; c['y']=y; objs.insert(pos+i,c)
if 'nextobjectid' in t: t['nextobjectid']=max(t['nextobjectid'],nid+len(EXTRA))
enc=wf_dsl.encode_amf3(t); assert wf_dsl.parse_dsl(enc)['tree']==t and '<objRef' not in json.dumps(t,default=str)
co=zlib.compressobj(9,zlib.DEFLATED,-15); files[TERRAIN+'.amf3.deflate']=co.compress(enc)+co.flush()
# verify each table parses back
for lp,b in files.items():
    if lp.endswith('.orderedmap'): assert isinstance(q.parse_node(b),dict)
shutil.rmtree(OUT,ignore_errors=True); os.makedirs(OUT)
for lp,b in files.items():
    p=os.path.join(OUT,hrel(lp)); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(b)
json.dump({lp:hrel(lp) for lp in files},open(os.path.join(OUT,'logical_map.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('ok',{lp:len(b) for lp,b in files.items()})
