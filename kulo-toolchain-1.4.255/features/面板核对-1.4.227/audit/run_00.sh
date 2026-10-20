cd "D:/WF/out/面板核对-1.4.227/audit"
codex exec -m gpt-6.1-sol -c model_reasoning_effort=ultra -s danger-full-access --skip-git-repo-check "读 TASK.md 并严格照做。本次 shard 名=00，只审这些角色（chars/<ID>.md 与 dsl/<ID>.txt）：111183,119950,119951,119970,119989,119990,119991,119992,119993,119994,119995,119996,119997,119998,119999,129950,129951,129952,129970,129990,129991,129992,129993,129994,129995,129996,129997。结果只写 findings/00.jsonl，不要改其他任何文件，不要联网。" > log_00.txt 2>&1
echo EXIT $? >> log_00.txt
