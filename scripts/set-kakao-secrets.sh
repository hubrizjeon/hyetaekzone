#!/bin/bash
# 카카오 로그인 키를 Cloudflare Worker(hyetaekzone-stats) 비밀값으로 등록합니다.
# 붙여넣은 값은 화면에 나오지 않고, 이 컴퓨터에도 저장되지 않습니다.
#   실행: bash scripts/set-kakao-secrets.sh
set -euo pipefail
cd "$(dirname "$0")/../stats-worker"
put() {  # $1 비밀값 이름, $2 값
  printf '%s' "$2" | npx -y wrangler secret put "$1" >/dev/null 2>&1 \
    && echo "✅ $1 등록" || { echo "❌ $1 등록 실패 — 'npx wrangler login' 후 다시 실행해 주세요"; exit 1; }
}
read -r -s -p "카카오 REST API 키를 붙여넣고 Enter: " REST; echo
[ -n "$REST" ] || { echo "❌ 비어 있습니다"; exit 1; }
put KAKAO_REST_KEY "$REST"
read -r -s -p "Client Secret 코드 (안 만들었으면 그냥 Enter): " SEC; echo
[ -n "$SEC" ] && put KAKAO_CLIENT_SECRET "$SEC" || echo "— Client Secret 은 건너뜀"
unset REST SEC
echo "끝. 1분 뒤 https://hubrizjeon.github.io/hyetaekzone/my.html 에서 「카카오로 시작하기」를 눌러 보세요."
