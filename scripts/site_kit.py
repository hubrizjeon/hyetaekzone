# -*- coding: utf-8 -*-
"""혜택존 공통 장치 — 카톡 공유 미리보기 · 「동료 선생님께 보내기」 · 「홈 화면에 추가」 · 방문·클릭 집계.

scripts/hotdeal.py 가 실행될 때마다 함께 적용됩니다 (야간 23시 · 아침 8시).
야간 갱신이 index.html 을 다시 써서 이 장치가 빠져도 여기서 되살립니다.
index.html 에서는 HZ-* 마커 안쪽과 HZ-KIT-CSS 마커 안쪽만 건드립니다.

집계는 stats-worker/ (Cloudflare Worker + D1) 로 갑니다. 개인정보 없이 날짜별 개수만 셉니다.
조회: scripts/stats.sh
"""
import html

SITE = "https://hubrizjeon.github.io/hyetaekzone/"
STATS = "https://hyetaekzone-stats.baglebagle.workers.dev/e"
SHARE_URL = SITE + "?ref=share"
TITLE = "오늘의 실속 혜택 · 돌봄플러스 혜택존"
DESC = "돌봄·가사 선생님을 위한 오늘의 혜택 모음. 정부 지원부터 장보기·커피 쿠폰까지 큰 글씨로 매일 새로 정리합니다."
SHARE_TEXT = "돌봄·가사 선생님을 위한 오늘의 혜택 모음이에요. 큰 글씨로 매일 새로 정리돼요."
HOT_TITLE = "🔥 오늘의 핫딜 · 돌봄플러스 혜택존"
HOT_DESC = "쿠팡 골드박스 특가와 카테고리별 인기 상품 모음 (쿠팡 파트너스 제휴 광고)"
VIEWPORT = '<meta name="viewport" content="width=device-width,initial-scale=1">'
E = lambda s: html.escape(str(s), quote=True)
M = {k: (f"<!-- HZ-{k}:START", f"<!-- HZ-{k}:END -->") for k in ("META", "TOOLS", "SHARE", "TRACK", "JS")}
CSS_START, CSS_END = "/* HZ-KIT-CSS:START */", "/* HZ-KIT-CSS:END */"

CSS = CSS_START + """
  .hz-tools{display:flex;gap:10px;margin:14px 0 4px}
  .hz-tools button,.hz-share-end button,.hz-close{font-family:inherit;font-weight:900;cursor:pointer;border-radius:14px}
  .hz-tools button{flex:1;font-size:17px;padding:14px 8px;border:2px solid var(--line);background:var(--card);color:var(--txt)}
  .hz-tools .hz-share,.hz-share-end .hz-share{background:var(--brand);border:2px solid var(--brand);color:#fff}
  .hz-guide{margin:12px 0 4px;border:2px solid #fed7aa;background:#fff7ed;border-radius:16px;padding:16px 18px;font-size:18px;color:var(--sub)}
  .hz-guide b{color:var(--txt)}
  .hz-guide ol{margin:10px 0 14px 24px}
  .hz-guide li{margin:8px 0}
  :root[data-theme="dark"] .hz-guide{background:#2c2013;border-color:#5a3f22}
  .hz-close{font-size:16px;padding:10px 18px;border:2px solid var(--line);background:var(--card);color:var(--txt)}
  .hz-share-end{margin-top:30px;text-align:center;font-size:18px;color:var(--sub)}
  .hz-share-end button{width:100%;margin-top:10px;font-size:19px;padding:16px}
  .hz-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#241c12;color:#fff;
    padding:14px 18px;border-radius:14px;font-size:17px;font-weight:700;z-index:50;width:max-content;max-width:90%;text-align:center}
  .hz-tools[hidden],.hz-guide[hidden],.hz-share-end[hidden],.hz-tools [hidden]{display:none!important}
  """ + CSS_END


def meta(title, desc, url):
    return f"""{M['META'][0]} — scripts/site_kit.py 가 관리 -->
<meta name="description" content="{E(desc)}">
<meta name="theme-color" content="#e8622a">
<meta property="og:type" content="website">
<meta property="og:site_name" content="돌봄플러스 혜택존">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
<meta property="og:image" content="{SITE}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-title" content="혜택존">
{M['META'][1]}
"""


TOOLS = f"""  {M['TOOLS'][0]} — scripts/site_kit.py 가 관리 -->
  <div class="hz-tools" hidden>
    <button type="button" class="hz-share" data-share>📤 동료 선생님께 보내기</button>
    <button type="button" class="hz-home" data-home>📲 홈 화면에 추가</button>
  </div>
  <div class="hz-guide" id="hz-guide" hidden>
    <b>홈 화면에 추가하면 앱처럼 한 번에 열려요</b>
    <ol id="hz-steps"></ol>
    <button type="button" class="hz-close" data-close>닫기</button>
  </div>
  {M['TOOLS'][1]}
"""

SHARE = f"""  {M['SHARE'][0]} — scripts/site_kit.py 가 관리 -->
  <div class="hz-share-end" hidden>
    도움이 됐다면 동료 선생님께도 알려 주세요 💙
    <button type="button" class="hz-share" data-share>📤 동료 선생님께 보내기</button>
  </div>
  {M['SHARE'][1]}
"""


def track_block(page):
    js = """<script>
(function(){
  var ENDPOINT='__EP__', PAGE='__PAGE__', DAY=new Date().toISOString().slice(0,10);
  function clean(s){ return String(s||'').replace(/\\s*\\d+$/,'').trim().slice(0,80); }
  function track(type,label){
    label=clean(label); if(!label) return;
    try{ var k='hz_track|'+DAY+'|'+type+'|'+label; localStorage.setItem(k,(parseInt(localStorage.getItem(k),10)||0)+1); }catch(e){}
    try{ navigator.sendBeacon(ENDPOINT,new Blob([JSON.stringify({page:PAGE,type:type,label:label})],{type:'text/plain;charset=UTF-8'})); }catch(e){}
  }
  window.hzTrack=track;
  function on(sel,type,fn){ document.querySelectorAll(sel).forEach(function(a){ a.addEventListener('click',function(){ track(type,fn(a)); }); }); }
  var txt=function(a){ return a.textContent; };
  on('.card .btn', 'card', function(a){
    var c=a.closest('.card'), w=c&&c.querySelector('.where'), s=c&&c.closest('section');
    if(c&&c.classList.contains('ad')) return;
    return (w?w.textContent.trim():'?')+(s&&s.id?'@'+s.id:''); });
  on('.card.ad .btn', 'buy', function(a){ var w=a.closest('.card').querySelector('.where'); return (w?w.textContent.trim():'?')+'@'+PAGE; });
  on('.toc a','toc',txt); on('.hd-cats a','cat',txt); on('.hd-filter a','filter',txt); on('.hd-sort a','sort',txt);
  on('.sources a','source',txt); on('#hd-more','more',function(){ return '더 보기'; });
  var ref=(location.search.match(/[?&]ref=([a-z]+)/)||[])[1];
  track('visit',(window.innerWidth<600?'mobile':'desktop')+(ref?'·'+ref:''));
  window.hzStats=function(){ var o={}; for(var i=0;i<localStorage.length;i++){ var k=localStorage.key(i); if(k&&k.indexOf('hz_track|')===0) o[k]=localStorage.getItem(k); } return o; };
})();
</script>""".replace("__EP__", STATS).replace("__PAGE__", page)
    return (f"{M['TRACK'][0]} — 방문·클릭 개수 집계 (개인정보 없음, scripts/site_kit.py 가 관리) -->\n"
            f"{js}\n{M['TRACK'][1]}\n")


JS = (M["JS"][0] + " — 보내기·홈 화면 추가 (scripts/site_kit.py 가 관리) -->\n" + """<script>
(function(){
  var URL_='__URL__', TITLE='__TITLE__', TEXT='__TEXT__';
  function t(type,label){ try{ window.hzTrack&&window.hzTrack(type,label); }catch(e){} }
  function toast(msg){ var d=document.createElement('div'); d.className='hz-toast'; d.setAttribute('role','status'); d.textContent=msg;
    document.body.appendChild(d); setTimeout(function(){ d.remove(); },3500); }
  function ask(){ window.prompt('이 주소를 길게 눌러 복사한 뒤 카톡에 붙여넣어 주세요', URL_); }
  function share(){
    if(navigator.share){ t('share','native'); navigator.share({title:TITLE,text:TEXT,url:URL_}).catch(function(){}); return; }
    t('share','copy');
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(URL_).then(function(){ toast('주소를 복사했어요. 카톡 대화창에 붙여넣기 하세요.'); }, ask);
    } else { ask(); }
  }
  var ua=navigator.userAgent, ios=/iPhone|iPad|iPod/.test(ua)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  var kakao=/KAKAOTALK/i.test(ua), samsung=/SamsungBrowser/i.test(ua);
  var standalone=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone;
  var deferred=null;
  window.addEventListener('beforeinstallprompt',function(e){ e.preventDefault(); deferred=e; });
  function steps(){
    if(kakao&&ios) return ['오른쪽 아래 <b>⋯</b> 버튼 → <b>「Safari로 열기」</b>를 누르세요','Safari 화면 아래 가운데 <b>공유 버튼</b>(네모에 위 화살표)을 누르세요','<b>「홈 화면에 추가」</b> → 오른쪽 위 <b>「추가」</b>'];
    if(kakao) return ['오른쪽 위 <b>⋮</b> 버튼 → <b>「다른 브라우저로 열기」</b>를 누르세요','열린 화면에서 <b>⋮</b> 버튼 → <b>「홈 화면에 추가」</b>','<b>「추가」</b>를 누르세요'];
    if(ios) return ['화면 아래 가운데 <b>공유 버튼</b>(네모에 위 화살표)을 누르세요','목록을 위로 올려 <b>「홈 화면에 추가」</b>를 누르세요','오른쪽 위 <b>「추가」</b>를 누르세요'];
    if(samsung) return ['화면 아래 <b>≡</b> 버튼을 누르세요','<b>「현재 페이지 추가」</b> → <b>「홈 화면」</b>을 누르세요','<b>「추가」</b>를 누르세요'];
    return ['오른쪽 위 <b>⋮</b>(점 세 개) 버튼을 누르세요','<b>「홈 화면에 추가」</b>를 누르세요','<b>「추가」</b>를 누르세요'];
  }
  function home(){
    if(deferred){ t('home','prompt'); deferred.prompt(); deferred=null; return; }
    t('home', kakao?'kakao':(ios?'ios':(samsung?'samsung':'android')));
    var g=document.getElementById('hz-guide'); if(!g) return;
    document.getElementById('hz-steps').innerHTML=steps().map(function(s){ return '<li>'+s+'</li>'; }).join('');
    g.hidden=false; g.scrollIntoView({block:'center',behavior:'smooth'});
  }
  document.querySelectorAll('[data-share]').forEach(function(b){ b.addEventListener('click',share); });
  document.querySelectorAll('[data-home]').forEach(function(b){ if(standalone){ b.hidden=true; return; } b.addEventListener('click',home); });
  document.querySelectorAll('[data-close]').forEach(function(b){ b.addEventListener('click',function(){ document.getElementById('hz-guide').hidden=true; }); });
  document.querySelectorAll('.hz-tools,.hz-share-end').forEach(function(el){ el.hidden=false; });
})();
</script>
""".replace("__URL__", SHARE_URL).replace("__TITLE__", TITLE).replace("__TEXT__", SHARE_TEXT)
      + M["JS"][1] + "\n")


def _replace_marked(src, key, block):
    s = src.rfind("\n", 0, src.index(M[key][0])) + 1
    e = src.index(M[key][1], s) + len(M[key][1])
    if src[e:e + 1] == "\n":
        e += 1
    return src[:s] + block + src[e:]


def _put(src, key, block, *, before=None, after=None):
    if M[key][0] in src:
        return _replace_marked(src, key, block)
    anchor = before or after
    if src.count(anchor) != 1:
        raise RuntimeError(f"{key} 넣을 자리({anchor.strip()[:30]})를 정확히 찾지 못함")
    return src.replace(anchor, block + anchor) if before else src.replace(anchor, anchor + "\n" + block)


def _track(src, page):
    block = track_block(page)
    if M["TRACK"][0] in src:
        return _replace_marked(src, "TRACK", block)
    old = src.find("/* ── 독자 반응 수집 (hz_track)")
    if old != -1:                               # 예전 hz_track 스크립트를 관리 블록으로 교체
        s = src.rfind("<script>", 0, old)
        e = src.index("</script>", old) + len("</script>")
        if src[e:e + 1] == "\n":
            e += 1
        return src[:s] + block + src[e:]
    return src.replace("</body>", block + "</body>", 1)


def apply_main(src):
    if CSS_START in src:
        s, e = src.index(CSS_START), src.index(CSS_END) + len(CSS_END)
        src = src[:s] + CSS + src[e:]
    else:
        src = src.replace("</style>", "  " + CSS + "\n</style>", 1)
    src = _put(src, "META", meta(TITLE, DESC, SITE), after=VIEWPORT)
    if M["TOOLS"][0] in src:
        src = _replace_marked(src, "TOOLS", TOOLS)
    else:                                       # 목차 바로 아래
        i = src.index('<div class="toc">')
        j = src.index("</div>", i) + len("</div>")
        if src[j:j + 1] == "\n":
            j += 1
        src = src[:j] + TOOLS + src[j:]
    src = _put(src, "SHARE", SHARE, before="  <footer>")
    src = _track(src, "main")
    src = _put(src, "JS", JS, before="</body>")
    return src


def page_head(head):
    """핫딜 페이지 머리 — 메인에서 복사한 공유 미리보기를 핫딜용으로 바꾼다."""
    return _replace_marked(head, "META", meta(HOT_TITLE, HOT_DESC, SITE + "hotdeal.html"))


def problems(index, page):
    out = []
    for k in M:
        if index.count(M[k][0]) != 1 or index.count(M[k][1]) != 1:
            out.append(f"index.html {k} 블록 이상")
    for need in (f'{SITE}og.png', 'rel="manifest"', STATS, "data-share", "data-home"):
        if need not in index:
            out.append(f"index.html 에 {need} 없음")
    if index.find(M["TRACK"][0]) > index.find(M["JS"][0]):
        out.append("집계 스크립트가 보내기 스크립트보다 뒤에 있음")
    if f'content="{SITE}hotdeal.html"' not in page or "PAGE='hotdeal'" not in page:
        out.append("hotdeal.html 공유 미리보기·집계 이상")
    return out
