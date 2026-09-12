/* 혜택존 방문·클릭 집계 + 쿠팡 상품 검색
   개인정보는 받지도 저장하지도 않습니다 — IP·쿠키·기기 ID 없이
   "날짜 · 페이지 · 종류 · 이름표" 별 개수만 셉니다. 검색어도 집계에 남기지 않습니다.

   POST /e           {page, type, label}   페이지가 보내는 기록 (sendBeacon, text/plain)
   GET  /stats?days=7                      집계 조회 — Authorization: Bearer <STATS_KEY>
   /rw/*, /auth/*, /me*, /admin/*          카카오 로그인·포인트 적립 (src/reward.js, D1 hyetaekzone-members)
   GET  /search?q=물티슈                    쿠팡 상품 검색 (제휴 링크) — 혜택존 페이지에서만 호출 가능
        쿠팡 키는 Worker 비밀값 COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY (scripts/set-worker-secrets.sh)
        같은 검색어는 12시간 동안 저장해 둔 결과를 씁니다 (쿠팡 호출 횟수 제한 대비).
        쿠팡이 거절하면 10분 쉬고, 그동안은 쿠팡 검색 결과 페이지로 가는 제휴 링크만 줍니다.
*/
import { handleReward, syncOrders, expirePoints } from './reward.js';

const ORIGINS = ['https://hubrizjeon.github.io', 'https://benefits.hubriz.io'];
const TYPES = new Set(['visit', 'card', 'toc', 'source', 'share', 'home', 'buy', 'filter', 'sort', 'more', 'cat', 'search', 'rw']);
const PAGES = new Set(['main', 'hotdeal']);

const CP_HOST = 'https://api-gateway.coupang.com';
const CP_BASE = '/v2/providers/affiliate_open_api/apis/openapi/v1';
const SUB_ID = 'hyetaekzone';
const KEEP_OK = 12 * 3600;      // 검색 결과 저장 시간 (초)
const KEEP_FALLBACK = 3600;     // 링크만 준 결과는 1시간 뒤 다시 시도
const COOLDOWN = 600;           // 쿠팡이 거절하면 10분 쉼

/* 날짜는 브라우저가 아니라 서버 기준 한국 시간 — 휴대폰 시계가 틀려도 집계가 흔들리지 않게 */
const kstDay = (offsetDays = 0) =>
  new Date(Date.now() + 9 * 3600e3 - offsetDays * 86400e3).toISOString().slice(0, 10);
const now = () => Math.floor(Date.now() / 1000);

function count(env, page, type, label) {
  return env.DB.prepare(
    `INSERT INTO daily (day, page, type, label, n) VALUES (?, ?, ?, ?, 1)
     ON CONFLICT(day, page, type, label) DO UPDATE SET n = n + 1`
  ).bind(kstDay(), page, type, label).run();
}

async function cpCall(env, method, path, query = '', body) {
  const d = new Date().toISOString();                         // 2026-09-11T09:45:10.123Z
  const dt = d.slice(2, 4) + d.slice(5, 7) + d.slice(8, 10) + 'T' + d.slice(11, 13) + d.slice(14, 16) + d.slice(17, 19) + 'Z';
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(env.COUPANG_SECRET_KEY),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = [...new Uint8Array(await crypto.subtle.sign('HMAC', key, enc.encode(dt + method + path + query)))]
    .map(b => b.toString(16).padStart(2, '0')).join('');
  const r = await fetch(CP_HOST + path + (query ? '?' + query : ''), {
    method,
    headers: {
      Authorization: `CEA algorithm=HmacSHA256, access-key=${env.COUPANG_ACCESS_KEY}, signed-date=${dt}, signature=${sig}`,
      'Content-Type': 'application/json;charset=UTF-8',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  let j = null;
  try { j = await r.json(); } catch { /* 빈 응답 */ }
  return { ok: r.status === 200 && j && String(j.rCode) === '0', status: r.status, j };
}

const yes = v => v === true || v === 'true' || v === 'True';
const https = u => (typeof u === 'string' && u.startsWith('https://')) ? u : '';
const plainSearch = q => 'https://www.coupang.com/np/search?q=' + encodeURIComponent(q);

async function cacheGet(env, q) {
  const row = await env.DB.prepare('SELECT body, exp FROM search_cache WHERE q = ?').bind(q).first();
  return row && row.exp > now() ? row.body : null;
}
const cachePut = (env, q, body, keep) =>
  env.DB.prepare(`INSERT INTO search_cache (q, body, exp) VALUES (?, ?, ?)
                  ON CONFLICT(q) DO UPDATE SET body = excluded.body, exp = excluded.exp`)
    .bind(q, body, now() + keep).run();

async function search(env, q) {
  const keys = env.COUPANG_ACCESS_KEY && env.COUPANG_SECRET_KEY;
  if (!keys) return { out: { q, items: [], more: plainSearch(q), aff: false }, keep: 0, label: 'nokey' };

  const resting = await cacheGet(env, '__cooldown__');
  if (!resting) {
    const query = `keyword=${encodeURIComponent(q)}&limit=10&subId=${SUB_ID}`;
    const r = await cpCall(env, 'GET', CP_BASE + '/products/search', query);
    if (r.ok && r.j.data) {
      const items = (r.j.data.productData || []).map(p => ({
        name: String(p.productName || '').slice(0, 120),
        price: Number(p.productPrice) || 0,
        img: https(p.productImage),
        url: https(p.productUrl),
        cat: String(p.categoryName || '').slice(0, 20),
        rocket: yes(p.isRocket),
        free: yes(p.isFreeShipping),
      })).filter(p => p.name && p.price > 0 && p.url);
      const more = https(r.j.data.landingUrl);
      return { out: { q, items, more: more || plainSearch(q), aff: !!more }, keep: KEEP_OK, label: items.length ? 'result' : 'empty' };
    }
    await cachePut(env, '__cooldown__', String(r.status), COOLDOWN);
  }
  // 상품 목록은 못 받았어도 쿠팡 검색 결과 페이지는 제휴 링크로 연결
  const d = await cpCall(env, 'POST', CP_BASE + '/deeplink', '', { coupangUrls: [plainSearch(q)], subId: SUB_ID });
  const link = d.ok && d.j.data && d.j.data[0] ? https(d.j.data[0].landingUrl || d.j.data[0].shortenUrl) : '';
  return { out: { q, items: [], more: link || plainSearch(q), aff: !!link }, keep: link ? KEEP_FALLBACK : 0, label: link ? 'link' : 'fail' };
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const origin = req.headers.get('Origin') || '';
    const allowed = ORIGINS.includes(origin) || /^http:\/\/localhost(:\d+)?$/.test(origin);
    const cors = { 'Access-Control-Allow-Origin': allowed ? origin : ORIGINS[0], Vary: 'Origin' };

    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...cors,
        'Access-Control-Allow-Methods': 'GET, POST', 'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400' } });
    }

    if (url.pathname === '/e' && req.method === 'POST') {
      if (!allowed) return new Response('forbidden', { status: 403, headers: cors });
      let d;
      try { d = JSON.parse(await req.text()); } catch { return new Response('bad', { status: 400, headers: cors }); }
      const type = String(d.type || '');
      const label = String(d.label || '').trim().slice(0, 80);
      const page = PAGES.has(d.page) ? d.page : 'main';
      if (!TYPES.has(type) || !label) return new Response('bad', { status: 400, headers: cors });
      await count(env, page, type, label);
      return new Response(null, { status: 204, headers: cors });
    }

    if (url.pathname === '/search' && req.method === 'GET') {
      const headers = { ...cors, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' };
      if (!allowed) return new Response('{"error":"forbidden"}', { status: 403, headers });
      const q = String(url.searchParams.get('q') || '').replace(/\s+/g, ' ').trim().toLowerCase().slice(0, 40);
      if (!q || q.startsWith('__')) return new Response('{"error":"검색어를 입력해 주세요"}', { status: 400, headers });

      let body = await cacheGet(env, q), label = 'cache';
      if (!body) {
        const r = await search(env, q);
        body = JSON.stringify(r.out);
        label = r.label;
        if (r.keep) ctx.waitUntil(cachePut(env, q, body, r.keep));
      }
      ctx.waitUntil(count(env, 'hotdeal', 'search', label));   // 검색어는 남기지 않고 결과 종류만 셉니다
      return new Response(body, { headers });
    }

    if (url.pathname === '/stats' && req.method === 'GET') {
      if (!env.STATS_KEY || req.headers.get('Authorization') !== `Bearer ${env.STATS_KEY}`) {
        return new Response('unauthorized', { status: 401 });
      }
      const days = Math.min(90, Math.max(1, parseInt(url.searchParams.get('days') || '7', 10) || 7));
      const since = kstDay(days - 1);
      const { results } = await env.DB.prepare(
        'SELECT day, page, type, label, n FROM daily WHERE day >= ? ORDER BY day DESC, n DESC'
      ).bind(since).all();
      return Response.json({ since, rows: results });
    }

    const rw = await handleReward(req, env, ctx, url, cors, allowed);
    if (rw) return rw;

    return new Response('hyetaekzone stats', { status: 404 });
  },

  // 매시 5분 — 쿠팡 주문 리포트에서 회원 구매를 옮기고 확정일이 된 적립을 확정, 유효기간 지난 포인트 소멸 (여러 번 돌려도 결과 같음)
  async scheduled(event, env, ctx) {
    ctx.waitUntil(syncOrders(env).then(() => expirePoints(env)));
  }
};
