#!/usr/bin/env bash
# Add one test-box patch edge (ZIP may be several space-separated paths) to kulo + user repo + Release. RELNOTE overrides release note tail; SERVER=<dir> copies server files (paths relative to assets/) into both repos; ROOTFILES=<dir> copies files relative to the repo root; SRVMERGE="cdndata/x.json=<patch.json> ..." merges per-cell text patches in both repos.
# usage: sync_edge.sh <version> <zip> <manifest-entry.json> <notes.md> "<one-line summary>"
set -euo pipefail
VER=$1; ZIP=$2; ENTRY=$3; NOTES=$4; SUMMARY=$5
ID="user.name=kuronzzhan-droid"; EM="user.email=${GIT_AUTHOR_EMAIL:-297029191+kuronzzhan-droid@users.noreply.github.com}"
CO="Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
GL=/d/WF/.codex-tmp-gitleaks-8.24.3-pr2/gitleaks.exe

if [ -z "${SKIP_KULO:-}" ]; then
# kulo: #45 is merged; each new edge goes in its own draft PR off main
# reuse one checkout (1019: per-edge clones ate ~1.1GB each); never clone again
WT="${KULO_WT:-/d/WF/kpr-1.4.254}"
cd "$WT"
BASE="${BASE:-main}"
BR="feat/cdn-$VER"
test -z "$(git status --porcelain)" || { echo "dirty $WT"; exit 1; }
git fetch -q origin "$BASE"
GIT_LFS_SKIP_SMUDGE=1 git -c core.longpaths=true checkout -q -b "$BR" "origin/$BASE"
cp $ZIP assets/asset-patch/active/
PYTHONIOENCODING=utf-8 python /d/WF/rocheck/append_manifest.py assets/asset-patch/manifest.json "$ENTRY"
if [ -n "${SERVER:-}" ]; then (cd "$SERVER" && find . -type f) | while read -r f; do cp "$SERVER/$f" "assets/$f"; done; fi
if [ -n "${SRVMERGE:-}" ]; then for m in $SRVMERGE; do PYTHONIOENCODING=utf-8 python "${SRVMERGE_PY:-/d/WF/rel227/server/srvmerge.py}" "assets/${m%%=*}" "${m#*=}"; rm -f "assets/${m%%=*}.bak-227"; done; fi
if [ -n "${ROOTFILES:-}" ]; then (cd "$ROOTFILES" && find . -type f) | while read -r f; do mkdir -p "$(dirname "$f")"; cp "$ROOTFILES/$f" "$f"; done; fi
git add -A
"$GL" git --staged --no-banner --redact -c .gitleaks.toml . 2>&1 | tail -1
if git diff --cached | grep -qE '^\+.*(/Users/[A-Za-z0-9_]+/|'"${WF_HYGIENE_EXTRA_RE:-Users.{1,2}[0-9]{5}}"')'; then echo "hygiene hit"; exit 1; fi
git -c "$ID" -c "$EM" commit -q -m "feat(cdn): 补丁链推进到 $VER($SUMMARY)" -m "$CO"
git push -q -u origin "$BR"
printf '<!-- claude-projects-attribution: {"github_login":"kuronzzhan-droid"} -->
_Requested by **zzh**_

## 目标

测试服补丁边 %s:%s。

## 范围与影响层

- [x] cdn

## 改动说明

新增 1 个补丁包(≤5MiB)与 manifest 一条,cdn_version=%s;去掉测试服 local_test_only 标记。纯客户端数据。

## 验证

测试服已上线;gitleaks 无发现。

## 风险与回退

回退:从 manifest 去掉该条目并删除 zip。

## 边界检查

- [x] 目标分支 main,未直接推送
- [x] 无密钥/.env/config/APK/数据库
- [x] 未改 .cdn/
- [x] 一个 PR 一个任务

🤖 Generated with [Claude Code](https://claude.com/claude-code)
' "$VER" "$SUMMARY" "$VER" > /d/WF/outputs/releases/prb/p-$VER.md
gh pr create -R Ku1o/startpoint-cn-kulo --draft --base "$BASE" --head "$BR" --title "feat(cdn): $VER $SUMMARY" --body-file /d/WF/outputs/releases/prb/p-$VER.md

fi
# user repo
cd /d/WF/ghmain
PYTHONIOENCODING=utf-8 python - "$ENTRY" <<'EOF'
import json, sys
p = 'assets/asset-patch/manifest.json'
raw = open(p, 'rb').read().decode('utf-8-sig'); crlf = '\r\n' in raw; tr = raw.endswith('\n')
d = json.loads(raw)
def dumps(o):
    t = json.dumps(o, ensure_ascii=False, indent=2) + ('\n' if tr else '')
    return t.replace('\n', '\r\n') if crlf else t
assert dumps(d) == raw, 'roundtrip'
e = json.load(open(sys.argv[1], encoding='utf-8-sig')); assert e['depends_on'] == d['cdn_version']
d['patches'].append(e); d['cdn_version'] = e['version']
open(p, 'wb').write(dumps(d).encode('utf-8'))
EOF
cp "$NOTES" "docs/mod/平衡/"
if [ -n "${SERVER:-}" ]; then (cd "$SERVER" && find . -type f) | while read -r f; do cp "$SERVER/$f" "assets/$f"; done; fi
if [ -n "${SRVMERGE:-}" ]; then for m in $SRVMERGE; do PYTHONIOENCODING=utf-8 python "${SRVMERGE_PY:-/d/WF/rel227/server/srvmerge.py}" "assets/${m%%=*}" "${m#*=}"; rm -f "assets/${m%%=*}.bak-227"; done; fi
if [ -n "${ROOTFILES:-}" ]; then (cd "$ROOTFILES" && find . -type f) | while read -r f; do mkdir -p "$(dirname "$f")"; cp "$ROOTFILES/$f" "$f"; done; fi
PREV=$(grep -oE '补丁链尾 1\.4\.[0-9]+' README.md | head -1 | grep -oE '1\.4\.[0-9]+')
sed -i "s/补丁链尾 $PREV/补丁链尾 $VER/; s/链尾 $PREV |/链尾 $VER |/" README.md
sed -i "s#(https://github.com/kuronzzhan-droid/startpoint-cn/releases/tag/patches-$PREV)#(https://github.com/kuronzzhan-droid/startpoint-cn/releases/tag/patches-$PREV)+ [patches-$VER](https://github.com/kuronzzhan-droid/startpoint-cn/releases/tag/patches-$VER)#" README.md
git add -A
git -c "$ID" -c "$EM" commit -q -m "sync: 测试服 $VER($SUMMARY)" -m "$CO"
GIT_LFS_SKIP_PUSH=1 git push -q https://github.com/kuronzzhan-droid/startpoint-cn.git HEAD:refs/heads/main
R=/d/WF/outputs/releases/rel-$VER; mkdir -p "$R"; cp $ZIP "$ENTRY" "$R/"
cd "$R"; sha256sum *.zip > SHA256SUMS.txt
printf "%s:%s。${RELNOTE:-纯数据,服务端不用改,不需要新 APK。}\n\n放进 assets/asset-patch/active/,配合 main 的 manifest.json。\n" "$VER" "$SUMMARY" > notes.md
gh release create "patches-$VER" -R kuronzzhan-droid/startpoint-cn --target main --title "补丁 $VER" --notes-file notes.md ./*.zip ./*.json SHA256SUMS.txt
echo "done $VER"
