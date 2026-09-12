// 카카오 로그인·포인트 적립 흐름을 키 없이 점검 — D1 은 node:sqlite(메모리), 카카오·쿠팡 응답은 가짜.
// 실행: node --no-warnings stats-worker/test/kakao-e2e.mjs   (Node 22.5 이상)
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import worker from '../src/index.js';

const db = new DatabaseSync(':memory:');
db.exec(readFileSync(new URL('../members.sql', import.meta.url), 'utf8'));
class Stmt { constructor(sql) { this.sql = sql; this.a = []; } bind(...a) { this.a = a; return this; }
  async first() { return db.prepare(this.sql).get(...this.a) ?? null; }
  async all() { return { results: db.prepare(this.sql).all(...this.a) }; }
  async run() { const r = db.prepare(this.sql).run(...this.a); return { meta: { changes: Number(r.changes) } }; }
  runSync() { return db.prepare(this.sql).run(...this.a); } }
const MEM = { prepare: s => new Stmt(s), async batch(list) { db.exec('BEGIN'); try { list.forEach(s => s.runSync()); db.exec('COMMIT'); } catch (e) { db.exec('ROLLBACK'); throw e; } } };
const env = { MEM, KAKAO_REST_KEY: 'rest-test', KAKAO_CLIENT_SECRET: 'secret-test', STATS_KEY: 'stats-test',
  PII_KEY: Buffer.alloc(32, 7).toString('base64'), COUPANG_ACCESS_KEY: 'a', COUPANG_SECRET_KEY: 'b', SITE_URL: 'https://hubrizjeon.github.io/hyetaekzone/' };
const ctx = { waitUntil() {} };
const W = 'https://hyetaekzone-stats.baglebagle.workers.dev';
const ORIGIN = { Origin: 'https://hubrizjeon.github.io' };

let kakaoUser = { id: 4242001, kakao_account: { profile: { nickname: '테스트대표' } } };
let coupang = { orders: [], cancels: [] };
const seen = [];
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.startsWith('https://kauth.kakao.com/oauth/token')) {
    const f = new URLSearchParams(init.body);
    seen.push(['token', f.get('client_id'), f.get('redirect_uri'), f.get('code'), f.get('client_secret')]);
    return Response.json(f.get('code') === 'good-code' ? { access_token: 'kakao-at' } : { error: 'invalid_grant' });
  }
  if (url.startsWith('https://kapi.kakao.com/v2/user/me')) {
    return Response.json(init.headers.Authorization === 'Bearer kakao-at' ? kakaoUser : {});
  }
  // 쿠팡처럼 큰 주문번호를 따옴표 없는 숫자 글자로 보냄
  const raw = d => JSON.stringify({ rCode: '0', data: d }).replace(/"orderId":"(\d+)"/g, '"orderId":$1');
  if (url.includes('/reports/orders')) return new Response(raw(coupang.orders));
  if (url.includes('/reports/cancels')) return new Response(raw(coupang.cancels));
  throw new Error('예상 못 한 호출 ' + url);
};
const call = (path, { method = 'GET', headers = {}, body } = {}) =>
  worker.fetch(new Request(W + path, { method, headers, body: body && JSON.stringify(body), redirect: 'manual' }), env, ctx);
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? '✅ ' : '❌ ') + msg); if (!cond) fails++; };

async function login(back = 'my', code = 'good-code') {
  const r1 = await call(`/auth/kakao?back=${back}`);
  const loc = new URL(r1.headers.get('Location')), cookie = r1.headers.get('Set-Cookie').split(';')[0];
  const r2 = await call(`/auth/kakao/callback?code=${code}&state=${loc.searchParams.get('state')}`, { headers: { Cookie: cookie } });
  return { r1, loc, cookie, r2, dest: r2.headers.get('Location') || '' };
}

// 1. 로그인 시작
const a = await login('admin');
ok(a.r1.status === 302 && a.loc.origin + a.loc.pathname === 'https://kauth.kakao.com/oauth/authorize', '로그인 시작 → 카카오 동의 화면으로 이동');
ok(a.loc.searchParams.get('client_id') === 'rest-test' && a.loc.searchParams.get('redirect_uri') === W + '/auth/kakao/callback', 'REST 키·Redirect URI 가 카카오에 등록할 주소와 같음');
ok(/^hz_state=[A-Za-z0-9_-]+\.admin$/.test(a.cookie) && /HttpOnly/.test(a.r1.headers.get('Set-Cookie')), '위조 방지 state 쿠키 (HttpOnly)');
// 2. 돌아오기
ok(a.dest.startsWith(env.SITE_URL + 'admin.html#login='), '로그인 성공 → 관리자 화면으로 돌아옴 (#login=토큰)');
ok(JSON.stringify(seen[0]) === JSON.stringify(['token', 'rest-test', W + '/auth/kakao/callback', 'good-code', 'secret-test']), '카카오 토큰 요청에 키·주소·코드·Client Secret 이 맞게 들어감');
const token = a.dest.split('#login=')[1];
// 3. 실패 경로
const bad = await call(`/auth/kakao/callback?code=good-code&state=WRONG`, { headers: { Cookie: a.cookie } });
ok(bad.headers.get('Location').endsWith('#rw=fail-state'), 'state 가 다르면 거절 (다른 사이트가 끼어드는 공격 방지)');
const cancel = await call(`/auth/kakao/callback?error=access_denied&state=x`, { headers: { Cookie: a.cookie } });
ok(cancel.headers.get('Location').endsWith('#rw=fail-cancel'), '카카오 동의 화면에서 취소 → 안내 문구');
const badCode = await login('my', 'bad-code');
ok(badCode.dest.endsWith('my.html#rw=fail-token'), '카카오가 토큰을 안 주면 → 실패 안내');
// 4. 내 정보
let me = await (await call('/me', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token } })).json();
ok(me.nick === '테스트대표' && me.subId === 'hzm00001' && me.admin === false, `회원 생성: ${me.nick} · 이름표 ${me.subId} · 관리자 아님`);
const noOrigin = await call('/me', { headers: { Authorization: 'Bearer ' + token } });
ok(noOrigin.status === 403, '혜택존이 아닌 곳에서 부르면 거절');
// 5. 다시 로그인
kakaoUser.kakao_account.profile.nickname = '바뀐닉네임';
const b = await login('my');
const token2 = b.dest.split('#login=')[1];
me = await (await call('/me', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token2 } })).json();
ok(me.subId === 'hzm00001' && me.nick === '바뀐닉네임', '같은 카카오 계정 재로그인 → 같은 회원·같은 이름표, 닉네임만 갱신');
ok(db.prepare('SELECT COUNT(*) n FROM members').get().n === 1, '회원이 중복으로 생기지 않음');
// 6. 관리자 지정
ok((await call('/admin/overview', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token } })).status === 401, '지정 전에는 관리자 화면 거절');
const mk = await (await call('/admin/make-admin', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' }, body: { id: 1 } })).json();
ok(mk.ok === true, 'make-admin.sh 방식으로 관리자 지정');
const ov = await call('/admin/overview', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token } });
ok(ov.status === 200 && (await ov.json()).admin.startsWith('바뀐닉네임'), '지정 후 카카오 로그인만으로 관리자 화면 열림');
const self = await call('/admin/make-admin', { method: 'POST', headers: { ...ORIGIN, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: { id: 1 } });
ok(self.status === 403, '관리자 회원도 관리자 지정은 못 함 (관리 키 전용)');
// 7. 쿠팡 동기화·확정·취소
coupang.orders = [
  { date: '20260911', subId: 'hzm00001', orderId: '99887766554433221', productId: 1, productName: '물티슈', quantity: 2, gmv: 24260, commission: 727 },
  { date: '20260710', subId: 'hzm00001', orderId: '11', productId: 2, productName: '에어드레서', quantity: 1, gmv: 410000, commission: 12300 },
  { date: '20260911', subId: 'hyetaekzone', orderId: '12', productId: 3, productName: '비회원 구매', quantity: 1, gmv: 5000, commission: 150 }];
coupang.cancels = [{ date: '20260912', subId: 'hzm00001', orderId: '99887766554433221', productId: 1, gmv: 12130 }];
const sync = await (await call('/admin/sync', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' }, body: {} })).json();
ok(sync.ok && sync.note.startsWith('주문 2 · 취소 1'), `쿠팡 동기화: ${sync.note} (비회원 주문은 저장 안 함)`);
ok(db.prepare("SELECT order_id FROM orders WHERE name='물티슈'").get().order_id === '99887766554433221', '큰 주문번호도 한 자리도 안 틀리고 저장');
me = await (await call('/me', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token2 } })).json();
const byName = Object.fromEntries(me.rows.map(r => [r.name, r]));
ok(byName['에어드레서'].status === 'done' && byName['에어드레서'].points === 1230, '7월 구매는 8/25 지나 적립 완료 · 수수료 12,300원의 10% = 1,230P');
ok(byName['물티슈'].status === 'pending' && byName['물티슈'].points === 36 && byName['물티슈'].confirmOn === '2026-10-25', '9월 구매 절반 취소 → 적립 예정 36P (727원×절반×10%), 10/25 확정');
ok(me.sums.balance === 1230 && me.sums.pending === 36, `잔액 ${me.sums.balance}P · 적립 예정 ${me.sums.pending}P`);
// 8. 소멸 (유효기간 1년)
db.prepare("UPDATE orders SET confirmed_at = ? WHERE name='에어드레서'").run(Math.floor(Date.now() / 1000) - 400 * 86400);
const { expirePoints } = await import('../src/reward.js');
await expirePoints(env); await expirePoints(env);
me = await (await call('/me', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token2 } })).json();
ok(me.sums.balance === 0 && me.sums.expired === 1230, '적립 완료 후 1년 지난 포인트 소멸 · 두 번 돌려도 한 번만 빠짐');
// 9. 로그아웃
await call('/me/logout', { method: 'POST', headers: { ...ORIGIN, Authorization: 'Bearer ' + token2 } });
ok((await call('/me', { headers: { ...ORIGIN, Authorization: 'Bearer ' + token2 } })).status === 401, '로그아웃하면 그 토큰은 더 못 씀');
ok(db.prepare('SELECT COUNT(*) n FROM sessions WHERE token_hash = ?').get(token).n === 0, 'DB 에는 로그인 토큰 원문이 없음 (해시만)');
// 10. 약관 동의 · 곧 사라질 포인트 · 원천징수 · 지급 내역 · 아침 보고
const t3 = (await login('my')).dest.split('#login=')[1];
const H = { ...ORIGIN, Authorization: 'Bearer ' + t3, 'Content-Type': 'application/json' };
me = await (await call('/me', { headers: H })).json();
ok(me.needTerms === true, '약관 동의 전에는 needTerms (적립 줄이 이름표를 안 붙임)');
db.prepare("INSERT INTO orders (order_id, product_id, sub_id, day, name, qty, gmv, commission, share, confirm_on, confirmed_at, points, created_at) VALUES ('X1','1','hzm00001','20250910','오래된 적립',1,2000000,600000,0.1,'2025-10-25',?,60000,?)")
  .run(Math.floor(Date.now() / 1000) - 350 * 86400, Math.floor(Date.now() / 1000) - 350 * 86400);
const acct = { holder: '홍길동', bank: '신한', account: '110123456789', agree: true, rrn1: '900101', rrn2: '1234567', agreeRrn: true };
let r = await call('/me/cashout', { method: 'POST', headers: H, body: acct });
ok(r.status === 403, '약관 동의 전에는 현금 교환 불가');
r = await call('/me/agree', { method: 'POST', headers: H, body: { ver: me.termsVer, terms: true, privacy: false } });
ok(r.status === 400, '개인정보 동의를 빼면 거절');
r = await call('/me/agree', { method: 'POST', headers: H, body: { ver: me.termsVer, terms: true, privacy: true } });
const agreed = await r.json();
me = await (await call('/me', { headers: H })).json();
ok(r.status === 200 && me.needTerms === false, '약관·개인정보 동의 → 적립 시작');
ok(agreed.bonus === 1000 && me.log.some(l => l.kind === 'bonus' && l.amount === 1000) && me.sums.balance === 61000, '처음 동의하면 가입 축하 1,000P (잔액 60,000 + 1,000)');
const again = await (await call('/me/agree', { method: 'POST', headers: H, body: { ver: me.termsVer, terms: true, privacy: true } })).json();
ok(again.bonus === 0, '다시 동의해도 가입 축하는 한 번만');
ok(me.sums.expiringSoon === 60000, `350일 된 적립 60,000P → 30일 안에 사라질 포인트 ${me.sums.expiringSoon}P 로 안내`);
await call('/admin/settings', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' },
  body: { share: 0.1, min_cashout: 10000, expire_days: 365, collect_rrn: 1, withholding_rate: 0.033, withholding_free_upto: 0 } });
const co = await (await call('/me/cashout', { method: 'POST', headers: H, body: acct })).json();
ok(co.amount === 61000 && co.tax === 2010 && co.net === 58990, `사업소득 3.3%: 61,000P → 소득세 1,830 + 지방소득세 180 = ${co.tax}원 · 입금 ${co.net}원`);
const cid = db.prepare("SELECT id FROM cashouts WHERE status='requested'").get().id;
await call('/admin/cashout/done', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' }, body: { id: cid } });
const mo = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);
const ex = await call('/admin/export?month=' + mo, { headers: { Authorization: 'Bearer stats-test' } });
const text = await ex.text(), lines = text.replace(/^﻿/, '').split('\r\n');
ok(ex.headers.get('Content-Type').startsWith('text/csv') && lines.length === 3 && lines[1].includes('900101-1234567') && lines[1].endsWith(',61000,1830,180,2010,58990,관리 키') && lines[2].startsWith('합계'),
  '지급 내역 CSV: 예금주·계좌·주민번호·세금·실지급액·합계 줄');
ok(db.prepare("SELECT COUNT(*) n FROM audit WHERE action='지급 내역 내보내기'").get().n === 1, '내보내기는 작업 기록에 남음');
const small = taxCheck => taxCheck;
await call('/admin/settings', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' },
  body: { share: 0.1, min_cashout: 10000, expire_days: 365, collect_rrn: 1, withholding_rate: 0.033, withholding_free_upto: 0 } });
await call('/admin/adjust', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' }, body: { id: 1, amount: 30000, memo: '시험' } });
const co2 = await (await call('/me/cashout', { method: 'POST', headers: H, body: acct })).json();
ok(co2.amount === 30000 && co2.tax === 0 && co2.net === 30000, '소득세 1,000원 미만(30,000P × 3% = 900원)은 소액부징수로 안 뗌');
const rep = await (await call('/admin/report', { headers: { Authorization: 'Bearer stats-test' } })).json();
ok(rep.cashPending.n === 1 && rep.members.n === 1 && rep.newOrders.n >= 2 && typeof rep.syncStale === 'boolean', `아침 보고 요약: 교환 대기 ${rep.cashPending.n}건 · 새 주문 ${rep.newOrders.n}건`);
ok(me.rows.every(x => 'createdAt' in x && 'confirmedAt' in x), '회원 알림용 시각(처음 잡힘·확정) 제공');
// 11. 탈퇴 후 같은 카카오 계정으로 재가입 → 가입 축하 다시 안 줌
const pendId = db.prepare("SELECT id FROM cashouts WHERE status='requested'").get().id;
await call('/admin/cashout/reject', { method: 'POST', headers: { Authorization: 'Bearer stats-test', 'Content-Type': 'application/json' }, body: { id: pendId, reason: '시험' } });
const del = await call('/me/delete', { method: 'POST', headers: H });
ok(del.status === 200, '처리 중 교환이 없으면 탈퇴 됨');
const t4 = (await login('my')).dest.split('#login=')[1];
const H4 = { ...ORIGIN, Authorization: 'Bearer ' + t4, 'Content-Type': 'application/json' };
const m4 = await (await call('/me', { headers: H4 })).json();
const ag4 = await (await call('/me/agree', { method: 'POST', headers: H4, body: { ver: m4.termsVer, terms: true, privacy: true } })).json();
const m5 = await (await call('/me', { headers: H4 })).json();
ok(m4.needTerms === true && ag4.bonus === 0 && m5.sums.balance === 0, '탈퇴 후 같은 카카오 계정 재가입 → 가입 축하 다시 안 줌');
ok(db.prepare('SELECT COUNT(*) n FROM bonus_claims').get().n === 1 && !db.prepare('SELECT kakao_hash h FROM bonus_claims').get().h.includes('4242001'), '중복 방지에는 카카오 회원번호 해시만 보관');
const st = await (await call('/rw/status', { headers: ORIGIN })).json();
ok(st.signupBonus === 1000, '상태 정보에 가입 축하 포인트 (화면 문구용)');
console.log(fails ? `\n❌ ${fails}개 실패` : '\n모두 통과');
process.exit(fails ? 1 : 0);
