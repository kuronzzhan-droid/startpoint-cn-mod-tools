#!/usr/bin/env bash
# check-hygiene.sh 的隔离回归测试。
#
# 为什么必须有它：这道门禁在开发过程中**两次静默失效**——正则里的反斜杠被
# 少写一层，Windows 家目录规则退化成永不匹配；豁免表用 case 模式匹配时，含
# 反斜杠的那条永远匹配不上。两次都是「扫描通过、其实没拦住」，跟主仓那次
# 「作者真实地址躺了三周」是同一种病。所以：每条规则都必须有一个能让它变红
# 的用例，删掉判据就必须变红。
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
GATE=scripts/check-hygiene.sh
fail=0
ok()   { printf "  [ok] %s
" "$*"; }
bad()  { printf "  [XX] %s
" "$*"; fail=1; }

work=$(mktemp -d); trap 'rm -rf -- "$work"' EXIT
probe=docs/.hygiene-selftest-probe.md

# 在临时 git 仓里跑，避免污染真实工作树。
expect_red() {
    local label="$1" payload="$2"
    printf "%s
" "$payload" > "$probe"
    git add -N -- "$probe" >/dev/null 2>&1
    bash "$GATE" --all >/dev/null 2>&1
    local rc=$?
    rm -f -- "$probe"
    git rm --cached -q -- "$probe" >/dev/null 2>&1 || true
    if (( rc == 1 )); then ok "$label 被拦下"; else bad "$label 没被拦下（门禁形同虚设）"; fi
}

bash "$GATE" --all >/dev/null 2>&1 && ok "干净树通过" || bad "干净树竟然不通过"

expect_red "内网 IP"        "host = 192.168.99.99"
expect_red "Windows 家目录" "path C:\Users\bob\x.json"
expect_red "POSIX 家目录"   "path /Users/bob/x.json"
expect_red "个人邮箱"       "contact someone@gmail.com"
expect_red "AWS 密钥"       "AKIAIOSFODNN7EXAMPLE"
expect_red "PEM 私钥"       "-----BEGIN RSA PRIVATE KEY-----"
expect_red "sk- 令牌"       "sk-abcdefghijklmnopqrstuvwxyz0123"

# 豁免必须是**行级**的：豁免文件里新增一条内网 IP 仍要红。
printf "
# leaked = 192.168.99.99
" >> wf_release_v1/target.py
bash "$GATE" --all >/dev/null 2>&1
rc=$?; git checkout -- wf_release_v1/target.py
(( rc == 1 )) && ok "豁免文件内新增 IP 仍被拦下（行级豁免生效）" \
                || bad "豁免退化成了整文件豁免"

# 豁免行被篡改（占位名换成真人名）也要红。
sed -i 's|"/Users/Alice/secret.json",|"/Users/mallory/secret.json",|' tests/test_release_v1_canonical.py
bash "$GATE" --all >/dev/null 2>&1
rc=$?; git checkout -- tests/test_release_v1_canonical.py
(( rc == 1 )) && ok "豁免行被改动后失去豁免" || bad "豁免行被改动后仍然放行"

if (( fail )); then printf "
卫生门禁自测失败。
"; exit 1; fi
printf "
卫生门禁自测通过。
"
