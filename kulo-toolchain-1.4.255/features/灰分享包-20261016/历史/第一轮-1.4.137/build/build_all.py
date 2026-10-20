"""重跑客户端、服务端、自检及说明；不部署、不启动服务端。"""
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
here=Path(__file__).resolve().parent
env=os.environ.copy()
env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
for script in ['server_merge.py','server_verify.py','server_source_supplement.py','build_client.py',
               'verify_client.py','run_prepush.py','write_report.py']:
    subprocess.run([sys.executable,str(here/script)],env=env,check=True,cwd=here.parent.parent)
