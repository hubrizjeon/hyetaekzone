# -*- coding: utf-8 -*-
"""쿠팡파트너스 실적 조회 — 클릭·주문·취소·수수료 (쿠팡 리포트 API)
   실행: python3 scripts/sales.py            최근 30일
         python3 scripts/sales.py 7          최근 7일
   쿠팡 집계는 보통 하루 늦게 반영됩니다. 수수료는 구매 확정 후 정산 기준으로 바뀔 수 있습니다.
   '혜택존' = 사이트 링크(subId hyetaekzone), '회원 hzm…' = 로그인 회원 링크, '기타' = 파트너스 사이트에서 직접 만든 링크 등."""
import sys, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coupang as C

days = max(1, min(30, int(sys.argv[1]) if len(sys.argv) > 1 else 30))   # 쿠팡은 한 번에 최대 30일
KST = datetime.timezone(datetime.timedelta(hours=9))
end = datetime.datetime.now(KST).date()
start = end - datetime.timedelta(days=days - 1)
q = f"startDate={start:%Y%m%d}&endDate={end:%Y%m%d}"

def get(name):
    s, r = C.call("GET", f"{C.BASE}/reports/{name}", q)
    if s != 200 or str(r.get("rCode")) != "0":
        raise SystemExit(f"❌ {name} 조회 실패 ({s}) {r.get('rMessage', '')}")
    return r.get("data") or []

def src(row):
    sid = row.get("subId") or ""
    return "혜택존" if sid == "hyetaekzone" else f"회원 {sid}" if sid.startswith("hzm") else "기타"
won = lambda n: f"{int(round(n)):,}원"
d = lambda s: f"{int(s[4:6])}/{int(s[6:8])}"

clicks, orders, cancels, comm = get("clicks"), get("orders"), get("cancels"), get("commission")
print(f"📊 쿠팡파트너스 실적 {start:%-m/%-d} ~ {end:%-m/%-d} (최근 {days}일)\n")
for who in ["혜택존"] + sorted({src(r) for r in orders + clicks if src(r).startswith("회원")}) + ["기타"]:
    c = sum(r.get("click", 0) for r in clicks if src(r) == who)
    oids = {r["orderId"] for r in orders if src(r) == who}
    gmv = sum(r.get("gmv", 0) for r in orders if src(r) == who)
    cm = sum(r.get("commission", 0) for r in comm if src(r) == who)
    print(f"[{who}] 클릭 {c}회 · 주문 {len(oids)}건 · 구매금액 {won(gmv)} · 예상 수수료 {won(cm)}")
print()
if orders:
    print("🛒 주문 내역")
    for r in sorted(orders, key=lambda r: r["date"], reverse=True):
        print(f"  {d(r['date'])} [{src(r)}] {r.get('productName','')[:30]} × {r.get('quantity',1)} · {won(r.get('gmv',0))}")
else:
    print("🛒 아직 주문이 없습니다")
if cancels:
    print("\n↩️ 취소")
    for r in cancels:
        print(f"  {d(r['date'])} [{src(r)}] {r.get('productName','')[:30]} · {won(r.get('gmv',0))}")
print("\n※ 쿠팡 집계는 하루쯤 늦게 반영됩니다. 정확한 정산은 partners.coupang.com 에서 확인하세요.")
