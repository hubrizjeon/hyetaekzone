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
# GitHub Actions(자동 정리·핫딜)가 먼저 올린 커밋이 있으면 합친 뒤 올립니다
git pull --rebase -q || { echo "❌ GitHub 쪽 변경과 겹쳐 자동으로 합치지 못했습니다. git status 를 확인하세요."; exit 1; }
git push

URL=$(gh api repos/{owner}/{repo}/pages --jq '.html_url' 2>/dev/null || echo "")
echo
echo "✅ 푸시 완료. 30~60초 뒤 반영됩니다."
[ -n "$URL" ] && echo "🔗 $URL"
