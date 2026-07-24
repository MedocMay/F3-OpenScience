#!/usr/bin/env bash
# 发布前一次性替换所有占位符。
#
# 用法:
#   bash scripts/setup-repo.sh                 # 交互式填写
#   GITHUB_USER=xxx REPO_NAME=yyy \
#   SECURITY_EMAIL=a@b.c CONDUCT_EMAIL=d@e.f \
#   bash scripts/setup-repo.sh                 # 非交互
#
# 替换完成后会自动校验,确保没有占位符残留。
set -euo pipefail
cd "$(dirname "$0")/.."

OLD_REPO="FrontierFirmFund/f3-openscience"
OLD_SEC="security@frontierfirm.fund"
OLD_CONDUCT="conduct@frontierfirm.fund"
OLD_AUTHOR="FrontierFirm.Fund"

echo "═══════════════════════════════════════════════"
echo "  F3-OpenScience 发布前占位符替换"
echo "═══════════════════════════════════════════════"
echo ""
echo "以下四项当前是占位值,发布前必须确认或替换:"
echo "  仓库地址  $OLD_REPO"
echo "  安全邮箱  $OLD_SEC"
echo "  准则邮箱  $OLD_CONDUCT"
echo "  作者署名  $OLD_AUTHOR"
echo ""

ask() {   # ask <变量名> <提示> <默认值>
  local __var="$1" __prompt="$2" __default="$3" __val
  __val="${!__var:-}"
  if [ -z "$__val" ]; then
    read -r -p "$__prompt [$__default]: " __val </dev/tty || true
    __val="${__val:-$__default}"
  fi
  printf -v "$__var" '%s' "$__val"
}

ask GITHUB_USER    "GitHub 用户名或组织名" "FrontierFirmFund"
ask REPO_NAME      "仓库名"                "f3-openscience"
ask SECURITY_EMAIL "安全漏洞报告邮箱"       "$OLD_SEC"
ask CONDUCT_EMAIL  "行为准则投诉邮箱"       "$OLD_CONDUCT"
ask AUTHOR_NAME    "作者/版权署名"          "$OLD_AUTHOR"

NEW_REPO="${GITHUB_USER}/${REPO_NAME}"

echo ""
echo "将执行以下替换:"
echo "  $OLD_REPO  →  $NEW_REPO"
echo "  $OLD_SEC  →  $SECURITY_EMAIL"
echo "  $OLD_CONDUCT  →  $CONDUCT_EMAIL"
echo "  $OLD_AUTHOR  →  $AUTHOR_NAME"
echo ""
read -r -p "确认?[y/N] " yes </dev/tty || yes=y
case "${yes:-N}" in [yY]*) ;; *) echo "已取消。"; exit 0 ;; esac

# RELEASE-CHECKLIST 与本脚本自身保留原文(它们是说明文档,替换后会自相矛盾)
FILES=$(grep -rl -e "$OLD_REPO" -e "$OLD_SEC" -e "$OLD_CONDUCT" -e "$OLD_AUTHOR" . \
  --include="*.md" --include="*.yml" --include="*.yaml" --include="*.cff" \
  --include="*.toml" --include="*.json" 2>/dev/null \
  | grep -v "RELEASE-CHECKLIST.md" | grep -v "scripts/setup-repo.sh" || true)

n=0
for f in $FILES; do
  python3 - "$f" "$OLD_REPO" "$NEW_REPO" "$OLD_SEC" "$SECURITY_EMAIL" \
                 "$OLD_CONDUCT" "$CONDUCT_EMAIL" "$OLD_AUTHOR" "$AUTHOR_NAME" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
for a, b in zip(sys.argv[2::2], sys.argv[3::2]):
    t = t.replace(a, b)
p.write_text(t, encoding="utf-8")
PY
  echo "  ✓ $f"
  n=$((n+1))
done

# LICENSE 版权行单独处理(非 .md/.yml)
if grep -q "$OLD_AUTHOR" LICENSE 2>/dev/null; then
  python3 - "$OLD_AUTHOR" "$AUTHOR_NAME" <<'PY'
import sys, pathlib
p = pathlib.Path("LICENSE")
p.write_text(p.read_text(encoding="utf-8").replace(sys.argv[1], sys.argv[2]), encoding="utf-8")
PY
  echo "  ✓ LICENSE"; n=$((n+1))
fi

echo ""
echo "已更新 $n 个文件。校验残留:"
LEFT=$(grep -rn -e "$OLD_REPO" -e "$OLD_SEC" -e "$OLD_CONDUCT" . \
  --include="*.md" --include="*.yml" --include="*.cff" --include="*.toml" --include="*.json" 2>/dev/null \
  | grep -v "RELEASE-CHECKLIST.md" | grep -v "scripts/setup-repo.sh" || true)
if [ -n "$LEFT" ]; then
  echo "$LEFT" | sed 's/^/  ✗ /'
  echo ""
  echo "⚠ 仍有占位符残留,请手动处理。"
  exit 1
fi
echo "  ✓ 无残留(RELEASE-CHECKLIST.md 与本脚本保留原文作为说明)"

echo ""
echo "═══ 下一步 ═══"
echo "  1. make test                    # 确认 14 套件全绿"
echo "  2. git init && git add -A"
echo "  3. git ls-files | grep -E '\\.env$|\\.db$'   # 应无输出"
echo "  4. git commit -m 'F3-OpenScience v0.2.0'"
echo "  5. git remote add origin git@github.com:${NEW_REPO}.git && git push -u origin main"
echo ""
echo "  仓库设置见 RELEASE-CHECKLIST.md 第 5 节。"
