cd "D:/WF/out/面板核对-1.4.227/audit"
until grep -q "^EXIT" rwlog_00.txt; do sleep 20; done
cp rewrites/00.json rewrites/00.pass1.json
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REVIEW_TASK.md 并严格照做（规范 STYLE.md，原始任务 REWRITE_TASK.md）。本次 shard 名=00，只处理这些角色：111183,119950,119951,119970,119989,119990,119991,119992,119993,119994,119995,119996,119997,119998,119999,129950,129951,129952,129970,129990,129991,129992,129993,129994,129995,129996,129997。可读 chars/ dsl/ cas/ 下这些角色的文件。只写 rewrites/00.json 与 rewrites/00.review.md，不要改其他文件，不要联网。用 Python 脚本读写文件，不要把长内容塞进单条 shell 命令（Windows 命令行长度有限）。" > rvlog_00.txt 2>&1
echo EXIT $? >> rvlog_00.txt
