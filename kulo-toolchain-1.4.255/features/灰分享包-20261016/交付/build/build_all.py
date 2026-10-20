"""重跑客户端、服务端、自检及说明；不部署、不启动服务端。"""
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
here=Path(__file__).resolve().parent
env=os.environ.copy()
env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
for script in ['build_inclusion_r3.py','review_gm_routes_r3.py','finalize_gm_route_review_r3.py',
               'content_inventory.py','audit_defects_220.py','build_five_priority.py','server_merge.py','server_verify.py','verify_five_server.py',
               'server_source_supplement.py','build_alignment.py','build_client.py',
               'verify_client.py','run_prepush.py','write_report.py','independent_review_r3.py',
               'write_report.py','finalize_delivery.py']:
    subprocess.run([sys.executable,str(here/script)],env=env,check=True,cwd=here.parent.parent)
