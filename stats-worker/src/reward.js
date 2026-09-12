/* 카카오 로그인 · 쿠팡 구매 포인트 적립 · 현금 교환 · 관리자
   - 로그인하면 회원마다 쿠팡 링크 이름표(subId, 예: hzm00001)가 생깁니다.
   - 사이트의 쿠팡 링크를 누를 때 이름표를 바꿔 끼워, 쿠팡 주문 리포트에서 누구 링크로 산 건지 알 수 있습니다.
     (쿠팡은 산 사람이 아니라 "어느 링크로 들어왔는지"만 알려줍니다. 링크를 누르고 24시간 안의 구매가 잡힙니다)
   - 포인트 = 그 주문으로 우리가 받는 쿠팡 수수료 × 적립 비율(설정, 기본 10%). 1P = 1원.
   - 매일 17:00(한국) 쿠팡 리포트를 읽어 회원 주문을 옮기고, 구매한 달의 다음 달 25일에 '적립 완료'로 확정.
     그 전에는 '적립 예정', 전액 취소·반품이면 '적립 취소'. 적립 완료 후 1년(설정)이 지나면 소멸.
   - 잔액이 1만 P(설정) 이상이면 현금 교환 신청 → 관리자가 계좌로 보내고 '지급 완료' (반려하면 포인트 복구).

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
const DEFAULTS = { share: 0.10, min_cashout: 10000, expire_days: 365 };
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
    `SELECT m.id, m.nick, m.sub_id, m.is_admin, m.status FROM sessions s JOIN members m ON m.id = s.member_id
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
  const q = `startDate=${ymd(kst(29))}&endDate=${ymd(kst())}`;      // 쿠팡은 한 번에 최대 30일
  const mine = r => String(r.subId || '').startsWith(SUB_PREFIX);
  try {
    const [orders, cancels, s] = await Promise.all([cpReport(env, 'orders', q), cpReport(env, 'cancels', q), settings(env)]);
    const st = [];
    for (const r of orders.filter(mine)) {
      st.push(env.MEM.prepare(
        `INSERT INTO orders (order_id, product_id, sub_id, day, name, qty, gmv, commission, share, confirm_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(order_id, product_id) DO UPDATE SET sub_id = excluded.sub_id, day = excluded.day, name = excluded.name,
           qty = excluded.qty, gmv = excluded.gmv, commission = excluded.commission, confirm_on = excluded.confirm_on
         WHERE orders.confirmed_at IS NULL`
      ).bind(String(r.orderId), String(r.productId), r.subId, String(r.date), String(r.productName || '').slice(0, 120),
        num(r.quantity) || 1, Math.round(Math.abs(num(r.gmv))), Math.round(Math.abs(num(r.commission))), s.share, confirmOn(String(r.date))));
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
    + COALESCE((SELECT SUM(amount) FROM points_log WHERE member_id = m.id AND kind = 'adjust' AND amount > 0 AND at <= ?), 0) AS old,
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
    env.MEM.prepare(`SELECT o.order_id, o.day, o.name, o.qty, o.gmv, o.commission, o.share, o.confirm_on, o.confirmed_at, o.points,
        COALESCE((SELECT SUM(c.gmv) FROM cancels c WHERE c.order_id = o.order_id AND c.product_id = o.product_id), 0) AS cancel
      FROM orders o WHERE o.sub_id = ? ORDER BY o.day DESC, o.order_id DESC LIMIT 500`).bind(m.sub_id).all(),
    env.MEM.prepare('SELECT kind, amount, memo, at FROM points_log WHERE member_id = ? ORDER BY at DESC, id DESC LIMIT 300').bind(m.id).all(),
    env.MEM.prepare(`SELECT id, amount, bank, acct_mask, status, reason, requested_at, done_at FROM cashouts
      WHERE member_id = ? ORDER BY id DESC LIMIT 100`).bind(m.id).all(),
  ]);
  const sums = { pending: 0, earned: 0, canceled: 0, used: 0, expired: 0, balance: 0 };
  const rows = ord.results.map(o => {
    let status, p;
    if (o.confirmed_at) { p = o.points; status = p > 0 ? 'done' : 'canceled'; }
    else if (o.gmv - o.cancel <= 0) { p = 0; status = 'canceled'; }
    else { p = orderPoints(o); status = 'pending'; }
    const full = orderPoints({ ...o, cancel: 0 });
    if (status === 'done') sums.earned += p; else if (status === 'pending') sums.pending += p; else sums.canceled += full;
    return { day: o.day, name: o.name, qty: o.qty, gmv: o.gmv, cancel: o.cancel, commission: o.commission,
             points: status === 'canceled' ? full : p, status, confirmOn: o.confirm_on };
  });
  let logSum = 0;
  for (const l of log.results) {
    logSum += l.amount;
    if (l.kind === 'expire') sums.expired -= l.amount;
  }
  sums.used = cash.results.filter(c => c.status !== 'rejected').reduce((a, c) => a + c.amount, 0);
  const allLog = await env.MEM.prepare('SELECT COALESCE(SUM(amount), 0) AS t FROM points_log WHERE member_id = ?').bind(m.id).first();
  sums.balance = sums.earned + allLog.t;
  return { sums, rows, log: log.results, cashouts: cash.results };
}

const BANK_RE = /^[가-힣A-Za-z0-9() ]{2,20}$/;

/* ── 요청 처리. 이 모듈 경로가 아니면 null ── */
export async function handleReward(req, env, ctx, url, cors, allowed) {
  const p = url.pathname;
  const back = BACK[url.searchParams.get('back')] ?? BACK.my;
  const body = async () => { try { return await req.json(); } catch { return {}; } };

  if (p === '/rw/status' && req.method === 'GET') {
    const s = await settings(env);
    return json({ on: !!env.KAKAO_REST_KEY, share: s.share, min: s.min_cashout, expireDays: s.expire_days }, 200, cors);
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
    const fail = why => new Response(null, { status: 302, headers: { Location: dest + '#rw=fail-' + why, 'Set-Cookie': clear } });
    if (url.searchParams.get('error')) return fail('cancel');           // 동의 화면에서 취소
    if (!state || state !== url.searchParams.get('state') || !url.searchParams.get('code')) return fail('state');

    const form = new URLSearchParams({ grant_type: 'authorization_code', client_id: env.KAKAO_REST_KEY,
      redirect_uri: url.origin + '/auth/kakao/callback', code: url.searchParams.get('code') });
    if (env.KAKAO_CLIENT_SECRET) form.set('client_secret', env.KAKAO_CLIENT_SECRET);
    const tr = await fetch('https://kauth.kakao.com/oauth/token', { method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8' }, body: form });
    const tok = await tr.json().catch(() => ({}));
    if (!tok.access_token) return fail('token');
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
        share: s.share, min: s.min_cashout, expireDays: s.expire_days, ...led, syncedAt: last ? last.at : null }, 200, cors);
    }

    if (p === '/me/cashout' && req.method === 'POST') {
      if (me.status !== 'ok') return json({ error: '이용이 멈춘 계정이에요. 고객센터로 문의해 주세요.' }, 403, cors);
      const d = await body();
      const holder = String(d.holder || '').trim(), bank = String(d.bank || '').trim(), account = String(d.account || '').replace(/[\s-]/g, '');
      if (!d.agree) return json({ error: '계좌 정보 수집에 동의해 주세요.' }, 400, cors);
      if (!/^[가-힣A-Za-z ]{2,20}$/.test(holder)) return json({ error: '예금주 이름을 확인해 주세요.' }, 400, cors);
      if (!BANK_RE.test(bank)) return json({ error: '은행을 골라 주세요.' }, 400, cors);
      if (!/^\d{8,16}$/.test(account)) return json({ error: '계좌번호는 숫자 8~16자리로 넣어 주세요.' }, 400, cors);
      const [s, led] = await Promise.all([settings(env), ledger(env, me)]);
      if (led.cashouts.some(c => c.status === 'requested')) return json({ error: '이미 신청한 교환이 처리 중이에요.' }, 409, cors);
      const amount = led.sums.balance;
      if (amount < s.min_cashout) return json({ error: `${s.min_cashout.toLocaleString('ko-KR')}P부터 바꿀 수 있어요.` }, 400, cors);
      const t = now();
      try {
        await env.MEM.batch([
          env.MEM.prepare(`INSERT INTO cashouts (member_id, nick, amount, bank, acct_mask, pii, status, requested_at)
            VALUES (?, ?, ?, ?, ?, ?, 'requested', ?)`).bind(me.id, me.nick, amount, bank, '****' + account.slice(-4),
            await seal(env, { holder, bank, account }), t),
          env.MEM.prepare(`INSERT INTO points_log (member_id, kind, amount, memo, at)
            SELECT ?, 'cashout', ?, '현금 교환 신청 #' || id, ? FROM cashouts WHERE member_id = ? AND status = 'requested'`)
            .bind(me.id, -amount, t, me.id),
        ]);
      } catch { return json({ error: '이미 신청한 교환이 처리 중이에요.' }, 409, cors); }
      return json({ ok: true, amount }, 200, cors);
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
      const { results } = await env.MEM.prepare(`SELECT id, member_id, nick, amount, bank, acct_mask, status, reason, requested_at, done_at, admin
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
      const c = await env.MEM.prepare(`SELECT id, member_id, amount FROM cashouts WHERE id = ? AND status = 'requested'`).bind(id).first();
      if (!c) return json({ error: '처리할 신청이 없어요 (이미 처리됨)' }, 409, cors);
      if (p.endsWith('/done')) {
        await env.MEM.batch([
          env.MEM.prepare(`UPDATE cashouts SET status = 'paid', done_at = ?, admin = ? WHERE id = ? AND status = 'requested'`).bind(now(), A.name, id),
          audit(env, A.name, '현금 지급 완료', id, `${c.amount}원`)]);
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
        const v = { share: num(d.share), min_cashout: Math.trunc(num(d.min_cashout)), expire_days: Math.trunc(num(d.expire_days)) };
        if (!(v.share > 0 && v.share <= 1) || v.min_cashout < 1000 || v.min_cashout > 1000000 || v.expire_days < 30 || v.expire_days > 1825)
          return json({ error: '비율 1~100%, 최소 교환 1,000~1,000,000P, 유효기간 30~1,825일' }, 400, cors);
        const before = await settings(env);
        await env.MEM.batch([
          ...Object.entries(v).map(([k, val]) => env.MEM.prepare('INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v').bind(k, String(val))),
          audit(env, A.name, '설정 변경', null, JSON.stringify({ before, after: v }))]);
      }
      return json(await settings(env), 200, cors);
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
