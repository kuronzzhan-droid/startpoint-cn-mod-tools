cd "D:/WF/out/面板核对-1.4.227/audit"
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REWRITE_TASK.md 并严格照做（规范见 STYLE.md）。本次 shard 名=01，只处理这些角色：129998,129999,131020,139950,139951,139970,139985,139990,139991,139992,139993,139994,139995,139996,139997,139998,139999,141099,149950,149951,149970,149985,149986,149987,149988,149989,149990。结果只写 rewrites/01.json，不要改其他任何文件，不要联网。" > rwlog_01.txt 2>&1
echo EXIT $? >> rwlog_01.txt
