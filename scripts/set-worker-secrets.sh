#!/bin/bash
# 쿠팡 키를 검색용 Cloudflare Worker(hyetaekzone-stats) 비밀값으로 등록합니다.
# ~/.hyetaekzone.env 에서 읽어 바로 넘기며, 키 값은 화면에 나오지 않습니다.
#   실행: bash scripts/set-worker-secrets.sh
set -euo pipefail
ENV_FILE="$HOME/.hyetaekzone.env"
cd "$(dirname "$0")/../stats-worker"
for k in COUPANG_ACCESS_KEY COUPANG_SECRET_KEY; do
  v=$(grep -E "^[[:space:]]*$k[[:space:]]*=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)
  if [ -z "$v" ]; then echo "❌ $k 가 $ENV_FILE 에 없습니다"; exit 1; fi
  printf '%s' "$v" | npx -y wrangler secret put "$k" >/dev/null 2>&1 \
    && echo "✅ $k 등록" || { echo "❌ $k 등록 실패 — 'npx wrangler login' 후 다시 실행해 주세요"; exit 1; }
done
echo "끝. 1분 뒤 핫딜 페이지 검색창에서 상품 목록이 보이면 성공입니다."
