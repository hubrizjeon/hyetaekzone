#!/bin/bash
# 혜택존 회원을 관리자로 지정합니다 (관리 키 사용, 키 값은 화면에 나오지 않음).
#   1) 대표님이 먼저 https://hubrizjeon.github.io/hyetaekzone/my.html 에서 카카오로 로그인
#   2) bash scripts/make-admin.sh            ← 회원 목록(번호·닉네임)을 보여줌
#   3) bash scripts/make-admin.sh <회원번호>  ← 그 회원을 관리자로 지정
set -euo pipefail
KEY=$(grep -o 'STATS_KEY=.*' "$HOME/keys/hyetaekzone/stats.txt" | cut -d= -f2)
W=https://hyetaekzone-stats.baglebagle.workers.dev
if [ $# -eq 0 ]; then
  curl -s "$W/admin/members" -H "Authorization: Bearer $KEY" | python3 -c '
import sys, json, datetime
for m in json.load(sys.stdin).get("members", []):
    t = datetime.datetime.fromtimestamp(m["created"]).strftime("%m/%d %H:%M")
    print(f"  #{m[\"id\"]}  {m[\"nick\"]}  (가입 {t}){\"  ← 관리자\" if m[\"is_admin\"] else \"\"}")' || echo "조회 실패"
  echo "관리자로 지정: bash scripts/make-admin.sh <번호>"
else
  curl -s -X POST "$W/admin/make-admin" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "{\"id\": $1}"
  echo; echo "→ https://hubrizjeon.github.io/hyetaekzone/admin.html 에서 확인"
fi
