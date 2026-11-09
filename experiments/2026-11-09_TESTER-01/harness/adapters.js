// TESTER-01, адаптеры игр: (1) правка при загрузке — выдать камеру карты наружу через уже существующий объект игры;
// (2) состояние игры текстом для руки A и W. Правка одна и та же для чистой копии и мутантов, логику игры не трогает.
const GAMES = {
  baeckerei: {
    detect: html => html.includes('window.BW = {'),
    patch: html => html.replace('window.BW = {', 'window.BW = { __toTile: toTile, __MW: MW, __MH: MH,'),
    query: seed => `?seed=${seed}&lang=ru`,
  },
  reifenwerk: {
    detect: html => html.includes('window.RW = {'),
    patch: html => html,                      // PixelGfx.toTile уже снаружи
    query: seed => `?seed=${seed}&lang=ru&gfx=pixel`,
  },
};
function detect(html) { for (const [k, g] of Object.entries(GAMES)) if (g.detect(html)) return k; return 'generic'; }

// Выполняется в странице: состояние игры, объекты карты и люди — компактно.
function pageState(game) {
  const r = v => typeof v === 'number' ? Math.round(v * 10) / 10 : v;
  const nm = o => o && (o.ru || o.name || o.label || o.de || o.id || o.type);
  const str = v => typeof v === 'string' ? v : null;
  const viewOf = tt => { if (!tt) return undefined; const [x0, y0] = tt(0, 0), [x1, y1] = tt(1, 1); return { x: [Math.ceil(x0), Math.floor(x1) - 1], y: [Math.ceil(y0), Math.floor(y1) - 1] }; };  // видимые клетки
  // строка журнала игры: «время: сообщение» (Reifenwerk — {t, msg}, Bäckerei — {d, c, msg})
  const logLine = e => {
    if (str(e)) return e.slice(0, 200);
    if (!e || typeof e !== 'object') return String(e);
    const when = str(e.t) || (e.d !== undefined ? `Д${e.d} ${String(Math.floor((e.c || 0) / 60)).padStart(2, '0')}:${String((e.c || 0) % 60).padStart(2, '0')}` : '');
    const m = e.msg != null ? String(e.msg) : e.ru != null ? String(e.ru) : e.text != null ? String(e.text) : JSON.stringify(e);  // msg бывает объектом-строкой
    return ((when ? when + ': ' : '') + m).slice(0, 200);
  };
  if (game === 'reifenwerk' && window.RW) {
    const RW = window.RW, s = RW.summary();
    const objects = RW.STATIONS.filter(o => o.built !== false).map(o => ({ id: o.id, name: nm(o), x: o.x, y: o.y, w: o.w, h: o.h, state: o.broken ? 'сломан' : o.state, busy: r(o.busy) }));
    const people = RW.S.workers.map(w => ({ name: w.name, role: w.role, x: r(w.x), y: r(w.y), state: w.state, energy: Math.round(w.energy), away: !!w.away }));
    return { summary: s, map: { size: [76, 52], view: viewOf(window.PixelGfx && window.PixelGfx.toTile), objects, people }, log: (RW.S.log || []).slice(-6).map(logLine) };
  }
  if (game === 'baeckerei' && window.BW) {
    const BW = window.BW, S = BW.S;
    const day = Math.floor(S.t / 1440), mm = Math.floor(S.t % 1440), clock = `${String(Math.floor(mm / 60)).padStart(2, '0')}:${String(mm % 60).padStart(2, '0')}`;
    const objects = (S.items || []).map(o => ({ id: o.uid || o.id, name: nm(o), x: o.x, y: o.y, w: o.w, h: o.h, rot: o.rot, state: o.broken ? 'сломан' : (o.batch ? 'работает' : 'простой'), stock: o.stock || undefined }));
    const people = S.workers.map(w => ({ name: w.name, role: w.role, shift: w.shift, x: r(w.x), y: r(w.y), state: w.state, energy: Math.round(w.energy), away: !!w.away }));
    const summary = { phase: S.phase, day, clock, speed: S.speed, money: Math.round(S.money), rep: r(S.rep), customers: S.customers.length, orders: (S.orders || []).length, mats: S.mats, price: S.price, plan: S.plan, loan: S.loan, negDays: S.negDays };
    return { summary, map: { size: [BW.__MW || 40, BW.__MH || 30], view: viewOf(BW.__toTile), objects, people }, log: (S.log || []).slice(-6).map(logLine) };
  }
  return window.render_game_to_text ? { text: String(window.render_game_to_text()).slice(0, 6000) } : null;
}

// Выполняется в странице: клетка карты → точка на экране (обратная к игровой toTile).
function pageTileToScreen(game, tx, ty) {
  const cv = document.getElementById('cv'); if (!cv) return null;
  const rc = cv.getBoundingClientRect();
  let toTile = null;
  if (game === 'baeckerei' && window.BW && window.BW.__toTile) toTile = window.BW.__toTile;
  if (game === 'reifenwerk' && window.PixelGfx) toTile = window.PixelGfx.toTile;
  if (!toTile) return null;
  const [x0, y0] = toTile(0, 0), [x1, y1] = toTile(1, 1);
  // центр клетки: в обеих играх hitTest/mapTile вычитают 0,5, т. е. клетка (tx, ty) — около tx + 0,5
  const fx = (tx + 0.5 - x0) / (x1 - x0), fy = (ty + 0.5 - y0) / (y1 - y0);
  if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return { off: true, view: [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)] };
  return { x: rc.left + fx * rc.width, y: rc.top + fy * rc.height };
}

module.exports = { GAMES, detect, pageState, pageTileToScreen };
