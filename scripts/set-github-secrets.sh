#!/usr/bin/env bash
# 쿠팡 키를 GitHub 저장소 비밀값으로 등록합니다 — 대표님이 직접 실행하세요.
# ~/.hyetaekzone.env 에서 읽어 바로 GitHub 로 보냅니다. 값은 화면·저장소·Claude 에 남지 않습니다.
set -euo pipefail
F="${HYETAEK_ENV:-$HOME/.hyetaekzone.env}"
for k in COUPANG_ACCESS_KEY COUPANG_SECRET_KEY; do
  v=$(grep -E "^$k=" "$F" | cut -d= -f2-)
  [ -n "$v" ] || { echo "❌ $F 에 $k 가 없습니다. 먼저 ~/hyetaekzone/setkeys.sh 를 실행하세요."; exit 1; }
  printf '%s' "$v" | gh secret set "$k" -R hubrizjeon/hyetaekzone
  echo "✅ $k 등록"
done
echo; echo "GitHub 에 등록된 비밀값 (이름만 보입니다):"; gh secret list -R hubrizjeon/hyetaekzone
