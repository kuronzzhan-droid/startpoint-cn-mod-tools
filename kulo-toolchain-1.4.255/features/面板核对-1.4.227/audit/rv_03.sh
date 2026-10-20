cd "D:/WF/out/面板核对-1.4.227/audit"
until grep -q "^EXIT" rwlog_03.txt; do sleep 20; done
cp rewrites/03.json rewrites/03.pass1.json
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REVIEW_TASK.md 并严格照做（规范 STYLE.md，原始任务 REWRITE_TASK.md）。本次 shard 名=03，只处理这些角色：169951,169970,169978,169980,169985,169988,169989,169991,169992,169993,169994,169995,169996,169997,169998,169999,179970,179981,179982,179983,179984,179985,179986,179999,251017,251053,261089。可读 chars/ dsl/ cas/ 下这些角色的文件。只写 rewrites/03.json 与 rewrites/03.review.md，不要改其他文件，不要联网。用 Python 脚本读写文件，不要把长内容塞进单条 shell 命令（Windows 命令行长度有限）。" > rvlog_03.txt 2>&1
echo EXIT $? >> rvlog_03.txt
