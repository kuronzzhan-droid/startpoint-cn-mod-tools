cd "D:/WF/out/面板核对-1.4.227/audit"
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REWRITE_TASK.md 并严格照做（规范见 STYLE.md）。本次 shard 名=02，只处理这些角色：149991,149992,149993,149994,149995,149996,149997,149998,149999,151015,151021,151027,151045,151159,159950,159951,159970,159985,159991,159992,159994,159995,159996,159997,159998,159999,169950。结果只写 rewrites/02.json，不要改其他任何文件，不要联网。" > rwlog_02.txt 2>&1
echo EXIT $? >> rwlog_02.txt
