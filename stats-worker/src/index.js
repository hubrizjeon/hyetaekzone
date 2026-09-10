/* 혜택존 방문·클릭 집계
   개인정보는 받지도 저장하지도 않습니다 — IP·쿠키·기기 ID 없이
   "날짜 · 페이지 · 종류 · 이름표" 별 개수만 셉니다.

   POST /e      {page, type, label}   페이지가 보내는 기록 (sendBeacon, text/plain)
   GET  /stats?days=7                 집계 조회 — Authorization: Bearer <STATS_KEY>
*/
const ORIGINS = ['https://hubrizjeon.github.io', 'https://benefits.hubriz.io'];
const TYPES = new Set(['visit', 'card', 'toc', 'source', 'share', 'home', 'buy', 'filter', 'sort', 'more', 'cat']);
const PAGES = new Set(['main', 'hotdeal']);

/* 날짜는 브라우저가 아니라 서버 기준 한국 시간 — 휴대폰 시계가 틀려도 집계가 흔들리지 않게 */
const kstDay = (offsetDays = 0) =>
  new Date(Date.now() + 9 * 3600e3 - offsetDays * 86400e3).toISOString().slice(0, 10);

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const origin = req.headers.get('Origin') || '';
    const allowed = ORIGINS.includes(origin) || /^http:\/\/localhost(:\d+)?$/.test(origin);
    const cors = { 'Access-Control-Allow-Origin': allowed ? origin : ORIGINS[0], Vary: 'Origin' };

    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...cors,
        'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type' } });
    }

    if (url.pathname === '/e' && req.method === 'POST') {
      if (!allowed) return new Response('forbidden', { status: 403, headers: cors });
      let d;
      try { d = JSON.parse(await req.text()); } catch { return new Response('bad', { status: 400, headers: cors }); }
      const type = String(d.type || '');
      const label = String(d.label || '').trim().slice(0, 80);
      const page = PAGES.has(d.page) ? d.page : 'main';
      if (!TYPES.has(type) || !label) return new Response('bad', { status: 400, headers: cors });
      await env.DB.prepare(
        `INSERT INTO daily (day, page, type, label, n) VALUES (?, ?, ?, ?, 1)
         ON CONFLICT(day, page, type, label) DO UPDATE SET n = n + 1`
      ).bind(kstDay(), page, type, label).run();
      return new Response(null, { status: 204, headers: cors });
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

    return new Response('hyetaekzone stats', { status: 404 });
  }
};
