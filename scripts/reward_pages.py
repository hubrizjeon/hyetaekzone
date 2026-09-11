# -*- coding: utf-8 -*-
"""내 적립(my.html)·개인정보 처리방침(privacy.html) 페이지를 만든다.
   scripts/hotdeal.py 가 핫딜을 새로 만들 때마다 같이 불러 스타일을 메인과 맞춘다."""
import re
import site_kit as K

API = K.STATS.rsplit("/", 1)[0]          # https://hyetaekzone-stats.….workers.dev
KAKAO_ICON = ('<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path fill="#000" '
              'd="M12 3C6.5 3 2 6.5 2 10.8c0 2.8 1.9 5.2 4.7 6.6l-1 3.6c-.1.3.3.6.6.4l4.2-2.8c.5.1 1 .1 1.5.1 '
              '5.5 0 10-3.5 10-7.9S17.5 3 12 3z"/></svg>')


def _head(index_src, title, desc, path):
    head = index_src[:index_src.index("</head>")]
    head = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", head, count=1, flags=re.S)
    head = K._replace_marked(head, "META", K.meta(title, desc, K.SITE + path))
    return head.replace('<meta name="robots" content="noindex', '<meta name="x-robots" content="noindex', 1) + "</head>\n"


def _page(index_src, title, desc, path, h1, hello, body):
    return f"""{_head(index_src, title, desc, path)}<body>

<header>
  <div class="wrap">
    <div class="brand">💙 HUBRIZ 돌봄플러스 혜택존</div>
    <h1>{h1}</h1>
    <p class="hello">{hello}</p>
  </div>
</header>

<div class="wrap">
  <a class="hd-back" href="./">← 혜택존으로 돌아가기</a>
{body}
  <footer>HUBRIZ 돌봄플러스 혜택존 · <a href="privacy.html">개인정보 처리방침</a></footer>
</div>
</body>
</html>
"""


MY_SCRIPT = """<script>
(function(){
  var API='__API__', KEY='hz_rw';
  function $(id){ return document.getElementById(id); }
  function el(tag,cls,text){ var e=document.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'null'); }catch(e){ return null; } }
  function save(s){ try{ if(s) localStorage.setItem(KEY,JSON.stringify(s)); else localStorage.removeItem(KEY); }catch(e){} }
  function show(id){ ['rw-wait','rw-off','rw-login','rw-me'].forEach(function(x){ $(x).hidden = x!==id; }); }
  function won(n){ return Number(n||0).toLocaleString('ko-KR'); }
  function md(d){ return (+d.slice(4,6))+'/'+(+d.slice(6,8)); }
  function mdDash(d){ return (+d.slice(5,7))+'/'+(+d.slice(8,10)); }

  var h=location.hash, tok=h.match(/login=([A-Za-z0-9_-]{20,})/), rw=h.match(/rw=([a-z-]+)/);
  if(tok) save({token:tok[1]});
  if(tok||rw) history.replaceState(null,'',location.pathname+location.search);
  var MSG={'fail-cancel':'카카오 로그인을 취소하셨어요. 다시 누르면 시작할 수 있어요.',
    'fail-state':'로그인 시간이 지났어요. 버튼을 다시 눌러 주세요.',
    'fail-token':'카카오 로그인에 실패했어요. 잠시 뒤 다시 눌러 주세요.',
    'fail-user':'카카오 정보를 받지 못했어요. 잠시 뒤 다시 눌러 주세요.'};
  if(rw&&MSG[rw[1]]){ $('rw-msg').textContent=MSG[rw[1]]; $('rw-msg').hidden=false; }

  var STATUS={done:['적립 완료','확정'], pending:['적립 예정',''], canceled:['적립 취소','구매 취소·반품']};
  function render(d){
    $('rw-nick').textContent=d.nick+' 님의 적립금';
    $('rw-done').textContent=won(d.sums.done)+'P';
    $('rw-pend').textContent=won(d.sums.pending)+'P';
    var list=$('rw-list'); list.textContent='';
    if(!d.rows.length){ $('rw-empty').hidden=false; }
    d.rows.forEach(function(r){
      var row=el('div','rw-row '+r.status), st=STATUS[r.status];
      row.appendChild(el('div','nm',r.name));
      row.appendChild(el('div','pt',(r.status==='canceled'?'':'+')+won(r.points)+'P'));
      var meta=md(r.day)+' 구매 · '+won(r.gmv)+'원'+(r.qty>1?' ('+r.qty+'개)':'');
      if(r.cancel>0 && r.status!=='canceled') meta+=' · 일부 취소 '+won(r.cancel)+'원';
      row.appendChild(el('div','meta',meta));
      var pill=el('span','rw-pill '+r.status,st[0]), side=el('div','side'); side.appendChild(pill);
      side.appendChild(el('small',null, r.status==='pending' ? mdDash(r.confirmOn)+' 확정 예정' : st[1]));
      row.appendChild(side);
      list.appendChild(row);
    });
    if(d.syncedAt){ var t=new Date(d.syncedAt*1000);
      $('rw-sync').textContent='쿠팡 구매 확인: '+(t.getMonth()+1)+'월 '+t.getDate()+'일 '+t.getHours()+'시 기준 · 하루 한 번 확인해요'; }
  }
  function me(){
    var s=load(); if(!s||!s.token){ show('rw-login'); return; }
    fetch(API+'/me',{headers:{Authorization:'Bearer '+s.token}}).then(function(r){
      if(r.status===401){ save(null); show('rw-login'); return; }
      return r.json().then(function(d){ s.sid=d.subId; s.nick=d.nick; save(s); render(d); show('rw-me'); });
    }).catch(fail);
  }
  function fail(){ $('rw-off-t').textContent='지금 적립 내역을 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.'; show('rw-off'); }
  function post(path){ var s=load()||{}; return fetch(API+path,{method:'POST',headers:{Authorization:'Bearer '+(s.token||'')}}); }
  $('rw-logout').addEventListener('click',function(){ post('/me/logout').then(null,function(){}).then(function(){ save(null); show('rw-login'); }); });
  $('rw-delete').addEventListener('click',function(){
    if(!confirm('탈퇴하면 적립 예정·적립 완료 포인트와 적립 내역이 모두 지워지고 되돌릴 수 없어요.\\n정말 탈퇴할까요?')) return;
    post('/me/delete').then(function(r){ if(!r.ok) throw 0; save(null); alert('탈퇴했어요. 그동안 이용해 주셔서 감사합니다.'); show('rw-login'); })
      .catch(function(){ alert('탈퇴 처리가 안 됐어요. 잠시 뒤 다시 눌러 주세요.'); });
  });
  fetch(API+'/rw/status').then(function(r){ return r.json(); }).then(function(st){ if(st.on) me(); else show('rw-off'); }).catch(fail);
})();
</script>""".replace("__API__", API)

MY_BODY = f"""
  <div class="hd-notice" id="rw-msg" role="status" hidden></div>

  <section id="rw-wait"><p class="rw-sync">불러오는 중…</p></section>

  <section id="rw-off" hidden>
    <div class="hd-notice" id="rw-off-t">포인트 적립 기능을 준비하고 있어요. 조금만 기다려 주세요.</div>
  </section>

  <section id="rw-login" hidden>
    <div class="card">
      <div class="what">핫딜을 사면 구매금액의 1%를 포인트로 모아 드려요</div>
      <ol class="rw-steps">
        <li>카카오로 로그인해요 (처음 한 번)</li>
        <li>로그인한 휴대폰에서 혜택존 핫딜·검색의 「구매하러 가기」를 눌러요</li>
        <li>24시간 안에 쿠팡에서 결제하면, 다음 날 오후쯤 여기에 <b>적립 예정</b>으로 나타나요</li>
      </ol>
      <a class="rw-kakao" href="{API}/auth/kakao?back=my">{KAKAO_ICON}카카오로 시작하기</a>
      <p class="rw-fine">카카오 회원번호와 닉네임만 받아 포인트 관리에만 씁니다 · <a href="privacy.html">개인정보 처리방침</a></p>
    </div>
  </section>

  <section id="rw-me" hidden>
    <h2 class="rw-hello" id="rw-nick"></h2>
    <div class="rw-sum">
      <div class="rw-tile done"><small>적립 완료</small><b id="rw-done">0P</b><span>쿠팡 정산이 끝나 확정된 포인트</span></div>
      <div class="rw-tile pend"><small>적립 예정</small><b id="rw-pend">0P</b><span>구매한 달의 다음 달 25일에 확정</span></div>
    </div>
    <div class="hd-notice">
      쿠팡은 <b>구매한 달의 다음 달 25일</b>에 취소·반품을 빼고 구매를 확정해요.
      그 전까지는 <b>적립 예정</b>, 확정되면 <b>적립 완료</b>로 바뀝니다. 취소·반품한 구매는 적립되지 않아요.
    </div>
    <h3 class="rw-h3">적립 내역</h3>
    <div id="rw-list"></div>
    <div class="rw-empty" id="rw-empty" hidden>
      아직 적립 내역이 없어요.<br>로그인한 이 휴대폰에서 핫딜의 「구매하러 가기」를 눌러 사면 다음 날 오후쯤 여기에 나타나요.
      <a class="hd-more" href="hotdeal.html">🔥 핫딜 상품 보러 가기 →</a>
    </div>
    <p class="rw-sync" id="rw-sync"></p>
    <p class="rw-fine">포인트 사용 방법은 따로 안내해 드립니다. 쿠팡은 산 사람이 아니라 어느 링크로 들어왔는지만 알려줘서,
      로그인하지 않은 채로 사거나 다른 사이트 링크로 사면 적립되지 않아요.</p>
    <div class="rw-acts"><button type="button" id="rw-logout">로그아웃</button><button type="button" id="rw-delete">탈퇴하기</button></div>
  </section>
{MY_SCRIPT}
"""

PRIVACY_BODY = """
  <div class="card rw-doc">
    <p>HUBRIZ 돌봄플러스 혜택존(이하 "혜택존")은 포인트 적립을 위해 아래와 같이 최소한의 개인정보만 처리합니다.</p>
    <h3>1. 처리하는 정보</h3>
    <ul>
      <li>카카오 로그인 시: 카카오 회원번호, 닉네임</li>
      <li>적립을 위해 쿠팡 파트너스에서 받는 정보: 회원 전용 링크로 산 상품의 구매일·상품명·수량·금액, 취소·반품 여부
        (쿠팡은 이름·연락처·주소 등 구매자 정보를 주지 않습니다)</li>
    </ul>
    <h3>2. 쓰는 곳</h3>
    <ul><li>회원 확인, 포인트 적립 예정·완료 내역 표시와 관리</li></ul>
    <h3>3. 보관 기간</h3>
    <ul><li>탈퇴할 때까지. 「내 적립」에서 탈퇴하면 회원 정보와 적립 내역을 바로 지웁니다.</li>
        <li>로그인 유지 정보는 90일이 지나면 자동으로 지워집니다.</li></ul>
    <h3>4. 다른 곳에 주는지</h3>
    <ul><li>제3자에게 제공하지 않습니다.</li></ul>
    <h3>5. 맡기는 곳 (처리 위탁)</h3>
    <ul><li>Cloudflare, Inc. — 서버·데이터 저장</li><li>㈜카카오 — 로그인</li></ul>
    <h3>6. 이용자의 권리</h3>
    <ul><li>언제든 「내 적립」에서 내역을 확인하고 탈퇴(삭제)할 수 있습니다.</li></ul>
    <h3>7. 개인정보 보호책임자</h3>
    <ul><li>HUBRIZ 돌봄플러스 대표</li></ul>
    <p class="rw-fine">시행일: 2026년 9월 12일</p>
  </div>
"""


def build(index_src):
    """(my.html, privacy.html) 내용을 돌려준다."""
    my = _page(index_src, "내 적립 · 돌봄플러스 혜택존", "핫딜을 사면 구매금액의 1%를 포인트로 모아 드려요", "my.html",
               "🪙 내 <b>적립금</b>", "카카오로 로그인하고 혜택존 핫딜로 사면 <b>구매금액의 1%</b>를 포인트로 모아 드려요.", MY_BODY)
    pv = _page(index_src, "개인정보 처리방침 · 돌봄플러스 혜택존", "혜택존 포인트 적립 개인정보 처리방침", "privacy.html",
               "개인정보 <b>처리방침</b>", "포인트 적립에 필요한 최소한의 정보만 받습니다.", PRIVACY_BODY)
    return my, pv
