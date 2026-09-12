#!/bin/bash
# 적립 비율(쿠팡 수수료 중 회원에게 주는 %)을 바꿉니다. 관리자 화면(설정)과 같은 일 — 카카오 로그인 전에도 쓸 수 있음.
#   bash scripts/set-rate.sh          ← 지금 설정 보기
#   bash scripts/set-rate.sh 30       ← 수수료의 30%로 (새로 잡히는 주문부터 적용)
set -euo pipefail
KEY=$(grep -o 'STATS_KEY=.*' "$HOME/keys/hyetaekzone/stats.txt" | cut -d= -f2)
W=https://hyetaekzone-stats.baglebagle.workers.dev
show() { python3 -c '
import sys, json
s = json.load(sys.stdin)
if "error" in s: sys.exit("❌ " + s["error"])
r, mn, ex = s["share"], s["min_cashout"], s["expire_days"]
per, need = int(100000 * 0.03 * r), int(mn / (0.03 * r))
rrn = "켬" if s.get("collect_rrn") else "끔"
print(f"적립 비율: 쿠팡 수수료의 {r*100:g}% (보통 구매금액의 약 {r*3:g}%)")
print(f"  10만원 사면 약 {per:,}P · {mn:,}P 모으려면 약 {need:,}원 구매")
print(f"최소 현금 교환 {mn:,}P · 유효기간 {ex}일 · 주민번호 받기 {rrn}")'; }
CUR=$(curl -s "$W/admin/settings" -H "Authorization: Bearer $KEY")
if [ $# -eq 0 ]; then echo "$CUR" | show; exit 0; fi
echo "$1" | grep -Eq '^[0-9]+(\.[0-9]+)?$' || { echo "❌ 숫자(%)로 넣어 주세요. 예: bash scripts/set-rate.sh 30"; exit 1; }
BODY=$(echo "$CUR" | python3 -c "import sys,json; s=json.load(sys.stdin); s['share']=float('$1')/100; print(json.dumps(s))")
curl -s -X POST "$W/admin/settings" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$BODY" | show
