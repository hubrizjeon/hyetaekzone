#!/usr/bin/env bash
# 최초 1회 배포 스크립트 (gh auth login 완료 후 실행)
set -euo pipefail
cd "$(dirname "$0")"

REPO="hyetaekzone"

echo "▶ GitHub 인증 확인..."
gh auth status >/dev/null 2>&1 || { echo "❌ 먼저 'gh auth login' 을 실행하세요."; exit 1; }
OWNER=$(gh api user --jq .login)
echo "  로그인 계정: $OWNER"

echo "▶ 저장소 생성 및 푸시..."
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "  이미 존재함 — 원격만 연결합니다."
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push
fi

echo "▶ GitHub Pages 활성화 (main / root)..."
gh api -X POST "repos/$OWNER/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  || gh api -X PUT "repos/$OWNER/$REPO/pages" \
       -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  || echo "  (이미 활성화되어 있을 수 있음)"

URL="https://$OWNER.github.io/$REPO/"
echo "▶ 배포 대기 중 (최대 3분)..."
for i in $(seq 1 36); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || echo 000)
  if [ "$CODE" = "200" ]; then
    echo "  ✅ HTTP 200"
    break
  fi
  printf "  [%02d/36] HTTP %s ...\n" "$i" "$CODE"
  sleep 5
done

echo "▶ 한글 인코딩 확인..."
curl -s "$URL" | grep -q "혜택존" && echo "  ✅ 한글 정상" || echo "  ⚠️ 한글 확인 실패"
curl -sI "$URL" | grep -i '^content-type' || true

echo
echo "🎉 완료!"
echo "🔗 $URL"
