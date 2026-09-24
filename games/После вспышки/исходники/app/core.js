'use strict';
// ════════════════════════ «После вспышки» — ядро: утилиты, данные, хранилище, ход месяца, решения, проверки, ИИ-мир
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
function h(tag, a, ...kids) {
  if (a != null && (a.nodeType || typeof a !== 'object' || Array.isArray(a))) { kids.unshift(a); a = null; }
  const e = document.createElement(tag);
  if (a) for (const k in a) {
    const v = a[k]; if (v == null || v === false) continue;
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (k === 'style') e.style.cssText = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(3)) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
const MINUS = '−';
const nf = {}; function NF(d) { return nf[d] || (nf[d] = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d })); }
function fmt(x, d = 1) { if (x == null || !isFinite(x)) return '—'; if (Math.abs(x) < 0.5 * Math.pow(10, -d)) x = 0; return NF(d).format(x).replace('-', MINUS); }
function sgn(x, d = 1) { if (x == null || !isFinite(x)) return '—'; if (Math.abs(x) < 0.5 * Math.pow(10, -d)) x = 0; const s = fmt(Math.abs(x), d); return (x > 0 ? '+' : x < 0 ? MINUS : '±') + s; }
function pct(x, d = 0) { return x == null || !isFinite(x) ? '—' : fmt(100 * x, d) + ' %'; }
function fmtPop(p) {
  if (!p) return 'нет данных';
  if (p >= 1e9) return fmt(p / 1e9, 2) + ' млрд';
  if (p >= 1e6) return fmt(p / 1e6, p >= 1e8 ? 0 : 1) + ' млн';
  if (p >= 1e4) return fmt(p / 1e3, 0) + ' тыс.';
  return fmt(p, 0);
}
function fmtK(x) { if (x == null || !isFinite(x)) return '—'; if (x >= 1e3) return fmt(x / 1e3, x >= 1e4 ? 1 : 2) + ' млн'; if (x >= 10) return fmt(x, 0) + ' тыс.'; return fmt(x, 1) + ' тыс.'; }   // из тысяч
function months(n) { n = Math.round(n); return n + ' ' + plural(n, 'месяц', 'месяца', 'месяцев'); }
function plural(n, a, b, c) { n = Math.abs(n) % 100; const n1 = n % 10; if (n > 10 && n < 20) return c; if (n1 > 1 && n1 < 5) return b; if (n1 === 1) return a; return c; }
function rid(n = 8) { const a = new Uint8Array(n); crypto.getRandomValues(a); return Array.from(a, b => (b % 36).toString(36)).join(''); }
function clone(o) { return o == null ? o : JSON.parse(JSON.stringify(o)); }
function deepMerge(t, s) { for (const k in s) { const v = s[k]; if (v && typeof v === 'object' && !Array.isArray(v) && t[k] && typeof t[k] === 'object' && !Array.isArray(t[k])) deepMerge(t[k], v); else t[k] = clone(v); } return t; }
function debounce(f, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; }
function toast(msg, ms = 3600) { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('on'), ms); }
function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

// ════════════════════════ данные
const DATA = {
  countries: JSON.parse($('#d-countries').textContent),   // названия, население
  topo110: JSON.parse($('#d-topo110').textContent),
  blob: null, world: null
};
let ISO = [];
const IDX = Object.create(null);
const ECON = Object.create(null);             // страны, которые есть в модели
async function gunzipB64(id) {
  const b64 = $('#' + id).textContent.trim();
  const bin = atob(b64), u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  if (typeof DecompressionStream === 'undefined') throw new Error('браузер не умеет распаковывать данные');
  const ds = new DecompressionStream('gzip');
  return await new Response(new Blob([u8]).stream().pipeThrough(ds)).text();
}
async function loadWorld() {
  DATA.world = JSON.parse($('#d-world').textContent);
  WORLD.setup(DATA.world);
  ISO = DATA.world.iso;
  ISO.forEach((iso, i) => { IDX[iso] = i; ECON[iso] = true; });
}
async function loadBlob() { DATA.blob = JSON.parse(await gunzipB64('d-blob')); return DATA.blob; }
const WC = iso => DATA.world.countries[IDX[iso]];
function cname(iso3) { const c = DATA.countries[iso3]; return c && c.ru ? c.ru : String(iso3 == null ? '—' : iso3); }
// города и сёла
const PL = { byC: Object.create(null), byKey: Object.create(null), all: false };
function placesOf(iso3) {
  if (PL.byC[iso3]) return PL.byC[iso3];
  if (!DATA.blob) return [];
  const s = DATA.blob.places[iso3], arr = [];
  if (s) for (const line of s.split('\n')) {
    const f = line.split('|');
    const p = { key: 'P:' + f[0], name: f[1], lon: +f[2], lat: +f[3], pop: +f[4], cap: +f[5], cc: iso3 };
    arr.push(p); PL.byKey[p.key] = p;
  }
  PL.byC[iso3] = arr; return arr;
}
function decodeAll() { if (PL.all || !DATA.blob) return; for (const k in DATA.blob.places) placesOf(k); PL.all = true; }
const CENTROID = Object.create(null);
function isLocal(key) { return key && key.charAt(0) !== 'C'; }
function placeInfo(key) {
  if (!key) return {};
  if (!isLocal(key)) {
    const iso3 = key.slice(2), c = DATA.countries[iso3] || {}, ctr = CENTROID[iso3] || [0, 0];
    return { key, kind: 'C', name: c.ru || iso3, cc: iso3, pop: c.P, lon: ctr[0], lat: ctr[1] };
  }
  let g = PL.byKey[key];
  if (!g && DATA.blob) { decodeAll(); g = PL.byKey[key]; }
  if (g) return { key, kind: 'P', name: g.name, cc: g.cc, pop: g.pop, lon: g.lon, lat: g.lat, cap: g.cap };
  return { key, kind: 'P', name: 'место', cc: null, unknown: true };
}

// ════════════════════════ состояние игры (год в коде — это ход-месяц: 0 — месяц бури)
const BASE = 0, MIN_GAP = 12000, LEASE = 25000, IDLE = 6, MAX_OWN = 3, DEC_MAX = 200 * 1024, EPS = 0.002, MAXH = 12, GAME_MONTHS = 60;
const CHAT_MAX = 320, CHAT_KEEP = 200, PLAYERS_MAX = 300, CHAT_LEN = 400;
const M = {
  remote: false, ready: false, yearOk: false, seen: {},
  c: { game: {}, ctrl: {}, pol: {}, patch: {}, fork: {}, players: {}, log2: {}, chat: {}, req: {} },
  sum: {}, news: {}, dec: {}, chk: {}, bad: {},
  st: null, stY: null, snaps: {},
  me: { id: null, isOwner: false, canWrite: true, canKnown: false },
  busy: false, stage: ''
};
const UI = { view: 'map', sel: null, tab: 'over', metric: 'grid', patchFilter: 'open', composer: null, fork: null };
const ACT = { id: null };
let USER = null, DB = null, DL = null, SAMPLE = null;
const PROFILES = Object.create(null);
function game() { return M.c.game.state || null; }
function curYear() { const g = game(); return g && g.year != null ? g.year : BASE; }
function tLabel(t) { return WORLD.label(t == null ? curYear() : t); }
function ctrlOf(iso) { const d = M.c.ctrl[iso]; return d && d.owner ? d : null; }
function ownerOf(iso) { const d = ctrlOf(iso); return d ? d.owner : null; }
function isMine(iso) { return !!ACT.id && ownerOf(iso) === ACT.id; }
function idleOf(d) { return d ? curYear() - (d.act != null ? d.act : d.since != null ? d.since : BASE) : 0; }
function isIdle(iso) { const d = ctrlOf(iso); return !!d && d.owner !== ACT.id && idleOf(d) >= IDLE; }
function myCountries() { return Object.keys(M.c.ctrl).filter(iso => ownerOf(iso) === ACT.id); }
function myCountriesOf(id) { return Object.keys(M.c.ctrl).filter(iso => ownerOf(iso) === id); }
function canAct() { return M.ready && M.me.canWrite !== false && !!ACT.id && !!game(); }
function hasOnce(p) { return !!p && WORLD.LEVERS.some(l => l.once && p[l.k] != null); }
function polDoc(d, Y) { const p = (d && d.p) || {}; return (d && d.oy === Y + 1) || !hasOnce(p) ? p : stripOnce(p); }
function polOf(iso) { return polDoc(M.c.pol[iso], curYear()); }
// сводка месяца
function sv(Y, iso, k) { const s = M.sum[Y]; if (!s) return null; const j = s.k.indexOf(k), row = s.c[IDX[iso]]; return row && j >= 0 ? row[j] : null; }
function wv(Y) { const s = M.sum[Y]; return s ? s.w : null; }
function stateTag(iso) { const d = M.dec[curYear()]; return ctrlOf(iso) ? 'player' : (d && d.src && d.src[iso]) || 'ai'; }

// игроки и имена
const PALETTE = ['#8E8BFF', '#5BC0A6', '#E07A5F', '#E0B04F', '#C084FC', '#4FB3E0', '#F472B6', '#9CCC65'];
function colorOf(id) { if (!id) return '#888'; if (PROFILES[id] && PROFILES[id].color) return PROFILES[id].color; let h1 = 0; for (let i = 0; i < id.length; i++) h1 = (h1 * 31 + id.charCodeAt(i)) >>> 0; return PALETTE[h1 % PALETTE.length]; }
function nameOf(id) {
  if (!id) return '—';
  if (id === 'ai') return 'ИИ'; if (id === 'sys') return 'система';
  const p = M.c.players[id]; if (p && p.nick) return p.nick;
  if (PROFILES[id] && PROFILES[id].name) return PROFILES[id].name;
  if (id.includes('~')) { const base = id.slice(0, id.indexOf('~')), n = id.slice(id.indexOf('~') + 1); return nameOf(base) + ' (' + n + ')'; }
  return id.startsWith('anon:') ? 'Гость ' + id.slice(5, 9) : 'Игрок';
}
const PROF_ASKED = Object.create(null);
let profTimer = null;
function refreshProfiles() {
  if (!USER || !USER.profiles || profTimer) return;
  const ids = Object.create(null);
  Object.values(M.c.ctrl).forEach(d => { if (d && d.owner) ids[d.owner] = 1; });
  Object.values(M.c.patch).forEach(p => { if (p && p.author) ids[p.author] = 1; });
  Object.values(M.c.players).forEach(p => { if (p && p.id) ids[p.id] = 1; });
  Object.values(M.c.chat || {}).forEach(m => { if (m && m.by) ids[m.by] = 1; });
  const need = Object.keys(ids).filter(i => !PROF_ASKED[i] && !i.startsWith('local:') && !i.startsWith('anon:') && !i.includes('~') && i !== 'ai' && i !== 'sys').slice(0, 40);
  if (!need.length) return;
  need.forEach(i => { PROF_ASKED[i] = 1; });
  profTimer = setTimeout(async () => {
    profTimer = null;
    try { const ps = await USER.profiles(need); for (const id in ps) PROFILES[id] = ps[id]; scheduleRender(); } catch (e) { }
  }, 60);
}

// ════════════════════════ хранилище: общая база (db) или этот браузер
const LOCAL_KEY = 'posle-vspyshki-v3';
const MEMONLY = { sum: 1 };
const TAB = rid(6);
function ME() { return (ACT.id || 'anon') + ':' + TAB; }
const B = {
  remote: false,
  async get(path) {
    if (this.remote) { const s = await DB.doc(path).get(); return s.exists ? clone(s.data()) : null; }
    const [c, id] = path.split('/');
    if (MEMONLY[c]) { const v = M.sum[id]; return v == null ? null : v; }
    const v = (M.c[c] || {})[id]; return v == null ? null : clone(v);
  },
  async set(path, obj) {
    if (this.remote) return DB.doc(path).set(obj);
    const [c, id] = path.split('/');
    if (MEMONLY[c]) { M.sum[id] = obj; return; }
    (M.c[c] = M.c[c] || {})[id] = clone(obj); localChanged(c);
  },
  async update(path, obj) {
    if (this.remote) return DB.doc(path).update(obj);
    const [c, id] = path.split('/'); const cur = (M.c[c] || {})[id];
    if (!cur) throw { code: 'invalid_argument', message: 'нет документа ' + path };
    deepMerge(cur, obj); localChanged(c);
  },
  async upsert(path, obj) {
    try { await this.update(path, obj); }
    catch (e) { if (!e || e.code !== 'invalid_argument') throw e; if (await this.get(path)) throw e; await this.set(path, obj); }
  },
  async del(path) {
    if (this.remote) return DB.doc(path).delete();
    const [c, id] = path.split('/'); if (M.c[c]) delete M.c[c][id]; localChanged(c);
  },
  async list(coll) {
    if (this.remote) { const q = await DB.collection(coll).limit(1000).get(); const o = Object.create(null); q.docs.forEach(d => { o[d.id] = clone(d.data()); }); return o; }
    return clone(M.c[coll] || {});
  },
  async where(coll, f, v) {
    if (this.remote) {
      try { const q = await DB.collection(coll).where(f, '==', v).limit(1000).get(); const o = Object.create(null); q.docs.forEach(d => { o[d.id] = clone(d.data()); }); return o; }
      catch (e) { console.warn('выборка', e); }
    }
    const all = await this.list(coll), o = Object.create(null);
    for (const id in all) if (all[id] && all[id][f] === v) o[id] = all[id];
    return o;
  },
  async lock(path, ttl) {
    if (!this.remote) return true;
    try { const r = await DB.doc(path).acquire({ holder: ME(), ttlMs: ttl || LEASE }); return !!r.acquired; }
    catch (e) { console.warn('аренда', e); return false; }
  },
  async unlock(path) { if (!this.remote) return; try { await DB.doc(path).acquire({ holder: ME(), ttlMs: 1000 }); } catch (e) { } }
};
const saveLocal = debounce(() => {
  if (B.remote) return;
  const snap = {}; for (const k in M.c) snap[k] = M.c[k];
  for (let keep = 60; keep >= 4; keep = Math.floor(keep / 2)) {
    const y0 = curYear() - keep;
    const cut = o => { const r = {}; for (const id in (o || {})) if (!/^\d+$/.test(id) || +id >= y0) r[id] = o[id]; return r; };
    const s2 = Object.assign({}, snap, { log2: cut(snap.log2), news: cut(snap.news), chk: cut(snap.chk) });
    if (lsSet(LOCAL_KEY, JSON.stringify(s2))) return;
  }
  toast('Хранилище браузера переполнено — мир не сохранится после перезагрузки.');
}, 400);
function localChanged(c) { saveLocal(); if (typeof scheduleRender === 'function') scheduleRender(); }
['dec', 'news', 'chk', 'ai'].forEach(k => { M.c[k] = M.c[k] || {}; });

// ════════════════════════ сводки месяцев
function sumDoc(Y, sm) { return { year: Y, mv: WORLD.MODELV, k: sm.k, c: sm.c, w: sm.w, ev: sm.ev }; }
const loading = new Map();
async function loadSum(Y) {
  if (Y < BASE || Y > curYear()) return null;
  if (M.sum[Y]) return M.sum[Y];
  if (M.bad[Y]) return null;
  if (loading.has(Y)) return loading.get(Y);
  const pr = (async () => {
    const d = await B.get('sum/' + Y); if (d) M.sum[Y] = d;
    if (!M.sum[Y]) {
      try { await replayTo(Y, y => setStage('Восстанавливаю мир: ' + tLabel(y) + '…')); }
      catch (e) { console.warn('восстановление', e); M.bad[Y] = true; }
      finally { setStage(''); }
    }
    return M.sum[Y] || null;
  })().finally(() => loading.delete(Y));
  loading.set(Y, pr); return pr;
}
async function getDec(y) {
  if (M.dec[y]) return M.dec[y];
  const d = await B.get('dec/' + y); if (!d) return null;
  if (d.parts) {
    const pol = {};
    for (let i = 0; i < d.parts; i++) { const pp = await B.get('decp/' + y + '-' + i); if (!pp) return null; Object.assign(pol, pp.pol); }
    d.pol = pol; delete d.parts;
  }
  M.dec[y] = d; return d;
}
async function loadNews(y) { if (M.news[y]) return M.news[y]; const d = await B.get('news/' + y); M.news[y] = d || { year: y, items: [] }; return M.news[y]; }
async function loadChk(y) { if (M.chk[y]) return M.chk[y]; const d = await B.get('chk/' + y); M.chk[y] = d || { year: y, items: [] }; return M.chk[y]; }

// ════════════════════════ воспроизведение мира по сохранённым решениям
function polArr(polByIso) { const o = {}; for (const iso in (polByIso || {})) if (IDX[iso] != null) o[IDX[iso]] = polByIso[iso]; return o; }
function wevOf(d) { return (d && d.wev) || {}; }
async function replayTo(Y, onProgress) {
  const g = game(); if (!g) throw new Error('мир не создан');
  const sid = g.seed + ':' + g.started;
  if (M.stSeed !== sid) { M.snaps = {}; M.st = null; M.stY = null; M.stSeed = sid; }
  if (M.st && M.stY === Y) return M.st;
  if (M.snaps[Y]) return M.snaps[Y];
  let y0 = BASE, st = null;
  const ks = Object.keys(M.snaps).map(Number).filter(y => y <= Y).sort((a, b) => b - a);
  if (ks.length) { y0 = ks[0]; st = M.snaps[y0]; } else { st = WORLD.init(g.seed); M.snaps[BASE] = st; }
  if (M.st && M.stY != null && M.stY > y0 && M.stY <= Y) { y0 = M.stY; st = M.st; }
  for (let y = y0 + 1; y <= Y; y++) {
    const d = await getDec(y);
    if (!d) throw new Error('нет записи решений за ' + tLabel(y));
    st = WORLD.step(st, polArr(d.pol), wevOf(d)).st;
    if (y % 6 === 0) M.snaps[y] = st;
    const s0 = M.sum[y];
    if (!s0 || s0.mv !== WORLD.MODELV) { M.sum[y] = sumDoc(y, WORLD.summary(st)); M.bad[y] = false; }
    if (onProgress) onProgress(y, Y);
    await sleep(0);
  }
  return st;
}
async function stateAt(Y, onProgress) { const st = await replayTo(Y, onProgress); M.st = st; M.stY = Y; return st; }
function dropYear(Y) {
  delete M.sum[Y]; delete M.dec[Y]; delete M.news[Y]; delete M.chk[Y]; delete M.snaps[Y]; delete M.bad[Y];
  if (M.stY === Y) { M.st = null; M.stY = null; }
}

// ════════════════════════ рычаги и решения
const LEV = Object.create(null); WORLD.LEVERS.forEach(l => { LEV[l.k] = l; });
const LEVGROUPS = [
  { ru: 'Приоритеты', ks: ['prC', 'prW', 'prG', 'prL', 'ration'] },
  { ru: 'Заводы', ks: ['exportT'] },
  { ru: 'Помощь другим', ks: ['aidT', 'aidF', 'aidFood', 'aidC', 'aidR'] }
];
const keyed = L => L.kind === 'sec' || L.kind === 'secb' || L.kind === 'iso';
function normv(v) { return v == null ? null : v; }
function applyCh(p, ch) {
  const o = clone(p || {});
  for (const k in ch) {
    const L = LEV[k], v = ch[k]; if (!L) continue;
    if (v == null) { delete o[k]; continue; }
    if (keyed(L)) {
      const m = Object.assign({}, o[k] || {});
      for (const x in v) { if (v[x] == null || v[x] === false) delete m[x]; else m[x] = v[x]; }
      if (Object.keys(m).length) o[k] = m; else delete o[k];
    } else o[k] = v;
  }
  return o;
}
function chPrevApp(base, ch, np) {
  const prev = {}, app = {};
  for (const k in ch) {
    const L = LEV[k]; if (!L) continue;
    if (keyed(L)) {
      prev[k] = {}; app[k] = {};
      const keys = ch[k] == null ? Object.keys((base && base[k]) || {}) : Object.keys(ch[k]);
      keys.forEach(x => { prev[k][x] = base && base[k] && base[k][x] != null ? base[k][x] : null; app[k][x] = np[k] && np[k][x] != null ? np[k][x] : null; });
    } else { prev[k] = base && base[k] != null ? base[k] : null; app[k] = np[k] != null ? np[k] : null; }
  }
  return { prev, app };
}
function unapplyCh(p, ch, prev, app) {
  const o = clone(p || {}); let touched = false;
  if (!prev || !app) return { p: o, touched };
  for (const k in ch) {
    const L = LEV[k]; if (!L) continue;
    if (keyed(L)) {
      const a = app[k] || {}, pr = prev[k] || {};
      for (const x in a) {
        if (a[x] == null && pr[x] == null) continue;
        const cur = o[k] && o[k][x] != null ? o[k][x] : null;
        if (!same(normv(cur), normv(a[x]))) continue;
        touched = true;
        if (pr[x] == null) { if (o[k]) { o[k] = Object.assign({}, o[k]); delete o[k][x]; if (!Object.keys(o[k]).length) delete o[k]; } }
        else { o[k] = Object.assign({}, o[k] || {}); o[k][x] = pr[x]; }
      }
    } else {
      if (app[k] == null && prev[k] == null) continue;
      const cur = o[k] != null ? o[k] : null;
      if (!same(normv(cur), normv(app[k]))) continue;
      touched = true;
      if (prev[k] == null) delete o[k]; else o[k] = prev[k];
    }
  }
  return { p: o, touched };
}
function stripOnce(p) { const o = clone(p || {}); WORLD.LEVERS.forEach(l => { if (l.once) delete o[l.k]; }); return o; }
function chEmpty(ch) { return !ch || !Object.keys(ch).length; }

// цели патчей: что должно улучшиться (значение метрики на горизонте; потери и человеко-месяцы — накопленные)
const GOALS = {
  served: { ru: 'Снабжение населения', unit: 'п.п.', dir: 1, st: (s, c) => 100 * s.served[c], sm: (Y, iso) => 100 * sv(Y, iso, 'served') },
  grid: { ru: 'Восстановленная сеть', unit: 'п.п.', dir: 1, st: (s, c) => 100 * s.grid[c], sm: (Y, iso) => 100 * sv(Y, iso, 'grid') },
  comms: { ru: 'Связь', unit: 'п.п.', dir: 1, st: (s, c) => 100 * s.comms[c], sm: (Y, iso) => 100 * sv(Y, iso, 'comms') },
  logi: { ru: 'Логистика', unit: 'п.п.', dir: 1, st: (s, c) => 100 * s.logi[c], sm: (Y, iso) => 100 * sv(Y, iso, 'logi') },
  hungry: { ru: 'Доля без еды', unit: 'п.п.', dir: -1, st: (s, c) => 100 * s.hungry[c], sm: (Y, iso) => 100 * sv(Y, iso, 'hungry') },
  fuel: { ru: 'Запас топлива', unit: 'мес.', dir: 1, st: (s, c) => s.fuel[c], sm: (Y, iso) => sv(Y, iso, 'fuel') },
  losses: { ru: 'Потери людей (накопленные)', unit: 'тыс.', dir: -1, st: (s, c) => s.losses[c], sm: (Y, iso) => sv(Y, iso, 'losses') },
  pm: { ru: 'Человеко-месяцы без снабжения', unit: 'млн', dir: -1, st: (s, c) => s.pm[c], sm: (Y, iso) => sv(Y, iso, 'pm') },
  econ: { ru: 'Экономика', unit: 'п.п.', dir: 1, st: (s, c) => 100 * s.econ[c], sm: (Y, iso) => 100 * sv(Y, iso, 'econ') }
};
function goalRu(g) { return (g && GOALS[g.m] ? GOALS[g.m].ru : (g && g.m) || '—') + (g && g.iso && IDX[g.iso] != null ? ' у страны ' + cname(g.iso) : ''); }
function goalIso(g, iso) { return g && g.iso && IDX[g.iso] != null ? g.iso : iso; }
function goalSt(g, st, iso) { return GOALS[g.m].st(st, IDX[iso]); }
function goalDir(g) { return GOALS[g.m].dir; }
function goalUnit(g) { return GOALS[g.m].unit; }

// ════════════════════════ мир: создание, ход месяца, сброс
async function createWorld(by) {
  const seed = (Math.random() * 2 ** 31) >>> 0, started = Date.now();
  const st = WORLD.init(seed), sm = WORLD.summary(st);
  M.snaps = { [BASE]: st }; M.st = st; M.stY = BASE; M.stSeed = seed + ':' + started;
  await B.set('sum/' + BASE, sumDoc(BASE, sm));
  M.sum[BASE] = sumDoc(BASE, sm);
  await B.set('log2/' + BASE, { ['w' + rid(4)]: { t: 'world', by, ts: Date.now() } });
  await B.set('game/state', { v: 3, mv: WORLD.MODELV, year: BASE, seed, started, lastAt: 0, lastBy: by, ai: true, fx: BASE, ph: {} });
}
function snapCtx() { return { ctrl: M.c.ctrl, pol: M.c.pol, req: M.c.req }; }
async function freshCtx() {
  if (!B.remote) return snapCtx();
  const [ctrl, pol, req] = await Promise.all([B.list('ctrl'), B.list('pol'), B.list('req')]);
  return { ctrl, pol, req };
}
// решения на месяц Yn: политики игроков, ИИ (свежие или прошлые), разовые меры только на свой месяц
function assemble(Yn, ai, prevDec, X) {
  X = X || snapCtx();
  const ctrl = X.ctrl || {}, isP = iso => !!(ctrl[iso] && ctrl[iso].owner);
  const pol = {}, src = {}, prevPol = (prevDec && prevDec.pol) || {}, prevSrc = (prevDec && prevDec.src) || {};
  for (const iso in prevPol) if (!isP(iso) && IDX[iso] != null) { const p = stripOnce(prevPol[iso]); if (!chEmpty(p)) { pol[iso] = p; src[iso] = prevSrc[iso] === 'player' ? 'was' : (prevSrc[iso] || 'ai'); } }
  if (ai && ai.pol) for (const iso in ai.pol) if (!isP(iso) && IDX[iso] != null) { const p = WORLD.sanitize(ai.pol[iso], iso); if (chEmpty(p)) { delete pol[iso]; delete src[iso]; } else { pol[iso] = p; src[iso] = 'ai'; } }
  for (const iso in ctrl) if (isP(iso) && IDX[iso] != null) { const p = WORLD.sanitize(polDoc((X.pol || {})[iso], Yn - 1), iso); if (chEmpty(p)) { delete pol[iso]; delete src[iso]; } else { pol[iso] = p; src[iso] = 'player'; } }
  return { year: Yn, mv: WORLD.MODELV, pol, src, wev: {} };
}
async function logAdd(entry, y, id) {
  y = y == null ? curYear() : y; id = id || (entry.t.charAt(0) + rid(6));
  entry.by = entry.by || ACT.id; entry.ts = Date.now();
  try { await B.upsert('log2/' + y, { [id]: entry }); } catch (e) { console.warn('хроника', e); }
  if (entry.by === ACT.id && typeof touchSeen === 'function') touchSeen();
}
function failWrite(e, what, perm = true) {
  if (perm && e && e.code === 'invalid_argument' && B.remote && !M.me.canKnown) { M.me.canWrite = false; renderAll(); toast(what + ': у вас доступ только на просмотр.'); return; }
  if (e && e.code === 'quota_exceeded') { toast(what + ': в общей базе закончилось место.'); return; }
  if (e && e.code === 'resource_exhausted') { toast(what + ': слишком часто — подождите немного.'); return; }
  if (e && e.code === 'revoked') { M.me.canWrite = false; renderAll(); toast(what + ': доступ к общей базе закрыт.'); return; }
  toast(what + (e && e.message ? ': ' + e.message : '.'));
}
function setStage(s) { M.stage = s; if (typeof renderTop === 'function') renderTop(); }

// ════════════════════════ ход месяца
function LeaseLost(msg) { this.lease = true; this.message = msg || 'аренда хода потеряна'; }
function makeRenew(R) {
  let last = Date.now();
  return async function renew() {
    const gap = Date.now() - last;
    if (!(await B.lock('game/state', LEASE))) throw new LeaseLost();
    if (gap > LEASE - 5000) { const g = await B.get('game/state'); if (!g || g.year !== R.y) throw new LeaseLost('месяц уже посчитал другой игрок'); }
    last = Date.now();
  };
}
function prepBusy(prep, Yn) { return !!(prep && prep.year === Yn && prep.until > Date.now() && prep.by && prep.by !== ME()); }
async function writeDec(Yn, dec, renew) {
  const js = JSON.stringify(dec);
  if (js.length <= DEC_MAX) { await B.set('dec/' + Yn, dec); return 0; }
  const isos = Object.keys(dec.pol), parts = []; let cur = {}, sz = 0;
  for (const iso of isos) {
    const s = JSON.stringify(dec.pol[iso]).length + iso.length + 4;
    if (sz + s > DEC_MAX - 8192 && Object.keys(cur).length) { parts.push(cur); cur = {}; sz = 0; }
    cur[iso] = dec.pol[iso]; sz += s;
  }
  if (Object.keys(cur).length) parts.push(cur);
  for (let i = 0; i < parts.length; i++) { if (renew) await renew(); await B.set('decp/' + Yn + '-' + i, { year: Yn, pol: parts[i] }); }
  if (renew) await renew();
  await B.set('dec/' + Yn, Object.assign({}, dec, { pol: {}, parts: parts.length }));
  return parts.length;
}
// фазы: когда мир впервые достиг цели (записывается в game/state.ph)
function phaseHits(sm) {
  const g = game(), ph = Object.assign({}, (g && g.ph) || {}), t = sm.t != null ? sm.t : curYear();
  if (t < 1) return ph;
  let changed = false;
  WORLD.PHASES.forEach(p => { if (ph[p.k] == null && sm.w[p.k] >= p.goal) { ph[p.k] = t; changed = true; } });
  return changed ? ph : null;
}
async function advanceYear(opts) {
  opts = opts || {};
  if (M.busy || !canAct()) return;
  M.busy = true; setStage('Готовлю ход…');
  let Yn = null, done = false, held = false;
  try {
    const g0 = await B.get('game/state'); if (!g0 || g0.year == null) return;
    const Y = g0.year; Yn = Y + 1;
    if (opts.auto && opts.forYear != null && opts.forYear !== Y) return;
    const since = Date.now() - (g0.lastAt || 0);
    if (B.remote && since >= 0 && since < MIN_GAP) {
      if (opts.auto) { M.busy = false; setStage(''); clearTimeout(MP.retry); MP.retry = setTimeout(() => advanceYear(opts), MIN_GAP - since + 300); return; }
      toast('Месяц только что сменился — подождите несколько секунд, чтобы все увидели итоги.'); return;
    }
    if (typeof setPresence === 'function') setPresence({ busy: Yn });
    await loadSum(Y);
    await stateAt(Y, y => setStage('Восстанавливаю мир: ' + tLabel(y) + '…'));
    let ai = await B.get('ai/' + Yn);
    if (!ai && g0.ai !== false) {
      const prep = await B.get('game/prep');
      if (prepBusy(prep, Yn)) { toast('Ход мира прямо сейчас обдумывает ИИ у другого игрока — подождите.'); return; }
      if (SAMPLE && M.aiOk !== false) {
        if (!(await B.lock('game/prep', 10000))) { toast('Ход мира прямо сейчас обдумывает ИИ у другого игрока — подождите.'); return; }
        const prep2 = await B.get('game/prep'); if (prepBusy(prep2, Yn)) { toast('Ход мира прямо сейчас обдумывает ИИ у другого игрока — подождите.'); return; }
        ai = await B.get('ai/' + Yn);
        if (!ai) {
          try { await B.set('game/prep', { year: Yn, by: ME(), until: Date.now() + 180000 }); } catch (e) { }
          setStage('ИИ решает за остальной мир…');
          try {
            ai = await askAI(Y);
            if (ai) { ai.year = Yn; ai.by = ACT.id; ai.ts = Date.now(); try { await B.set('ai/' + Yn, ai); } catch (e) { console.warn(e); } }
          } finally { try { await B.set('game/prep', { year: Yn, by: '', until: 0 }); } catch (e) { } }
        }
      } else {
        // без Claude — встроенные правила: результат детерминирован состоянием мира, поэтому блокировка не нужна
        setStage('Остальной мир решает…');
        ai = sanitizeAI(ruleAI(Y));
        if (ai) { ai.year = Yn; ai.by = 'rules'; ai.ts = Date.now(); try { await B.set('ai/' + Yn, ai); } catch (e) { console.warn(e); } }
      }
    }
    setStage('Считаю месяц…');
    if (!(await B.lock('game/state', LEASE))) { if (!opts.auto) toast('Месяц прямо сейчас считает другой игрок — подождите несколько секунд.'); return; }
    held = true;
    const R = { y: Y }, renew = makeRenew(R);
    const g1 = await B.get('game/state'); if (!g1 || g1.year !== Y) { if (!opts.auto) toast('Этот месяц уже посчитал другой игрок.'); return; }
    if (Y > BASE && g1.fx !== Y) { setStage('Дописываю итоги прошлого месяца…'); await finishYear(Y, renew).catch(e => { console.warn('итоги', e); }); await renew(); }
    const X = await freshCtx();
    const prevDec = await getDec(Y);
    const dec = assemble(Yn, ai, prevDec, X);
    const S0 = await stateAt(Y);
    const S1 = WORLD.step(S0, polArr(dec.pol), dec.wev).st;
    const sm = WORLD.summary(S1), sumD = sumDoc(Yn, sm);
    const newsD = makeNews(Y, Yn, ai, [], {}, sumD, M.sum[Y]);
    setStage('Записываю итоги…');
    await renew(); await B.set('sum/' + Yn, sumD);
    await writeDec(Yn, dec, renew);
    await renew(); await B.set('news/' + Yn, newsD);
    await renew();
    const g2 = await B.get('game/state'); if (!g2 || g2.year !== Y) { if (!opts.auto) toast('Этот месяц уже посчитал другой игрок.'); return; }
    const upd = { year: Yn, lastAt: Date.now(), lastBy: ACT.id, mv: WORLD.MODELV, fx: null };
    M.c.game.state = Object.assign({}, g2); const ph = phaseHits(sm); if (ph) upd.ph = ph;
    await B.update('game/state', upd);
    done = true; R.y = Yn;
    M.sum[Yn] = sumD; M.dec[Yn] = dec; M.news[Yn] = newsD; delete M.chk[Yn]; delete M.bad[Yn];
    M.st = S1; M.stY = Yn; if (Yn % 6 === 0) M.snaps[Yn] = S1;
    if (!B.remote) { M.c.game.state.year = Yn; if (ph) M.c.game.state.ph = ph; localChanged('game'); }
    await logAdd({ t: 'year' }, Yn, 'y' + Yn);
    let checks = [];
    try { checks = await finishYear(Yn, renew); }
    catch (e) { console.warn('итоги месяца', e); toast('Месяц посчитан, но итоги (проверки патчей) допишет следующий ход.', 5000); }
    if (!B.remote) await onYearChanged();
    const pass = checks.filter(c => c.res === 'pass').length, fail = checks.filter(c => c.res === 'fail').length;
    const newPh = ph ? WORLD.PHASES.filter(p => ph[p.k] === Yn).map(p => p.ru) : [];
    toast(`${tLabel(Yn)}: ${worldLine(Yn)}` + (typeof myDigest === 'function' ? myDigest(Yn) : '') + (newPh.length ? ` Достигнута фаза: ${newPh.join(', ')}!` : '')
      + (checks.length ? ` Проверки патчей: подтвердились ${pass}, не подтвердились ${fail}.` : ''), 9000);
  } catch (e) {
    if (!done && Yn != null) dropYear(Yn);
    if (e && e.lease) toast('Ход занял слишком много времени — месяц посчитает другой игрок или попробуйте ещё раз.', 6000);
    else { console.error(e); failWrite(e, 'Не получилось посчитать месяц', false); }
  } finally {
    if (held) await B.unlock('game/state'); M.busy = false; setStage('');
    if (typeof setPresence === 'function') setPresence({ busy: null });
    if (done && typeof touchSeen === 'function') touchSeen();
  }
}
function worldLine(Y) { const w = wv(Y); if (!w) return ''; return `мир — связь ${pct(w.comms)}, снабжение ${pct(w.served)}, свет ${pct(w.grid)}.`; }
// ════════════════════════ итоги месяца: проверки патчей, откаты, чистка — отдельно и идемпотентно
async function finishYear(Yn, renew) {
  const Y = Yn - 1;
  const ctrl = await B.list('ctrl');
  if (renew) await renew();
  const merged = await B.where('patch', 'status', 'merged');
  const all = Object.values(merged).filter(p => p && p.status === 'merged' && p.checked == null && IDX[p.iso] != null && p.year != null && p.year < Yn && (p.due == null ? p.year + ((p.goal && p.goal.h) || 1) : p.due) <= Yn);
  const stale = all.filter(p => Yn - p.year > MAXH), due = all.filter(p => Yn - p.year <= MAXH).sort((a, b) => a.year - b.year);
  let checks = [];
  if (due.length) { setStage('Проверяю патчи: 0 из ' + due.length + '…'); checks = await runChecks(Yn, due, renew); }
  stale.forEach(p => checks.push({ pid: p.pid, iso: p.iso, m: (p.goal && p.goal.m) || 'served', h: Yn - p.year, res: 'stale', ok: false }));
  await loadSum(Y); await loadSum(Yn);
  const pmap = {}; all.forEach(p => { pmap[p.pid] = p; });
  if (renew) await renew();
  const ai = await B.get('ai/' + Yn);
  const newsD = makeNews(Y, Yn, ai, checks, pmap, M.sum[Yn], M.sum[Y]);
  await B.set('news/' + Yn, newsD); M.news[Yn] = newsD;
  const chkD = { year: Yn, items: checks };
  await B.set('chk/' + Yn, chkD); M.chk[Yn] = chkD;
  if (checks.length) { if (renew) await renew(); await applyCheckResults(checks, Yn, ctrl, pmap); }
  try { await pruneAll(); } catch (e) { console.warn('чистка', e); }
  if (renew) await renew();
  await B.update('game/state', { fx: Yn });
  if (!B.remote) { M.c.game.state.fx = Yn; }
  setStage('');
  return checks;
}
async function runChecks(Yn, due, renew) {
  const out = [];
  const Y0min = due.reduce((m, p) => Math.min(m, p.year), Yn);
  const decs = {}; for (let y = Y0min + 1; y <= Yn; y++) { const d = await getDec(y); if (!d) throw new Error('нет решений за ' + tLabel(y)); decs[y] = d; }
  const act = {}; let st = await replayTo(Y0min); act[Y0min] = st;
  for (let y = Y0min + 1; y <= Yn; y++) { st = WORLD.step(st, polArr(decs[y].pol), wevOf(decs[y])).st; act[y] = st; await sleep(0); }
  let n = 0;
  for (const p of due) {
    try {
      const Y0 = p.year, g = p.goal || { m: 'served', h: 1 };
      let sh = act[Y0], diverged = false;
      for (let y = Y0 + 1; y <= Yn; y++) {
        const pol = Object.assign({}, decs[y].pol);
        const r = unapplyCh(pol[p.iso] || {}, p.ch, p.prev, p.app);
        if (r.touched) { diverged = true; if (chEmpty(r.p)) delete pol[p.iso]; else pol[p.iso] = r.p; }
        sh = diverged ? WORLD.step(sh, polArr(pol), wevOf(decs[y])).st : act[y];
        await sleep(0);
      }
      const gi = goalIso(g, p.iso), a = goalSt(g, act[Yn], gi), b = goalSt(g, sh, gi);
      const d = (a - b) * goalDir(g);
      const eps = g.m === 'losses' ? 0.5 : g.m === 'pm' ? 0.05 : g.m === 'fuel' ? 0.02 : 0.2;   // порог «разницы нет» в единицах цели
      const res = d > eps ? 'pass' : d < -eps ? 'fail' : 'neutral';
      out.push({ pid: p.pid, iso: p.iso, m: g.m, h: Yn - Y0, a: +a.toFixed(4), b: +b.toFixed(4), d: +d.toFixed(4), ok: res === 'pass', res });
    } catch (e) { console.warn('проверка', p.pid, e); }
    setStage('Проверяю патчи: ' + (++n) + ' из ' + due.length + '…');
    if (renew) await renew();
  }
  return out;
}
async function applyCheckResults(checks, Yn, ctrl, pmap) {
  for (const c of checks) {
    const p = pmap[c.pid]; if (!p || p.checked != null) continue;
    let status = c.res === 'pass' ? 'kept' : c.res === 'fail' ? 'failed' : c.res === 'stale' ? 'stale' : 'neutral';
    if (c.res === 'fail' && p.autoRevert !== false && ctrl[p.iso] && ctrl[p.iso].owner) {
      try {
        const cur = await B.get('pol/' + p.iso);
        const r = unapplyCh(polDoc(cur, Yn), p.ch, p.prev, p.app);
        if (r.touched) { await putPol(p.iso, WORLD.sanitize(r.p, p.iso), Yn); status = 'reverted'; }
      } catch (e) { console.warn('откат', e); }
    }
    try { await B.update('patch/' + c.pid, { status, res: c, checked: Yn }); } catch (e) { console.warn(e); }
    await logAdd({ t: 'check', pid: c.pid, iso: c.iso, ok: c.res === 'pass', status, by: 'sys' }, Yn, 'c' + c.pid);
  }
}
async function putPol(iso, p, Y) {
  const doc = { iso, p, t: Date.now(), oy: hasOnce(p) ? Y + 1 : null };
  await B.set('pol/' + iso, doc);
  if (B.remote) M.c.pol[iso] = doc;
  return doc;
}

// ════════════════════════ новости месяца: события модели, цифры, ИИ, проверки
const AIDRU = { T: 'трансформаторы', F: 'топливо', Food: 'продовольствие', C: 'бригады', R: 'радиокомплекты' };
function aidQ(what, q) { return what === 'T' ? fmt(q, 0) + ' шт.' : what === 'C' ? fmt(q, 0) + ' тыс. чел.' : what === 'R' ? fmt(q, 0) + ' компл.' : fmt(q, 0) + ' дней'; }
function makeNews(Y, Yn, ai, checks, pmap, b, a) {
  const items = [];
  if (ai && Array.isArray(ai.news)) ai.news.slice(0, 8).forEach(n => items.push({ src: 'ai', title: String(n.title || '').slice(0, 140), text: String(n.text || '').slice(0, 600), iso: (n.iso || []).filter(x => IDX[x] != null).slice(0, 6) }));
  (b && b.ev || []).forEach(e => {
    if (e.k === 'storm2') items.push({ src: 'model', title: 'Вторая буря: на высоких широтах снова отключения', text: 'Часть восстановленных узлов сети вышла из строя, повреждена аппаратура связи.', iso: [] });
    else if (e.k === 'aid') items.push({ src: 'model', title: `${cname(e.from)} → ${cname(e.to)}: ${AIDRU[e.what]}, ${aidQ(e.what, e.q)}`, text: 'Помощь дойдёт через месяц.', iso: [e.from, e.to] });
    else if (e.k === 'aidfail') items.push({ src: 'model', title: `${cname(e.from)} не смогла отправить помощь в ${cname(e.to)}`, text: 'Нет связи с получателем или логистики у отправителя (нужно не меньше 20 %).', iso: [e.from, e.to] });
  });
  if (a && b) {
    const gi = b.k.indexOf('served'), gg = b.k.indexOf('grid'), gh = b.k.indexOf('hungry'), gp = b.k.indexOf('P');
    const rows = ISO.map(iso => { const r = b.c[IDX[iso]], r0 = a.c[IDX[iso]]; return { iso, P: r[gp], ds: r[gi] - r0[gi], dg: r[gg] - r0[gg], h: r[gh] }; }).filter(r => r.P > 3);
    rows.slice().sort((x, y) => y.ds * y.P - x.ds * x.P).slice(0, 2).forEach(r => { if (r.ds > 0.05) items.push({ src: 'model', title: `${cname(r.iso)}: снабжение улучшилось на ${fmt(100 * r.ds, 0)} п.п.`, text: 'Вода и еда дошли до большего числа людей.', iso: [r.iso] }); });
    rows.slice().sort((x, y) => x.ds * x.P - y.ds * y.P).slice(0, 2).forEach(r => { if (r.ds < -0.05) items.push({ src: 'model', title: `${cname(r.iso)}: снабжение ухудшилось на ${fmt(-100 * r.ds, 0)} п.п.`, text: 'Кончается топливо или еда, раздача не справляется.', iso: [r.iso] }); });
    rows.slice().sort((x, y) => y.h * y.P - x.h * x.P).slice(0, 2).forEach(r => { if (r.h > 0.3) items.push({ src: 'model', title: `${cname(r.iso)}: без еды ${fmt(100 * r.h, 0)} % населения`, text: 'Нужны поставки продовольствия и топливо для раздачи.', iso: [r.iso] }); });
    rows.slice().sort((x, y) => y.dg * y.P - x.dg * x.P).slice(0, 1).forEach(r => { if (r.dg > 0.03) items.push({ src: 'model', title: `${cname(r.iso)}: сеть восстановлена ещё на ${fmt(100 * r.dg, 0)} п.п.`, text: 'Смонтированы новые трансформаторы, свет вернулся в новые районы.', iso: [r.iso] }); });
  }
  (checks || []).forEach(c => {
    const p = (pmap && pmap[c.pid]) || M.c.patch[c.pid]; if (!p) return;
    if (c.res === 'stale') { items.push({ src: 'check', title: `Патч «${p.title}» (${cname(c.iso)}): срок проверки вышел`, text: 'Проверить его уже не с чем — слишком много месяцев прошло.', iso: [c.iso], pid: c.pid }); return; }
    const w = c.res === 'pass' ? 'подтвердился' : c.res === 'fail' ? 'не подтвердился' : 'ничего не изменил';
    items.push({ src: 'check', title: `Патч «${p.title}» (${cname(c.iso)}) ${w}`, text: `${goalRu(p.goal)}: ${sgn(c.d, 2)} ${goalUnit(p.goal)} против «тени» без патча.`, iso: [c.iso], pid: c.pid });
  });
  return { year: Yn, items: items.slice(0, 24) };
}

// ════════════════════════ ИИ-мир: правительства стран без игроков (вызов Claude)
function aiCountries(Y) {
  const s = M.sum[Y]; if (!s) return [];
  const pi = s.k.indexOf('P'), si = s.k.indexOf('served');
  return ISO.filter(iso => !ctrlOf(iso)).sort((a, b) => s.c[IDX[b]][pi] * (1 - s.c[IDX[b]][si] + 0.2) - s.c[IDX[a]][pi] * (1 - s.c[IDX[a]][si] + 0.2)).slice(0, 18);
}
function brief(Y, iso) {
  const r = (k, d = 2) => { const v = sv(Y, iso, k); return v == null ? null : +(+v).toFixed(d); };
  return { iso, name: cname(iso), pop_mln: r('P', 1), served: r('served'), grid: r('grid'), comms: r('comms'), logi: r('logi'), fuel_months: r('fuel'), food_months: r('food'), hungry: r('hungry'), crews_k: r('crews', 1), spare_transformers: r('Tsp', 0), need_new_transformers: r('Tnew', 0), factory_output: WORLD.isFactory(iso) ? r('prod', 1) : 0, losses_k: r('losses', 0), policy: (M.dec[Y] && M.dec[Y].pol[iso]) || {} };
}
const AI_MAX = 40000;
function buildAIPrompt(Y) {
  const Yn = Y + 1, s = M.sum[Y];
  const owned = Object.keys(M.c.ctrl).filter(iso => ctrlOf(iso) && IDX[iso] != null);
  const players = owned.slice(0, 20).map(iso => ({ iso, name: cname(iso), served: +(sv(Y, iso, 'served') || 0).toFixed(2), grid: +(sv(Y, iso, 'grid') || 0).toFixed(2), policy: polOf(iso) }));
  const reqs = Object.values(M.c.req).filter(q => q && q.open).slice(0, 20).map(q => ({ iso: q.iso, name: cname(q.iso), text: String(q.text || '').slice(0, 200) }));
  const levers = WORLD.LEVERS.map(l => l.k + ' (' + l.ru + (l.kind === 'iso' ? ', по странам-получателям' : '') + (l.min != null ? `, ${l.min}…${l.max} ${l.unit}` : '') + ')').join('; ');
  const mk = nc => ({
    month_index: Y, month: tLabel(Y), decide_for: tLabel(Yn),
    world: { comms: +s.w.comms.toFixed(2), logistics: +s.w.logi.toFixed(2), served: +s.w.served.toFixed(2), grid: +s.w.grid.toFixed(2), satellites: +s.w.S.toFixed(2), transformer_output_per_month: +s.w.prod.toFixed(0), losses_k: +s.w.losses.toFixed(0) },
    ai_countries: aiCountries(Y).slice(0, nc).map(iso => brief(Y, iso)),
    player_countries: players, requests_for_help: reqs,
    last_news: ((M.news[Y] && M.news[Y].items) || []).slice(0, 6).map(n => n.title)
  });
  let ctx = JSON.stringify(mk(18));
  if (ctx.length > AI_MAX) ctx = JSON.stringify(mk(12));
  if (ctx.length > AI_MAX) ctx = JSON.stringify(mk(8));
  return [
    `Ты — «остальной мир» в игре о восстановлении после геомагнитной сверхбури: электросети, спутники и дальняя связь выведены из строя по всей планете. Закончился ${tLabel(Y)} (месяц ${Y} после бури). Реши, что правительства стран без игроков сделают в ${tLabel(Yn)}.`,
    'Действуй как реальные правительства: сначала спасают своих (вода, еда, связь), но страны с заводами трансформаторов и запасами топлива и зерна помогают другим — особенно тем, кто просит и с кем есть связь. Помощь невозможна без связи у получателя (comms ≥ 0.2) и логистики у отправителя (logi ≥ 0.2). Радикальные решения — редкость.',
    'Модель считает всё сама; ты задаёшь только решения. Рычаги (доли — десятичные: 0.4 = 40 %; приоритеты prC/prW/prG/prL нормируются на единицу): ' + levers + '.',
    'Данные (доли 0…1; запасы в месяцах потребления; трансформаторы в штуках; бригады и потери в тысячах человек):',
    ctx,
    'Ответь ТОЛЬКО JSON такого вида (все поля необязательны):',
    '{"policies":{"AAA":{"prC":0.4,"prW":0.3,"prG":0.2,"prL":0.1,"ration":0.7,"exportT":0.5,"aidF":{"BBB":30},"aidFood":{"CCC":20},"aidT":{"DDD":10},"aidC":{"EEE":5},"aidR":{"FFF":2}}},"news":[{"title":"…","text":"…","iso":["AAA"]}]}',
    'policies — ПОЛНАЯ новая политика страны (заменяет прежнюю; укажи только страны, где что-то меняется; aid* — разовые отправки этого месяца). news — 3–6 коротких новостей по-русски о главных решениях и событиях месяца (заголовок до 90 знаков, текст 1–2 предложения). Коды стран — ISO3.'
  ].join('\n\n');
}
function sanitizeAI(r) {
  if (!r || typeof r !== 'object') return null;
  const out = { pol: {}, news: [] };
  for (const iso in (r.policies || {})) if (IDX[iso] != null && !ctrlOf(iso)) out.pol[iso] = WORLD.sanitize(r.policies[iso], iso);
  if (Array.isArray(r.news)) out.news = r.news.filter(n => n && n.title).slice(0, 8).map(n => ({ title: String(n.title).slice(0, 140), text: String(n.text || '').slice(0, 600), iso: Array.isArray(n.iso) ? n.iso.filter(x => IDX[x] != null) : [] }));
  return out;
}
// ════════════════════════ ИИ-мир без Claude: встроенные правила для стран без игроков (детерминированы состоянием мира)
function ruleAI(Y) {
  const s = M.sum[Y]; if (!s) return null;
  const g = game(), seed = ((g && g.seed) || 0) ^ (Y * 2654435761 >>> 0);
  let r = seed >>> 0; const rnd = () => { r = (r + 0x6D2B79F5) >>> 0; let t = r; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const pick = a => a[Math.floor(rnd() * a.length)];
  const B_ = {}; const b = iso => B_[iso] || (B_[iso] = brief(Y, iso));
  const free = ISO.filter(iso => !ctrlOf(iso) && b(iso).pop_mln >= 0.3);
  const needy = aiCountries(Y), policies = {}, news = [], used = Object.create(null);
  // 1. приоритеты и нормирование — по тому, что хуже всего
  for (const iso of needy) {
    const c = b(iso), prev = c.policy || {}, p = {};
    if (c.comms < 0.4) Object.assign(p, { prC: 0.45, prW: 0.35, prG: 0.1, prL: 0.1 });
    else if (c.served < 0.7) Object.assign(p, { prC: 0.2, prW: 0.4, prG: 0.2, prL: 0.2 });
    else if (c.grid < 0.8) Object.assign(p, { prC: 0.15, prW: 0.15, prG: 0.45, prL: 0.25 });
    else Object.assign(p, { prC: 0.2, prW: 0.2, prG: 0.3, prL: 0.3 });
    p.ration = c.fuel_months < 1.5 ? 0.85 : c.fuel_months < 3 ? 0.65 : 0.45;
    if (c.factory_output > 0) p.exportT = c.grid >= 0.6 ? 0.5 : 0.25;
    const changed = ['prC', 'prW', 'prG', 'prL', 'ration', 'exportT'].some(k => p[k] != null && Math.abs((prev[k] != null ? prev[k] : (WORLD.LEVERS.find(l => l.k === k) || {}).def || 0) - p[k]) > 0.12);
    if (!changed) continue;
    policies[iso] = p;
    if (news.length < 3) {
      const why = c.comms < 0.4 ? pick(['бросает бригады на связь: без радио помощь не дойдёт', 'сначала связь — вышки, узлы, КВ-сеть']) : c.served < 0.7 ? pick(['главное — вода и еда: насосы, склады, раздача', 'кормить и поить людей — остальное потом']) : c.grid < 0.8 ? pick(['переключается на монтаж трансформаторов', 'бригады уходят на электросеть']) : 'выравнивает приоритеты: сеть и дороги';
      news.push({ title: `${cname(iso)} ${why}`, text: p.ration >= 0.85 ? 'Топливо — только больницам, водоканалу и узлам связи.' : p.ration >= 0.65 ? 'Нормирование топлива ужесточено.' : 'Запасы позволяют ослабить нормирование.', iso: [iso] });
    }
  }
  // 2. помощь: кто просит (игроки) и кому хуже всего — от тех, у кого есть запас, связь и логистика
  const reqs = Object.values(M.c.req).filter(q => q && q.open && IDX[q.iso] != null).map(q => q.iso);
  const ok = iso => b(iso).comms >= 0.15;
  const wantF = reqs.filter(iso => ok(iso) && b(iso).fuel_months < 1.5).concat(needy.filter(iso => ok(iso) && b(iso).fuel_months < 1 && b(iso).hungry > 0.15)).filter((v, i, a) => a.indexOf(v) === i);
  const wantFood = reqs.filter(iso => ok(iso) && b(iso).hungry > 0.2).concat(needy.filter(iso => ok(iso) && b(iso).hungry > 0.3)).filter((v, i, a) => a.indexOf(v) === i);
  const wantT = reqs.filter(iso => ok(iso) && b(iso).need_new_transformers > 20).concat(needy.filter(iso => ok(iso) && b(iso).grid < 0.5 && b(iso).need_new_transformers > 50)).filter((v, i, a) => a.indexOf(v) === i).sort((x, y) => b(y).need_new_transformers - b(x).need_new_transformers);
  const wantR = needy.filter(iso => b(iso).comms < 0.2).concat(reqs.filter(iso => b(iso).comms < 0.3)).filter((v, i, a) => a.indexOf(v) === i);
  const donor = k => free.filter(iso => !policies[iso] || !policies[iso][k]).filter(iso => { const c = b(iso); return c.logi >= 0.25 && c.comms >= 0.25 && !(k === 'aidF' ? c.fuel_months < 4 : k === 'aidFood' ? c.food_months < 4 : k === 'aidT' ? !(c.spare_transformers > 30 && c.grid >= 0.5) : k === 'aidC' ? !(c.grid > 0.85 && c.crews_k > 8) : !(c.comms >= 0.6)); });
  const give = (k, want, q, top) => {
    let n = 0;
    for (const to of want) {
      if (n >= top) break;
      const ds = donor(k).filter(d => d !== to && !used[d + k]).sort((x, y) => (k === 'aidF' ? b(y).fuel_months - b(x).fuel_months : k === 'aidFood' ? b(y).food_months - b(x).food_months : k === 'aidT' ? b(y).spare_transformers - b(x).spare_transformers : b(y).pop_mln - b(x).pop_mln));
      const d = ds[0]; if (!d) continue;
      used[d + k] = 1; n++;
      const p = policies[d] || (policies[d] = Object.assign({}, b(d).policy || {}, {}));
      ['aidT', 'aidF', 'aidFood', 'aidC', 'aidR'].forEach(x => { if (p[x] && typeof p[x] === 'object') delete p[x]; });   // разовые отправки прошлого месяца не повторяются
      p[k] = Object.assign({}, p[k] || {}, { [to]: q(to, d) });
      if (news.length < 6 && n === 1) news.push({ title: `${cname(d)} → ${cname(to)}: ${AIDRU[k.slice(3)]}, ${aidQ(k.slice(3), p[k][to])}`, text: k === 'aidR' ? 'КВ-радио и спутниковые терминалы: без связи страна не может даже попросить о помощи.' : 'Правительство откликнулось ' + (reqs.includes(to) ? 'на просьбу о помощи.' : 'на сводки о положении в стране.'), iso: [d, to] });
    }
  };
  give('aidF', wantF, to => b(to).pop_mln > 50 ? 15 : 30, 3);
  give('aidFood', wantFood, to => b(to).pop_mln > 50 ? 15 : 30, 3);
  give('aidT', wantT, (to, d) => Math.max(5, Math.min(60, Math.round(b(d).spare_transformers * 0.3))), 2);
  give('aidR', wantR, () => 2, 2);
  give('aidC', needy.filter(iso => ok(iso) && b(iso).grid < 0.4 && b(iso).crews_k < 3), (to, d) => Math.max(1, Math.min(10, Math.round(b(d).crews_k * 0.2))), 1);
  return { policies, news };
}
let AICTL = null;
async function askAI(Y) {
  if (!SAMPLE) return sanitizeAI(ruleAI(Y));
  AICTL = new AbortController();
  try {
    const r = await SAMPLE.json(buildAIPrompt(Y), { modelTier: 'default', signal: AICTL.signal, cache: false });
    return sanitizeAI(r);
  } catch (e) {
    if (e && ['not_granted', 'sampling_disabled', 'not_declared', 'capability_disabled', 'capability_removed'].includes(e.code)) { M.aiOk = false; toast('Claude недоступен в этом просмотре — остальной мир ходит по встроенным правилам.', 6000); }
    else if (e && e.code === 'cancelled') toast('Раздумья Claude остановлены — остальной мир сходил по встроенным правилам.');
    else if (e && e.code === 'rate_limited') toast('Claude сейчас перегружен (лимит) — остальной мир сходил по встроенным правилам.', 6000);
    else toast('Claude не ответил (' + ((e && e.code) || 'ошибка') + ') — остальной мир сходил по встроенным правилам.', 6000);
    return sanitizeAI(ruleAI(Y));
  } finally { AICTL = null; }
}

// ════════════════════════ действия игроков
function ctrlIdle(d) { return !!d && curYear() - (d.act != null ? d.act : d.since != null ? d.since : BASE) >= IDLE; }
async function touchCtrl(iso) {
  const d = M.c.ctrl[iso]; if (!d || d.owner !== ACT.id) return;
  const Y = curYear(); if (d.act === Y) return;
  try { await B.update('ctrl/' + iso, { act: Y }); if (B.remote) M.c.ctrl[iso] = Object.assign({}, d, { act: Y }); } catch (e) { }
}
async function claimCountry(iso) {
  if (!canAct() || IDX[iso] == null) return;
  const mine = myCountries();
  if (mine.includes(iso)) return;
  if (mine.length >= MAX_OWN) { toast(`Одному игроку можно вести не больше ${MAX_OWN} стран — сначала отдайте какую-нибудь ИИ.`); return; }
  try {
    const pre = await B.get('ctrl/' + iso);
    if (pre && pre.owner && pre.owner !== ACT.id && !ctrlIdle(pre)) { toast('Страной уже управляет ' + nameOf(pre.owner) + '.'); return; }
    if (!(await B.lock('ctrl/' + iso, 4000))) { toast('Страну прямо сейчас берёт кто-то другой — попробуйте через пару секунд.'); return; }
    const cur = await B.get('ctrl/' + iso);
    if (cur && cur.owner && cur.owner !== ACT.id && !ctrlIdle(cur)) { toast('Страной уже управляет ' + nameOf(cur.owner) + '.'); return; }
    const Y = curYear(), d = await getDec(Y);
    await putPol(iso, WORLD.sanitize(stripOnce((d && d.pol && d.pol[iso]) || {}), iso), Y);
    await B.set('ctrl/' + iso, { iso, owner: ACT.id, since: Y, act: Y, t: Date.now(), autoRevert: true });
    if (B.remote) M.c.ctrl[iso] = { iso, owner: ACT.id, since: Y, act: Y, t: Date.now(), autoRevert: true };
    await logAdd({ t: 'claim', iso });
    toast((cur && cur.owner ? 'Страна была брошена — теперь ею управляете вы: ' : 'Теперь вы управляете: ') + cname(iso) + '. Решения вступят в силу со следующего месяца.');
  } catch (e) { failWrite(e, 'Не получилось взять страну'); }
}
async function releaseCountry(iso) {
  if (!canAct() || !isMine(iso)) return;
  try { await B.del('ctrl/' + iso); await logAdd({ t: 'release', iso }); toast(cname(iso) + ' снова под управлением ИИ.'); }
  catch (e) { failWrite(e, 'Не получилось отказаться'); }
}
async function createPatch(iso, ch, goal, title, note, site, autoRevert) {
  if (!canAct()) return null;
  const pid = 'p' + rid(8);
  const doc = { pid, iso, author: ACT.id, t: Date.now(), created: curYear(), title: String(title || '').slice(0, 90) || 'Без названия', note: String(note || '').slice(0, 600),
    ch: clone(ch), goal: { m: GOALS[goal.m] ? goal.m : 'served', h: Math.max(1, Math.min(12, goal.h | 0)), iso: goal.iso && IDX[goal.iso] != null && goal.iso !== iso ? goal.iso : null }, status: 'open', site: site || null, autoRevert: autoRevert !== false };
  try { await B.set('patch/' + pid, doc); if (B.remote) M.c.patch[pid] = doc; await logAdd({ t: 'patch', pid, iso }); return doc; }
  catch (e) { failWrite(e, 'Не получилось сохранить патч'); return null; }
}
async function mergePatch(pid) {
  let p = M.c.patch[pid]; if (!p) { try { p = await B.get('patch/' + pid); } catch (e) { } }
  if (!p || !canAct()) return;
  if (!isMine(p.iso)) { toast('Принимать патчи может только тот, кто управляет страной.'); return; }
  try {
    const fresh = (await B.get('patch/' + pid)) || p;
    if (fresh.status !== 'open') { toast('Патч уже ' + statusRu(fresh.status) + '.'); return; }
    const g = await B.get('game/state'), Y = g && g.year != null ? g.year : curYear();
    const cur = await B.get('pol/' + p.iso), base = polDoc(cur, Y);
    const np = WORLD.sanitize(applyCh(base, p.ch), p.iso);
    const pa = chPrevApp(base, p.ch, np);
    await putPol(p.iso, np, Y);
    await B.update('patch/' + pid, { status: 'merged', year: Y, due: Y + p.goal.h, mergedBy: ACT.id, prev: pa.prev, app: pa.app });
    if (B.remote) M.c.patch[pid] = Object.assign({}, fresh, { status: 'merged', year: Y, due: Y + p.goal.h, mergedBy: ACT.id, prev: pa.prev, app: pa.app });
    await touchCtrl(p.iso);
    await logAdd({ t: 'merge', pid, iso: p.iso });
    toast(`Патч принят. Вступит в силу в ${tLabel(Y + 1)}, проверка — в конце ${tLabel(Y + p.goal.h)}.`);
  } catch (e) { failWrite(e, 'Не получилось принять патч'); }
}
async function rejectPatch(pid) {
  let p = M.c.patch[pid]; if (!p) { try { p = await B.get('patch/' + pid); } catch (e) { } }
  if (!p || !canAct()) return;
  if (!isMine(p.iso) && p.author !== ACT.id) return;
  try {
    const fresh = (await B.get('patch/' + pid)) || p;
    if (fresh.status !== 'open') { toast('Патч уже ' + statusRu(fresh.status) + '.'); return; }
    await B.update('patch/' + pid, { status: 'rejected', by2: ACT.id });
    await logAdd({ t: 'reject', pid, iso: p.iso });
  } catch (e) { failWrite(e, 'Не получилось отклонить'); }
}
// заявка о помощи: видна всем игрокам и ИИ
async function setRequest(iso, text, open) {
  if (!isMine(iso)) return;
  const doc = { iso, by: ACT.id, t: Date.now(), y: curYear(), text: String(text || '').slice(0, 300), open: !!open };
  try { await B.set('req/' + iso, doc); if (B.remote) M.c.req[iso] = doc; else localChanged('req'); await touchCtrl(iso); await logAdd({ t: open ? 'req' : 'unreq', iso }); toast(open ? 'Заявка опубликована: её видят игроки и ИИ.' : 'Заявка снята.'); }
  catch (e) { failWrite(e, 'Не получилось'); }
}
async function setAI(on) {
  if (!canAct()) return;
  try { await B.update('game/state', { ai: !!on }); if (!B.remote) { M.c.game.state.ai = !!on; localChanged('game'); } } catch (e) { failWrite(e, 'Не получилось'); }
}
async function resetWorld() {
  if (!(await B.lock('game/state', 30000))) { toast('Только что считался месяц — попробуйте через 10–15 секунд.'); return; }
  try {
    for (const coll of ['ctrl', 'pol', 'patch', 'sum', 'dec', 'decp', 'news', 'chk', 'ai', 'log2', 'fork', 'chat', 'req']) {
      for (let pass = 0; pass < 10; pass++) {
        const all = await B.list(coll), ids = Object.keys(all); if (!ids.length) break;
        for (const id of ids) await B.del(coll + '/' + id);
      }
    }
    for (const k of ['ctrl', 'pol', 'patch', 'fork', 'log2', 'dec', 'news', 'chk', 'ai', 'chat', 'req']) M.c[k] = {};
    M.sum = {}; M.news = {}; M.dec = {}; M.chk = {}; M.bad = {}; M.snaps = {}; M.st = null; M.stY = null;
    await createWorld(ACT.id);
    if (!B.remote) await onYearChanged(true);
    UI.sel = null; toast('Новый мир: снова октябрь 2026, первый месяц после бури.');
  } catch (e) { console.error(e); failWrite(e, 'Не получилось начать заново', false); }
}
async function pruneAll() {
  const pats = Object.values(M.c.patch).filter(Boolean);
  if (pats.length > 800) {
    const old = pats.filter(p => p.status !== 'open' && p.status !== 'merged').sort((a, b) => a.t - b.t).slice(0, pats.length - 600);
    for (const p of old) { try { await B.del('patch/' + p.pid); } catch (e) { break; } }
  }
  const forks = Object.values(M.c.fork).filter(Boolean);
  if (forks.length > 200) { for (const f of forks.sort((a, b) => a.t - b.t).slice(0, forks.length - 150)) { try { await B.del('fork/' + f.id); } catch (e) { break; } } }
  const msgs = Object.values(M.c.chat || {}).filter(Boolean);
  if (msgs.length > CHAT_MAX) { for (const m of msgs.sort((a, b) => a.t - b.t).slice(0, msgs.length - CHAT_KEEP)) { try { await B.del('chat/' + m.id); } catch (e) { break; } } }
  const pls = Object.values(M.c.players || {}).filter(p => p && p.id && !myCountriesOf(p.id).length && p.id !== ACT.id);
  if (pls.length > PLAYERS_MAX) { for (const p of pls.sort((a, b) => (a.seen || 0) - (b.seen || 0)).slice(0, pls.length - PLAYERS_MAX + 50)) { try { await B.del('players/' + p.id); } catch (e) { break; } } }
}
