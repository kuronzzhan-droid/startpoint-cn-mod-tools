import os, sys, json, csv, subprocess
os.environ["WF_EXTRA_DIRS"]=os.environ.get("WF_EXTRA_DIRS", r"D:/WF/out/碧-1.4.216/patch-test-212")
import env; env.setup(int(os.environ.get("VTIP","213")))
from base149 import *
CID="169978"
def csvrow(s): return next(csv.reader([s]))
def conv_board(node): return {b:{slot:[csvrow(t)] for slot,t in slots.items()} for b,slots in node.items()}
def conv_node(node):
    out={}
    for b,slots in node.items():
        ob={}
        for _,t in slots.items():
            r=csvrow(t); ids,cnts=r[2].split(","),r[3].split(",")
            ob[r[0]]={"items":{i:int(c) for i,c in zip(ids,cnts)},"manaCost":int(r[4]),"field1":r[1],"field5":r[5],"field6":r[6]}
        out[b]=ob
    return out
cb=load("master/generated/mana_board.orderedmap"); cn=load("master/mana_board/mana_node.orderedmap")
print("client board has",CID in cb,"node has",CID in cn, source("master/generated/mana_board.orderedmap"), source("master/mana_board/mana_node.orderedmap"))
mnc=json.loads(subprocess.check_output(["git","-C",r"D:/WF/startpoint-cn-kulo","show","origin/main:assets/mana_node_cnmod.json"]).decode("utf-8"))
print("kulo cnmod == client conv:", mnc[CID]==conv_node(cn[CID]))
if mnc[CID]!=conv_node(cn[CID]):
    a,b=mnc[CID],conv_node(cn[CID])
    for bd in sorted(set(a)|set(b)):
        for k in sorted(set(a.get(bd,{}))|set(b.get(bd,{}))):
            if a.get(bd,{}).get(k)!=b.get(bd,{}).get(k): print(" diff",bd,k,a.get(bd,{}).get(k),b.get(bd,{}).get(k))
board=conv_board(cb[CID]); json.dump(board,open("mana_board_169978.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("board slots",sum(len(v) for v in board.values()))
ch=load("master/character/character.orderedmap")[CID]; print("character row",str(ch)[:400])
cdn=json.load(open("k_cdn_p5b.json",encoding="utf-8"))[CID][0]
print("server cdn row == client row:", cdn==csvrow(ch)); print(cdn[-3:], csvrow(ch)[-3:])
