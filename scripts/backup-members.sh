#!/bin/bash
# 회원·포인트 DB(hyetaekzone-members) 백업 — 매주 일요일 03:30 자동 (launchd: io.hubriz.hyetaekzone-backup)
# 파일은 저장소 밖 ~/keys/hyetaekzone/backups (계좌·주민번호는 암호화된 채 들어 있음). 최근 12개(약 3달)만 보관.
# 되살리기: gunzip 한 뒤  npx wrangler d1 execute hyetaekzone-members --remote --file <파일>  (먼저 대표 확인)
# 그 밖에 Cloudflare D1 자체 되돌리기(Time Travel)도 있음: npx wrangler d1 time-travel info hyetaekzone-members
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
DIR="$HOME/keys/hyetaekzone/backups"
mkdir -p "$DIR" && chmod 700 "$DIR"
F="$DIR/members-$(date +%Y%m%d-%H%M).sql"
cd "$(dirname "$0")/../stats-worker"
if ! npx -y wrangler d1 export hyetaekzone-members --remote --output "$F" >/dev/null 2>&1; then
  echo "$(date '+%F %T') ❌ 백업 실패 (wrangler 로그인 확인: npx wrangler whoami)"; exit 1
fi
chmod 600 "$F" && gzip -f "$F"
n=0; for old in $(ls -1t "$DIR"/members-*.sql.gz); do n=$((n+1)); [ $n -gt 12 ] && rm -f "$old"; done
echo "$(date '+%F %T') ✅ 백업 $(basename "$F").gz ($(du -h "$F.gz" | cut -f1))"
