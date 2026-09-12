# -*- coding: utf-8 -*-
"""아침 메일에 넣을 포인트 현황 (관리 키로 Worker /admin/report 조회). 키 값은 출력하지 않음.
   실행: python3 scripts/points_report.py     — 메일 본문에 그대로 붙일 글을 출력"""
import json, os, sys, time, datetime, urllib.request

W = "https://hyetaekzone-stats.baglebagle.workers.dev"
KEYFILE = os.path.expanduser("~/keys/hyetaekzone/stats.txt")
won = lambda n: f"{int(n or 0):,}"
md = lambda t: datetime.datetime.fromtimestamp(t).strftime("%-m/%-d %H:%M")


def main():
    try:
        key = next(l.split("=", 1)[1].strip() for l in open(KEYFILE, encoding="utf-8") if l.startswith("STATS_KEY="))
        req = urllib.request.Request(f"{W}/admin/report?since={int(time.time()) - 86400}", headers={"Authorization": f"Bearer {key}", "User-Agent": "hyetaekzone-report/1.0"})  # 파이썬 기본 UA 는 Cloudflare 가 막음
        d = json.load(urllib.request.urlopen(req, timeout=20))
    except Exception as e:  # noqa: BLE001
        print(f"🪙 포인트 현황: 조회 실패 ({type(e).__name__}) — admin.html 에서 직접 확인해 주세요")
        return 1
    m, o, c, s = d["members"], d["newOrders"], d["cashPending"], d["settings"]
    out = ["🪙 포인트 현황 (최근 24시간)"]
    if c["n"]:
        out.append(f"- 💸 현금 교환 대기 {c['n']}건 · {won(c['amt'])}P (가장 오래된 신청 {md(c['oldest'])}) → https://hubrizjeon.github.io/hyetaekzone/admin.html")
    else:
        out.append("- 현금 교환 대기: 없음")
    nt = f" · 약관 미동의 {m['noterms']}명" if m.get("noterms") else ""
    out.append(f"- 새 회원 {m['new']}명 (전체 {m['n']}명{nt})")
    if o["n"]:
        first = " 🎉 첫 회원 구매가 쿠팡 실적에 잡혔어요 — 회원 링크 적립이 실제로 작동합니다" if d.get("firstEver") else ""
        out.append(f"- 회원 구매 {o['n']}건 · {won(o['gmv'])}원 · 구매한 회원 {o['buyers']}명{first}")
    else:
        out.append("- 회원 구매: 새로 잡힌 것 없음")
    out.append(f"- 회원 포인트 잔액 합계 {won(d['liability'])}P · 적립 비율 수수료의 {s['share']*100:g}%")
    ls = d.get("lastSync")
    if d.get("syncStale") or not ls or not ls.get("ok"):
        note = f"{md(ls['at'])} {ls.get('note', '')}" if ls else "기록 없음"
        out.append(f"- ⚠️ 쿠팡 동기화가 36시간 넘게 성공하지 못했어요 (마지막: {note}) — 확인 필요")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
