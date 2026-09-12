# -*- coding: utf-8 -*-
"""내 적립(my.html)·관리자(admin.html)·개인정보 처리방침(privacy.html) 페이지를 만든다.
   scripts/hotdeal.py 가 핫딜을 새로 만들 때마다 같이 불러 스타일을 메인과 맞춘다."""
import re
import site_kit as K

API = K.STATS.rsplit("/", 1)[0]          # https://hyetaekzone-stats.….workers.dev
KAKAO_ICON = ('<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path fill="#000" '
              'd="M12 3C6.5 3 2 6.5 2 10.8c0 2.8 1.9 5.2 4.7 6.6l-1 3.6c-.1.3.3.6.6.4l4.2-2.8c.5.1 1 .1 1.5.1 '
              '5.5 0 10-3.5 10-7.9S17.5 3 12 3z"/></svg>')
BANKS = ["KB국민", "신한", "우리", "하나", "NH농협", "IBK기업", "카카오뱅크", "토스뱅크", "케이뱅크", "SC제일",
         "한국씨티", "새마을금고", "신협", "우체국", "수협", "부산", "iM뱅크(대구)", "경남", "광주", "전북", "제주", "산업"]
OFFICER = "김개똥 · 010-0000-0000"      # 개인정보 보호책임자 (대표 지정 2026-09-12)


def _head(index_src, title, desc, path, noindex=False):
    head = index_src[:index_src.index("</head>")]
    head = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", head, count=1, flags=re.S)
    head = K._replace_marked(head, "META", K.meta(title, desc, K.SITE + path))
    if noindex:
        head += '  <meta name="robots" content="noindex, nofollow">\n'
    return head + "</head>\n"


def _page(index_src, title, desc, path, h1, hello, body, noindex=False):
    return f"""{_head(index_src, title, desc, path, noindex)}<body>

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
  <footer>HUBRIZ 돌봄플러스 혜택존 · <a href="terms.html">포인트 이용약관</a> · <a href="privacy.html">개인정보 처리방침</a></footer>
</div>
</body>
</html>
"""


# ───────────────────────── 내 적립 ─────────────────────────
MY_SCRIPT = """<script>
(function(){
  var API='__API__', KEY='hz_rw';
  function $(id){ return document.getElementById(id); }
  function el(tag,cls,text){ var e=document.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'null'); }catch(e){ return null; } }
  function save(s){ try{ if(s) localStorage.setItem(KEY,JSON.stringify(s)); else localStorage.removeItem(KEY); }catch(e){} }
  function show(id){ ['rw-wait','rw-off','rw-login','rw-terms','rw-me'].forEach(function(x){ $(x).hidden = x!==id; }); }
  function won(n){ return Number(n||0).toLocaleString('ko-KR'); }
  function md(d){ return (+d.slice(4,6))+'/'+(+d.slice(6,8)); }
  function mdDash(d){ return (+d.slice(5,7))+'/'+(+d.slice(8,10)); }
  function mdTs(t){ var d=new Date(t*1000); return (d.getMonth()+1)+'/'+d.getDate(); }
  function pct(x){ return Math.round(x*1000)/10+'%'; }

  var h=location.hash, tok=h.match(/login=([A-Za-z0-9_-]{20,})/), rw=h.match(/rw=([a-z-]+)/);
  if(tok) save({token:tok[1]});
  if(tok||rw) history.replaceState(null,'',location.pathname+location.search);
  var MSG={'fail-cancel':'카카오 로그인을 취소하셨어요. 다시 누르면 시작할 수 있어요.',
    'fail-state':'로그인 시간이 지났어요. 버튼을 다시 눌러 주세요.',
    'fail-token':'카카오 로그인에 실패했어요. 잠시 뒤 다시 눌러 주세요.',
    'fail-user':'카카오 정보를 받지 못했어요. 잠시 뒤 다시 눌러 주세요.'};
  function note(t){ $('rw-msg').textContent=t; $('rw-msg').hidden=!t; }
  if(rw&&MSG[rw[1]]) note(MSG[rw[1]]);

  var STATUS={done:['적립 완료','확정'], pending:['적립 예정',''], canceled:['적립 취소','구매 취소·반품']};
  var CASH={requested:['입금 준비 중','pending'], paid:['입금 완료','done'], rejected:['반려 · 포인트 돌려드림','canceled']};
  function rules(d){
    var ul=$('rw-rules'); ul.textContent='';
    ['포인트는 이 사이트 링크로 산 상품에서 우리가 받는 쿠팡 수수료의 '+pct(d.share)+'예요 (보통 구매금액의 약 '+pct(d.share*0.03)+').',
     '구매한 달의 다음 달 25일에 쿠팡이 취소·반품을 빼고 확정하면 「적립 완료」가 돼요. 그 전에는 「적립 예정」이에요.',
     '1P = 1원. '+won(d.min)+'P부터 모인 포인트 전부를 현금으로 계좌에 받을 수 있어요.',
     '적립 완료 후 '+(d.expireDays>=365&&d.expireDays%365===0?(d.expireDays/365)+'년':d.expireDays+'일')+'이 지나도록 쓰지 않은 포인트는 사라져요.',
     '로그인한 이 기기에서 누른 링크로 24시간 안에 사야 적립돼요. 쿠팡은 산 사람이 아니라 어느 링크로 들어왔는지만 알려줘요.']
      .forEach(function(t){ ul.appendChild(el('li',null,t)); });
  }
  function cash(d){
    var box=$('rw-cash-box'), form=$('rw-cash'); box.textContent=''; form.hidden=true;
    var pend=d.cashouts.filter(function(c){ return c.status==='requested'; })[0];
    if(pend){ box.appendChild(el('div','rw-cash-msg','💸 '+won(pend.net!=null?pend.net:pend.amount)+'원 입금을 준비하고 있어요'+(pend.tax?' (세금 '+won(pend.tax)+'원 제외)':'')+' · '+mdTs(pend.requested_at)+' 신청 · '+pend.bank+' '+pend.acct_mask)); return; }
    if(d.status!=='ok'){ box.appendChild(el('div','rw-cash-msg','이용이 멈춘 계정이라 지금은 현금 교환을 할 수 없어요.')); return; }
    if(d.sums.balance>=d.min){ form.hidden=false;
      var tax=d.withholdingRate>0&&d.sums.balance>d.withholdingFreeUpto?Math.floor(d.sums.balance*d.withholdingRate/10)*10:0, tx=$('rw-tax');
      tx.hidden=!tax; if(tax) tx.textContent='세금(원천징수 '+pct(d.withholdingRate)+') '+won(tax)+'원을 빼고 '+won(d.sums.balance-tax)+'원이 입금돼요.';
      $('rw-cash-go').textContent=won(d.sums.balance-tax)+'원 현금으로 받기';
      var rr=$('rw-rrn'); rr.hidden=!d.collectRrn; form.rrn1.required=form.rrn2.required=form.agreeRrn.required=!!d.collectRrn; return; }
    var left=d.min-d.sums.balance, bar=el('div','rw-prog'), fill=el('i');
    fill.style.width=Math.max(2,Math.min(100,d.sums.balance/d.min*100))+'%'; bar.appendChild(fill);
    box.appendChild(el('div','rw-cash-msg',won(left)+'P 더 모이면 현금으로 받을 수 있어요 ('+won(d.min)+'P부터)'));
    box.appendChild(bar);
  }
  function render(d){
    $('rw-nick').textContent=d.nick+' 님의 포인트';
    $('rw-bal').textContent=won(d.sums.balance)+'P';
    $('rw-pend').textContent=won(d.sums.pending)+'P';
    $('rw-totals').textContent='지금까지 적립 완료 '+won(d.sums.earned)+'P · 현금으로 바꾼 포인트 '+won(d.sums.used)+'P'+(d.sums.expired?' · 사라짐 '+won(d.sums.expired)+'P':'');
    var soon=$('rw-soon'); soon.hidden=!d.sums.expiringSoon;
    if(d.sums.expiringSoon) soon.textContent='⏳ 30일 안에 사라질 포인트 '+won(d.sums.expiringSoon)+'P — '+(d.sums.balance>=d.min?'지금 현금으로 받아 두세요.':'적립 완료 후 '+(d.expireDays>=365&&d.expireDays%365===0?(d.expireDays/365)+'년':d.expireDays+'일')+'이 지나면 사라져요.');
    news(d);
    rules(d); cash(d);
    var list=$('rw-list'); list.textContent=''; $('rw-empty').hidden=d.rows.length>0;
    d.rows.forEach(function(r){
      var row=el('div','rw-row '+r.status), st=STATUS[r.status];
      row.appendChild(el('div','nm',r.name));
      row.appendChild(el('div','pt',(r.status==='canceled'?'':'+')+won(r.points)+'P'));
      var meta=md(r.day)+' 구매 · '+won(r.gmv)+'원'+(r.qty>1?' ('+r.qty+'개)':'');
      if(r.cancel>0 && r.status!=='canceled') meta+=' · 일부 취소 '+won(r.cancel)+'원';
      row.appendChild(el('div','meta',meta));
      var side=el('div','side'); side.appendChild(el('span','rw-pill '+r.status,st[0]));
      side.appendChild(el('small',null, r.status==='pending' ? mdDash(r.confirmOn)+' 확정 예정' : st[1]));
      row.appendChild(side); list.appendChild(row);
    });
    var use=[]; d.cashouts.forEach(function(c){ use.push({at:c.requested_at, name:'현금 교환 · '+c.bank+' '+c.acct_mask+(c.tax?' · 세금 '+won(c.tax)+'원 제외 '+won(c.net)+'원 입금':''), pt:-c.amount, pill:CASH[c.status], sub:c.status==='rejected'?(c.reason||''):(c.done_at?mdTs(c.done_at)+' 입금':'')}); });
    d.log.forEach(function(l){ if(l.kind==='adjust') use.push({at:l.at, name:'관리자 조정 · '+(l.memo||''), pt:l.amount, pill:['조정','done'], sub:''});
      if(l.kind==='expire') use.push({at:l.at, name:l.memo||'유효기간 지나 소멸', pt:l.amount, pill:['소멸','canceled'], sub:''}); });
    use.sort(function(a,b){ return b.at-a.at; });
    var ul=$('rw-use'); ul.textContent=''; $('rw-use-h').hidden=!use.length;
    use.forEach(function(u){ var row=el('div','rw-row '+u.pill[1]);
      row.appendChild(el('div','nm',u.name)); row.appendChild(el('div','pt',(u.pt>0?'+':'−')+won(Math.abs(u.pt))+'P'));
      row.appendChild(el('div','meta',mdTs(u.at))); var side=el('div','side'); side.appendChild(el('span','rw-pill '+u.pill[1],u.pill[0]));
      if(u.sub) side.appendChild(el('small',null,u.sub)); row.appendChild(side); ul.appendChild(row); });
    if(d.syncedAt){ var t=new Date(d.syncedAt*1000);
      $('rw-sync').textContent='쿠팡 구매 확인: '+(t.getMonth()+1)+'월 '+t.getDate()+'일 '+t.getHours()+'시 기준 · 하루 한 번 확인해요'; }
    $('rw-admin').hidden=!d.admin;
  }
  /* 지난번에 본 뒤로 바뀐 것 (이 기기 기준) */
  function news(d){
    var box=$('rw-news'), seen=0; box.textContent=''; box.hidden=true;
    try{ seen=+localStorage.getItem('hz_rw_seen')||0; }catch(e){}
    var now=Math.floor(Date.now()/1000), items=[];
    if(seen){
      d.rows.forEach(function(r){
        if(r.createdAt>seen && r.status==='pending') items.push([r.createdAt,'🛒 새 구매가 잡혔어요 · '+r.name+' · 적립 예정 '+won(r.points)+'P']);
        if(r.confirmedAt>seen && r.status==='done') items.push([r.confirmedAt,'✅ 적립 완료 · '+r.name+' · '+won(r.points)+'P']);
      });
      d.cashouts.forEach(function(c){
        if(c.done_at>seen && c.status==='paid') items.push([c.done_at,'💸 '+won(c.net!=null?c.net:c.amount)+'원을 입금했어요']);
        if(c.done_at>seen && c.status==='rejected') items.push([c.done_at,'↩️ 현금 교환이 반려됐어요 · '+(c.reason||'')+' · 포인트는 돌려드렸어요']);
      });
      d.log.forEach(function(l){
        if(l.at>seen && l.kind==='expire') items.push([l.at,'⏳ '+won(-l.amount)+'P가 유효기간이 지나 사라졌어요']);
        if(l.at>seen && l.kind==='adjust') items.push([l.at,'🛠️ 포인트 조정 '+(l.amount>0?'+':'−')+won(Math.abs(l.amount))+'P · '+(l.memo||'')]);
      });
    }
    items.sort(function(a,b){ return b[0]-a[0]; }).slice(0,6).forEach(function(it){ box.appendChild(el('li',null,it[1])); });
    box.hidden=!box.children.length;
    try{ localStorage.setItem('hz_rw_seen', String(now)); }catch(e){}
  }
  $('rw-agree').addEventListener('submit',function(e){ e.preventDefault(); var f=e.target, s=load()||{};
    fetch(API+'/me/agree',{method:'POST',headers:{Authorization:'Bearer '+(s.token||''),'Content-Type':'application/json'},
      body:JSON.stringify({ver:f.dataset.ver, terms:f.terms.checked, privacy:f.privacy.checked})})
      .then(function(r){ return r.json().then(function(j){ if(!r.ok) throw new Error(j.error||''); }); })
      .then(function(){ note('✅ 동의했어요. 이제 핫딜로 사면 포인트가 쌓여요.'); me(); })
      .catch(function(err){ alert(err.message||'잠시 뒤 다시 눌러 주세요.'); });
  });
  function me(){
    var s=load(); if(!s||!s.token){ show('rw-login'); return; }
    fetch(API+'/me',{headers:{Authorization:'Bearer '+s.token}}).then(function(r){
      if(r.status===401){ save(null); show('rw-login'); return; }
      return r.json().then(function(d){
        if(d.needTerms){ delete s.sid; s.nick=d.nick; save(s); $('rw-agree').dataset.ver=d.termsVer; $('rw-terms-nick').textContent=d.nick+' 님, 반가워요!'; show('rw-terms'); return; }
        s.sid=d.subId; s.nick=d.nick; save(s); render(d); show('rw-me'); });
    }).catch(fail);
  }
  function fail(){ $('rw-off-t').textContent='지금 적립 내역을 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.'; show('rw-off'); }
  function post(path,data){ var s=load()||{}; return fetch(API+path,{method:'POST',
    headers:{Authorization:'Bearer '+(s.token||''),'Content-Type':'application/json'}, body:JSON.stringify(data||{})}); }
  $('rw-cash').addEventListener('submit',function(e){ e.preventDefault(); var f=e.target, b=$('rw-cash-go');
    if(!confirm('모인 포인트 전부를 '+f.bank.value+' 계좌('+f.holder.value+')로 받을게요. 신청할까요?')) return;
    b.disabled=true;
    post('/me/cashout',{holder:f.holder.value, bank:f.bank.value, account:f.account.value, agree:f.agree.checked,
      rrn1:f.rrn1.value, rrn2:f.rrn2.value, agreeRrn:f.agreeRrn.checked}).then(function(r){
      return r.json().then(function(d){ if(!r.ok) throw new Error(d.error||'신청하지 못했어요.');
        f.reset(); note('💸 '+won(d.amount)+'원 현금 교환을 신청했어요. 확인 후 계좌로 보내 드릴게요.'); window.scrollTo(0,0); me(); });
    }).catch(function(err){ alert(err.message||'신청하지 못했어요. 잠시 뒤 다시 눌러 주세요.'); }).then(function(){ b.disabled=false; });
  });
  $('rw-logout').addEventListener('click',function(){ post('/me/logout').then(null,function(){}).then(function(){ save(null); show('rw-login'); }); });
  $('rw-delete').addEventListener('click',function(){
    if(!confirm('탈퇴하면 포인트와 적립 내역이 모두 지워지고 되돌릴 수 없어요.\\n정말 탈퇴할까요?')) return;
    post('/me/delete').then(function(r){ return r.json().then(function(d){ if(!r.ok) throw new Error(d.error||''); }); })
      .then(function(){ save(null); alert('탈퇴했어요. 그동안 이용해 주셔서 감사합니다.'); show('rw-login'); })
      .catch(function(err){ alert(err.message||'탈퇴 처리가 안 됐어요. 잠시 뒤 다시 눌러 주세요.'); });
  });
  fetch(API+'/rw/status').then(function(r){ return r.json(); }).then(function(st){ if(st.on) me(); else show('rw-off'); }).catch(fail);
})();
</script>""".replace("__API__", API)

BANK_OPTS = "".join(f'<option value="{b}">{b}</option>' for b in BANKS)
MY_BODY = f"""
  <div class="hd-notice" id="rw-msg" role="status" hidden></div>

  <section id="rw-wait"><p class="rw-sync">불러오는 중…</p></section>

  <section id="rw-off" hidden>
    <div class="hd-notice" id="rw-off-t">포인트 적립 기능을 준비하고 있어요. 조금만 기다려 주세요.</div>
  </section>

  <section id="rw-login" hidden>
    <div class="card">
      <div class="what">혜택존 핫딜로 사면 포인트가 쌓이고, 1만 포인트부터 현금으로 받아요</div>
      <ol class="rw-steps">
        <li>카카오로 로그인해요 (처음 한 번)</li>
        <li>로그인한 휴대폰에서 혜택존 핫딜·검색의 「구매하러 가기」를 눌러요</li>
        <li>24시간 안에 쿠팡에서 결제하면, 다음 날 오후쯤 여기에 <b>적립 예정</b>으로 나타나요</li>
      </ol>
      <a class="rw-kakao" href="{API}/auth/kakao?back=my">{KAKAO_ICON}카카오로 시작하기</a>
      <p class="rw-fine">카카오 회원번호와 닉네임만 받아 포인트 관리에만 씁니다 · <a href="privacy.html">개인정보 처리방침</a></p>
    </div>
  </section>

  <section id="rw-terms" hidden>
    <form class="card rw-agree" id="rw-agree">
      <div class="what" id="rw-terms-nick"></div>
      <p>포인트 적립을 시작하기 전에 처음 한 번만 동의해 주세요.</p>
      <label class="rw-check"><input type="checkbox" name="terms" required> <span>[필수] <a href="terms.html" target="_blank">포인트 이용약관</a>에 동의해요</span></label>
      <label class="rw-check"><input type="checkbox" name="privacy" required> <span>[필수] <a href="privacy.html" target="_blank">개인정보 수집·이용</a>(카카오 회원번호·닉네임, 적립 구매 기록)에 동의해요</span></label>
      <button type="submit" class="rw-go">동의하고 시작하기</button>
      <p class="rw-fine">동의하지 않으면 적립되지 않아요. 언제든 「탈퇴하기」로 모든 정보를 지울 수 있어요.</p>
    </form>
  </section>

  <section id="rw-me" hidden>
    <h2 class="rw-hello" id="rw-nick"></h2>
    <ul class="rw-news" id="rw-news" hidden aria-label="새 소식"></ul>
    <div class="rw-sum">
      <div class="rw-tile done"><small>쓸 수 있는 포인트</small><b id="rw-bal">0P</b><span>적립 완료된 포인트 (1P = 1원)</span></div>
      <div class="rw-tile pend"><small>적립 예정</small><b id="rw-pend">0P</b><span>구매한 달의 다음 달 25일에 확정</span></div>
    </div>
    <p class="rw-sync" id="rw-totals"></p>
    <p class="rw-soon" id="rw-soon" hidden></p>

    <h3 class="rw-h3">💸 현금으로 받기</h3>
    <div id="rw-cash-box"></div>
    <form class="rw-form" id="rw-cash" hidden autocomplete="off">
      <label>예금주<input name="holder" required maxlength="20" placeholder="예: 홍길동"></label>
      <label>은행<select name="bank" required><option value="">은행을 골라 주세요</option>{BANK_OPTS}</select></label>
      <label>계좌번호<input name="account" required inputmode="numeric" maxlength="20" placeholder="숫자만 (- 없이)"></label>
      <label class="rw-check"><input type="checkbox" name="agree" required> 현금 입금을 위해 예금주·은행·계좌번호를 받는 데 동의해요.
        암호화해 보관하고, 입금 기록은 세법에 따라 5년 뒤 지워요.</label>
      <fieldset class="rw-rrn" id="rw-rrn" hidden>
        <legend>주민등록번호 <small>세금 신고용</small></legend>
        <div class="rw-rrn-row"><input name="rrn1" inputmode="numeric" maxlength="6" placeholder="앞 6자리" autocomplete="off" aria-label="주민등록번호 앞 6자리">
          <span aria-hidden="true">−</span><input name="rrn2" type="password" inputmode="numeric" maxlength="7" placeholder="뒤 7자리" autocomplete="off" aria-label="주민등록번호 뒤 7자리"></div>
        <p>포인트를 현금으로 드리면 회사가 세금 신고(원천징수·지급명세서 제출)를 해야 해서 소득세법에 따라 받아요.
          암호화해 보관하고 관리자만 세금 신고에 씁니다. 신고 서류 보관 기간(5년)이 지나면 지워요.</p>
        <label class="rw-check"><input type="checkbox" name="agreeRrn"> 세금 신고를 위한 주민등록번호 수집·이용에 동의해요.</label>
      </fieldset>
      <p class="rw-tax" id="rw-tax" hidden></p>
      <button type="submit" class="rw-go" id="rw-cash-go">현금으로 받기</button>
    </form>

    <h3 class="rw-h3">적립 내역</h3>
    <div id="rw-list"></div>
    <div class="rw-empty" id="rw-empty" hidden>
      아직 적립 내역이 없어요.<br>로그인한 이 휴대폰에서 핫딜의 「구매하러 가기」를 눌러 사면 다음 날 오후쯤 여기에 나타나요.
      <a class="hd-more" href="hotdeal.html">🔥 핫딜 상품 보러 가기 →</a>
    </div>
    <h3 class="rw-h3" id="rw-use-h" hidden>포인트 사용·변동</h3>
    <div id="rw-use"></div>
    <p class="rw-sync" id="rw-sync"></p>

    <h3 class="rw-h3">적립 규정</h3>
    <ul class="rw-rules" id="rw-rules"></ul>
    <div class="rw-acts"><a class="rw-adm" id="rw-admin" href="admin.html" hidden>관리자 화면</a>
      <button type="button" id="rw-logout">로그아웃</button><button type="button" id="rw-delete">탈퇴하기</button></div>
  </section>
{MY_SCRIPT}
"""

# ───────────────────────── 관리자 ─────────────────────────
ADMIN_CSS = """<style>
  .wrap{max-width:1120px}
  .ad-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px}
  .ad-tabs button{font-family:inherit;font-size:16px;font-weight:800;padding:9px 14px;border-radius:12px;cursor:pointer;
    border:2px solid var(--line);background:var(--card);color:var(--txt)}
  .ad-tabs button[aria-selected="true"]{background:var(--txt);border-color:var(--txt);color:var(--bg)}
  .ad-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 14px}
  .ad-k{border:2px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--card)}
  .ad-k small{display:block;font-size:14px;font-weight:800;color:var(--sub)}
  .ad-k b{display:block;font-size:22px;font-weight:900;font-variant-numeric:tabular-nums;white-space:nowrap}
  .ad-k span{font-size:13px;color:var(--mut)}
  .ad-k.warn{border-color:#f59e0b}
  .ad-h{font-size:18px;font-weight:900;margin:20px 0 8px}
  .ad-scroll{overflow-x:auto;border:2px solid var(--line);border-radius:12px}
  .ad-t{width:100%;border-collapse:collapse;font-size:15px;font-variant-numeric:tabular-nums}
  .ad-t th,.ad-t td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;vertical-align:top}
  .ad-t th{font-size:13px;color:var(--sub);background:var(--bg2)}
  .ad-t td.r,.ad-t th.r{text-align:right}
  .ad-t tr.click{cursor:pointer}
  .ad-t tr.click:hover td{background:var(--bg2)}
  .ad-btn{font-family:inherit;font-size:14px;font-weight:800;padding:6px 10px;border-radius:9px;cursor:pointer;
    border:2px solid var(--line);background:var(--card);color:var(--txt);margin:0 4px 4px 0}
  .ad-btn.pri{background:#15803d;border-color:#15803d;color:#fff}
  .ad-btn.bad{color:#b91c1c;border-color:#fca5a5}
  .ad-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
  .ad-row input,.ad-row select,.ad-row textarea{font-family:inherit;font-size:16px;padding:8px 10px;border:2px solid var(--line);
    border-radius:10px;background:var(--bg);color:var(--txt)}
  .ad-row textarea{width:100%;min-height:70px}
  .ad-card{border:2px solid var(--line);border-radius:14px;padding:14px 16px;background:var(--card);margin:10px 0}
  .ad-muted{font-size:14px;color:var(--mut)}
  .ad-ok{color:#15803d;font-weight:800}.ad-no{color:#b91c1c;font-weight:800}
  .ad-reveal{font-size:17px;font-weight:800;background:var(--rw-bar);border:2px solid var(--rw-bar-line);border-radius:10px;padding:8px 12px;margin-top:6px}
</style>"""

ADMIN_SCRIPT = """<script>
(() => {
  const API = '__API__', KEY = 'hz_rw', $ = id => document.getElementById(id);
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } };
  const won = n => Number(n || 0).toLocaleString('ko-KR');
  const ts = t => { if (!t) return '—'; const d = new Date(t * 1000); return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`; };
  const md = d => `${+d.slice(4,6)}/${+d.slice(6,8)}`;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const btn = (text, cls, fn) => { const b = el('button', 'ad-btn ' + (cls || ''), text); b.type = 'button'; b.addEventListener('click', fn); return b; };
  const ST = { pending: '적립 예정', done: '적립 완료', canceled: '적립 취소', requested: '입금 대기', paid: '지급 완료', rejected: '반려', ok: '정상', blocked: '정지' };
  async function api(path, data) {
    const s = load() || {};
    const r = await fetch(API + path, data === undefined ? { headers: { Authorization: 'Bearer ' + (s.token || '') } }
      : { method: 'POST', headers: { Authorization: 'Bearer ' + (s.token || ''), 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const j = await r.json().catch(() => ({}));
    if (r.status === 401) { gate(); throw new Error('login'); }
    if (!r.ok) throw new Error(j.error || '처리하지 못했어요');
    return j;
  }
  function table(cols, rows, onClick) {
    const wrap = el('div', 'ad-scroll'), t = el('table', 'ad-t'), hr = el('tr');
    cols.forEach(c => { const th = el('th', c.r ? 'r' : '', c.h); hr.appendChild(th); });
    const th = el('thead'); th.appendChild(hr); t.appendChild(th);
    const tb = el('tbody');
    if (!rows.length) { const tr = el('tr'), td = el('td', 'ad-muted', '없음'); td.colSpan = cols.length; tr.appendChild(td); tb.appendChild(tr); }
    rows.forEach(row => { const tr = el('tr', onClick ? 'click' : '');
      cols.forEach(c => { const td = el('td', c.r ? 'r' : ''); const v = c.v(row); if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? '' : v; tr.appendChild(td); });
      if (onClick) tr.addEventListener('click', e => { if (e.target.tagName !== 'BUTTON') onClick(row); });
      tb.appendChild(tr); });
    t.appendChild(tb); wrap.appendChild(t); return wrap;
  }
  const kpi = (label, value, sub, warn) => { const k = el('div', 'ad-k' + (warn ? ' warn' : '')); k.appendChild(el('small', null, label));
    k.appendChild(el('b', null, value)); if (sub) k.appendChild(el('span', null, sub)); return k; };

  function gate() { $('ad-app').hidden = true; $('ad-gate').hidden = false; }
  const tabs = { dash, cash, members, settings };
  function go(name) { document.querySelectorAll('.ad-tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.t === name));
    const box = $('ad-body'); box.textContent = ''; tabs[name](box).catch(e => { if (e.message !== 'login') box.appendChild(el('p', 'ad-no', e.message)); }); }
  document.querySelectorAll('.ad-tabs button').forEach(b => b.addEventListener('click', () => go(b.dataset.t)));

  async function dash(box) {
    const d = await api('/admin/overview');
    $('ad-who').textContent = d.admin + ' 님';
    $('ad-cash-n').textContent = d.cashPending.n ? ` ${d.cashPending.n}` : '';
    const g = el('div', 'ad-grid');
    g.appendChild(kpi('현금 교환 대기', `${d.cashPending.n}건`, `${won(d.cashPending.amt)}원`, d.cashPending.n > 0));
    g.appendChild(kpi('회원', `${won(d.members.n)}명`, `오늘 +${d.members.today || 0} · 7일 +${d.members.week || 0}`));
    g.appendChild(kpi('적립 예정 합계', `${won(d.orders.pending)}P`, '다음 달 25일 확정 예정'));
    g.appendChild(kpi('회원 포인트 잔액', `${won(d.liability)}P`, '지급해야 할 수 있는 금액'));
    g.appendChild(kpi('이번 달 지급', `${won(d.paidThisMonth.amt)}원`, `${d.paidThisMonth.n}건`));
    g.appendChild(kpi('소멸된 포인트', `${won(d.expired)}P`, `유효기간 ${d.settings.expire_days}일`));
    const rate = kpi('적립 비율', `수수료의 ${Math.round(d.settings.share * 1000) / 10}%`, `구매금액의 약 ${Math.round(d.settings.share * 30) / 10}%`);
    rate.appendChild(btn('바꾸기', '', () => go('settings'))); g.appendChild(rate);
    box.appendChild(g);
    box.appendChild(el('h3', 'ad-h', '이번 달 회원 구매 (쿠팡 기준)'));
    const g2 = el('div', 'ad-grid');
    const ratio = d.orders.m_comm ? Math.round(d.orders.m_points / d.orders.m_comm * 100) : 0;
    g2.appendChild(kpi('구매금액', `${won(d.orders.m_gmv)}원`));
    g2.appendChild(kpi('우리 수수료', `${won(d.orders.m_comm)}원`));
    g2.appendChild(kpi('회원 적립', `${won(d.orders.m_points)}P`, `수수료의 ${ratio}%`));
    g2.appendChild(kpi('남는 수수료', `${won(d.orders.m_comm - d.orders.m_points)}원`));
    box.appendChild(g2);
    if (d.site) { box.appendChild(el('h3', 'ad-h', '오늘 사이트'));
      const g3 = el('div', 'ad-grid');
      g3.appendChild(kpi('방문', won(d.site.visit || 0))); g3.appendChild(kpi('구매 버튼', won(d.site.buy || 0))); g3.appendChild(kpi('검색', won(d.site.search || 0)));
      box.appendChild(g3); }
    box.appendChild(el('h3', 'ad-h', '연결 상태 · 쿠팡 동기화 (매일 17시)'));
    const st = el('div', 'ad-row');
    [['카카오 로그인', d.kakaoOn], ['쿠팡 키', d.coupangOn], ['계좌 암호화 키', d.piiOn]].forEach(([n, on]) => st.appendChild(el('span', on ? 'ad-ok' : 'ad-no', `${on ? '✅' : '❌'} ${n}`)));
    st.appendChild(btn('지금 쿠팡 읽기', '', async e => { e.target.disabled = true; try { const r = await api('/admin/sync', {}); alert((r.ok ? '완료: ' : '실패: ') + r.note); go('dash'); } catch (err) { alert(err.message); } }));
    box.appendChild(st);
    box.appendChild(table([{ h: '시각', v: r => ts(r.at) }, { h: '결과', v: r => r.ok ? '성공' : '실패' }, { h: '내용', v: r => r.note }], d.sync));
  }

  async function cash(box) {
    const row = el('div', 'ad-row'), sel = el('select');
    [['requested', '입금 대기'], ['paid', '지급 완료'], ['rejected', '반려'], ['all', '전체']].forEach(([v, t]) => { const o = el('option', null, t); o.value = v; sel.appendChild(o); });
    sel.value = cash.st || 'requested'; sel.addEventListener('change', () => { cash.st = sel.value; go('cash'); });
    row.appendChild(el('b', null, '현금 교환 신청')); row.appendChild(sel); box.appendChild(row);
    const ex = el('div', 'ad-row'), mon = el('input'); mon.type = 'month'; mon.value = new Date().toISOString().slice(0, 7);
    ex.appendChild(el('span', 'ad-muted', '세금 신고용')); ex.appendChild(mon);
    ex.appendChild(btn('지급 내역 엑셀(CSV) 받기', '', async () => {
      if (!confirm(mon.value + ' 지급 내역을 받을까요? 계좌번호·주민번호가 들어 있어 기록에 남고, 파일은 안전한 곳에 보관해 주세요.')) return;
      const s = load() || {}; const r = await fetch(API + '/admin/export?month=' + mon.value, { headers: { Authorization: 'Bearer ' + (s.token || '') } });
      if (!r.ok) { alert('받지 못했어요'); return; }
      const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = `혜택존-지급내역-${mon.value}.csv`;
      document.body.appendChild(a); a.click(); a.remove(); }));
    box.appendChild(ex);
    box.appendChild(el('p', 'ad-muted', '계좌로 직접 보낸 뒤 「지급 완료」를 눌러 주세요. 반려하면 포인트가 회원에게 돌아갑니다. 계좌·주민번호 보기는 기록에 남고, 주민번호는 세금 신고에만 쓰세요.'));
    const d = await api('/admin/cashouts?status=' + sel.value);
    box.appendChild(table([
      { h: '#', v: c => c.id }, { h: '신청', v: c => ts(c.requested_at) }, { h: '회원', v: c => `${c.nick || '(탈퇴)'} #${c.member_id}` },
      { h: '교환', r: 1, v: c => won(c.amount) + 'P' }, { h: '세금', r: 1, v: c => c.tax ? won(c.tax) + '원' : '—' },
      { h: '보낼 돈', r: 1, v: c => won(c.net != null ? c.net : c.amount) + '원' }, { h: '계좌', v: c => `${c.bank} ${c.acct_mask}` },
      { h: '상태', v: c => ST[c.status] + (c.reason ? ` · ${c.reason}` : '') + (c.done_at ? ` (${ts(c.done_at)})` : '') },
      { h: '처리', v: c => { const w = el('div');
        if (c.status === 'requested') {
          w.appendChild(btn('계좌 보기', '', async () => { try { const i = await api('/admin/cashout/reveal', { id: c.id });
            const r = el('div', 'ad-reveal', `${i.holder} · ${i.bank} ${i.account}` + (i.rrn ? ` · 주민번호 ${i.rrn}` : '')); w.appendChild(r); } catch (e) { alert(e.message); } }));
          w.appendChild(btn('지급 완료', 'pri', async () => { if (!confirm(`${c.nick}님에게 ${won(c.net != null ? c.net : c.amount)}원을 보내셨나요?`)) return;
            try { await api('/admin/cashout/done', { id: c.id }); go('cash'); } catch (e) { alert(e.message); } }));
          w.appendChild(btn('반려', 'bad', async () => { const reason = prompt('반려 사유 (회원에게 보입니다)'); if (!reason) return;
            try { await api('/admin/cashout/reject', { id: c.id, reason }); go('cash'); } catch (e) { alert(e.message); } }));
        } else if (c.status === 'paid') { w.appendChild(btn('계좌 보기', '', async () => { try { const i = await api('/admin/cashout/reveal', { id: c.id });
            w.appendChild(el('div', 'ad-reveal', `${i.holder} · ${i.bank} ${i.account}` + (i.rrn ? ` · 주민번호 ${i.rrn}` : ''))); } catch (e) { alert(e.message); } })); }
        return w; } },
    ], d.cashouts));
  }

  async function members(box) {
    const row = el('div', 'ad-row'), q = el('input'); q.placeholder = '닉네임 · 이름표 · 번호'; q.value = members.q || '';
    q.addEventListener('keydown', e => { if (e.key === 'Enter') { members.q = q.value.trim(); go('members'); } });
    row.appendChild(q); row.appendChild(btn('검색', '', () => { members.q = q.value.trim(); go('members'); })); box.appendChild(row);
    const d = await api('/admin/members' + (members.q ? '?q=' + encodeURIComponent(members.q) : ''));
    box.appendChild(el('p', 'ad-muted', `${d.members.length}명 · 줄을 누르면 상세`));
    box.appendChild(table([
      { h: '#', v: m => m.id }, { h: '닉네임', v: m => m.nick + (m.is_admin ? ' ⭐' : '') }, { h: '이름표', v: m => m.sub_id },
      { h: '가입', v: m => ts(m.created) }, { h: '최근 로그인', v: m => ts(m.last_login) }, { h: '주문', r: 1, v: m => m.orders },
      { h: '적립 예정', r: 1, v: m => won(m.pending) }, { h: '잔액', r: 1, v: m => won(m.balance) }, { h: '상태', v: m => ST[m.status] },
    ], d.members, m => detail(m.id)));
  }

  async function detail(id) {
    const box = $('ad-body'); box.textContent = '';
    box.appendChild(btn('← 회원 목록', '', () => go('members')));
    const d = await api('/admin/member?id=' + id), m = d.member;
    const c = el('div', 'ad-card');
    c.appendChild(el('div', 'ad-h', `#${m.id} ${m.nick} ${m.is_admin ? '⭐ 관리자' : ''}`));
    c.appendChild(el('div', 'ad-muted', `이름표 ${m.sub_id} · 가입 ${ts(m.created)} · 최근 로그인 ${ts(m.last_login)} · 상태 ${ST[m.status]}`));
    const g = el('div', 'ad-grid');
    g.appendChild(kpi('잔액', won(d.sums.balance) + 'P')); g.appendChild(kpi('적립 예정', won(d.sums.pending) + 'P'));
    g.appendChild(kpi('적립 완료 누적', won(d.sums.earned) + 'P')); g.appendChild(kpi('현금 교환', won(d.sums.used) + '원'));
    c.appendChild(g);
    const r1 = el('div', 'ad-row');
    r1.appendChild(btn(m.status === 'blocked' ? '정지 해제' : '이용 정지', m.status === 'blocked' ? '' : 'bad', async () => {
      if (!confirm(m.status === 'blocked' ? '정지를 풀까요?' : '이 회원의 현금 교환을 막을까요? (적립 내역은 유지)')) return;
      await api('/admin/member/update', { id, status: m.status === 'blocked' ? 'ok' : 'blocked' }); detail(id); }));
    c.appendChild(r1);
    const r2 = el('div', 'ad-row'), memo = el('textarea'); memo.value = m.memo || ''; memo.placeholder = '관리자 메모 (회원에게 안 보임)';
    r2.appendChild(memo); r2.appendChild(btn('메모 저장', '', async () => { await api('/admin/member/update', { id, memo: memo.value }); alert('저장했어요'); }));
    c.appendChild(r2);
    const r3 = el('div', 'ad-row'), amt = el('input'), why = el('input');
    amt.type = 'number'; amt.placeholder = '포인트 (+지급 / −차감)'; why.placeholder = '사유 (회원에게 보입니다)'; why.style.flex = '1';
    r3.appendChild(amt); r3.appendChild(why);
    r3.appendChild(btn('포인트 조정', '', async () => { try { await api('/admin/adjust', { id, amount: Number(amt.value), memo: why.value }); detail(id); } catch (e) { alert(e.message); } }));
    c.appendChild(r3);
    box.appendChild(c);
    box.appendChild(el('h3', 'ad-h', '쿠팡 주문'));
    box.appendChild(table([{ h: '구매일', v: o => md(o.day) }, { h: '상품', v: o => o.name }, { h: '금액', r: 1, v: o => won(o.gmv) },
      { h: '취소', r: 1, v: o => o.cancel ? won(o.cancel) : '' }, { h: '수수료', r: 1, v: o => won(o.commission) },
      { h: '포인트', r: 1, v: o => won(o.points) }, { h: '상태', v: o => ST[o.status] + (o.status === 'pending' ? ` (${o.confirmOn.slice(5)} 확정)` : '') }], d.rows));
    box.appendChild(el('h3', 'ad-h', '포인트 변동'));
    box.appendChild(table([{ h: '시각', v: l => ts(l.at) }, { h: '종류', v: l => ({ cashout: '현금 교환', refund: '반려 복구', adjust: '조정', expire: '소멸' })[l.kind] || l.kind },
      { h: '포인트', r: 1, v: l => (l.amount > 0 ? '+' : '') + won(l.amount) }, { h: '내용', v: l => l.memo || '' }], d.log));
  }

  async function settings(box) {
    const s = await api('/admin/settings'), c = el('div', 'ad-card');
    c.appendChild(el('div', 'ad-h', '적립 설정'));
    c.appendChild(el('p', 'ad-muted', '적립 비율은 바꾼 뒤 새로 잡히는 주문부터 적용돼요. 이미 잡힌 주문은 그때 비율 그대로입니다.'));
    const f = [['share', '적립 비율 (쿠팡 수수료의 %)', Math.round(s.share * 1000) / 10], ['min_cashout', '최소 현금 교환 (P)', s.min_cashout], ['expire_days', '포인트 유효기간 (일)', s.expire_days],
      ['withholding_rate', '원천징수율 (%) — 0이면 안 뗌', Math.round(s.withholding_rate * 1000) / 10], ['withholding_free_upto', '이 금액(원) 이하 교환은 안 뗌', s.withholding_free_upto]];
    const inputs = {};
    f.forEach(([k, label, v]) => { const r = el('label', 'ad-row'); r.appendChild(el('span', null, label)); const i = el('input'); i.type = 'number'; i.value = v; i.step = 'any'; inputs[k] = i; r.appendChild(i); c.appendChild(r); });
    const quick = el('div', 'ad-row'); quick.appendChild(el('span', 'ad-muted', '빠른 선택'));
    [10, 20, 30, 50].forEach(n => quick.appendChild(btn(`${n}%`, '', () => { inputs.share.value = n; preview(); })));
    c.insertBefore(quick, c.children[3]);
    const pv = el('div', 'ad-reveal'); c.appendChild(pv);
    function preview() {
      const r = Number(inputs.share.value) / 100, min = Number(inputs.min_cashout.value) || 0;
      pv.textContent = r > 0 ? `수수료 3% 상품을 10만원 사면 회원 적립 약 ${won(Math.floor(100000 * 0.03 * r))}P · ${won(min)}P를 모으려면 약 ${won(Math.ceil(min / (0.03 * r)))}원 구매` : '비율을 넣어 주세요';
    }
    inputs.share.addEventListener('input', preview); inputs.min_cashout.addEventListener('input', preview); preview();
    const rr = el('label', 'ad-row'), cb = el('input'); cb.type = 'checkbox'; cb.checked = !!s.collect_rrn;
    rr.appendChild(cb); rr.appendChild(el('span', null, '현금 교환 때 주민등록번호 받기 (세금 신고·원천징수용)')); c.appendChild(rr);
    c.appendChild(el('p', 'ad-muted', '원천징수는 세무사 확인 후 켜세요. 예: 기타소득이면 22%(소득세 20% + 지방소득세 2%), 건당 5만원 이하는 과세하지 않는 경우가 많아요. 바꾸면 그 뒤 신청부터 적용돼요.'));
    c.appendChild(btn('저장', 'pri', async () => { try { await api('/admin/settings', { share: Number(inputs.share.value) / 100,
      min_cashout: Number(inputs.min_cashout.value), expire_days: Number(inputs.expire_days.value), collect_rrn: cb.checked,
      withholding_rate: Number(inputs.withholding_rate.value) / 100, withholding_free_upto: Number(inputs.withholding_free_upto.value) }); alert('저장했어요'); go('settings'); } catch (e) { alert(e.message); } }));
    box.appendChild(c);
    box.appendChild(el('h3', 'ad-h', '관리자 작업 기록'));
    const a = await api('/admin/audit');
    box.appendChild(table([{ h: '시각', v: r => ts(r.at) }, { h: '누가', v: r => r.admin }, { h: '무엇을', v: r => r.action },
      { h: '대상', v: r => r.target || '' }, { h: '내용', v: r => r.detail || '' }], a.audit));
  }

  const s = load();
  if (!s || !s.token) gate(); else { $('ad-app').hidden = false; go('dash'); }
})();
</script>""".replace("__API__", API)

ADMIN_BODY = f"""{ADMIN_CSS}
  <section id="ad-gate" hidden>
    <div class="card">
      <div class="what">관리자만 볼 수 있어요</div>
      <p class="rw-fine">관리자로 지정된 카카오 계정으로 로그인해 주세요. 로그인 후 이 화면으로 돌아옵니다.</p>
      <a class="rw-kakao" href="{API}/auth/kakao?back=admin">{KAKAO_ICON}카카오로 로그인</a>
    </div>
  </section>
  <section id="ad-app" hidden>
    <div class="ad-row"><b id="ad-who"></b></div>
    <nav class="ad-tabs" role="tablist">
      <button type="button" data-t="dash" aria-selected="true">대시보드</button>
      <button type="button" data-t="cash">현금 교환<span id="ad-cash-n"></span></button>
      <button type="button" data-t="members">회원</button>
      <button type="button" data-t="settings">설정·기록</button>
    </nav>
    <div id="ad-body"></div>
  </section>
<script>(function(){{ var h=location.hash.match(/login=([A-Za-z0-9_-]{{20,}})/);
  if(h){{ try{{ localStorage.setItem('hz_rw', JSON.stringify({{token:h[1]}})); }}catch(e){{}} history.replaceState(null,'',location.pathname); }} }})();</script>
{ADMIN_SCRIPT}
"""

# ───────────────────────── 개인정보 처리방침 ─────────────────────────
PRIVACY_BODY = f"""
  <div class="card rw-doc">
    <p>HUBRIZ 돌봄플러스 혜택존(이하 "혜택존")은 포인트 적립과 현금 교환을 위해 아래와 같이 필요한 개인정보만 처리합니다.</p>
    <h3>1. 처리하는 정보</h3>
    <ul>
      <li>카카오 로그인 시: 카카오 회원번호, 닉네임</li>
      <li>적립을 위해 쿠팡 파트너스에서 받는 정보: 회원 전용 링크로 산 상품의 구매일·상품명·수량·금액, 취소·반품 여부
        (쿠팡은 이름·연락처·주소 등 구매자 정보를 주지 않습니다)</li>
      <li>현금 교환 신청 시: 예금주, 은행, 계좌번호, 주민등록번호(세금 신고용)</li>
    </ul>
    <h3>2. 쓰는 곳</h3>
    <ul><li>회원 확인, 포인트 적립 예정·완료 내역 표시와 관리</li><li>현금 교환 신청 확인과 계좌 입금</li>
        <li>현금 지급에 따른 세금 신고(원천징수, 지급명세서 제출) — 주민등록번호는 소득세법 제145조·제164조 등 법령에 근거해 이 목적으로만 처리합니다.</li></ul>
    <h3>3. 보관 기간</h3>
    <ul><li>회원 정보·적립 내역: 탈퇴할 때까지. 「내 적립」에서 탈퇴하면 바로 지웁니다.</li>
        <li>현금 교환 계좌 정보·주민등록번호: 암호화해 보관하며, 반려되면 바로 지우고, 입금한 기록은 국세기본법상 증빙 보관을 위해 입금 후 5년 동안 보관한 뒤 지웁니다.</li>
        <li>로그인 유지 정보는 90일이 지나면 자동으로 지워집니다.</li></ul>
    <h3>4. 다른 곳에 주는지</h3>
    <ul><li>제3자에게 제공하지 않습니다. 법령에 따라 요구되는 경우는 예외로 합니다.</li></ul>
    <h3>5. 맡기는 곳 (처리 위탁)</h3>
    <ul><li>Cloudflare, Inc. — 서버·데이터 저장</li><li>㈜카카오 — 로그인</li></ul>
    <h3>6. 이용자의 권리</h3>
    <ul><li>언제든 「내 적립」에서 내역을 확인하고 탈퇴(삭제)할 수 있습니다. 현금 교환이 처리 중일 때는 입금 후 탈퇴할 수 있습니다.</li></ul>
    <h3>7. 개인정보 보호책임자</h3>
    <ul><li>{OFFICER}</li></ul>
    <p class="rw-fine">시행일: 2026년 9월 12일</p>
  </div>
"""


TERMS_BODY = """
  <div class="card rw-doc">
    <p>이 약관은 HUBRIZ 돌봄플러스 혜택존(이하 "혜택존")의 포인트 적립과 현금 교환에 관한 약속입니다. 처음 로그인할 때 동의해 주셔야 적립이 시작됩니다.</p>
    <h3>제1조 (포인트가 쌓이는 방법)</h3>
    <ul><li>카카오로 로그인한 기기에서 혜택존의 쿠팡 링크(핫딜·검색의 「구매하러 가기」)를 누르고 24시간 안에 쿠팡에서 결제한 구매에 포인트가 쌓입니다.</li>
        <li>포인트는 그 구매로 혜택존이 쿠팡에서 받는 수수료에 적립 비율을 곱한 만큼입니다. 적립 비율은 「내 포인트 → 적립 규정」에 표시되며, 바뀌면 그 뒤 새로 확인되는 구매부터 적용하고 이미 확인된 구매에는 소급하지 않습니다.</li>
        <li>적립은 쿠팡 파트너스가 알려주는 구매 기록만을 기준으로 합니다. 쿠팡이 집계하지 않은 구매(로그인하지 않은 상태, 다른 사이트 링크, 쿠팡 정책상 제외되는 구매 등)는 적립되지 않습니다.</li></ul>
    <h3>제2조 (적립 예정과 적립 완료)</h3>
    <ul><li>구매가 확인되면 「적립 예정」으로 표시되고, 쿠팡이 취소·반품을 반영해 확정하는 구매한 달의 다음 달 25일에 「적립 완료」가 됩니다.</li>
        <li>취소·반품된 구매는 적립되지 않으며, 일부만 취소되면 남은 금액만큼 적립됩니다.</li></ul>
    <h3>제3조 (현금 교환)</h3>
    <ul><li>1포인트는 1원이며, 「내 포인트」에 표시된 최소 포인트 이상이 모이면 모인 포인트 전부를 본인 명의 계좌로 받을 수 있습니다.</li>
        <li>신청 후 확인을 거쳐 보통 7영업일 안에 입금합니다. 예금주가 회원 본인과 다르거나 정보가 틀리면 반려하고 포인트를 돌려드립니다.</li>
        <li>관련 법령에 따라 세금을 원천징수해야 하는 경우 세금을 뺀 금액을 입금하며, 세금 신고를 위해 주민등록번호를 받을 수 있습니다.</li></ul>
    <h3>제4조 (유효기간)</h3>
    <ul><li>적립 완료된 포인트는 적립 완료 후 「내 포인트」에 표시된 기간(현재 1년)이 지나면 사라집니다. 먼저 쌓인 포인트부터 쓴 것으로 봅니다.</li>
        <li>사라지기 30일 전부터 「내 포인트」에 안내합니다.</li></ul>
    <h3>제5조 (부정 이용)</h3>
    <ul><li>구매 조작, 비정상적인 반복 구매·취소, 다른 사람의 정보 사용 등 부정한 방법으로 쌓은 포인트는 회수하고 이용을 멈출 수 있습니다.</li></ul>
    <h3>제6조 (탈퇴)</h3>
    <ul><li>언제든 「내 포인트 → 탈퇴하기」로 탈퇴할 수 있으며, 남은 포인트와 적립 내역은 함께 사라집니다. 현금 교환이 처리 중이면 입금 후 탈퇴할 수 있습니다.</li></ul>
    <h3>제7조 (서비스 변경·종료)</h3>
    <ul><li>적립 규정이 바뀌면 사이트에 알립니다. 서비스를 끝낼 때는 30일 전에 알리고, 그동안 최소 교환 기준과 관계없이 남은 적립 완료 포인트를 현금으로 교환할 수 있게 합니다.</li></ul>
    <h3>제8조 (문의)</h3>
    <ul><li>개인정보 보호책임자: {OFFICER}</li></ul>
    <p class="rw-fine">시행일: 2026년 9월 12일 (약관 버전 2026-09-12)</p>
  </div>
"""


def build(index_src):
    """(my.html, privacy.html, admin.html, terms.html) 내용을 돌려준다."""
    my = _page(index_src, "내 적립 · 돌봄플러스 혜택존", "혜택존 핫딜로 사면 포인트가 쌓이고 1만 포인트부터 현금으로 받아요", "my.html",
               "🪙 내 <b>포인트</b>", "카카오로 로그인하고 혜택존 핫딜로 사면 포인트가 쌓여요. <b>1만 포인트부터 현금</b>으로 받을 수 있어요.", MY_BODY)
    pv = _page(index_src, "개인정보 처리방침 · 돌봄플러스 혜택존", "혜택존 포인트 적립 개인정보 처리방침", "privacy.html",
               "개인정보 <b>처리방침</b>", "포인트 적립과 현금 교환에 필요한 정보만 받습니다.", PRIVACY_BODY)
    ad = _page(index_src, "관리자 · 돌봄플러스 혜택존", "혜택존 관리자", "admin.html",
               "🛠️ <b>관리자</b>", "회원·포인트·현금 교환을 관리합니다.", ADMIN_BODY, noindex=True)
    tm = _page(index_src, "포인트 이용약관 · 돌봄플러스 혜택존", "혜택존 포인트 적립·현금 교환 이용약관", "terms.html",
               "포인트 <b>이용약관</b>", "포인트 적립과 현금 교환에 관한 약속입니다.", TERMS_BODY.replace("{OFFICER}", OFFICER))
    return my, pv, ad, tm
