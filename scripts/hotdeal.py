#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔥 오늘의 핫딜 — 쿠팡파트너스 골드박스로 혜택존 핫딜 칸과 전용 페이지를 다시 만든다.

  python3 scripts/hotdeal.py                   index.html 의 핫딜 칸 + hotdeal.html 갱신
  python3 scripts/hotdeal.py --check           파일은 건드리지 않고 무엇이 올라갈지만 출력
  python3 scripts/hotdeal.py --check --force-fallback   상품 0개인 날의 모습 점검

원칙 (HANDOFF 7장 · 2026-09-10 대표 결정)
- 매일 유지: 핫딜 칸과 목차 「🔥 오늘의 핫딜」은 없어지지 않는다
- 메인: 혜택 6개 카테고리 뒤 · 꿀팁 앞에 대표 3개 + 「핫딜 상품 전체 보기」
- 전용 페이지 hotdeal.html: 쿠팡파트너스 상품만 (혜택 정보 섞지 않음)
- 쿠팡 API 는 정가·할인율을 주지 않는다 → 할인율을 적지 않는다.
  사실인 것(골드박스 선정, 판매가와 확인 시각, 로켓배송)만 적는다
- 확인 안 되는 상품은 뺀다: 이름·가격·링크·이미지 누락 / 5만원 초과 / 대상 외 카테고리
- 통과 상품 0개거나 API 실패 → 골드박스 바로가기 카드 1장
- 네이버 언급 금지
- index.html 에서는 PARTNERS 마커 안쪽, HOTDEAL-CSS 마커 안쪽, 목차 칩만 건드린다
"""
import argparse, datetime, html, os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coupang as C  # noqa: E402

ROOT = HERE.parent
INDEX = ROOT / "index.html"
PAGE = ROOT / "hotdeal.html"
SUB_ID = "hyetaekzone"
PRICE_CAP = 50_000
MAIN_COUNT = 3
GOLDBOX_URL = "https://www.coupang.com/np/goldbox"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 쿠팡이 상품마다 돌려주는 categoryName → 페이지 그룹. 여기 없는 카테고리는 싣지 않는다.
# (HANDOFF 의 카테고리 ID 표는 실제 응답과 달라 쓰지 않는다 — 2026-09-10 확인:
#  1012·1024 가 둘 다 신선식품, 1014 가 유아용품을 돌려줌)
GROUPS = [
    ("life",    "🧻 생활용품",      "생활용품",     ["생활용품"]),
    ("food",    "🍚 먹거리",        "먹거리",       ["식품", "로켓프레시"]),
    ("kitchen", "🍳 주방용품",      "주방용품",     ["주방용품"]),
    ("beauty",  "💄 뷰티",          "뷰티",         ["뷰티"]),
    ("home",    "🛏️ 침구·인테리어", "침구·인테리어", ["가구/홈인테리어", "홈인테리어"]),
    ("health",  "💊 건강식품",      "건강식품",     ["헬스/건강식품"]),
]
GROUP_BY_CAT = {c: g for g in GROUPS for c in g[3]}

P_START, P_END = "<!-- PARTNERS:START", "<!-- PARTNERS:END -->"
CSS_START, CSS_END = "/* HOTDEAL-CSS:START */", "/* HOTDEAL-CSS:END */"
CHIP = '<a class="hot" href="hotdeal.html">🔥 오늘의 핫딜</a>'
TIPS_ANCHOR = '  <div class="tips">'
E = lambda s: html.escape(str(s), quote=True)

CSS = CSS_START + """
  .hd-rule{border:0;border-top:6px solid var(--line);margin:52px 0 0}
  .hd-rule-label{text-align:center;margin-top:-16px}
  .hd-rule-label span{background:var(--bg);color:var(--mut);font-size:15px;font-weight:800;padding:0 12px}
  #hotdeal{margin-top:24px}
  .hd-notice{background:#f7f5f2;border:2px solid var(--line);border-radius:16px;
    padding:16px 18px;font-size:18px;color:var(--sub);line-height:1.7;margin-bottom:16px}
  .hd-notice b{color:var(--txt)}
  :root[data-theme="dark"] .hd-notice{background:#241b12}
  .hd-group{font-size:20px;font-weight:900;margin:26px 0 12px;scroll-margin-top:14px}
  .card.ad{border:2px dashed #e5b9c4;box-shadow:none}
  .ad .where{background:#57534e}
  .adtag{font-size:14px;font-weight:900;color:#fff;background:#9ca3af;padding:4px 10px;border-radius:8px}
  .hd-img{display:block;width:100%;max-height:240px;object-fit:contain;background:#fff;border-radius:12px;margin:2px 0 12px}
  .ad .what{font-size:21px}
  .ad .how small{font-size:15px;color:var(--mut)}
  .ad .btn{background:#e11d48;box-shadow:0 4px 0 #9f1239}
  .hd-more{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:4px;width:100%;
    border:3px solid #e11d48;color:#e11d48;background:var(--card);text-decoration:none;
    font-size:20px;font-weight:900;padding:15px;border-radius:15px}
  .hd-back{display:inline-block;margin:18px 0 8px;font-size:18px;font-weight:800;color:var(--sub);text-decoration:none}
  .hd-stamp{font-size:15px;color:var(--mut);margin:0 0 4px}
  """ + CSS_END

NOTICE = """
    <div class="hd-notice">
      <b>이 영역은 제휴 링크입니다.</b><br>
      이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.<br>
      구매하셔도 여러분이 내시는 가격은 같습니다.<br>
      가격·할인율은 수시로 바뀌니 쿠팡에서 최종 가격을 확인해 주세요.
    </div>"""

DATE_SCRIPT = ("<script>(function(){var d=new Date(),D=['일','월','화','수','목','금','토'];"
               "var e=document.getElementById('today');if(e)e.textContent=d.getFullYear()+'년 '+"
               "(d.getMonth()+1)+'월 '+d.getDate()+'일 ('+D[d.getDay()]+')';})();</script>")


def stamp(now):
    ampm = "오전" if now.hour < 12 else "오후"
    return f"{now.month}월 {now.day}일 {ampm} {now.hour % 12 or 12}:{now.minute:02d}"


def today_text(now):
    return f"{now.year}년 {now.month}월 {now.day}일 ({'월화수목금토일'[now.weekday()]})"


def fetch():
    st, body = C.goldbox(limit=100, sub_id=SUB_ID)
    if st != 200 or not isinstance(body, dict) or str(body.get("rCode")) != "0":
        raise RuntimeError(f"골드박스 조회 실패: HTTP {st} {str(body)[:200]}")
    return body.get("data") or []


def select(items):
    picks, skipped, seen = [], [], set()
    for it in items:
        name = (it.get("productName") or "").strip()
        url, img = it.get("productUrl") or "", it.get("productImage") or ""
        cat, pid = it.get("categoryName") or "", it.get("productId")
        try:
            price = int(float(it.get("productPrice") or 0))
        except (TypeError, ValueError):
            price = 0
        why = None
        if not name or not url.startswith("https://link.coupang.com/") or not img.startswith("https://"):
            why = "정보 누락"
        elif price <= 0:
            why = "가격 없음"
        elif price > PRICE_CAP:
            why = f"{PRICE_CAP:,}원 초과"
        elif cat not in GROUP_BY_CAT:
            why = f"대상 외 카테고리({cat})"
        elif pid in seen:
            why = "중복"
        if why:
            skipped.append((name or "(이름 없음)", why))
            continue
        seen.add(pid)
        picks.append(dict(name=name, price=price, url=url, img=img, cat=cat,
                          group=GROUP_BY_CAT[cat], rocket=bool(it.get("isRocket")),
                          free=bool(it.get("isFreeShipping"))))
    return picks, skipped


def fallback_link():
    """상품 0개인 날의 골드박스 바로가기. 제휴 링크를 못 만들면 일반 링크(수수료 없음)."""
    try:
        st, body = C.deeplink([GOLDBOX_URL], sub_id=SUB_ID)
        data = (body or {}).get("data") or []
        if st == 200 and data:
            u = data[0].get("shortenUrl") or data[0].get("landingUrl") or ""
            if u.startswith("https://"):
                return u, True
    except Exception:  # noqa: BLE001 — 실패하면 아래 일반 링크
        pass
    return GOLDBOX_URL, False


def card(p, st):
    ship = "🚀 로켓배송" if p["rocket"] else "📦 일반배송"
    ship += " · 무료배송" if p["free"] else " · 배송비는 쿠팡에서 확인"
    return f"""
    <div class="card ad">
      <div class="tagrow"><span class="where">{E(p['group'][2])}</span><span class="adtag">광고</span></div>
      <img class="hd-img" src="{E(p['img'])}" alt="{E(p['name'])}" loading="lazy">
      <div class="what">{E(p['name'])}</div>
      <div class="how"><span class="ic">💰</span><span>쿠팡 판매가 <b>{p['price']:,}원</b> <small>({E(st)} 확인)</small></span></div>
      <div class="how"><span class="ic">🏷️</span><span>쿠팡 골드박스 선정 상품</span></div>
      <div class="how"><span class="ic">🚚</span><span>{ship}</span></div>
      <span class="badge info">가격은 수시로 바뀝니다 · 쿠팡에서 최종 확인</span>
      <a class="btn" href="{E(p['url'])}" target="_blank" rel="noopener nofollow sponsored">구매하러 가기 <span class="arr">→</span></a>
    </div>"""


def fallback_card(url, affiliate):
    tag = '<span class="adtag">광고</span>' if affiliate else ""
    rel = "noopener nofollow sponsored" if affiliate else "noopener"
    return f"""
    <div class="card ad">
      <div class="tagrow"><span class="where">쿠팡 골드박스</span>{tag}</div>
      <div class="what">오늘의 특가는 쿠팡 골드박스에서 바로 확인하세요</div>
      <div class="how"><span class="ic">🏷️</span><span>쿠팡의 골드박스 특가 상품 모음입니다</span></div>
      <a class="btn" href="{E(url)}" target="_blank" rel="{rel}">골드박스 보러 가기 <span class="arr">→</span></a>
    </div>"""


def main_block(picks, st, fb):
    cards = "".join(card(p, st) for p in picks[:MAIN_COUNT]) if picks else fb
    more = (f'\n    <a class="hd-more" href="hotdeal.html">🔥 핫딜 상품 전체 보기 ({len(picks)}개) '
            f'<span class="arr">→</span></a>') if picks else ""
    return f"""  {P_START} — scripts/hotdeal.py 가 만듭니다. 손으로 고치지 마세요 (야간 갱신도 건드리지 않음) -->
  <hr class="hd-rule">
  <div class="hd-rule-label"><span>여기부터는 제휴 광고입니다</span></div>
  <section id="hotdeal">
    <div class="cat-head">
      <span class="cat-emoji">🔥</span>
      <div>
        <div class="cat-title">오늘의 핫딜</div>
        <div class="cat-note">쿠팡 골드박스 상품 · 제휴 링크 · {E(st)} 기준</div>
      </div>
    </div>{NOTICE}{cards}{more}
  </section>
  {P_END}
"""


def apply_index(src, block):
    if CSS_START in src:
        src = re.sub(re.escape(CSS_START) + r".*?" + re.escape(CSS_END), lambda m: CSS, src, flags=re.S)
    else:
        src = src.replace("</style>", "  " + CSS + "\n</style>", 1)

    i = src.index('<div class="toc">')
    j = src.index("</div>", i)
    if "hotdeal.html" not in src[i:j]:
        src = src[:j] + "  " + CHIP + "\n  " + src[j:]

    if P_START in src:
        s = src.rfind("\n", 0, src.index(P_START)) + 1
        e = src.index(P_END, s) + len(P_END)
        if src[e:e + 1] == "\n":
            e += 1
        src = src[:s] + block + src[e:]
    else:
        if src.count(TIPS_ANCHOR) != 1:
            raise RuntimeError("꿀팁(<div class=\"tips\">) 위치를 정확히 찾지 못해 핫딜 칸을 넣지 않았습니다")
        src = src.replace(TIPS_ANCHOR, block + "\n" + TIPS_ANCHOR)
    return src


def build_page(index_src, picks, st, fb, now):
    head = index_src[:index_src.index("</head>")]
    head = re.sub(r"<title>.*?</title>", "<title>오늘의 핫딜 · 돌봄플러스 혜택존</title>", head, count=1, flags=re.S)
    present = [g for g in GROUPS if any(p["group"] is g for p in picks)]
    toc = "\n".join(f'    <a href="#g-{g[0]}">{g[1]}</a>' for g in present)
    groups = "".join(
        f'\n  <div class="hd-group" id="g-{g[0]}">{g[1]}</div>'
        + "".join(card(p, st) for p in picks if p["group"] is g) for g in present) if picks else fb
    toc_html = f'\n  <div class="toc">\n{toc}\n  </div>' if picks else ""
    return f"""{head}</head>
<body>

<header>
  <div class="wrap">
    <div class="brand">💙 HUBRIZ 돌봄플러스 혜택존</div>
    <h1>🔥 오늘의 <b>핫딜</b></h1>
    <div class="date" id="today">{today_text(now)}</div>
    <p class="hello">쿠팡 골드박스에 오른 생활·먹거리·주방 상품을 모았어요. <b>이 페이지의 상품은 모두 제휴 광고</b>입니다.</p>
  </div>
</header>

<div class="wrap">

  <a class="hd-back" href="./">← 혜택존으로 돌아가기</a>
{NOTICE}
  <p class="hd-stamp">쿠팡 가격 확인: {E(st)} · 가격은 수시로 바뀝니다</p>{toc_html}
{groups}

  <a class="hd-back" href="./">← 혜택존으로 돌아가기</a>

  <footer>
    HUBRIZ 돌봄플러스 혜택존 · 오늘의 핫딜<br>
    이 페이지의 모든 상품 링크는 쿠팡 파트너스 제휴 링크입니다.<br>
    ※ 가격·배송 조건은 수시로 바뀝니다. 구매 전 쿠팡에서 최종 확인해 주세요.
  </footer>

</div>

{DATE_SCRIPT}
</body>
</html>
"""


def validate(old, new, page):
    problems = []
    for label, text, n in [("PARTNERS 시작", P_START, 1), ("PARTNERS 끝", P_END, 1),
                           ("핫딜 CSS", CSS_START, 1), ("목차 칩", 'href="hotdeal.html">🔥 오늘의 핫딜', 1),
                           ("꿀팁", '<div class="tips">', 1)]:
        if new.count(text) != n:
            problems.append(f"index.html {label} {new.count(text)}곳 (정상 {n})")
    if new.index(P_START) > new.index('<div class="tips">'):
        problems.append("핫딜 칸이 꿀팁 뒤에 있음")
    if new.count("네이버") != old.count("네이버") or "네이버" in page:
        problems.append("네이버 언급이 추가됨")
    for label, t in (("index.html", new), ("hotdeal.html", page)):
        if len(re.findall(r"<a\b", t)) != t.count("</a>"):
            problems.append(f"{label} 링크 태그 짝이 맞지 않음")
    if problems:
        raise RuntimeError("검증 실패 — 파일을 바꾸지 않았습니다: " + "; ".join(problems))


def write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="파일을 바꾸지 않고 결과만 출력")
    ap.add_argument("--force-fallback", action="store_true", help="상품 0개인 날의 모습 점검")
    a = ap.parse_args()

    now = datetime.datetime.now(KST)
    st = stamp(now)
    err = None
    try:
        items = fetch()
    except Exception as ex:  # noqa: BLE001
        items, err = [], str(ex)
    picks, skipped = select(items)
    if a.force_fallback:
        picks = []

    fb, fb_aff = "", None
    if not picks:
        url, fb_aff = fallback_link()
        fb = fallback_card(url, fb_aff)

    old = INDEX.read_text(encoding="utf-8")
    new = apply_index(old, main_block(picks, st, fb))
    page = build_page(new, picks, st, fb, now)
    validate(old, new, page)

    print(f"쿠팡 가격 확인 시각: {st}")
    if err:
        print(f"⚠️ {err}")
    print(f"골드박스 {len(items)}개 → 싣는 상품 {len(picks)}개 · 뺀 상품 {len(skipped)}개")
    for g in GROUPS:
        n = sum(1 for p in picks if p["group"] is g)
        if n:
            print(f"  {g[1]} {n}개")
    if picks:
        print("메인 대표 3개:", " / ".join(f"{p['name'][:18]} {p['price']:,}원" for p in picks[:MAIN_COUNT]))
    else:
        print(f"상품 0개 → 골드박스 바로가기 카드 ({'제휴 링크' if fb_aff else '일반 링크 · 수수료 없음'})")
    for name, why in skipped:
        print(f"  - 뺌: {name[:26]} ({why})")

    if a.check:
        print("(--check: 파일은 바꾸지 않았습니다)")
        return 0
    write(INDEX, new)
    write(PAGE, page)
    print("저장: index.html (핫딜 칸) · hotdeal.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
