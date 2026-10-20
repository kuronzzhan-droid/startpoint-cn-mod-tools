cd "D:/WF/out/面板核对-1.4.227/audit"
until grep -q "^EXIT" rwlog_01.txt; do sleep 20; done
cp rewrites/01.json rewrites/01.pass1.json
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REVIEW_TASK.md 并严格照做（规范 STYLE.md，原始任务 REWRITE_TASK.md）。本次 shard 名=01，只处理这些角色：129998,129999,131020,139950,139951,139970,139985,139990,139991,139992,139993,139994,139995,139996,139997,139998,139999,141099,149950,149951,149970,149985,149986,149987,149988,149989,149990。可读 chars/ dsl/ cas/ 下这些角色的文件。只写 rewrites/01.json 与 rewrites/01.review.md，不要改其他文件，不要联网。用 Python 脚本读写文件，不要把长内容塞进单条 shell 命令（Windows 命令行长度有限）。" > rvlog_01.txt 2>&1
echo EXIT $? >> rvlog_01.txt
