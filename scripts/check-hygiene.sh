#!/usr/bin/env bash
# 提交卫生检查：阻止内网 IP、家目录、个人邮箱、.env 和凭据字面量进入公开仓。
#
# 本仓是主仓 startpoint-cn 的下游导出仓，正则与主仓 scripts/check-hygiene.sh
# 保持同一套。加这道门禁的直接起因：Codex 云端直推把作者的真实内网地址带进了
# 7 个文件、42 处，一路推到公网，没有任何东西拦它。
# 注意：本文件与 scripts/tests/test-hygiene.sh 是仅有的两个整文件豁免，门禁
# 扫不到它们——所以这两个文件里**绝不能**出现任何真实地址/凭据，示例一律用
# 明显的占位值（192.168.99.99 之类）。主仓那次事故就是真实地址躺在豁免文件里
# 三周没人发现。
#
# 用法：
#   bash scripts/check-hygiene.sh          # 检查已暂存文件（pre-commit）
#   bash scripts/check-hygiene.sh --all    # 检查全部已跟踪文件（CI）
set -uo pipefail

MODE="${1:-staged}"
fail=0
note() { printf '  [x] %s\n' "$*"; fail=1; }

IP_RE='192\.168\.[0-9]+\.[0-9]+'
HOME_RE='(/Users/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+)'
EMAIL_RE='[A-Za-z0-9._%+-]+@(qq|gmail|163|126|outlook|hotmail|foxmail|yahoo)\.com'
# 只收高精度凭据形态（各家 token 的固定前缀 + PEM 私钥头）。
# 刻意不做 `token\s*=\s*"..."` 这类通用关键字规则：本仓测试里大量出现
# CN_ADMIN_TOKEN / SECRET_TOKEN 这些**故意的**占位字面量，通用规则会把它们
# 全部误报，逼出一张长豁免名单——而长豁免名单正是主仓踩过的坑。
SECRET_RE='(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'

# ---------------------------------------------------------------------------
# 豁免表：**「文件路径 + 该行去缩进后的完整内容」精确匹配**，绝不按文件整体豁免。
#
# 主仓的教训写在它自己的脚本注释里：曾经因为三个测试文件长期挂着整文件豁免，
# 作者真实的内网地址在里面躺了三周没人发现。所以这里只豁免下列具体行，
# 同一文件里的任何其它命中 —— 包括新加的行 —— 一律红。
#
# 1-3) RFC1918 私网段常量，不是泄漏。删了会让 publicHost 校验器不再承认
#      192.168/16 家用网段（wf_release_v1/target.py:200 要求 loopback 或
#      RFC1918，家用 LAN 绝大多数就在这一段）。以后看到不要当漏网重删：
#        wf_release_v1/_loopback_http.py:27
#        wf_release_v1/platform.py:47
#        wf_release_v1/target.py:37
# 4-5) 反例 fixture：test_redacts_untrusted_invalid_paths_from_errors 要证明
#      家目录形状的路径被拒绝且从报错里抹掉，"Alice" 是通用占位名。路径必须
#      保持家目录形状，否则这个测试就不再测它要测的东西：
#        tests/test_release_v1_canonical.py:132,133,135
# ---------------------------------------------------------------------------
# 逐条是「文件路径|该行去缩进后的完整内容」。用 [[ == "$var" ]] 做**字面量**比较，
# 不要退回 case 模式匹配：case 的 glob 把反斜杠当转义符，含 C:\Users\ 的那条
# 永远匹配不上，豁免看似写了其实没生效（本仓实测踩过两次）。
ALLOW_LINES=(
    'wf_release_v1/_loopback_http.py|ipaddress.ip_network("192.168.0.0/16"),'
    'wf_release_v1/platform.py|ipaddress.ip_network("192.168.0.0/16"),'
    'wf_release_v1/target.py|ipaddress.ip_network("192.168.0.0/16"),'
    'tests/test_release_v1_canonical.py|r"C:\Users\Alice\secret.json",'
    'tests/test_release_v1_canonical.py|"C:/Users/Alice/secret.json",'
    'tests/test_release_v1_canonical.py|"/Users/Alice/secret.json",'
)

allowed_line() {
    local path="$1" line="$2" trimmed entry
    trimmed="${line#"${line%%[![:space:]]*}"}"
    for entry in "${ALLOW_LINES[@]}"; do
        [[ "$path|$trimmed" == "$entry" ]] && return 0
    done
    return 1
}

paths_file=$(mktemp)
trap 'rm -f -- "$paths_file"' EXIT

scan_paths() {
    local path
    while IFS= read -r -d '' path; do
        [[ -f "$path" ]] || continue
        # 仅有的两个整文件例外：它们的内容**就是**策略字面量本身——
        # 门禁脚本(正则+豁免表)和门禁自测(成排的植入用密钥/IP/家目录)。
        # 除这两个文件外不得再有整文件豁免，一律走 ALLOW_LINES 行级豁免。
        case "$path" in
            scripts/check-hygiene.sh|scripts/tests/test-hygiene.sh) continue ;;
        esac
        printf '%s\0' "$path" >> "$paths_file"
        if [[ "$path" == '.env' || "$path" == 'profiles.json' ]]; then
            note "$path 不得提交（只提交 .example 版本）"
        fi
    done
}

if [[ "$MODE" == '--all' ]]; then
    git ls-files -z | scan_paths
else
    git diff --cached --name-only -z --diff-filter=ACMR | scan_paths
fi

[[ -s "$paths_file" ]] || { printf '提交卫生检查通过（无待检文件）。\n'; exit 0; }

# 四条规则统一逐行判定，命中豁免表才放过。
#
# 两个坑都踩过，别改回去：
# 1) grep 必须一次吃下全部文件（-Z 让文件名以 NUL 结尾，路径含冒号也不会解析
#    错）。退回「每文件一次 grep」= 4 条规则 x 数百文件 = 上千次进程启动，
#    实测一次全量扫描 4 分钟；批量之后 2 秒。
# 2) 正则必须走 `-f 模式文件`，不能作为 argv 传给 xargs。MSYS/Git-Bash 的
#    xargs 会吃掉命令模板里的反斜杠，HOME_RE 的 Windows 分支被削掉一层后
#    ERE 里退化成字面量，于是这条规则**静默失效**——本地 pre-commit 全绿，
#    实际一个 C:\Users\ 都没拦住（本仓实测复现过）。模式文件对 shell 与
#    xargs 双重免疫。
check_re() {
    local re="$1" label="$2" pat path rest line lineno
    pat=$(mktemp)
    printf '%s\n' "$re" > "$pat"
    while IFS= read -r -d '' path && IFS= read -r rest; do
        lineno="${rest%%:*}"
        line="${rest#*:}"
        allowed_line "$path" "$line" && continue
        note "$label：$path:$lineno"
        printf '      %s\n' "$line"
    done < <(xargs -0 -r grep -nHZE -f "$pat" < "$paths_file" 2>/dev/null || true)
    rm -f -- "$pat"
}

check_re "$IP_RE"     '内网 IP'
check_re "$HOME_RE"   '家目录路径'
check_re "$EMAIL_RE"  '个人邮箱'
check_re "$SECRET_RE" '疑似凭据'

if (( fail )); then
    printf '\n提交卫生检查失败：请清除上述内网 IP、家目录、个人邮箱、.env、凭据字面量。\n'
    printf '%s\n' '（host/port 走 env 或配置；路径用相对路径；确为占位示例时只加「文件+整行」窄豁免。）'
    exit 1
fi
printf '提交卫生检查通过。\n'
