'use strict';
// ════════════════════════ Экономика форков — ядро: утилиты, данные, хранилище, действия
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
function fmt(x, d = 1) { if (x == null || !isFinite(x)) return '—'; return NF(d).format(x).replace('-', MINUS); }
function sgn(x, d = 1) { if (x == null || !isFinite(x)) return '—'; const s = fmt(Math.abs(x), d); return (x > 0 ? '+' : x < 0 ? MINUS : '±') + s; }
function fmtPop(p) {
  if (!p) return 'нет данных';
  if (p >= 1e9) return fmt(p / 1e9, 2) + ' млрд';
  if (p >= 1e6) return fmt(p / 1e6, p >= 1e8 ? 0 : 1) + ' млн';
  if (p >= 1e4) return fmt(p / 1e3, 0) + ' тыс.';
  return fmt(p, 0);
}
function fmtMoney(v) { return v == null ? '—' : fmt(Math.round(v), 0) + ' $'; }
function plural(n, a, b, c) { n = Math.abs(n) % 100; const n1 = n % 10; if (n > 10 && n < 20) return c; if (n1 > 1 && n1 < 5) return b; if (n1 === 1) return a; return c; }
function years(n) { return n + ' ' + plural(n, 'год', 'года', 'лет'); }
function rid(n = 8) { const a = new Uint8Array(n); crypto.getRandomValues(a); return Array.from(a, b => (b % 36).toString(36)).join(''); }
function hashId(s) { let h1 = 0x811c9dc5, h2 = 0x1b873593; for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = Math.imul(h2 ^ c, 2246822507); } return ((h1 >>> 0).toString(16).padStart(8, '0') + (h2 >>> 0).toString(16).padStart(8, '0')).slice(0, 8); }
function clone(o) { return o == null ? o : JSON.parse(JSON.stringify(o)); }
function deepMerge(t, s) { for (const k in s) { const v = s[k]; if (v && typeof v === 'object' && !Array.isArray(v) && t[k] && typeof t[k] === 'object' && !Array.isArray(t[k])) deepMerge(t[k], v); else t[k] = clone(v); } return t; }
function debounce(f, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; }
function toast(msg, ms = 3200) { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('on'), ms); }
function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

// ════════════════════════ данные
const DATA = {
  countries: JSON.parse($('#d-countries').textContent),
  topo110: JSON.parse($('#d-topo110').textContent),
  blob: null
};
const ECON = {};
Object.values(DATA.countries).forEach(c => { ECON[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0, pg: c.pg }; });
const PL = { byC: {}, byKey: {}, all: false };
async function loadBlob() {
  const b64 = $('#d-blob').textContent.trim();
  const bin = atob(b64), u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  let text;
  if (typeof DecompressionStream !== 'undefined') {
    const ds = new DecompressionStream('gzip');
    text = await new Response(new Blob([u8]).stream().pipeThrough(ds)).text();
  } else throw new Error('Браузер не умеет распаковывать данные');
  DATA.blob = JSON.parse(text);
  return DATA.blob;
}
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
function cname(iso3) { const c = DATA.countries[iso3]; return c ? c.ru : iso3; }

// ════════════════════════ состояние игры (зеркало общей базы или локальный мир)
const YEAR0 = 2026, MIN_GAP = 15000, CAP_PATCHES = 1000, CAP_PLACES = 700;
const M = {
  mode: 'local', remote: false, ready: false,
  c: { game: {}, places: {}, patches: {}, hist: {}, histl: {}, histc: {}, meta: {}, log: {}, players: {} },
  me: { id: null, isOwner: false, canWrite: true },
  busy: false,
  Y: {}   // год → { H: страны, L: места, C: проверки } — собранные из документов
};
const UI = { view: 'map', sel: null, metric: 'W', world: 'forks', pick: false, patchFilter: 'all', patchQ: '', patchSort: 'trust' };
const ACT = { id: null };
let USER = null, DB = null, DL = null;
const PROFILES = {};
function game() { return M.c.game.state || null; }
function curYear() { const g = game(); return g && g.year != null ? g.year : YEAR0; }
function place(key) { return M.c.places[key] || null; }
function rulesOf(key) { const p = place(key), out = {}; if (p && p.rules) for (const q in p.rules) if (p.rules[q]) out[q] = p.rules[q]; return out; }
function ownerOf(key) { const p = place(key); return p && p.owner ? p.owner : null; }
function isLocal(key) { return key && key.charAt(0) !== 'C'; }
function isActive(key) { const p = place(key); return !!(p && (p.owner || Object.values(p.rules || {}).some(Boolean))); }
function canAct() { return M.ready && M.me.canWrite !== false && !!ACT.id && !!game(); }

// запись года: страны + места + проверки
function rec(y) {
  const Yr = M.Y[y]; if (!Yr || !Yr.H) return null;
  const H = Yr.H, L = Yr.L || {}, C = Yr.C || {};
  return Object.assign({}, H, { ls: L.ls || {}, lopt: L.lopt || {}, rp: Object.assign({}, H.rp || {}, L.lrp || {}),
    plan: Object.assign({}, H.plan, { ls: L.pls || {} }), chk: C.chk || [], done: C.done || [] });
}
function yearH(y) { return M.Y[y] && M.Y[y].H; }
function yearC(y) { return M.Y[y] && M.Y[y].C; }
function stateOf(key, world, y) {
  y = y == null ? curYear() : y; const R = rec(y); if (!R) return null;
  const plan = world === 'plan';
  if (!isLocal(key)) { const a = (plan ? R.plan.cs : R.cs)[key.slice(2)]; return a ? ENGINE.unpackC(a) : null; }
  const a = (plan ? R.plan.ls : R.ls)[key];
  if (a) return ENGINE.unpackL(a);
  const cc = placeInfo(key).cc; if (!cc) return null;
  const s = (plan ? R.plan.cs : R.cs)[cc]; if (!s) return null;
  const st = ENGINE.unpackC(s); st.inherited = true; return st;
}
function piStarOf(key) { const cc = isLocal(key) ? placeInfo(key).cc : key.slice(2); return ECON[cc] ? SIM.params(ECON[cc]).piStar : 3; }

// сведения о месте
const CENTROID = {};
function placeInfo(key) {
  if (!key) return {};
  if (!isLocal(key)) {
    const iso3 = key.slice(2), c = DATA.countries[iso3] || {};
    const ctr = CENTROID[iso3] || [0, 0];
    return { key, kind: 'C', name: c.ru || iso3, cc: iso3, pop: c.P, lon: ctr[0], lat: ctr[1] };
  }
  const d = place(key), g = PL.byKey[key];
  if (key.startsWith('P:')) {
    const b = g || d || {};
    return { key, kind: 'P', name: b.name || '…', cc: b.cc, pop: b.pop, lon: b.lon, lat: b.lat, cap: b.cap || 0 };
  }
  return d ? { key, kind: 'U', name: d.name, cc: d.cc, pop: d.pop, lon: d.lon, lat: d.lat, parent: d.parent, by: d.by } : { key, kind: 'U', name: '…' };
}
function kindLabel(info) {
  if (info.kind === 'C') return 'Страна';
  if (info.kind === 'U') return 'Добавлено игроком';
  if (info.cap === 2) return 'Столица';
  if (info.cap === 1) return 'Центр региона';
  return (info.pop || 0) >= 20000 ? 'Город' : 'Посёлок или село';
}
// имя игрока
function nameOf(id) {
  if (!id) return 'никто';
  if (id === 'sys') return 'проверка';
  const pl = M.c.players[id];
  if (pl && pl.nick) return pl.nick;
  const p = PROFILES[id];
  if (p && p.name) return p.name;
  let hh = 0; for (let i = 0; i < id.length; i++) hh = (hh * 31 + id.charCodeAt(i)) >>> 0;
  return 'Игрок №' + (100 + hh % 900);
}
const PALETTE = ['#3E3BD8', '#2E7D6B', '#B4492F', '#B07A12', '#7A3FB8', '#1F7FA8', '#A8326E', '#4D7A1F'];
function colorOf(id) {
  if (!id) return '#888';
  const p = PROFILES[id]; if (p && p.color && !M.c.players[id]?.nick) return p.color;
  let h1 = 0; for (let i = 0; i < id.length; i++) h1 = (h1 * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[h1 % PALETTE.length];
}
let profTimer = null;
function refreshProfiles() {
  if (!USER) return;
  clearTimeout(profTimer);
  profTimer = setTimeout(async () => {
    const ids = new Set();
    Object.values(M.c.places).forEach(p => { if (p.owner) ids.add(p.owner); if (p.by) ids.add(p.by); });
    Object.values(M.c.patches).forEach(p => p.by && ids.add(p.by));
    Object.values(M.c.log).forEach(L => Object.values(L || {}).forEach(e => e && e.by && ids.add(e.by)));
    Object.keys(M.c.players).forEach(i => ids.add(i));
    if (M.me.id) ids.add(M.me.id);
    const list = [...ids].filter(i => i && !i.startsWith('h:') && !i.startsWith('local:') && i !== 'sys');
    if (!list.length) return;
    try {
      const ps = await USER.profiles(list); let changed = false;
      for (const i of list) { const p = ps[i]; if (p && (!PROFILES[i] || PROFILES[i].name !== p.name)) { PROFILES[i] = { name: p.name, color: p.color }; changed = true; } }
      if (changed) renderAll();
    } catch (e) { /* имена необязательны */ }
  }, 150);
}

// ════════════════════════ хранилище: общая база (db) или этот браузер
const LOCAL_KEY = 'ekonomika-forkov-v1';
const B = {
  remote: false,
  async get(path) {
    if (this.remote) { const s = await DB.doc(path).get(); return s.exists ? clone(s.data()) : null; }
    const [c, id] = path.split('/'); const v = (M.c[c] || {})[id]; return v == null ? null : clone(v);
  },
  async set(path, obj) {
    if (this.remote) return DB.doc(path).set(obj);
    const [c, id] = path.split('/'); (M.c[c] = M.c[c] || {})[id] = clone(obj); localChanged(c);
  },
  async update(path, obj) {
    if (this.remote) return DB.doc(path).update(obj);
    const [c, id] = path.split('/'); const cur = (M.c[c] || {})[id];
    if (!cur) throw { code: 'invalid_argument', message: 'нет документа ' + path };
    deepMerge(cur, obj); localChanged(c);
  },
  async upsert(path, obj) {
    try { await this.update(path, obj); }
    catch (e) {
      if (!e || e.code !== 'invalid_argument') throw e;
      if (await this.get(path)) throw e;   // документ есть — значит ошибка другая, не затираем
      await this.set(path, obj);
    }
  },
  async del(path) {
    if (this.remote) return DB.doc(path).delete();
    const [c, id] = path.split('/'); if (M.c[c]) delete M.c[c][id]; localChanged(c);
  },
  async list(coll) {
    if (this.remote) { const q = await DB.collection(coll).limit(1000).get(); const o = {}; q.docs.forEach(d => { o[d.id] = clone(d.data()); }); return o; }
    return clone(M.c[coll] || {});
  },
  async lock(path, ttl) {
    if (!this.remote) return true;
    try { const r = await DB.doc(path).acquire({ holder: (ACT.id || 'anon') + ':' + TAB, ttlMs: ttl || 20000 }); return !!r.acquired; }
    catch (e) { return false; }
  }
};
const TAB = rid(6);
// локальный режим: сохраняем мир в браузере (если можно)
const saveLocal = debounce(() => {
  if (B.remote) return;
  const ys = Object.keys(M.c.hist).map(Number).sort((a, b) => b - a);
  for (let keep = ys.length; keep >= 1; keep = Math.floor(keep / 2)) {
    const kept = new Set(ys.slice(0, keep));
    const pick = (coll) => { const o = {}; for (const id in (M.c[coll] || {})) if (kept.has(parseInt(id, 10))) o[id] = M.c[coll][id]; return o; };
    const snap = Object.assign({}, M.c, { hist: pick('hist'), histl: pick('histl'), histc: pick('histc'), log: pick('log') });
    if (lsSet(LOCAL_KEY, JSON.stringify(snap))) return;
  }
}, 500);
function localChanged(c) { saveLocal(); scheduleRender(c); }

// ════════════════════════ мир: создание, ход года, сброс
function econForEngine() { return ECON; }
async function createWorld(by) {
  const seed = (Math.random() * 2 ** 31) >>> 0;
  const H0 = ENGINE.initialHistory(ECON, YEAR0, seed);
  await putYear(YEAR0, splitRec(H0));
  await B.set('meta/series', { f: { [YEAR0]: H0.agg.forks }, p: { [YEAR0]: H0.agg.plan } });
  await B.set('meta/pstats', { v: 1 });
  await B.set('log/' + YEAR0, { ['w' + rid(4)]: { t: 'world', by, ts: Date.now() } });
  await B.set('game/state', { year: YEAR0, seed, started: Date.now(), lastAt: 0, lastBy: by, v: 1 });
}
function splitRec(R) {
  const rpC = {}, rpL = {};
  for (const k in (R.rp || {})) (isLocal(k) ? rpL : rpC)[k] = R.rp[k];
  return {
    hist: { year: R.year, seed: R.seed, cs: R.cs, copt: R.copt || {}, rp: rpC, plan: { cs: R.plan.cs, opts: R.plan.opts }, ev: R.ev || [], shock: R.shock || null, agg: R.agg },
    histl: { ls: R.ls || {}, pls: R.plan.ls || {}, lopt: R.lopt || {}, lrp: rpL },
    histc: { chk: R.chk || [], done: R.done || [] }
  };
}
// Документ базы — не больше 256 КиБ, поэтому места и проверки года пишутся частями
const PART = 190 * 1024;
function partsOfLocals(L) {
  const keys = [...new Set([].concat(Object.keys(L.ls), Object.keys(L.pls), Object.keys(L.lopt), Object.keys(L.lrp)))];
  const parts = []; let cur = [], size = 0;
  for (const k of keys) {
    const row = [k, L.ls[k] || null, L.pls[k] || null, L.lopt[k] || null, L.lrp[k] || null], n = JSON.stringify(row).length + 1;
    if (size + n > PART && cur.length) { parts.push({ L: cur }); cur = []; size = 0; }
    cur.push(row); size += n;
  }
  parts.push({ L: cur }); return parts;
}
function partsOfChecks(C) {
  const parts = []; let cur = { chk: [], done: [] }, size = 0;
  const push = (f, x) => { const n = JSON.stringify(x).length + 1; if (size + n > PART && cur.chk.length + cur.done.length) { parts.push(cur); cur = { chk: [], done: [] }; size = 0; } cur[f].push(x); size += n; };
  C.chk.forEach(x => push('chk', x)); C.done.forEach(x => push('done', x));
  parts.push(cur); return parts;
}
async function putYear(Y, P3) {
  const pl = partsOfLocals(P3.histl), pc = partsOfChecks(P3.histc);
  await B.set('hist/' + Y, P3.hist);
  for (let i = 0; i < pl.length; i++) await B.set('histl/' + Y + '~' + i, pl[i]);
  for (let i = 0; i < pc.length; i++) await B.set('histc/' + Y + '~' + i, pc[i]);
  await B.set('histl/' + Y, { n: pl.length }); await B.set('histc/' + Y, { n: pc.length });
  M.Y[Y] = { H: clone(P3.hist), L: clone(P3.histl), C: clone(P3.histc) };
}
async function getParts(coll, y) {
  const idx = await B.get(coll + '/' + y); if (!idx || !idx.n) return [];
  return Promise.all(Array.from({ length: idx.n }, (_, i) => B.get(coll + '/' + y + '~' + i)));
}
// загрузить год: what — какие части нужны ('H' страны, 'L' места, 'C' проверки)
async function loadYear(y, fresh, what = 'HLC') {
  const cur = M.Y[y] || {};
  const need = what.split('').filter(k => fresh || !cur[k]);
  if (!need.length) return rec(y);
  const got = {};
  await Promise.all(need.map(async k => {
    if (k === 'H') got.H = await B.get('hist/' + y);
    if (k === 'L') { const L = { ls: {}, pls: {}, lopt: {}, lrp: {} }; (await getParts('histl', y)).forEach(p => (p && p.L || []).forEach(([key, a, b, c, d]) => { if (a) L.ls[key] = a; if (b) L.pls[key] = b; if (c) L.lopt[key] = c; if (d) L.lrp[key] = d; })); got.L = L; }
    if (k === 'C') { const C = { chk: [], done: [] }; (await getParts('histc', y)).forEach(p => { if (p) { C.chk.push(...(p.chk || [])); C.done.push(...(p.done || [])); } }); got.C = C; }
  }));
  if (need.includes('H') && !got.H) return null;
  M.Y[y] = Object.assign({}, cur, got);
  return rec(y);
}
// активные места для движка: у кого есть управляющий или решения, и их родители
function buildLocals(places) {
  const locals = {}, rules = {};
  for (const key in places) {
    const p = places[key]; if (!p) continue;
    const r = {}; let any = false;
    for (const q in (p.rules || {})) if (p.rules[q]) { r[q] = p.rules[q]; any = true; }
    if (any) rules[key] = r;
    if (isLocal(key) && (any || p.owner) && p.cc && ECON[p.cc]) locals[key] = { cc: p.cc, pop: p.pop || 1000, parent: p.parent || null };
  }
  for (const key in Object.assign({}, locals)) {
    let k = locals[key].parent, g = 0;
    while (k && !locals[k] && g++ < 5) {
      const p = places[k] || PL.byKey[k] || null;
      const pp = places[key];
      locals[k] = { cc: (p && p.cc) || locals[key].cc, pop: (p && p.pop) || (pp && pp.parentPop) || 1000, parent: (p && p.parent) || null };
      k = locals[k].parent;
    }
  }
  return { locals, rules };
}
async function advanceYear() {
  if (M.busy || !canAct()) return;
  M.busy = true; renderTop();
  try {
    if (!(await B.lock('game/state', 12000))) { toast('Год прямо сейчас считает другой игрок — подождите несколько секунд.'); return; }
    const st = await B.get('game/state'); if (!st || st.year == null) return;
    const wait = MIN_GAP - (Date.now() - (st.lastAt || 0));
    if (B.remote && wait > 0 && wait <= MIN_GAP) { toast('Год только что сменился — подождите несколько секунд, чтобы все успели увидеть итоги.'); return; }
    const y = st.year;
    const prev = clone(await loadYear(y, true));
    if (!prev) { toast('Нет записи прошлого года — перезагрузите страницу.'); return; }
    const places = await B.list('places');
    const { locals, rules } = buildLocals(places);
    const { hist, reverts } = ENGINE.step(prev, ECON, locals, rules, M.c.patches);
    // продлить аренду и убедиться, что этот год ещё никто не посчитал
    if (!(await B.lock('game/state', 12000))) { toast('Год прямо сейчас считает другой игрок.'); return; }
    const st2 = await B.get('game/state'); if (!st2 || st2.year !== y) { toast('Этот год уже посчитал другой игрок.'); return; }
    const Y = y + 1;
    await putYear(Y, splitRec(hist));
    // откаты: место перечитывается прямо перед записью, чтобы не затереть решение, принятое во время расчёта
    const byKey = {};
    // своего решения не было (место наследовало у родителя) или было «как было» — откат просто снимает решение
    for (const rv of reverts) rv.qs.forEach((q, i) => { (byKey[rv.key] = byKey[rv.key] || {})[q] = { pid: rv.pid, val: (+rv.prev[i] === 0 || (rv.own && !rv.own[i])) ? null : { pid: 'revert:' + rv.pid, opt: +rv.prev[i], since: Y, by: 'sys' } }; });
    for (const key in byKey) {
      try {
        const cur = await B.get('places/' + key); if (!cur || !cur.rules) continue;
        const upd = {}; for (const q in byKey[key]) { const c = cur.rules[q]; if (c && c.pid === byKey[key][q].pid) upd[q] = byKey[key][q].val; }
        if (Object.keys(upd).length) await B.update('places/' + key, { rules: upd });
      } catch (e) { console.warn('откат', key, e); }
    }
    await B.upsert('meta/series', { f: { [Y]: hist.agg.forks }, p: { [Y]: hist.agg.plan } });
    if (hist.done.length) {
      const cur = (await B.get('meta/pstats')) || {}, upd = {};
      for (const d of hist.done) { const o = upd[d.pid] || cur[d.pid] || { ok: 0, fail: 0 }; upd[d.pid] = { ok: o.ok + (d.ok ? 1 : 0), fail: o.fail + (d.ok ? 0 : 1) }; }
      await B.upsert('meta/pstats', upd);
    }
    await prunePatches(places, hist, Y);
    await B.set('log/' + Y, { ['y' + rid(4)]: { t: 'year', by: ACT.id, ts: Date.now() } });
    await B.update('game/state', { year: Y, lastAt: Date.now(), lastBy: ACT.id });
    if (!B.remote) await onYearChanged();
    const pass = hist.done.filter(d => d.ok).length, fail = hist.done.length - pass;
    const evs = hist.ev.filter(e => EVT[e.t]).map(e => EVT[e.t].short), evTxt = evs.join(', ');
    toast(`Наступил ${Y} год.` + (evs.length ? ' ' + evTxt.charAt(0).toUpperCase() + evTxt.slice(1) + '.' : '')
      + (hist.done.length ? ` Проверки по итогам: прошли — ${pass}, не прошли — ${fail}${fail ? ' (эти патчи откачены)' : ''}.` : ''), 5600);
  } catch (e) {
    console.error(e); failWrite(e, 'Не получилось посчитать год', false);
  } finally { M.busy = false; renderTop(); }
}
// старые патчи, которые нигде не действуют, удаляются, чтобы общая база не упёрлась в предел документов
async function prunePatches(places, hist, Y) {
  const all = Object.values(M.c.patches); if (all.length <= CAP_PATCHES - 100) return;
  const used = new Set();
  for (const k in places) for (const q in (places[k].rules || {})) { const r = places[k].rules[q]; if (r) used.add(String(r.pid).replace('revert:', '')); }
  (hist.chk || []).forEach(c => used.add(c.pid));
  const old = all.filter(p => !used.has(p.pid) && p.year <= Y - 5).sort((a, b) => a.t - b.t).slice(0, 60);
  for (const p of old) { try { await B.del('patches/' + p.pid); } catch (e) { break; } }
}
async function resetWorld() {
  if (!(await B.lock('game/state', 30000))) { toast('Только что считался год — попробуйте через 10–15 секунд.'); return; }
  try {
    for (const coll of ['places', 'patches', 'hist', 'histl', 'histc', 'log', 'meta']) {
      for (let pass = 0; pass < 10; pass++) {
        const all = await B.list(coll), ids = Object.keys(all);
        if (!ids.length) break;
        for (const id of ids) await B.del(coll + '/' + id);
      }
    }
    M.c.hist = {}; M.c.histl = {}; M.c.histc = {}; M.c.log = {}; M.Y = {}; if (typeof loadingYears !== 'undefined') loadingYears.clear();
    await createWorld(ACT.id);
    if (!B.remote) await onYearChanged();
    UI.sel = null; toast('Мир начат заново с данных 2026 года.');
  } catch (e) { console.error(e); failWrite(e, 'Не получилось начать заново', false); }
}
function failWrite(e, what, perm = true) {
  // отказ в простой записи — почти наверняка нет права ходить; большие записи (год) могут не пройти и по размеру
  if (perm && e && e.code === 'invalid_argument' && B.remote) { M.me.canWrite = false; renderAll(); toast(what + ': у вас доступ только на просмотр.'); return; }
  if (e && e.code === 'quota_exceeded') { toast(what + ': в общей базе закончилось место (лимит документов).'); return; }
  if (e && e.code === 'resource_exhausted') { toast(what + ': слишком часто — подождите немного.'); return; }
  toast(what + (e && e.message ? ': ' + e.message : '.'));
}

// ════════════════════════ действия игроков
async function logAdd(entry) {
  const y = curYear(), id = entry.t.charAt(0) + rid(6);
  entry.by = entry.by || ACT.id; entry.ts = Date.now();
  try { await B.upsert('log/' + y, { [id]: entry }); } catch (e) { console.warn('хроника', e); }
}
function placeSkeleton(key) {
  const i = placeInfo(key);
  if (i.kind === 'C') return { key, kind: 'C', cc: i.cc, rules: {} };
  return { key, kind: i.kind, cc: i.cc, name: i.name, lat: i.lat, lon: i.lon, pop: i.pop || 0, rules: {} };
}
async function claim(key) {
  if (!canAct()) return;
  if (isLocal(key) && !place(key) && Object.keys(M.c.places).filter(isLocal).length >= CAP_PLACES) { toast('В мире уже слишком много активных мест — это ограничение общей базы.'); return; }
  try {
    const pre = await B.get('places/' + key);
    if (pre && pre.owner && pre.owner !== ACT.id) { toast('Место уже занято: ' + nameOf(pre.owner) + '.'); return; }
    if (!(await B.lock('places/' + key, 3000))) { toast('Это место прямо сейчас берёт кто-то другой — попробуйте через пару секунд.'); return; }
    const cur = await B.get('places/' + key);
    if (cur && cur.owner && cur.owner !== ACT.id) { toast('Место уже занято: ' + nameOf(cur.owner) + '.'); return; }
    const base = cur && cur.key ? cur : placeSkeleton(key);
    base.owner = ACT.id; base.since = curYear();
    await B.set('places/' + key, base);
    await logAdd({ t: 'claim', key });
    toast('Теперь вы управляете: ' + placeInfo(key).name + '.');
  } catch (e) { failWrite(e, 'Не получилось взять место'); }
}
async function release(key) {
  if (!canAct() || ownerOf(key) !== ACT.id) return;
  try {
    await logAdd({ t: 'release', key });
    if (key.startsWith('P:') && !Object.keys(rulesOf(key)).length) await B.del('places/' + key);
    else await B.update('places/' + key, { owner: null });
  }
  catch (e) { failWrite(e, 'Не получилось отказаться'); }
}
function patchLevel(ch) { return Object.keys(ch).some(q => SIM.Q[SIM.QI[q]].level === 'country') ? 'C' : 'A'; }
function canAdoptAt(pa, key) { return pa && (!isLocal(key) || patchLevel(pa.ch) === 'A'); }
async function createPatch(ch, m, hz, note) {
  if (!canAct()) return null;
  if (Object.keys(M.c.patches).length >= CAP_PATCHES) { toast(`В мире уже ${CAP_PATCHES} патчей — это предел общей базы. Старые неиспользуемые патчи удаляются сами при смене года.`); return null; }
  const t = Date.now();
  let pid = hashId(ACT.id + JSON.stringify(ch) + m + hz + note + t + rid(6));
  if (M.c.patches[pid] || await B.get('patches/' + pid)) pid = hashId(pid + rid(8));
  const doc = { pid, by: ACT.id, ch, m, h: Math.max(1, Math.min(10, Math.round(+hz) || 3)), note: note || '', year: curYear(), t, lvl: patchLevel(ch) };
  try { await B.set('patches/' + pid, doc); await logAdd({ t: 'patch', pid }); return doc; }
  catch (e) { failWrite(e, 'Не получилось создать патч'); return null; }
}
async function adopt(key, pid, doc) {
  if (!canAct()) return;
  if (ownerOf(key) !== ACT.id) { toast('Принять патч может только управляющий этого места.'); return; }
  let pa = doc || M.c.patches[pid];
  if (!pa) { try { pa = await B.get('patches/' + pid); } catch (e) { pa = null; } }
  if (!pa) { toast('Патч ' + pid + ' не найден.'); return; }
  if (!canAdoptAt(pa, key)) { toast('Этот патч меняет ставку или пошлины — его можно принять только в стране.'); return; }
  const rules = {};
  for (const q in pa.ch) rules[q] = { pid, opt: +pa.ch[q], since: curYear(), m: pa.m, h: pa.h, by: ACT.id };
  try { await B.update('places/' + key, { rules }); await logAdd({ t: 'adopt', key, pid }); toast(`Патч ${pid} принят: ${placeInfo(key).name}. Он начнёт действовать в ${curYear() + 1} году.`); }
  catch (e) { failWrite(e, 'Не получилось принять патч'); }
}
async function dropRule(key, q) {
  if (!canAct() || ownerOf(key) !== ACT.id) return;
  const cur = rulesOf(key)[q];
  try { await B.update('places/' + key, { rules: { [q]: null } }); await logAdd({ t: 'drop', key, q, pid: cur && cur.pid }); }
  catch (e) { failWrite(e, 'Не получилось снять решение'); }
}
async function addVillage(v) {
  if (!canAct()) return null;
  if (Object.keys(M.c.places).filter(isLocal).length >= CAP_PLACES) { toast('В мире уже слишком много активных мест.'); return null; }
  const key = 'U:' + rid(7);
  const doc = { key, kind: 'U', name: v.name, cc: v.cc, lat: +v.lat.toFixed(5), lon: +v.lon.toFixed(5), pop: v.pop || 0, parent: v.parent || null, parentPop: v.parentPop || 0,
    by: ACT.id, t: Date.now(), owner: v.own ? ACT.id : null, since: v.own ? curYear() : null, rules: {} };
  try { await B.set('places/' + key, doc); await logAdd({ t: 'village', key }); return key; }
  catch (e) { failWrite(e, 'Не получилось добавить место'); return null; }
}
async function addSeatPlayer(nick) {
  const id = (B.remote ? 'h:' : 'local:') + rid(6);
  try { await B.set('players/' + id, { nick: nick.slice(0, 32), host: M.me.id || 'local', seen: Date.now() }); return id; }
  catch (e) { failWrite(e, 'Не получилось добавить игрока'); return null; }
}
// статистика патчей
function patchStats(pid) {
  const s = (M.c.meta.pstats || {})[pid] || { ok: 0, fail: 0 };
  let live = 0; const where = [];
  for (const key in M.c.places) { const r = M.c.places[key].rules || {}; if (Object.values(r).some(x => x && x.pid === pid)) { live++; where.push(key); } }
  return { ok: s.ok || 0, fail: s.fail || 0, live, where };
}
function authorTrust(uid) {
  let ok = 0, fail = 0; const ps = M.c.meta.pstats || {};
  for (const pid in M.c.patches) if (M.c.patches[pid].by === uid && ps[pid]) { ok += ps[pid].ok || 0; fail += ps[pid].fail || 0; }
  return { ok, fail, share: ok + fail ? ok / (ok + fail) : null };
}
const EVT = {
  crisis: { ic: '⚡', short: 'мировой кризис', text: 'Мировой кризис: спрос во всех странах упал' },
  oil: { ic: '🛢', short: 'скачок цен на сырьё', text: 'Скачок цен на сырьё: инфляция выросла во всём мире' },
  boom: { ic: '☀', short: 'мировой подъём', text: 'Мировой подъём: спрос вырос во всех странах' }
};
const MNAME = { W: 'благополучие', y: 'доход на человека', u: 'безработица', pi: 'отклонение инфляции от цели', D: 'долг' };
function qName(q) { return SIM.Q[SIM.QI[q]].name; }
function qShort(q) { return SIM.Q[SIM.QI[q]].short; }
function optText(q, o) { return SIM.Q[SIM.QI[q]].opts[String(+o)]; }
function arrow(o) { return +o > 0 ? '↑' : +o < 0 ? '↓' : '='; }
function chText(ch) { return Object.keys(ch).sort((a, b) => SIM.QI[a] - SIM.QI[b]).map(q => qShort(q) + ' ' + arrow(ch[q])).join(', '); }
function diffText(metric, v) {
  const M0 = SIM.METRICS[metric]; if (!M0) return sgn(v, 2);
  if (metric === 'y') return sgn(v, 1) + '%';
  if (metric === 'W') return sgn(v, 2);
  return sgn(v, 2) + (metric === 'D' ? ' п.п.' : ' п.п.');
}
