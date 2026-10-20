cd "D:/WF/out/面板核对-1.4.227/audit"
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 TASK.md 并严格照做。本次 shard 名=01，只审这些角色（chars/<ID>.md 与 dsl/<ID>.txt）：129998,129999,131020,139950,139951,139970,139985,139990,139991,139992,139993,139994,139995,139996,139997,139998,139999,141099,149950,149951,149970,149985,149986,149987,149988,149989,149990。结果只写 findings/01.jsonl，不要改其他任何文件，不要联网。" > log_01.txt 2>&1
echo EXIT $? >> log_01.txt
