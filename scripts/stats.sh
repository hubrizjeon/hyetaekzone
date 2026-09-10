#!/usr/bin/env bash
# 혜택존 방문·클릭 집계 보기 (개인정보 없이 날짜별 개수만)
#   scripts/stats.sh        최근 7일
#   scripts/stats.sh 30     최근 30일
# 키: ~/keys/hyetaekzone/stats.txt (저장소 밖)
set -euo pipefail
DAYS="${1:-7}"
KEY=$(grep -o 'STATS_KEY=.*' "$HOME/keys/hyetaekzone/stats.txt" | cut -d= -f2)
JSON=$(curl -s "https://hyetaekzone-stats.baglebagle.workers.dev/stats?days=$DAYS" -H "Authorization: Bearer $KEY")
python3 - "$JSON" <<'PY'
import sys, json, collections
d = json.loads(sys.argv[1])
rows, since = d.get("rows", []), d.get("since")
print(f"── 혜택존 집계 ({since} 부터) ──")
if not rows:
    print("아직 기록이 없습니다.")
    sys.exit()
NAME = {"visit": "방문", "card": "혜택 버튼", "buy": "핫딜 구매 버튼", "toc": "목차", "cat": "핫딜 카테고리",
        "filter": "핫딜 필터", "sort": "핫딜 정렬", "more": "더 보기", "source": "출처",
        "share": "보내기", "home": "홈 화면 추가"}
by_day = collections.defaultdict(collections.Counter)
for r in rows:
    by_day[r["day"]][r["type"]] += r["n"]
print("\n날짜         방문  혜택버튼  핫딜구매  보내기  홈화면")
for day in sorted(by_day, reverse=True):
    c = by_day[day]
    print(f"{day}  {c['visit']:>4}  {c['card']:>8}  {c['buy']:>8}  {c['share']:>6}  {c['home']:>6}")
tot = collections.defaultdict(collections.Counter)
for r in rows:
    tot[r["type"]][r["label"]] += r["n"]
for t in ("visit", "card", "buy", "share", "home", "cat", "filter", "sort"):
    if tot[t]:
        top = ", ".join(f"{k} {v}" for k, v in tot[t].most_common(5))
        print(f"\n{NAME[t]} 많이 누른 순: {top}")
PY
