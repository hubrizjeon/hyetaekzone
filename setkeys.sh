#!/usr/bin/env bash
# API 키를 안전하게 입력받아 ~/.hyetaekzone.env 에 저장합니다.
# 입력값은 화면에 표시되지 않고, 저장소에도 올라가지 않습니다.

ENV_FILE="${HYETAEK_ENV:-$HOME/.hyetaekzone.env}"
TTY_IN="${HYETAEK_TTY:-/dev/tty}"

exec 3< "$TTY_IN" || { echo "입력 장치를 열 수 없습니다: $TTY_IN" >&2; exit 1; }

c_b=$'\033[1m'; c_g=$'\033[32m'; c_y=$'\033[33m'; c_d=$'\033[2m'; c_0=$'\033[0m'

COUPANG_ACCESS_KEY=""; COUPANG_SECRET_KEY=""
NAVER_CLIENT_ID="";    NAVER_CLIENT_SECRET=""

# 기존 값 읽기
if [ -f "$ENV_FILE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in
      COUPANG_ACCESS_KEY|COUPANG_SECRET_KEY|NAVER_CLIENT_ID|NAVER_CLIENT_SECRET)
        printf -v "$k" '%s' "$v" ;;
    esac
  done < "$ENV_FILE"
fi

mask() {
  local v="$1" n=${#1}
  if   [ "$n" -eq 0 ]; then printf '(비어있음)'
  elif [ "$n" -le 8 ]; then printf '********'
  else printf '%s...%s (%d자)' "${v:0:3}" "${v: -3}" "$n"
  fi
}

ask() {   # ask VAR "설명" 필수여부
  local var="$1" desc="$2" req="$3" cur val
  cur="${!var}"
  while : ; do
    echo
    echo "${c_b}${desc}${c_0}"
    [ -n "$cur" ] && echo "${c_d}  현재 값: $(mask "$cur")  ·  그대로 두려면 Enter${c_0}"
    printf '  %s > ' "$var"
    IFS= read -r -s val <&3
    echo
    val="$(printf '%s' "$val" | tr -d '[:space:]')"

    if [ -n "$val" ]; then
      printf -v "$var" '%s' "$val"
      echo "  ${c_g}저장됨${c_0} $(mask "$val")"; return
    fi
    if [ -n "$cur" ]; then
      echo "  ${c_d}유지함${c_0}"; return
    fi
    if [ "$req" != "yes" ]; then
      echo "  ${c_d}건너뜀${c_0}"; return
    fi
    echo "  ${c_y}값이 필요합니다. 다시 입력해 주세요.${c_0}"
  done
}

echo
echo "${c_b}━━━ 돌봄플러스 혜택존 · API 키 설정 ━━━${c_0}"
echo "${c_d}입력값은 화면에 보이지 않습니다."
echo "저장 위치: $ENV_FILE   (홈 폴더 · 저장소 밖 · 본인만 읽기)${c_0}"

echo
echo "${c_b}[1/2] 쿠팡파트너스${c_0} ${c_d}— 파트너스 > 마이페이지 > Open API${c_0}"
ask COUPANG_ACCESS_KEY "쿠팡 ACCESS KEY" yes
ask COUPANG_SECRET_KEY "쿠팡 SECRET KEY" yes

echo
echo "${c_b}[2/2] 네이버${c_0} ${c_d}(선택 — 없으면 Enter로 건너뛰세요)${c_0}"
echo "${c_d}  네이버클라우드 > NAVER API HUB > Shopping Insight${c_0}"
ask NAVER_CLIENT_ID     "네이버 CLIENT ID" no
ask NAVER_CLIENT_SECRET "네이버 CLIENT SECRET" no

umask 077
{
  echo "# 돌봄플러스 혜택존 API 키 — $(date '+%Y-%m-%d %H:%M')"
  echo "# 저장소 밖(홈 폴더)에 있으며 git에 올라가지 않습니다."
  echo "COUPANG_ACCESS_KEY=${COUPANG_ACCESS_KEY}"
  echo "COUPANG_SECRET_KEY=${COUPANG_SECRET_KEY}"
  echo "NAVER_CLIENT_ID=${NAVER_CLIENT_ID}"
  echo "NAVER_CLIENT_SECRET=${NAVER_CLIENT_SECRET}"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo
echo "${c_g}${c_b}✅ 저장 완료${c_0}  $ENV_FILE"
echo
printf '   %-22s %s\n' "COUPANG_ACCESS_KEY"  "$(mask "$COUPANG_ACCESS_KEY")"
printf '   %-22s %s\n' "COUPANG_SECRET_KEY"  "$(mask "$COUPANG_SECRET_KEY")"
printf '   %-22s %s\n' "NAVER_CLIENT_ID"     "$(mask "$NAVER_CLIENT_ID")"
printf '   %-22s %s\n' "NAVER_CLIENT_SECRET" "$(mask "$NAVER_CLIENT_SECRET")"
echo
echo "${c_d}권한: $(ls -l "$ENV_FILE" | awk '{print $1}')  ·  다시 실행하면 언제든 변경됩니다.${c_0}"
echo
