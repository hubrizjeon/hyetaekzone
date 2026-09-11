/* 카카오 로그인 · 쿠팡 구매 포인트 적립
   - 로그인하면 회원마다 쿠팡 링크 이름표(subId, 예: hzm00001)가 생깁니다.
   - 사이트의 쿠팡 링크를 누를 때 이름표를 바꿔 끼워, 쿠팡 주문 리포트에서 누구 링크로 산 건지 알 수 있습니다.
     (쿠팡은 산 사람이 아니라 "어느 링크로 들어왔는지"만 알려줍니다. 링크를 누르고 24시간 안의 구매가 잡힙니다)
   - 매일 17:00(한국) 쿠팡 리포트를 읽어 회원 주문을 옮기고, 구매한 달의 다음 달 25일이 지나면 '적립 완료'로 확정합니다.
     그 전에는 '적립 예정', 취소·반품되면 '적립 취소'.

   GET  /rw/status                 적립 기능 켜짐 여부 {on}
   GET  /auth/kakao?back=my        카카오 로그인 시작 → 끝나면 사이트로 돌아가며 #login=<토큰>
   GET  /auth/kakao/callback       (카카오가 부름)
   GET  /me                        내 적립 내역 — Authorization: Bearer <토큰>
   POST /me/logout                 로그아웃
   POST /me/delete                 탈퇴 (회원·주문 기록 삭제)
   GET  /admin/members             회원별 적립 현황 — Authorization: Bearer <STATS_KEY>
   POST /admin/sync                쿠팡 리포트 지금 읽기 — 같은 키
   비밀값: KAKAO_REST_KEY, KAKAO_CLIENT_SECRET(선택), COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
*/
const RATE = 0.01;                 // 구매금액의 1%
const SESSION_DAYS = 90;
const SUB_PREFIX = 'hzm';
const BACK = { my: 'my.html', hotdeal: 'hotdeal.html', main: '' };
const CP_HOST = 'https://api-gateway.coupang.com';
const CP_BASE = '/v2/providers/affiliate_open_api/apis/openapi/v1';

const now = () => Math.floor(Date.now() / 1000);
const kst = (offsetDays = 0) => new Date(Date.now() + 9 * 3600e3 - offsetDays * 86400e3);
const ymd = d => d.toISOString().slice(0, 10).replace(/-/g, '');
const siteUrl = env => env.SITE_URL || 'https://hubrizjeon.github.io/hyetaekzone/';
const points = gmv => Math.max(0, Math.floor(gmv * RATE));
const json = (data, status, headers) =>
  new Response(JSON.stringify(data), { status, headers: { ...headers, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });

function confirmOn(day) {          // 'YYYYMMDD' → 다음 달 25일 'YYYY-MM-25'
  let y = +day.slice(0, 4), m = +day.slice(4, 6) + 1;
  if (m > 12) { m = 1; y += 1; }
  return `${y}-${String(m).padStart(2, '0')}-25`;
}

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

async function memberFromAuth(req, env) {
  const t = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
  if (!t || t.length < 20) return null;
  return env.MEM.prepare(
    `SELECT m.id, m.nick, m.sub_id FROM sessions s JOIN members m ON m.id = s.member_id
     WHERE s.token_hash = ? AND s.exp > ?`).bind(await sha256(t), now()).first();
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
    const [orders, cancels] = await Promise.all([cpReport(env, 'orders', q), cpReport(env, 'cancels', q)]);
    const st = [];
    for (const r of orders.filter(mine)) {
      st.push(env.MEM.prepare(
        `INSERT INTO orders (order_id, product_id, sub_id, day, name, qty, gmv, confirm_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(order_id, product_id) DO UPDATE SET sub_id = excluded.sub_id, day = excluded.day, name = excluded.name,
           qty = excluded.qty, gmv = excluded.gmv, confirm_on = excluded.confirm_on WHERE orders.confirmed_at IS NULL`
      ).bind(String(r.orderId), String(r.productId), r.subId, String(r.date), String(r.productName || '').slice(0, 120),
        Number(r.quantity) || 1, Math.round(Math.abs(Number(r.gmv) || 0)), confirmOn(String(r.date))));
    }
    for (const r of cancels.filter(mine)) {
      st.push(env.MEM.prepare(
        `INSERT INTO cancels (order_id, product_id, day, gmv) VALUES (?, ?, ?, ?)
         ON CONFLICT(order_id, product_id, day) DO UPDATE SET gmv = excluded.gmv`
      ).bind(String(r.orderId), String(r.productId), String(r.date), Math.round(Math.abs(Number(r.gmv) || 0))));
    }
    // 확정: 확정일이 된 주문은 (구매금액 − 취소금액)의 1%로 포인트를 고정합니다
    const today = kst().toISOString().slice(0, 10);
    st.push(env.MEM.prepare(
      `UPDATE orders SET confirmed_at = ?, points = MAX(0, CAST((gmv - COALESCE((SELECT SUM(c.gmv) FROM cancels c
         WHERE c.order_id = orders.order_id AND c.product_id = orders.product_id), 0)) * ? AS INTEGER))
       WHERE confirmed_at IS NULL AND confirm_on <= ?`).bind(now(), RATE, today));
    const note = `주문 ${orders.filter(mine).length} · 취소 ${cancels.filter(mine).length} (전체 주문 ${orders.length})`;
    st.push(env.MEM.prepare('INSERT OR REPLACE INTO sync_log (at, ok, note) VALUES (?, 1, ?)').bind(now(), note));
    await env.MEM.batch(st);
    return { ok: true, note };
  } catch (e) {
    await env.MEM.prepare('INSERT OR REPLACE INTO sync_log (at, ok, note) VALUES (?, 0, ?)').bind(now(), String(e.message).slice(0, 200)).run();
    return { ok: false, note: String(e.message) };
  }
}

/* 회원 한 명의 내역 — 상태: done 적립 완료 / pending 적립 예정 / canceled 적립 취소 */
async function ledger(env, subId) {
  const { results } = await env.MEM.prepare(
    `SELECT o.day, o.name, o.qty, o.gmv, o.confirm_on, o.confirmed_at, o.points,
            COALESCE((SELECT SUM(c.gmv) FROM cancels c WHERE c.order_id = o.order_id AND c.product_id = o.product_id), 0) AS cancel
     FROM orders o WHERE o.sub_id = ? ORDER BY o.day DESC, o.order_id DESC LIMIT 300`).bind(subId).all();
  const sums = { pending: 0, done: 0, canceled: 0 };
  const rows = results.map(o => {
    const left = o.gmv - o.cancel;
    let status, p;
    if (o.confirmed_at) { p = o.points; status = p > 0 ? 'done' : 'canceled'; }
    else if (left <= 0) { p = 0; status = 'canceled'; }
    else { p = points(left); status = 'pending'; }
    sums[status] += status === 'canceled' ? points(o.gmv) : p;
    return { day: o.day, name: o.name, qty: o.qty, gmv: o.gmv, cancel: o.cancel, points: status === 'canceled' ? points(o.gmv) : p,
             status, confirmOn: o.confirm_on };
  });
  return { sums, rows };
}

/* ── 요청 처리. 이 모듈 경로가 아니면 null ── */
export async function handleReward(req, env, ctx, url, cors, allowed) {
  const p = url.pathname;
  const back = BACK[url.searchParams.get('back')] ?? BACK.my;

  if (p === '/rw/status' && req.method === 'GET') {
    return json({ on: !!env.KAKAO_REST_KEY, rate: RATE }, 200, cors);
  }

  if (p === '/auth/kakao' && req.method === 'GET') {
    if (!env.KAKAO_REST_KEY) return Response.redirect(siteUrl(env) + back + '#rw=off', 302);
    const state = randomToken().slice(0, 24);
    const q = new URLSearchParams({ client_id: env.KAKAO_REST_KEY, redirect_uri: url.origin + '/auth/kakao/callback',
      response_type: 'code', state });
    return new Response(null, { status: 302, headers: {
      Location: 'https://kauth.kakao.com/oauth/authorize?' + q,
      'Set-Cookie': `hz_state=${state}.${url.searchParams.get('back') || 'my'}; Path=/auth; Max-Age=600; HttpOnly; Secure; SameSite=Lax` } });
  }

  if (p === '/auth/kakao/callback' && req.method === 'GET') {
    const [state, b] = cookie(req, 'hz_state').split('.');
    const dest = siteUrl(env) + (BACK[b] ?? BACK.my);
    const fail = why => new Response(null, { status: 302, headers: { Location: dest + '#rw=fail-' + why,
      'Set-Cookie': 'hz_state=; Path=/auth; Max-Age=0; HttpOnly; Secure; SameSite=Lax' } });
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
    await env.MEM.batch([
      env.MEM.prepare('INSERT INTO sessions (token_hash, member_id, exp) VALUES (?, ?, ?)').bind(await sha256(token), m.id, t + SESSION_DAYS * 86400),
      env.MEM.prepare('DELETE FROM sessions WHERE exp < ?').bind(t),
    ]);
    return new Response(null, { status: 302, headers: { Location: dest + '#login=' + token,
      'Set-Cookie': 'hz_state=; Path=/auth; Max-Age=0; HttpOnly; Secure; SameSite=Lax' } });
  }

  if (p.startsWith('/me')) {
    if (!allowed) return json({ error: 'forbidden' }, 403, cors);
    const me = await memberFromAuth(req, env);
    if (!me) return json({ error: 'login' }, 401, cors);
    if (p === '/me' && req.method === 'GET') {
      const [{ sums, rows }, last] = await Promise.all([ledger(env, me.sub_id),
        env.MEM.prepare('SELECT at FROM sync_log WHERE ok = 1 ORDER BY at DESC LIMIT 1').first()]);
      return json({ nick: me.nick, subId: me.sub_id, rate: RATE, sums, rows, syncedAt: last ? last.at : null }, 200, cors);
    }
    if (p === '/me/logout' && req.method === 'POST') {
      const t = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
      await env.MEM.prepare('DELETE FROM sessions WHERE token_hash = ?').bind(await sha256(t)).run();
      return json({ ok: true }, 200, cors);
    }
    if (p === '/me/delete' && req.method === 'POST') {
      await env.MEM.batch([
        env.MEM.prepare('DELETE FROM cancels WHERE (order_id, product_id) IN (SELECT order_id, product_id FROM orders WHERE sub_id = ?)').bind(me.sub_id),
        env.MEM.prepare('DELETE FROM orders WHERE sub_id = ?').bind(me.sub_id),
        env.MEM.prepare('DELETE FROM sessions WHERE member_id = ?').bind(me.id),
        env.MEM.prepare('DELETE FROM members WHERE id = ?').bind(me.id),
      ]);
      return json({ ok: true }, 200, cors);
    }
    return json({ error: 'not found' }, 404, cors);
  }

  if (p.startsWith('/admin/')) {
    if (!env.STATS_KEY || req.headers.get('Authorization') !== `Bearer ${env.STATS_KEY}`) return new Response('unauthorized', { status: 401 });
    if (p === '/admin/sync' && req.method === 'POST') return json(await syncOrders(env), 200, {});
    if (p === '/admin/members' && req.method === 'GET') {
      const { results } = await env.MEM.prepare('SELECT id, nick, sub_id, created, last_login FROM members ORDER BY id').all();
      const out = [];
      for (const m of results) out.push({ ...m, ...(await ledger(env, m.sub_id)).sums });
      const logs = (await env.MEM.prepare('SELECT at, ok, note FROM sync_log ORDER BY at DESC LIMIT 5').all()).results;
      return json({ members: out, sync: logs }, 200, {});
    }
  }
  return null;
}
