/* 카카오 로그인 · 쿠팡 구매 포인트 적립 · 현금 교환 · 관리자
   - 로그인하면 회원마다 쿠팡 링크 이름표(subId, 예: hzm00001)가 생깁니다.
   - 사이트의 쿠팡 링크를 누를 때 이름표를 바꿔 끼워, 쿠팡 주문 리포트에서 누구 링크로 산 건지 알 수 있습니다.
     (쿠팡은 산 사람이 아니라 "어느 링크로 들어왔는지"만 알려줍니다. 링크를 누르고 24시간 안의 구매가 잡힙니다)
   - 포인트 = 그 주문으로 우리가 받는 쿠팡 수수료 × 적립 비율(설정, 기본 10%). 1P = 1원.
   - 매시 5분 쿠팡 리포트를 읽어 회원 주문을 옮기고, 구매한 달의 다음 달 25일에 '적립 완료'로 확정.
     그 전에는 '적립 예정', 전액 취소·반품이면 '적립 취소'. 적립 완료 후 1년(설정)이 지나면 소멸.
   - 잔액이 1만 P(설정) 이상이면 현금 교환 신청 → 관리자가 계좌로 보내고 '지급 완료' (반려하면 포인트 복구).
     세금 신고(원천징수·지급명세서)용으로 주민등록번호를 함께 받습니다(설정으로 끄기 가능). 계좌·주민번호는 AES-GCM 암호화.

   회원:  GET /rw/status · GET /auth/kakao?back=my · GET /auth/kakao/callback
          GET /me · POST /me/cashout · POST /me/logout · POST /me/delete        (Authorization: Bearer <로그인 토큰>)
   관리자: /admin/*  — 관리자 회원의 로그인 토큰, 또는 Bearer <STATS_KEY>
          overview · members · member?id= · member/update · adjust · cashouts · cashout/reveal|done|reject
          settings · audit · sync · make-admin(STATS_KEY 전용)
   비밀값: KAKAO_REST_KEY, KAKAO_CLIENT_SECRET(선택), COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY, PII_KEY, STATS_KEY
*/
const SESSION_DAYS = 90;
const SUB_PREFIX = 'hzm';
const BACK = { my: 'my.html', hotdeal: 'hotdeal.html', main: '', admin: 'admin.html' };
const DEFAULTS = { share: 0.10, min_cashout: 10000, expire_days: 365, collect_rrn: 1, withholding_rate: 0, withholding_free_upto: 50000, signup_bonus: 1000 };
// signup_bonus: 처음 가입(약관 동의)할 때 한 번 주는 포인트. 같은 카카오 계정은 탈퇴 후 다시 가입해도 다시 안 줌 (bonus_claims)
// withholding_rate: 원천징수율 합계 (0 = 안 뗌. 사업소득 0.033 = 소득세 3% + 지방소득세 0.3%) · withholding_free_upto: 이 금액 이하 교환은 떼지 않음 (사업소득은 0)
const TERMS_VER = '2026-09-12';   // 포인트 이용약관 버전 — 약관을 바꾸면 올려서 다시 동의받음
const SOON_DAYS = 30;             // '곧 사라질 포인트' 안내 기간   // collect_rrn: 현금 교환 때 주민등록번호 받기 (원천징수용)
const PII_KEEP_DAYS = 5 * 365;     // 지급 기록의 계좌 정보 보관 (세무 증빙)
const CP_HOST = 'https://api-gateway.coupang.com';
const CP_BASE = '/v2/providers/affiliate_open_api/apis/openapi/v1';

const now = () => Math.floor(Date.now() / 1000);
const kst = (offsetDays = 0) => new Date(Date.now() + 9 * 3600e3 - offsetDays * 86400e3);
const ymd = d => d.toISOString().slice(0, 10).replace(/-/g, '');
const kstMidnight = () => { const d = kst(); return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000) - 9 * 3600; };
const siteUrl = env => env.SITE_URL || 'https://hubrizjeon.github.io/hyetaekzone/';
const json = (data, status, headers) =>
  new Response(JSON.stringify(data), { status, headers: { ...headers, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
const num = v => Number(v) || 0;

function confirmOn(day) {          // 'YYYYMMDD' → 다음 달 25일 'YYYY-MM-25'
  let y = +day.slice(0, 4), m = +day.slice(4, 6) + 1;
  if (m > 12) { m = 1; y += 1; }
  return `${y}-${String(m).padStart(2, '0')}-25`;
}
/* 주문 한 줄의 포인트 = 수수료 × (취소 뺀 금액 / 구매금액) × 비율 */
const orderPoints = o => o.gmv > 0 ? Math.floor(num(o.commission) * Math.max(0, o.gmv - num(o.cancel)) / o.gmv * num(o.share)) : 0;
const POINTS_SQL = `CAST(CASE WHEN o.gmv > 0 THEN o.commission * MAX(0, o.gmv - COALESCE((SELECT SUM(c.gmv) FROM cancels c
  WHERE c.order_id = o.order_id AND c.product_id = o.product_id), 0)) * 1.0 / o.gmv * o.share ELSE 0 END AS INTEGER)`;

function randomToken() {
  const b = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function sha256(s) {
  const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join('');
}
function cookie(req, name) {
  const m = (req.headers.get('Cookie') || '').match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? m[1] : '';
}
const b64 = u8 => btoa(String.fromCharCode(...u8));
const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function piiKey(env) {
  if (!env.PII_KEY) throw new Error('PII_KEY 없음');
  return crypto.subtle.importKey('raw', unb64(env.PII_KEY), 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function seal(env, obj) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await piiKey(env), new TextEncoder().encode(JSON.stringify(obj))));
  return b64(iv) + '.' + b64(ct);
}
async function unseal(env, s) {
  const [iv, ct] = s.split('.');
  return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(iv) }, await piiKey(env), unb64(ct))));
}

async function settings(env) {
  const s = { ...DEFAULTS };
  const { results } = await env.MEM.prepare('SELECT k, v FROM settings').all();
  for (const r of results) if (r.k in s) s[r.k] = Number(r.v);
  return s;
}
const audit = (env, admin, action, target, detail) =>
  env.MEM.prepare('INSERT INTO audit (at, admin, action, target, detail) VALUES (?, ?, ?, ?, ?)')
    .bind(now(), admin, action, target == null ? null : String(target), detail == null ? null : String(detail).slice(0, 500));

async function memberFromAuth(req, env) {
  const t = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
  if (!t || t.length < 20) return null;
  return env.MEM.prepare(
    `SELECT m.id, m.nick, m.sub_id, m.is_admin, m.status, m.terms_ver FROM sessions s JOIN members m ON m.id = s.member_id
     WHERE s.token_hash = ? AND s.exp > ?`).bind(await sha256(t), now()).first();
}
async function adminFrom(req, env) {
  if (env.STATS_KEY && req.headers.get('Authorization') === `Bearer ${env.STATS_KEY}`) return { name: '관리 키', key: true };
  const me = await memberFromAuth(req, env);
  return me && me.is_admin && me.status === 'ok' ? { name: `${me.nick}(#${me.id})`, id: me.id } : null;
}

/* ── 쿠팡 리포트 ── */
async function cpReport(env, name, query) {
  const d = new Date().toISOString();
  const dt = d.slice(2, 4) + d.slice(5, 7) + d.slice(8, 10) + 'T' + d.slice(11, 13) + d.slice(14, 16) + d.slice(17, 19) + 'Z';
  const path = `${CP_BASE}/reports/${name}`;
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(env.COUPANG_SECRET_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = [...new Uint8Array(await crypto.subtle.sign('HMAC', key, enc.encode(dt + 'GET' + path + query)))]
    .map(b => b.toString(16).padStart(2, '0')).join('');
  const r = await fetch(`${CP_HOST}${path}?${query}`, { headers: {
    Authorization: `CEA algorithm=HmacSHA256, access-key=${env.COUPANG_ACCESS_KEY}, signed-date=${dt}, signature=${sig}` } });
  // 주문번호가 자바스크립트 숫자 범위를 넘을 수 있어 글자로 바꿔 읽습니다
  const text = (await r.text()).replace(/"(orderId|productId)"\s*:\s*(\d+)/g, '"$1":"$2"');
  let j = null;
  try { j = JSON.parse(text); } catch { /* 빈 응답 */ }
  if (r.status !== 200 || !j || String(j.rCode) !== '0') throw new Error(`쿠팡 ${name} ${r.status} ${j && j.rMessage || ''}`.trim());
  return j.data || [];
}

export async function syncOrders(env) {
  if (!env.COUPANG_ACCESS_KEY || !env.COUPANG_SECRET_KEY) return { ok: false, note: '쿠팡 키 없음' };
  const q = `startDate=${ymd(kst(29))}&endDate=${ymd(kst())}`;      // 쿠팡은 한 번에 최대 30일 (매시간 같은 범위를 다시 읽어도 결과는 같음)
  const mine = r => String(r.subId || '').startsWith(SUB_PREFIX);
  try {
    const [orders, cancels, s] = await Promise.all([cpReport(env, 'orders', q), cpReport(env, 'cancels', q), settings(env)]);
    const st = [];
    for (const r of orders.filter(mine)) {
      st.push(env.MEM.prepare(
        `INSERT INTO orders (order_id, product_id, sub_id, day, name, qty, gmv, commission, share, confirm_on, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(order_id, product_id) DO UPDATE SET sub_id = excluded.sub_id, day = excluded.day, name = excluded.name,
           qty = excluded.qty, gmv = excluded.gmv, commission = excluded.commission, confirm_on = excluded.confirm_on
         WHERE orders.confirmed_at IS NULL`
      ).bind(String(r.orderId), String(r.productId), r.subId, String(r.date), String(r.productName || '').slice(0, 120),
        num(r.quantity) || 1, Math.round(Math.abs(num(r.gmv))), Math.round(Math.abs(num(r.commission))), s.share, confirmOn(String(r.date)), now()));
    }
    for (const r of cancels.filter(mine)) {
      st.push(env.MEM.prepare(
        `INSERT INTO cancels (order_id, product_id, day, gmv) VALUES (?, ?, ?, ?)
         ON CONFLICT(order_id, product_id, day) DO UPDATE SET gmv = excluded.gmv`
      ).bind(String(r.orderId), String(r.productId), String(r.date), Math.round(Math.abs(num(r.gmv)))));
    }
    // 확정: 확정일이 된 주문은 포인트를 고정합니다
    const today = kst().toISOString().slice(0, 10);
    st.push(env.MEM.prepare(`UPDATE orders AS o SET confirmed_at = ?, points = ${POINTS_SQL}
       WHERE o.confirmed_at IS NULL AND o.confirm_on <= ?`).bind(now(), today));
    const note = `주문 ${orders.filter(mine).length} · 취소 ${cancels.filter(mine).length} (전체 주문 ${orders.length})`;
    st.push(env.MEM.prepare('INSERT OR REPLACE INTO sync_log (at, ok, note) VALUES (?, 1, ?)').bind(now(), note));
    await env.MEM.batch(st);
    return { ok: true, note };
  } catch (e) {
    await env.MEM.prepare('INSERT OR REPLACE INTO sync_log (at, ok, note) VALUES (?, 0, ?)').bind(now(), String(e.message).slice(0, 200)).run();
    return { ok: false, note: String(e.message) };
  }
}

/* 소멸: 적립 완료(또는 + 조정) 후 유효기간이 지난 포인트 중 아직 쓰지 않은 만큼 (먼저 쌓인 것부터 쓴 것으로 봄) */
export async function expirePoints(env) {
  const s = await settings(env);
  const cutoff = now() - s.expire_days * 86400;
  const { results } = await env.MEM.prepare(`SELECT m.id,
      COALESCE((SELECT SUM(points) FROM orders WHERE sub_id = m.sub_id AND confirmed_at <= ?), 0)
    + COALESCE((SELECT SUM(amount) FROM points_log WHERE member_id = m.id AND kind IN ('adjust', 'bonus') AND amount > 0 AND at <= ?), 0) AS old,
      COALESCE((SELECT -SUM(amount) FROM points_log WHERE member_id = m.id AND amount < 0), 0)
    - COALESCE((SELECT SUM(amount) FROM points_log WHERE member_id = m.id AND kind = 'refund'), 0) AS used
    FROM members m`).bind(cutoff, cutoff).all();
  const st = results.filter(r => r.old - r.used > 0).map(r =>
    env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, admin, at) VALUES (?, 'expire', ?, ?, '자동', ?)`)
      .bind(r.id, -(r.old - r.used), `적립 후 ${s.expire_days}일 지나 소멸`, now()));
  st.push(env.MEM.prepare(`UPDATE cashouts SET pii = NULL WHERE pii IS NOT NULL AND status = 'paid' AND done_at < ?`).bind(now() - PII_KEEP_DAYS * 86400));
  st.push(env.MEM.prepare('DELETE FROM sessions WHERE exp < ?').bind(now()));
  await env.MEM.batch(st);
  return st.length - 2;
}

/* 회원 한 명의 장부 */
async function ledger(env, m) {
  const [ord, log, cash] = await Promise.all([
    env.MEM.prepare(`SELECT o.order_id, o.day, o.name, o.qty, o.gmv, o.commission, o.share, o.confirm_on, o.confirmed_at, o.points, o.created_at,
        COALESCE((SELECT SUM(c.gmv) FROM cancels c WHERE c.order_id = o.order_id AND c.product_id = o.product_id), 0) AS cancel
      FROM orders o WHERE o.sub_id = ? ORDER BY o.day DESC, o.order_id DESC LIMIT 500`).bind(m.sub_id).all(),
    env.MEM.prepare('SELECT kind, amount, memo, at FROM points_log WHERE member_id = ? ORDER BY at DESC, id DESC LIMIT 300').bind(m.id).all(),
    env.MEM.prepare(`SELECT id, amount, tax, net, bank, acct_mask, status, reason, requested_at, done_at FROM cashouts
      WHERE member_id = ? ORDER BY id DESC LIMIT 100`).bind(m.id).all(),
  ]);
  const sums = { pending: 0, earned: 0, canceled: 0, used: 0, expired: 0, balance: 0, expiringSoon: 0 };
  const rows = ord.results.map(o => {
    let status, p;
    if (o.confirmed_at) { p = o.points; status = p > 0 ? 'done' : 'canceled'; }
    else if (o.gmv - o.cancel <= 0) { p = 0; status = 'canceled'; }
    else { p = orderPoints(o); status = 'pending'; }
    const full = orderPoints({ ...o, cancel: 0 });
    if (status === 'done') sums.earned += p; else if (status === 'pending') sums.pending += p; else sums.canceled += full;
    return { day: o.day, name: o.name, qty: o.qty, gmv: o.gmv, cancel: o.cancel, commission: o.commission,
             points: status === 'canceled' ? full : p, status, confirmOn: o.confirm_on, createdAt: o.created_at, confirmedAt: o.confirmed_at };
  });
  let logSum = 0;
  for (const l of log.results) {
    logSum += l.amount;
    if (l.kind === 'expire') sums.expired -= l.amount;
  }
  sums.used = cash.results.filter(c => c.status !== 'rejected').reduce((a, c) => a + c.amount, 0);
  const allLog = await env.MEM.prepare('SELECT COALESCE(SUM(amount), 0) AS t FROM points_log WHERE member_id = ?').bind(m.id).first();
  sums.balance = sums.earned + allLog.t;
  // 곧 사라질 포인트: 유효기간이 30일 안에 끝나는 적립 중 아직 쓰지 않은 만큼 (소멸과 같은 계산)
  const s = await settings(env), soon = now() - (s.expire_days - SOON_DAYS) * 86400;
  const e = await env.MEM.prepare(`SELECT
      COALESCE((SELECT SUM(points) FROM orders WHERE sub_id = ? AND confirmed_at IS NOT NULL AND confirmed_at <= ?), 0)
    + COALESCE((SELECT SUM(amount) FROM points_log WHERE member_id = ? AND kind IN ('adjust', 'bonus') AND amount > 0 AND at <= ?), 0) AS old,
      COALESCE((SELECT -SUM(amount) FROM points_log WHERE member_id = ? AND amount < 0), 0)
    - COALESCE((SELECT SUM(amount) FROM points_log WHERE member_id = ? AND kind = 'refund'), 0) AS used`)
    .bind(m.sub_id, soon, m.id, soon, m.id, m.id).first();
  sums.expiringSoon = Math.max(0, Math.min(sums.balance, e.old - e.used));
  return { sums, rows, log: log.results, cashouts: cash.results };
}

const BANK_RE = /^[가-힣A-Za-z0-9() ]{2,20}$/;
/* 원천징수: 합계 비율 = 소득세 + 지방소득세(소득세의 10%). 각각 10원 미만 버림.
   소득세가 1,000원 미만이면 떼지 않음(소득세법 제86조 소액부징수). free_upto 이하 교환도 떼지 않음 */
function taxOf(amount, s) {
  if (!(s.withholding_rate > 0) || amount <= s.withholding_free_upto) return { income: 0, local: 0, tax: 0 };
  const incomeRate = Math.round(s.withholding_rate / 1.1 * 1e6) / 1e6;          // 0.033 → 0.03 (소수 계산 오차 제거)
  const income = Math.floor(amount * incomeRate / 10 + 1e-9) * 10;
  if (income < 1000) return { income: 0, local: 0, tax: 0 };
  const local = Math.floor(income * 0.1 / 10) * 10;
  return { income, local, tax: income + local };
}
const csv = rows => '\uFEFF' + rows.map(r => r.map(v => { const t = v == null ? '' : String(v); return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; }).join(',')).join('\r\n');
/* 주민등록번호 형식: 앞 6자리 생년월일이 실제 날짜이고 뒤 첫 자리가 1~8 (2020년 이후 번호는 검증숫자 규칙이 없어 형식만 봄) */
function validRrn(front, back) {
  if (!/^\d{6}$/.test(front) || !/^[1-8]\d{6}$/.test(back)) return false;
  const century = '1256'.includes(back[0]) ? 1900 : 2000;
  const y = century + +front.slice(0, 2), m = +front.slice(2, 4), dd = +front.slice(4, 6);
  const dt = new Date(Date.UTC(y, m - 1, dd));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === dd && dt.getTime() <= Date.now();
}

/* ── 요청 처리. 이 모듈 경로가 아니면 null ── */
export async function handleReward(req, env, ctx, url, cors, allowed) {
  const p = url.pathname;
  const back = BACK[url.searchParams.get('back')] ?? BACK.my;
  const body = async () => { try { return await req.json(); } catch { return {}; } };

  if (p === '/rw/status' && req.method === 'GET') {
    const s = await settings(env);
    return json({ on: !!env.KAKAO_REST_KEY, share: s.share, min: s.min_cashout, expireDays: s.expire_days, collectRrn: !!s.collect_rrn,
      withholdingRate: s.withholding_rate, withholdingFreeUpto: s.withholding_free_upto, termsVer: TERMS_VER, signupBonus: s.signup_bonus }, 200, cors);
  }

  if (p === '/auth/kakao' && req.method === 'GET') {
    if (!env.KAKAO_REST_KEY) return Response.redirect(siteUrl(env) + back + '#rw=off', 302);
    const state = randomToken().slice(0, 24);
    const q = new URLSearchParams({ client_id: env.KAKAO_REST_KEY, redirect_uri: url.origin + '/auth/kakao/callback',
      response_type: 'code', state });
    const b = BACK[url.searchParams.get('back')] !== undefined ? url.searchParams.get('back') : 'my';
    return new Response(null, { status: 302, headers: {
      Location: 'https://kauth.kakao.com/oauth/authorize?' + q,
      'Set-Cookie': `hz_state=${state}.${b}; Path=/auth; Max-Age=600; HttpOnly; Secure; SameSite=Lax` } });
  }

  if (p === '/auth/kakao/callback' && req.method === 'GET') {
    const [state, b] = cookie(req, 'hz_state').split('.');
    const dest = siteUrl(env) + (BACK[b] ?? BACK.my);
    const clear = 'hz_state=; Path=/auth; Max-Age=0; HttpOnly; Secure; SameSite=Lax';
    const fail = (why, code) => new Response(null, { status: 302, headers: {
      Location: dest + '#rw=fail-' + why + (code ? '-' + String(code).toLowerCase().replace(/[^a-z0-9]/g, '') : ''), 'Set-Cookie': clear } });
    if (url.searchParams.get('error')) return fail('cancel');           // 동의 화면에서 취소
    if (!state || state !== url.searchParams.get('state') || !url.searchParams.get('code')) return fail('state');

    const form = new URLSearchParams({ grant_type: 'authorization_code', client_id: env.KAKAO_REST_KEY,
      redirect_uri: url.origin + '/auth/kakao/callback', code: url.searchParams.get('code') });
    if (env.KAKAO_CLIENT_SECRET) form.set('client_secret', env.KAKAO_CLIENT_SECRET);
    const tr = await fetch('https://kauth.kakao.com/oauth/token', { method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8' }, body: form });
    const tok = await tr.json().catch(() => ({}));
    if (!tok.access_token) {
      // 원인을 남겨 둠 (키 값은 넣지 않음). KOE010 = 클라이언트 시크릿 불일치·미등록
      await audit(env, '카카오', '로그인 실패', null, `${tok.error_code || ''} ${tok.error || ''} ${tok.error_description || ''}`.trim()).run().catch(() => {});
      return fail('token', tok.error_code);
    }
    const ur = await fetch('https://kapi.kakao.com/v2/user/me', { headers: { Authorization: 'Bearer ' + tok.access_token } });
    const u = await ur.json().catch(() => ({}));
    if (!u.id) return fail('user');
    const nick = String((u.kakao_account && u.kakao_account.profile && u.kakao_account.profile.nickname) ||
                        (u.properties && u.properties.nickname) || '회원').slice(0, 30);

    const t = now();
    const m = await env.MEM.prepare(
      `INSERT INTO members (kakao_id, nick, created, last_login) VALUES (?, ?, ?, ?)
       ON CONFLICT(kakao_id) DO UPDATE SET nick = excluded.nick, last_login = excluded.last_login
       RETURNING id, sub_id`).bind(String(u.id), nick, t, t).first();
    if (!m.sub_id) {
      await env.MEM.prepare('UPDATE members SET sub_id = ? WHERE id = ?').bind(SUB_PREFIX + String(m.id).padStart(5, '0'), m.id).run();
    }
    const token = randomToken();
    await env.MEM.prepare('INSERT INTO sessions (token_hash, member_id, exp) VALUES (?, ?, ?)')
      .bind(await sha256(token), m.id, t + SESSION_DAYS * 86400).run();
    return new Response(null, { status: 302, headers: { Location: dest + '#login=' + token, 'Set-Cookie': clear } });
  }

  if (p.startsWith('/me')) {
    if (!allowed) return json({ error: 'forbidden' }, 403, cors);
    const me = await memberFromAuth(req, env);
    if (!me) return json({ error: 'login' }, 401, cors);

    if (p === '/me' && req.method === 'GET') {
      const [led, s, last] = await Promise.all([ledger(env, me), settings(env),
        env.MEM.prepare('SELECT at FROM sync_log WHERE ok = 1 ORDER BY at DESC LIMIT 1').first()]);
      return json({ nick: me.nick, subId: me.sub_id, status: me.status, admin: !!me.is_admin,
        share: s.share, min: s.min_cashout, expireDays: s.expire_days, collectRrn: !!s.collect_rrn,
        withholdingRate: s.withholding_rate, withholdingFreeUpto: s.withholding_free_upto, signupBonus: s.signup_bonus,
        needTerms: me.terms_ver !== TERMS_VER, termsVer: TERMS_VER, ...led, syncedAt: last ? last.at : null }, 200, cors);
    }

    if (p === '/me/agree' && req.method === 'POST') {
      const d = await body();
      if (d.ver !== TERMS_VER || !d.terms || !d.privacy) return json({ error: '이용약관과 개인정보 수집·이용에 모두 동의해 주세요.' }, 400, cors);
      const row = await env.MEM.prepare('SELECT kakao_id, terms_at FROM members WHERE id = ?').bind(me.id).first();
      await env.MEM.prepare('UPDATE members SET terms_ver = ?, terms_at = ? WHERE id = ?').bind(TERMS_VER, now(), me.id).run();
      // 가입 축하 포인트: 처음 동의할 때 한 번. 같은 카카오 계정이면(탈퇴 후 재가입 포함) 다시 주지 않음
      let bonus = 0;
      const s = await settings(env);
      if (!row.terms_at && s.signup_bonus > 0) {
        const claim = await env.MEM.prepare('INSERT OR IGNORE INTO bonus_claims (kakao_hash, at) VALUES (?, ?)')
          .bind(await sha256('kakao:' + row.kakao_id), now()).run();
        if (claim.meta.changes === 1) {
          await env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, admin, at) VALUES (?, 'bonus', ?, '가입 축하 포인트', '자동', ?)`)
            .bind(me.id, s.signup_bonus, now()).run();
          bonus = s.signup_bonus;
        }
      }
      return json({ ok: true, bonus }, 200, cors);
    }

    if (p === '/me/cashout' && req.method === 'POST') {
      if (me.terms_ver !== TERMS_VER) return json({ error: '포인트 이용약관에 먼저 동의해 주세요.' }, 403, cors);
      if (me.status !== 'ok') return json({ error: '이용이 멈춘 계정이에요. 고객센터로 문의해 주세요.' }, 403, cors);
      const d = await body();
      const holder = String(d.holder || '').trim(), bank = String(d.bank || '').trim(), account = String(d.account || '').replace(/[\s-]/g, '');
      if (!d.agree) return json({ error: '계좌 정보 수집에 동의해 주세요.' }, 400, cors);
      if (!/^[가-힣A-Za-z ]{2,20}$/.test(holder)) return json({ error: '예금주 이름을 확인해 주세요.' }, 400, cors);
      if (!BANK_RE.test(bank)) return json({ error: '은행을 골라 주세요.' }, 400, cors);
      if (!/^\d{8,16}$/.test(account)) return json({ error: '계좌번호는 숫자 8~16자리로 넣어 주세요.' }, 400, cors);
      const [s, led] = await Promise.all([settings(env), ledger(env, me)]);
      let rrn;
      if (s.collect_rrn) {
        const front = String(d.rrn1 || '').trim(), back = String(d.rrn2 || '').trim();
        if (!d.agreeRrn) return json({ error: '세금 신고를 위한 주민등록번호 수집에 동의해 주세요.' }, 400, cors);
        if (!validRrn(front, back)) return json({ error: '주민등록번호를 확인해 주세요 (앞 6자리 · 뒤 7자리).' }, 400, cors);
        rrn = `${front}-${back}`;
      }
      if (led.cashouts.some(c => c.status === 'requested')) return json({ error: '이미 신청한 교환이 처리 중이에요.' }, 409, cors);
      const amount = led.sums.balance;
      if (amount < s.min_cashout) return json({ error: `${s.min_cashout.toLocaleString('ko-KR')}P부터 바꿀 수 있어요.` }, 400, cors);
      const t = now(), tx = taxOf(amount, s), tax = tx.tax, net = amount - tax;
      try {
        await env.MEM.batch([
          env.MEM.prepare(`INSERT INTO cashouts (member_id, nick, amount, tax, tax_income, tax_local, net, bank, acct_mask, pii, status, requested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'requested', ?)`).bind(me.id, me.nick, amount, tax, tx.income, tx.local, net, bank, '****' + account.slice(-4),
            await seal(env, rrn ? { holder, bank, account, rrn } : { holder, bank, account }), t),
          env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, at)
            SELECT ?, 'cashout', ?, '현금 교환 신청 #' || id, ? FROM cashouts WHERE member_id = ? AND status = 'requested'`)
            .bind(me.id, -amount, t, me.id),
        ]);
      } catch { return json({ error: '이미 신청한 교환이 처리 중이에요.' }, 409, cors); }
      return json({ ok: true, amount, tax, net }, 200, cors);
    }

    if (p === '/me/logout' && req.method === 'POST') {
      const t = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
      await env.MEM.prepare('DELETE FROM sessions WHERE token_hash = ?').bind(await sha256(t)).run();
      return json({ ok: true }, 200, cors);
    }

    if (p === '/me/delete' && req.method === 'POST') {
      const pend = await env.MEM.prepare(`SELECT id FROM cashouts WHERE member_id = ? AND status = 'requested'`).bind(me.id).first();
      if (pend) return json({ error: '현금 교환이 처리 중이라 지금은 탈퇴할 수 없어요. 입금된 뒤 다시 눌러 주세요.' }, 409, cors);
      await env.MEM.batch([
        env.MEM.prepare('DELETE FROM cancels WHERE (order_id, product_id) IN (SELECT order_id, product_id FROM orders WHERE sub_id = ?)').bind(me.sub_id),
        env.MEM.prepare('DELETE FROM orders WHERE sub_id = ?').bind(me.sub_id),
        env.MEM.prepare('DELETE FROM points_log WHERE member_id = ?').bind(me.id),
        env.MEM.prepare(`UPDATE cashouts SET pii = NULL WHERE member_id = ? AND status = 'rejected'`).bind(me.id),
        env.MEM.prepare('DELETE FROM sessions WHERE member_id = ?').bind(me.id),
        env.MEM.prepare('DELETE FROM members WHERE id = ?').bind(me.id),
      ]);
      return json({ ok: true }, 200, cors);
    }
    return json({ error: 'not found' }, 404, cors);
  }

  if (p.startsWith('/admin/')) {
    const A = await adminFrom(req, env);
    if (!A) return json({ error: 'admin' }, 401, cors);
    const d = req.method === 'POST' ? await body() : {};
    const id = Number(d.id || url.searchParams.get('id')) || 0;

    if (p === '/admin/overview' && req.method === 'GET') {
      const month = ymd(kst()).slice(0, 6);
      const [mc, ord, logs, cash, paid, sync, s] = await Promise.all([
        env.MEM.prepare('SELECT COUNT(*) n, SUM(created >= ?) today, SUM(created >= ?) week, SUM(status = \'blocked\') blocked FROM members')
          .bind(kstMidnight(), now() - 7 * 86400).first(),
        env.MEM.prepare(`SELECT COUNT(*) n,
            SUM(CASE WHEN o.confirmed_at IS NULL THEN ${POINTS_SQL} ELSE 0 END) pending,
            SUM(CASE WHEN o.confirmed_at IS NOT NULL THEN o.points ELSE 0 END) earned,
            SUM(CASE WHEN o.day LIKE ? THEN o.gmv ELSE 0 END) m_gmv,
            SUM(CASE WHEN o.day LIKE ? THEN o.commission ELSE 0 END) m_comm,
            SUM(CASE WHEN o.day LIKE ? THEN ${POINTS_SQL} ELSE 0 END) m_points
          FROM orders o`).bind(month + '%', month + '%', month + '%').first(),
        env.MEM.prepare('SELECT COALESCE(SUM(amount), 0) t, COALESCE(-SUM(CASE WHEN kind = \'expire\' THEN amount END), 0) expired FROM points_log').first(),
        env.MEM.prepare(`SELECT COUNT(*) n, COALESCE(SUM(amount), 0) amt FROM cashouts WHERE status = 'requested'`).first(),
        env.MEM.prepare(`SELECT COUNT(*) n, COALESCE(SUM(amount), 0) amt FROM cashouts WHERE status = 'paid' AND done_at >= ?`)
          .bind(Math.floor(Date.UTC(+month.slice(0, 4), +month.slice(4, 6) - 1, 1) / 1000) - 9 * 3600).first(),
        env.MEM.prepare('SELECT at, ok, note FROM sync_log ORDER BY at DESC LIMIT 5').all(),
        settings(env),
      ]);
      let site = null;
      if (env.DB) {
        const today = kst().toISOString().slice(0, 10);
        const { results } = await env.DB.prepare('SELECT type, SUM(n) n FROM daily WHERE day = ? GROUP BY type').bind(today).all();
        site = Object.fromEntries(results.map(r => [r.type, r.n]));
      }
      return json({ admin: A.name, members: mc, orders: ord, liability: num(ord.earned) + num(logs.t), expired: logs.expired,
        cashPending: cash, paidThisMonth: paid, sync: sync.results, settings: s, site,
        kakaoOn: !!env.KAKAO_REST_KEY, coupangOn: !!env.COUPANG_ACCESS_KEY, piiOn: !!env.PII_KEY }, 200, cors);
    }

    if (p === '/admin/members' && req.method === 'GET') {
      const q = String(url.searchParams.get('q') || '').trim();
      const { results } = await env.MEM.prepare(`SELECT id, nick, sub_id, created, last_login, status, is_admin FROM members
        ${q ? 'WHERE nick LIKE ? OR sub_id LIKE ? OR CAST(id AS TEXT) = ?' : ''} ORDER BY id DESC LIMIT 500`)
        .bind(...(q ? [`%${q}%`, `%${q}%`, q] : [])).all();
      const out = await Promise.all(results.map(async m => {
        const l = await ledger(env, m);
        return { ...m, orders: l.rows.length, ...l.sums };
      }));
      return json({ members: out }, 200, cors);
    }

    if (p === '/admin/member' && req.method === 'GET') {
      const m = await env.MEM.prepare('SELECT id, nick, sub_id, created, last_login, status, is_admin, memo FROM members WHERE id = ?').bind(id).first();
      if (!m) return json({ error: '없는 회원' }, 404, cors);
      return json({ member: m, ...(await ledger(env, m)) }, 200, cors);
    }

    if (p === '/admin/member/update' && req.method === 'POST') {
      const sets = [], vals = [];
      if (d.status === 'ok' || d.status === 'blocked') { sets.push('status = ?'); vals.push(d.status); }
      if (typeof d.memo === 'string') { sets.push('memo = ?'); vals.push(d.memo.slice(0, 500)); }
      if (!sets.length) return json({ error: '바꿀 내용 없음' }, 400, cors);
      await env.MEM.batch([env.MEM.prepare(`UPDATE members SET ${sets.join(', ')} WHERE id = ?`).bind(...vals, id),
        audit(env, A.name, d.status ? `회원 ${d.status === 'blocked' ? '정지' : '정지 해제'}` : '메모 수정', id, d.memo)]);
      return json({ ok: true }, 200, cors);
    }

    if (p === '/admin/adjust' && req.method === 'POST') {
      const amount = Math.trunc(num(d.amount)), memo = String(d.memo || '').trim().slice(0, 200);
      if (!amount || Math.abs(amount) > 1000000 || !memo) return json({ error: '포인트(±)와 사유를 넣어 주세요.' }, 400, cors);
      const m = await env.MEM.prepare('SELECT id FROM members WHERE id = ?').bind(id).first();
      if (!m) return json({ error: '없는 회원' }, 404, cors);
      await env.MEM.batch([
        env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, admin, at) VALUES (?, 'adjust', ?, ?, ?, ?)`).bind(id, amount, memo, A.name, now()),
        audit(env, A.name, '포인트 조정', id, `${amount > 0 ? '+' : ''}${amount}P · ${memo}`)]);
      return json({ ok: true }, 200, cors);
    }

    if (p === '/admin/cashouts' && req.method === 'GET') {
      const st = url.searchParams.get('status') || 'requested';
      const { results } = await env.MEM.prepare(`SELECT id, member_id, nick, amount, tax, net, bank, acct_mask, status, reason, requested_at, done_at, admin
        FROM cashouts ${st === 'all' ? '' : 'WHERE status = ?'} ORDER BY id DESC LIMIT 300`).bind(...(st === 'all' ? [] : [st])).all();
      return json({ cashouts: results }, 200, cors);
    }

    if (p === '/admin/cashout/reveal' && req.method === 'POST') {
      const c = await env.MEM.prepare('SELECT pii FROM cashouts WHERE id = ?').bind(id).first();
      if (!c || !c.pii) return json({ error: '계좌 정보가 없어요 (반려됐거나 보관 기간이 지남)' }, 404, cors);
      const info = await unseal(env, c.pii);
      await audit(env, A.name, '계좌 보기', id, null).run();
      return json(info, 200, cors);
    }

    if ((p === '/admin/cashout/done' || p === '/admin/cashout/reject') && req.method === 'POST') {
      const c = await env.MEM.prepare(`SELECT id, member_id, amount, tax, net FROM cashouts WHERE id = ? AND status = 'requested'`).bind(id).first();
      if (!c) return json({ error: '처리할 신청이 없어요 (이미 처리됨)' }, 409, cors);
      if (p.endsWith('/done')) {
        await env.MEM.batch([
          env.MEM.prepare(`UPDATE cashouts SET status = 'paid', done_at = ?, admin = ? WHERE id = ? AND status = 'requested'`).bind(now(), A.name, id),
          audit(env, A.name, '현금 지급 완료', id, `${c.net ?? c.amount}원 (세금 ${c.tax || 0}원)`)]);
      } else {
        const reason = String(d.reason || '').trim().slice(0, 200);
        if (!reason) return json({ error: '반려 사유를 넣어 주세요.' }, 400, cors);
        await env.MEM.batch([
          env.MEM.prepare(`UPDATE cashouts SET status = 'rejected', reason = ?, done_at = ?, admin = ?, pii = NULL WHERE id = ? AND status = 'requested'`)
            .bind(reason, now(), A.name, id),
          env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, admin, at) VALUES (?, 'refund', ?, ?, ?, ?)`)
            .bind(c.member_id, c.amount, `현금 교환 반려 #${id} · ${reason}`, A.name, now()),
          audit(env, A.name, '현금 교환 반려', id, reason)]);
      }
      return json({ ok: true }, 200, cors);
    }

    if (p === '/admin/settings') {
      if (req.method === 'POST') {
        const prev = await settings(env);
        const v = { share: num(d.share), min_cashout: Math.trunc(num(d.min_cashout)), expire_days: Math.trunc(num(d.expire_days)), collect_rrn: d.collect_rrn ? 1 : 0,
          withholding_rate: num(d.withholding_rate), withholding_free_upto: Math.trunc(num(d.withholding_free_upto)),
          signup_bonus: d.signup_bonus === undefined ? prev.signup_bonus : Math.trunc(num(d.signup_bonus)) };
        if (!(v.share > 0 && v.share <= 1) || v.min_cashout < 1000 || v.min_cashout > 1000000 || v.expire_days < 30 || v.expire_days > 1825
            || !(v.withholding_rate >= 0 && v.withholding_rate <= 0.5) || !(v.withholding_free_upto >= 0 && v.withholding_free_upto <= 10000000)
            || !(v.signup_bonus >= 0 && v.signup_bonus <= 100000))
          return json({ error: '비율 1~100%, 최소 교환 1,000~1,000,000P, 유효기간 30~1,825일, 원천징수율 0~50%, 가입 축하 0~100,000P' }, 400, cors);
        const before = prev;
        await env.MEM.batch([
          ...Object.entries(v).map(([k, val]) => env.MEM.prepare('INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v').bind(k, String(val))),
          audit(env, A.name, '설정 변경', null, JSON.stringify({ before, after: v }))]);
      }
      return json(await settings(env), 200, cors);
    }

    if (p === '/admin/export' && req.method === 'GET') {
      // 지급 내역 (세금 신고·지급명세서용). 그 달에 '지급 완료'한 건. 계좌·주민번호를 풀어 넣으니 기록을 남김
      const mo = String(url.searchParams.get('month') || kst().toISOString().slice(0, 7));
      if (!/^\d{4}-\d{2}$/.test(mo)) return json({ error: '월은 2026-09 형식' }, 400, cors);
      const from = Math.floor(Date.UTC(+mo.slice(0, 4), +mo.slice(5, 7) - 1, 1) / 1000) - 9 * 3600;
      const to = Math.floor(Date.UTC(+mo.slice(0, 4), +mo.slice(5, 7), 1) / 1000) - 9 * 3600;
      const { results } = await env.MEM.prepare(`SELECT * FROM cashouts WHERE status = 'paid' AND done_at >= ? AND done_at < ? ORDER BY done_at`).bind(from, to).all();
      const day = t => new Date((t + 9 * 3600) * 1000).toISOString().slice(0, 10);
      const rows = [['지급일', '신청번호', '회원번호', '닉네임', '예금주', '은행', '계좌번호', '주민등록번호', '지급액(교환 포인트)', '소득세', '지방소득세', '원천징수 합계', '실지급액', '처리자']];
      for (const c of results) {
        let i = {};
        if (c.pii) { try { i = await unseal(env, c.pii); } catch { i = {}; } }
        rows.push([day(c.done_at), c.id, c.member_id, c.nick, i.holder || '(보관 기간 지남)', c.bank, i.account || c.acct_mask, i.rrn || '',
          c.amount, c.tax_income || 0, c.tax_local || 0, c.tax || 0, c.net ?? c.amount, c.admin]);
      }
      const sum = k => results.reduce((a, c) => a + (c[k] || 0), 0);
      rows.push(['합계', '', '', '', '', '', '', '', sum('amount'), sum('tax_income'), sum('tax_local'), sum('tax'),
        results.reduce((a, c) => a + (c.net ?? c.amount), 0), '']);
      await audit(env, A.name, '지급 내역 내보내기', mo, `${results.length}건`).run();
      return new Response(csv(rows), { headers: { ...cors, 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store',
        'Content-Disposition': `attachment; filename="hyetaekzone-payouts-${mo}.csv"` } });
    }

    if (p === '/admin/report' && req.method === 'GET') {
      // 아침 메일용 요약 (scripts/points_report.py)
      const since = Number(url.searchParams.get('since')) || now() - 86400;
      const [mem, ord, all, cash, last, lastOk, lg] = await Promise.all([
        env.MEM.prepare('SELECT COUNT(*) n, COALESCE(SUM(created >= ?), 0) new, COALESCE(SUM(terms_ver IS NULL OR terms_ver != ?), 0) noterms FROM members').bind(since, TERMS_VER).first(),
        env.MEM.prepare('SELECT COUNT(*) n, COALESCE(SUM(gmv), 0) gmv, COUNT(DISTINCT sub_id) buyers FROM orders WHERE created_at >= ?').bind(since).first(),
        env.MEM.prepare('SELECT COUNT(*) n FROM orders').first(),
        env.MEM.prepare(`SELECT COUNT(*) n, COALESCE(SUM(amount), 0) amt, MIN(requested_at) oldest FROM cashouts WHERE status = 'requested'`).first(),
        env.MEM.prepare('SELECT at, ok, note FROM sync_log ORDER BY at DESC LIMIT 1').first(),
        env.MEM.prepare('SELECT at FROM sync_log WHERE ok = 1 ORDER BY at DESC LIMIT 1').first(),
        env.MEM.prepare(`SELECT COALESCE(SUM(amount), 0) t FROM points_log`).first(),
      ]);
      const earned = await env.MEM.prepare('SELECT COALESCE(SUM(points), 0) t FROM orders WHERE confirmed_at IS NOT NULL').first();
      return json({ since, members: mem, newOrders: ord, firstEver: ord.n > 0 && ord.n === all.n, cashPending: cash, lastSync: last,
        syncStale: !lastOk || lastOk.at < now() - 36 * 3600, liability: earned.t + lg.t, settings: await settings(env) }, 200, cors);
    }

    if (p === '/admin/audit' && req.method === 'GET') {
      const { results } = await env.MEM.prepare('SELECT at, admin, action, target, detail FROM audit ORDER BY id DESC LIMIT 200').all();
      return json({ audit: results }, 200, cors);
    }

    if (p === '/admin/sync' && req.method === 'POST') {
      const r = await syncOrders(env);
      await audit(env, A.name, '쿠팡 지금 읽기', null, r.note).run();
      return json(r, 200, cors);
    }

    if (p === '/admin/make-admin' && req.method === 'POST') {
      if (!A.key) return json({ error: '관리 키로만 할 수 있어요' }, 403, cors);
      const on = d.on === false ? 0 : 1;
      const r = await env.MEM.prepare('UPDATE members SET is_admin = ? WHERE id = ?').bind(on, id).run();
      await audit(env, A.name, on ? '관리자 지정' : '관리자 해제', id, null).run();
      return json({ ok: r.meta.changes === 1 }, 200, cors);
    }

    // 예전 스크립트 호환: 회원 요약 목록
    return json({ error: 'not found' }, 404, cors);
  }
  return null;
}
