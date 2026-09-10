#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔥 오늘의 핫딜 — 쿠팡파트너스 상품으로 혜택존 핫딜 칸과 전용 페이지를 다시 만든다.

  python3 scripts/hotdeal.py                   index.html 의 핫딜 칸 + hotdeal.html 갱신
  python3 scripts/hotdeal.py --check           파일은 건드리지 않고 무엇이 올라갈지만 출력
  python3 scripts/hotdeal.py --check --force-fallback   상품 0개인 날의 모습 점검

원칙 (HANDOFF 7장 · 2026-09-10 대표 결정)
- 매일 유지: 핫딜 칸과 목차 「🔥 핫딜 상품」(「🆕 새소식」 바로 옆)은 없어지지 않는다
- 메인: 혜택 6개 카테고리 뒤 · 꿀팁 앞에 대표 3개(서로 다른 카테고리) + 카테고리 바로가기 + 「전체 보기」
- 전용 페이지 hotdeal.html: 쿠팡파트너스 상품만. 골드박스 특가 + 전 카테고리 인기 상품
  · 필터: 전체 / 🔥 골드박스 특가 / 카테고리별    · 정렬: 쿠팡 인기순 / 낮은 가격순 / 높은 가격순
  · 처음 30개, 「상품 더 보기」로 30개씩
- 가격 상한·카테고리 제한 없음 (대표 결정). 이름·가격·링크·이미지가 빠진 상품만 뺀다
- 쿠팡 API 는 정가·할인율을 주지 않는다 → 할인율을 적지 않고, 할인순 정렬도 없다
- 통과 상품 0개거나 API 실패 → 골드박스 바로가기 카드 1장
- 네이버 언급 금지
- index.html 에서는 PARTNERS 마커 안쪽, HOTDEAL-CSS 마커 안쪽, 목차 칩만 건드린다
"""
import argparse, datetime, html, os, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coupang as C  # noqa: E402

ROOT = HERE.parent
INDEX = ROOT / "index.html"
PAGE = ROOT / "hotdeal.html"
SUB_ID = "hyetaekzone"
PER_CATEGORY = 20           # 카테고리별 인기 상품 수
MAIN_COUNT = 3
MAIN_CHIPS = 8              # 메인 「카테고리별로 보기」 버튼 수 (나머지는 전체 보기에서)
PAGE_STEP = 30              # 핫딜 페이지 한 번에 보여줄 상품 수
GOLDBOX_URL = "https://www.coupang.com/np/goldbox"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 카테고리 인기 상품을 받아올 쿠팡 카테고리 번호.
# 번호가 곧 내용은 아니다 (예: 1012·1024 → 신선식품, 1025·1026 → 여행 도서) — 그래서
# 페이지 분류는 번호가 아니라 상품마다 쿠팡이 붙여 준 categoryName 으로 한다.
CATEGORY_IDS = [1001, 1002, 1010, 1011, 1012, 1013, 1014, 1015, 1016, 1017,
                1018, 1019, 1020, 1021, 1024, 1025, 1026, 1029, 1030]

# (id, 제목, 카드 이름표, 쿠팡 categoryName 들) — 이 순서대로 버튼이 놓인다
GROUPS = [
    ("life",    "🧻 생활용품",      "생활용품",     ["생활용품"]),
    ("food",    "🍚 먹거리",        "먹거리",       ["식품", "로켓프레시"]),
    ("kitchen", "🍳 주방용품",      "주방용품",     ["주방용품"]),
    ("beauty",  "💄 뷰티",          "뷰티",         ["뷰티"]),
    ("fashion", "👗 패션·잡화",     "패션·잡화",    ["패션잡화", "패션의류", "여성패션", "남성패션"]),
    ("health",  "💊 건강식품",      "건강식품",     ["헬스/건강식품"]),
    ("home",    "🛏️ 가구·인테리어", "가구·인테리어", ["가구/홈인테리어", "홈인테리어"]),
    ("travel",  "✈️ 여행·레저",     "여행·레저",    ["국내투어", "해외투어", "여행", "국내여행", "해외여행"]),
    ("digital", "📺 가전·디지털",   "가전·디지털",  ["가전디지털"]),
    ("baby",    "👶 출산·유아",     "출산·유아",    ["출산/유아"]),
    ("sports",  "⛳ 스포츠·레저",   "스포츠·레저",  ["스포츠/레저용품"]),
    ("pet",     "🐾 반려동물",      "반려동물",     ["반려/애완용품"]),
    ("car",     "🚗 자동차용품",    "자동차용품",   ["자동차용품"]),
    ("book",    "📚 도서",          "도서",         ["도서/음반"]),
    ("office",  "✏️ 문구·사무",     "문구·사무",    ["문구/사무용품"]),
    ("toy",     "🧸 완구·취미",     "완구·취미",    ["완구/취미"]),
    ("etc",     "🛍️ 기타",          "기타",         []),
]
GROUP_BY_CAT = {c: g for g in GROUPS for c in g[3]}
ETC = GROUPS[-1]

P_START, P_END = "<!-- PARTNERS:START", "<!-- PARTNERS:END -->"
CSS_START, CSS_END = "/* HOTDEAL-CSS:START */", "/* HOTDEAL-CSS:END */"
CHIP = '<a class="hot" href="hotdeal.html">🔥 핫딜 상품</a>'   # 목차 두 번째 칸 (「🆕 새소식」 바로 옆)
NEW_OLD, NEW_LABEL = ">🆕 오늘 새 소식<", ">🆕 새소식<"         # 대표 결정 2026-09-10
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
  .card.ad{border:2px dashed #e5b9c4;box-shadow:none}
  .ad .where{background:#57534e}
  .adtag{font-size:14px;font-weight:900;color:#fff;background:#9ca3af;padding:4px 10px;border-radius:8px}
  .gbtag{font-size:14px;font-weight:900;color:#fff;background:#e11d48;padding:4px 10px;border-radius:8px}
  .hd-img{display:block;width:100%;max-height:240px;object-fit:contain;background:#fff;border-radius:12px;margin:2px 0 12px}
  .ad .what{font-size:21px}
  .ad .how small{font-size:15px;color:var(--mut)}
  .ad .btn{background:#e11d48;box-shadow:0 4px 0 #9f1239}
  .hd-more{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:4px;width:100%;
    border:3px solid #e11d48;color:#e11d48;background:var(--card);text-decoration:none;cursor:pointer;
    font-family:inherit;font-size:20px;font-weight:900;padding:15px;border-radius:15px}
  .hd-back{display:inline-block;margin:18px 0 8px;font-size:18px;font-weight:800;color:var(--sub);text-decoration:none}
  .hd-stamp{font-size:15px;color:var(--mut);margin:0 0 4px}
  .hd-cats{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0 12px}
  .hd-cats b,.hd-row b{width:100%;font-size:17px;color:var(--sub)}
  .hd-cats a,.hd-filter a,.hd-sort a{display:inline-flex;align-items:center;background:var(--card);border:2px solid var(--line);
    color:var(--txt);text-decoration:none;font-weight:800;font-size:16px;padding:9px 13px;border-radius:13px}
  .hd-row{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
  .hd-filter a.on,.hd-sort a.on{background:#e11d48;border-color:#e11d48;color:#fff}
  .hd-count{font-size:17px;font-weight:800;color:var(--sub);margin:14px 0 10px;padding-top:12px;border-top:2px solid var(--line)}
  #hd-list [hidden],.hd-more[hidden]{display:none!important}
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

# 필터·정렬·더 보기. 스크립트가 꺼져 있으면 모든 상품이 인기순으로 그대로 보인다.
LIST_SCRIPT = """<script>
(function(){
  var list=document.getElementById('hd-list'); if(!list) return;
  var cards=[].slice.call(list.querySelectorAll('.card.ad'));
  var fBtns=[].slice.call(document.querySelectorAll('.hd-filter a')), sBtns=[].slice.call(document.querySelectorAll('.hd-sort a'));
  var more=document.getElementById('hd-more'), cnt=document.getElementById('hd-count'), bar=document.querySelector('.hd-tools');
  var STEP=__STEP__, st={f:'all', s:'pop', n:STEP};
  function match(c){ return st.f==='all' || (st.f==='gb' ? c.dataset.gb==='1' : c.dataset.g===st.f); }
  function key(c){ return st.s==='low' ? +c.dataset.p : st.s==='high' ? -c.dataset.p : +c.dataset.o; }
  function render(){
    var m=cards.filter(match).sort(function(a,b){ return key(a)-key(b); });
    cards.forEach(function(c){ c.hidden=true; });
    m.forEach(function(c,i){ list.appendChild(c); c.hidden = i>=st.n; });
    cnt.textContent = m.length+'개 상품';
    var left=m.length-st.n; more.hidden = left<=0;
    if(left>0) more.textContent='상품 더 보기 (남은 '+left+'개) ↓';
    fBtns.forEach(function(b){ var on=b.dataset.f===st.f; b.classList.toggle('on',on); b.setAttribute('aria-pressed',on); });
    sBtns.forEach(function(b){ var on=b.dataset.s===st.s; b.classList.toggle('on',on); b.setAttribute('aria-pressed',on); });
  }
  function top(){ window.scrollTo(0, bar.offsetTop-8); }
  fBtns.forEach(function(b){ b.addEventListener('click',function(e){ e.preventDefault();
    st.f=b.dataset.f; st.n=STEP; render(); top();
    history.replaceState(null,'', st.f==='all' ? location.pathname : '#g-'+st.f); }); });
  sBtns.forEach(function(b){ b.addEventListener('click',function(e){ e.preventDefault();
    st.s=b.dataset.s; st.n=STEP; render(); top(); }); });
  more.addEventListener('click',function(){ st.n+=STEP; render(); });
  var h=location.hash.replace('#g-','');
  if(fBtns.some(function(b){ return b.dataset.f===h; })) st.f=h;
  render();
})();
</script>""".replace("__STEP__", str(PAGE_STEP))


def stamp(now):
    ampm = "오전" if now.hour < 12 else "오후"
    return f"{now.month}월 {now.day}일 {ampm} {now.hour % 12 or 12}:{now.minute:02d}"


def today_text(now):
    return f"{now.year}년 {now.month}월 {now.day}일 ({'월화수목금토일'[now.weekday()]})"


def _ok(st, body):
    return st == 200 and isinstance(body, dict) and str(body.get("rCode")) == "0"


def fetch():
    """골드박스 먼저, 그다음 카테고리 인기 상품. 실패한 곳은 건너뛰고 기록한다."""
    items, errs = [], []
    st, body = C.goldbox(limit=100, sub_id=SUB_ID)
    if _ok(st, body):
        items += [dict(it, _src="goldbox") for it in body.get("data") or []]
    else:
        errs.append(f"골드박스 HTTP {st}")
    for cid in CATEGORY_IDS:
        try:
            st, body = C.best_category(cid, limit=PER_CATEGORY, sub_id=SUB_ID)
        except Exception as ex:  # noqa: BLE001
            st, body = 0, {"err": str(ex)}
        if _ok(st, body):
            items += [dict(it, _src="best") for it in body.get("data") or []]
        else:
            errs.append(f"카테고리 {cid} HTTP {st}")
        time.sleep(0.2)
    return items, errs


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
        elif pid in seen:
            why = "중복"
        if why:
            if why != "중복":
                skipped.append((name or "(이름 없음)", why))
            continue
        seen.add(pid)
        picks.append(dict(name=name, price=price, url=url, img=img, cat=cat,
                          group=GROUP_BY_CAT.get(cat, ETC), src=it["_src"], order=len(picks),
                          rocket=bool(it.get("isRocket")), free=bool(it.get("isFreeShipping"))))
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
    g, gb = p["group"], p["src"] == "goldbox"
    if g[0] == "travel":
        ship = "🎫 이용권 · 사용 조건은 쿠팡에서 확인"
    else:
        ship = ("🚀 로켓배송" if p["rocket"] else "📦 일반배송") + \
               (" · 무료배송" if p["free"] else " · 배송비는 쿠팡에서 확인")
    src = ('<span class="ic">🏷️</span><span>쿠팡 골드박스 선정 상품</span>' if gb
           else f'<span class="ic">⭐</span><span>쿠팡 {E(g[2])} 인기 상품</span>')
    gbtag = '<span class="gbtag">🔥 골드박스</span>' if gb else ""
    return f"""
    <div class="card ad" data-g="{g[0]}" data-p="{p['price']}" data-o="{p['order']}" data-gb="{1 if gb else 0}">
      <div class="tagrow"><span class="where">{E(g[2])}</span><span class="adtag">광고</span>{gbtag}</div>
      <img class="hd-img" src="{E(p['img'])}" alt="{E(p['name'])}" loading="lazy">
      <div class="what">{E(p['name'])}</div>
      <div class="how"><span class="ic">💰</span><span>쿠팡 판매가 <b>{p['price']:,}원</b> <small>({E(st)} 확인)</small></span></div>
      <div class="how">{src}</div>
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


def main_picks(picks):
    """메인 대표 상품 — 되도록 서로 다른 카테고리에서 하나씩 (골드박스 → 인기 순)."""
    out, used = [], set()
    for p in picks:
        if p["group"][0] not in used:
            out.append(p)
            used.add(p["group"][0])
        if len(out) == MAIN_COUNT:
            return out
    for p in picks:
        if len(out) == MAIN_COUNT:
            break
        if p not in out:
            out.append(p)
    return out


def group_counts(picks):
    return [(g, sum(1 for p in picks if p["group"] is g)) for g in GROUPS
            if any(p["group"] is g for p in picks)]


def filters(picks):
    """(id, 버튼 글자) — 전체, 골드박스 특가, 카테고리들"""
    out = [("all", f"전체 {len(picks)}")]
    n_gb = sum(1 for p in picks if p["src"] == "goldbox")
    if n_gb:
        out.append(("gb", f"🔥 골드박스 특가 {n_gb}"))
    out += [(g[0], f"{g[1]} {n}") for g, n in group_counts(picks)]
    return out


def main_block(picks, st, fb):
    cards = "".join(card(p, st) for p in main_picks(picks)) if picks else fb
    chips = [f for f in filters(picks) if f[0] != "all"][:MAIN_CHIPS]
    cats = "".join(f'\n      <a href="hotdeal.html#g-{fid}">{E(label)}</a>' for fid, label in chips)
    more = (f'\n    <div class="hd-cats"><b>카테고리별로 보기</b>{cats}\n    </div>'
            f'\n    <a class="hd-more" href="hotdeal.html">🔥 핫딜 상품 전체 보기 ({len(picks)}개) '
            f'<span class="arr">→</span></a>') if picks else ""
    return f"""  {P_START} — scripts/hotdeal.py 가 만듭니다. 손으로 고치지 마세요 (야간 갱신도 건드리지 않음) -->
  <hr class="hd-rule">
  <div class="hd-rule-label"><span>여기부터는 제휴 광고입니다</span></div>
  <section id="hotdeal">
    <div class="cat-head">
      <span class="cat-emoji">🔥</span>
      <div>
        <div class="cat-title">오늘의 핫딜</div>
        <div class="cat-note">쿠팡 골드박스·인기 상품 · 제휴 링크 · {E(st)} 기준</div>
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

    # 목차: 「🆕 새소식」 바로 옆에 「🔥 핫딜 상품」. 야간 갱신이 문구·순서를 되돌려도 여기서 바로잡는다
    i = src.index('<div class="toc">')
    j = src.index("</div>", i)
    lines = [ln.replace(NEW_OLD, NEW_LABEL) for ln in src[i:j].split("\n") if 'href="hotdeal.html"' not in ln]
    k = next((n for n, ln in enumerate(lines) if 'href="#new"' in ln), 0)
    lines.insert(k + 1, "    " + CHIP)
    src = src[:i] + "\n".join(lines) + src[j:]

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
    if picks:
        fbtn = "\n".join(f'      <a href="#g-{fid}" data-f="{fid}" aria-pressed="false">{E(lb)}</a>'
                         for fid, lb in filters(picks))
        sbtn = "\n".join(f'      <a href="#" data-s="{sid}" aria-pressed="false">{lb}</a>'
                         for sid, lb in (("pop", "쿠팡 인기순"), ("low", "낮은 가격순"), ("high", "높은 가격순")))
        tools = f"""
  <div class="hd-tools">
    <nav class="hd-row hd-filter" aria-label="카테고리"><b>무엇을 볼까요</b>
{fbtn}
    </nav>
    <nav class="hd-row hd-sort" aria-label="정렬"><b>순서</b>
{sbtn}
    </nav>
    <p class="hd-count" id="hd-count">{len(picks)}개 상품</p>
  </div>"""
        body = ('\n  <div id="hd-list">' + "".join(card(p, st) for p in picks) + "\n  </div>"
                '\n  <button class="hd-more" id="hd-more" type="button" hidden>상품 더 보기</button>')
    else:
        tools, body = "", fb
    return f"""{head}</head>
<body>

<header>
  <div class="wrap">
    <div class="brand">💙 HUBRIZ 돌봄플러스 혜택존</div>
    <h1>🔥 오늘의 <b>핫딜</b></h1>
    <div class="date" id="today">{today_text(now)}</div>
    <p class="hello">쿠팡 골드박스 특가와 카테고리별 인기 상품을 모았어요. <b>이 페이지의 상품은 모두 제휴 광고</b>입니다.</p>
  </div>
</header>

<div class="wrap">

  <a class="hd-back" href="./">← 혜택존으로 돌아가기</a>
{NOTICE}
  <p class="hd-stamp">쿠팡 가격 확인: {E(st)} · 가격은 수시로 바뀝니다</p>{tools}
{body}

  <a class="hd-back" href="./">← 혜택존으로 돌아가기</a>

  <footer>
    HUBRIZ 돌봄플러스 혜택존 · 오늘의 핫딜<br>
    이 페이지의 모든 상품 링크는 쿠팡 파트너스 제휴 링크입니다.<br>
    ※ 가격·배송 조건은 수시로 바뀝니다. 구매 전 쿠팡에서 최종 확인해 주세요.
  </footer>

</div>

{LIST_SCRIPT if picks else ""}
{DATE_SCRIPT}
</body>
</html>
"""


def validate(old, new, page):
    problems = []
    for label, text, n in [("PARTNERS 시작", P_START, 1), ("PARTNERS 끝", P_END, 1),
                           ("핫딜 CSS", CSS_START, 1), ("목차 칩", CHIP, 1),
                           ("꿀팁", '<div class="tips">', 1)]:
        if new.count(text) != n:
            problems.append(f"index.html {label} {new.count(text)}곳 (정상 {n})")
    toc = new[new.index('<div class="toc">'):]
    toc = toc[:toc.index("</div>")]
    if 'href="#new"' in toc and toc.index('href="#new"') > toc.index("hotdeal.html"):
        problems.append("핫딜 칩이 새소식 앞에 있음")
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
    try:
        items, errs = fetch()
    except Exception as ex:  # noqa: BLE001
        items, errs = [], [str(ex)]
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
    for e in errs:
        print(f"⚠️ {e}")
    n_gb = sum(1 for p in picks if p["src"] == "goldbox")
    print(f"받은 상품 {len(items)}개 → 싣는 상품 {len(picks)}개 (골드박스 {n_gb} · 카테고리 인기 {len(picks) - n_gb}) · 뺀 상품 {len(skipped)}개")
    print("  " + " · ".join(f"{g[1]} {n}" for g, n in group_counts(picks)))
    if picks:
        print("메인 대표 3개:", " / ".join(f"[{p['group'][2]}] {p['name'][:16]} {p['price']:,}원" for p in main_picks(picks)))
        print(f"가격 범위: {min(p['price'] for p in picks):,}원 ~ {max(p['price'] for p in picks):,}원")
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
