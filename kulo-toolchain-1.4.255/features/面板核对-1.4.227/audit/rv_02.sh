cd "D:/WF/out/面板核对-1.4.227/audit"
until grep -q "^EXIT" rwlog_02.txt; do sleep 20; done
cp rewrites/02.json rewrites/02.pass1.json
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REVIEW_TASK.md 并严格照做（规范 STYLE.md，原始任务 REWRITE_TASK.md）。本次 shard 名=02，只处理这些角色：149991,149992,149993,149994,149995,149996,149997,149998,149999,151015,151021,151027,151045,151159,159950,159951,159970,159985,159991,159992,159994,159995,159996,159997,159998,159999,169950。可读 chars/ dsl/ cas/ 下这些角色的文件。只写 rewrites/02.json 与 rewrites/02.review.md，不要改其他文件，不要联网。用 Python 脚本读写文件，不要把长内容塞进单条 shell 命令（Windows 命令行长度有限）。" > rvlog_02.txt 2>&1
echo EXIT $? >> rvlog_02.txt
