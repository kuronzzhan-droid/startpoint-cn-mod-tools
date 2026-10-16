import os,sys,hashlib,subprocess,json,tempfile
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"); sys.path.insert(0,os.getcwd())
from live149 import *
sys.path.insert(0,r'D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools')
import wf_assets
from pathlib import Path
S=Path(r'D:/WF/out/kulo-patch-toolkit/store131/production')
FF=r"C:/ProgramData/HP/LCDDisplayHelper/bin/ffmpeg"
def get(lp):
    try: return read_raw(lp)[0]
    except FileNotFoundError: pass
    h=hashlib.sha1((lp+SALT).encode()).hexdigest()
    for r in ('upload','medium_upload','android_upload'):
        p=S/r/h[:2]/h[2:]
        if p.is_file(): return p.read_bytes()
    return None
names=sys.argv[1:]
out={}
for n in names:
    b=get(n+'.mp3')
    if b is None: print(n,'MISSING'); continue
    tmp=Path(tempfile.gettempdir())/'se.mp3'; tmp.write_bytes(wf_assets.mp3_decode(b))
    r=subprocess.run([FF,'-hide_banner','-nostats','-i',str(tmp),'-af','ebur128=peak=true','-f','null','-'],capture_output=True,text=True)
    e=r.stderr
    I=[l for l in e.splitlines() if l.strip().startswith('I:')]; P=[l for l in e.splitlines() if l.strip().startswith('Peak:')]
    d=subprocess.run([FF,'-hide_banner','-i',str(tmp)],capture_output=True,text=True).stderr
    dur=[l.split('Duration:')[1].split(',')[0].strip() for l in d.splitlines() if 'Duration:' in l]
    print(f"{n.split('/')[-1]:44s} dur={dur[0] if dur else '?'} {I[-1].strip() if I else ''} {P[-1].strip() if P else ''}")
