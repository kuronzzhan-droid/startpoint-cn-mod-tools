cd "D:/WF/out/面板核对-1.4.227/audit"
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 REWRITE_TASK.md 并严格照做（规范见 STYLE.md）。本次 shard 名=03，只处理这些角色：169951,169970,169978,169980,169985,169988,169989,169991,169992,169993,169994,169995,169996,169997,169998,169999,179970,179981,179982,179983,179984,179985,179986,179999,251017,251053,261089。结果只写 rewrites/03.json，不要改其他任何文件，不要联网。" > rwlog_03.txt 2>&1
echo EXIT $? >> rwlog_03.txt
