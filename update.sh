#!/usr/bin/env bash
# 혜택존 사이트 업데이트 (index.html 수정 후 이 스크립트 실행)
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-update: $(date '+%Y-%m-%d %H:%M')}"

if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
  echo "변경사항이 없습니다."
  exit 0
fi

git add -A
git commit -m "$MSG"
git push

URL=$(gh api repos/{owner}/{repo}/pages --jq '.html_url' 2>/dev/null || echo "")
echo
echo "✅ 푸시 완료. 30~60초 뒤 반영됩니다."
[ -n "$URL" ] && echo "🔗 $URL"
