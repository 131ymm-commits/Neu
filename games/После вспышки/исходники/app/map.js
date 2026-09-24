// ════════════════════════ карта: проекция, отрисовка, приближение до сёл
const RM = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)').matches : false;
function dur(ms) { return RM ? 0 : ms; }
const MAP = { cv: null, ctx: null, hit: null, dpr: 1, W: 0, H: 0, BW: 1000, BH: 520, s0: 1, ox: 0, oy: 0, t: null, zoom: null,
  f110: [], f50: null, sphere: null, grat: null, dots: [], hover: null, col: {}, colVer: 0, raf: 0, pal: null, fitted: false };
const MAPM = {
  grid: { name: 'Свет', short: 'Свет', get: iso => svc(iso, 'grid'), fmt: v => pct(v), kind: 'glow', dom: [0, 1], hint: 'доля восстановленной электросети' },
  comms: { name: 'Связь', short: 'Связь', get: iso => svc(iso, 'comms'), fmt: v => pct(v), kind: 'seqgood', dom: [0, 1], hint: 'радиосеть, вышки, спутники' },
  logi: { name: 'Логистика', short: 'Логистика', get: iso => svc(iso, 'logi'), fmt: v => pct(v), kind: 'seqgood', dom: [0, 1], hint: 'топливо, порты, склады, подвоз' },
  served: { name: 'Снабжение', short: 'Снабжение', get: iso => svc(iso, 'served'), fmt: v => pct(v), kind: 'seqgood', dom: [0, 1], hint: 'доля населения с водой и едой' },
  hungry: { name: 'Без еды', short: 'Голод', get: iso => svc(iso, 'hungry'), fmt: v => pct(v), kind: 'seqbad', dom: [0, 0.6], hint: 'доля населения, до которой не дошла еда' },
  fuel: { name: 'Топливо', short: 'Топливо', get: iso => svc(iso, 'fuel'), fmt: v => fmt(v, 1) + ' мес.', kind: 'seqgood', dom: [0, 3], hint: 'запас в месяцах критического потребления' },
  losses: { name: 'Потери', short: 'Потери', get: iso => { const l = svc(iso, 'losses'), P = svc(iso, 'P'); return l != null && P ? l / P : null; }, fmt: v => fmt(v, 1) + ' на тыс.', kind: 'seqbad', dom: [0, 15], hint: 'избыточные потери на тысячу жителей с начала бури (грубая оценка)' },
  who: { name: 'Кто управляет', short: 'Управление', kind: 'who', hint: 'игроки и ИИ' }
};
function svc(iso, k) { return sv(curYear(), iso, k); }
let FONT_STACK = 'system-ui, sans-serif';
function readPalette() {
  FONT_STACK = css('--sans') || FONT_STACK;
  MAP.pal = { sea: css('--sea'), land: css('--land'), na: css('--land-na'), ink: css('--ink'), muted: css('--muted'), line: css('--line'),
    bg: css('--bg'), panel: css('--panel'), accent: css('--accent'), good: css('--good'), bad: css('--bad'), warn: css('--warn'), glow: css('--glow') || '#F2C14E' };
  MAP.colVer++;
}
function interp(a, b, t) { return d3.interpolateLab(a, b)(Math.max(0, Math.min(1, t))); }
function valueColor(metric, v, iso) {
  const P = MAP.pal, m = MAPM[metric];
  if (v == null || !isFinite(v)) return P.na;
  const t = (v - m.dom[0]) / (m.dom[1] - m.dom[0]);
  if (m.kind === 'glow') return interp(P.land, P.glow, t);
  if (m.kind === 'seqgood') return interp(P.land, P.good, t);
  if (m.kind === 'seqbad') return interp(P.land, P.bad, t);
  return P.land;
}
function countryFill(iso3) {
  const P = MAP.pal; if (!iso3 || !ECON[iso3]) return P.na;
  if (!M.ready || !M.sum[curYear()]) return P.land;
  if (UI.metric === 'who') { const o = ownerOf(iso3); if (!o) return stateTag(iso3) === 'ai' && M.dec[curYear()] && M.dec[curYear()].pol[iso3] ? interp(P.land, P.warn, 0.35) : P.land; return interp(P.land, o === ACT.id ? P.accent : colorOf(o), 0.55); }
  return valueColor(UI.metric, MAPM[UI.metric].get(iso3), iso3);
}
function recolor() { MAP.col = {}; for (const iso3 in ECON) MAP.col[iso3] = countryFill(iso3); requestDraw(); }
const SITE_ST = { open: 1, merged: 1, kept: 1, neutral: 1 };
function siteKeys() { const o = Object.create(null); for (const id in M.c.patch) { const p = M.c.patch[id]; if (p && p.site && SITE_ST[p.status]) o[p.site] = p; } return o; }

function initMap() {
  MAP.cv = $('#map'); MAP.ctx = MAP.cv.getContext('2d'); MAP.hit = document.createElement('canvas').getContext('2d');
  readPalette();
  const proj = MAP.proj = d3.geoNaturalEarth1().fitExtent([[0, 0], [MAP.BW, MAP.BH]], { type: 'Sphere' });
  const path = d3.geoPath(proj);
  MAP.sphere = new Path2D(path({ type: 'Sphere' }));
  MAP.grat = new Path2D(path(d3.geoGraticule10()));
  MAP.f110 = buildFeatures(DATA.topo110, path, true);
  MAP.t = d3.zoomIdentity;
  MAP.zoom = d3.zoom().scaleExtent([1, 2500]).clickDistance(6)
    .on('start', () => MAP.cv.classList.add('drag'))
    .on('zoom', e => { MAP.t = e.transform; hideTip(); requestDraw(); })
    .on('end', () => MAP.cv.classList.remove('drag'));
  d3.select(MAP.cv).call(MAP.zoom).on('dblclick.zoom', null);
  MAP.cv.addEventListener('click', onMapClick);
  MAP.cv.addEventListener('dblclick', e => { const p = pt(e); d3.select(MAP.cv).transition().duration(dur(350)).call(MAP.zoom.scaleBy, 2.5, p); });
  MAP.cv.addEventListener('mousemove', onMapMove);
  MAP.cv.addEventListener('mouseleave', hideTip);
  new ResizeObserver(() => resizeMap()).observe($('#mapwrap'));
  $('#zin').onclick = () => d3.select(MAP.cv).transition().duration(dur(300)).call(MAP.zoom.scaleBy, 2);
  $('#zout').onclick = () => d3.select(MAP.cv).transition().duration(dur(300)).call(MAP.zoom.scaleBy, 0.5);
  $('#zhome').onclick = () => d3.select(MAP.cv).transition().duration(dur(500)).call(MAP.zoom.transform, d3.zoomIdentity);
  resizeMap();
}
function buildFeatures(topo, path, centroids) {
  const fc = topojson.feature(topo, topo.objects.countries);
  return fc.features.map(f => {
    const iso3 = f.id || null, b = path.bounds(f);
    if (centroids && iso3 && !CENTROID[iso3]) {
      // центр по крупнейшему куску
      let best = null, ba = -1;
      const polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates.map(c => ({ type: 'Polygon', coordinates: c })) : [f.geometry];
      polys.forEach(g => { const a = d3.geoArea(g); if (a > ba) { ba = a; best = g; } });
      CENTROID[iso3] = d3.geoCentroid(best || f);
    }
    let mb = b;
    if (f.geometry && f.geometry.type === 'MultiPolygon') {
      let best = null, ba = -1;
      f.geometry.coordinates.forEach(c => { const g = { type: 'Polygon', coordinates: c }, a = d3.geoArea(g); if (a > ba) { ba = a; best = g; } });
      if (best) mb = path.bounds(best);
    }
    return { iso3, name: iso3 ? cname(iso3) : ((f.properties && f.properties.n) || ''), path: new Path2D(path(f)), bb: b, mb };
  });
}
function ensure50() {
  if (MAP.f50 || !DATA.blob) return;
  MAP.f50 = buildFeatures(DATA.blob.topo50, d3.geoPath(MAP.proj), true);
}
function resizeMap() {
  const w = $('#mapwrap'); const W = w.clientWidth, H = w.clientHeight; if (!W || !H) return;
  // что было в центре экрана — чтобы карта не прыгала при смене размера
  const moved = MAP.W && MAP.H && MAP.t && (MAP.t.k !== 1 || MAP.t.x !== 0 || MAP.t.y !== 0);
  const c0 = moved ? toBase(MAP.W / 2, MAP.H / 2) : null;
  MAP.W = W; MAP.H = H; MAP.dpr = Math.min(2.5, window.devicePixelRatio || 1);
  MAP.cv.width = Math.round(W * MAP.dpr); MAP.cv.height = Math.round(H * MAP.dpr);
  const narrow = W < 900;
  const padTop = narrow ? 92 : 64, padBot = narrow ? 70 : 40;
  const availH = Math.max(120, H - padTop - padBot);
  MAP.s0 = Math.min(W / MAP.BW, availH / MAP.BH) * 0.98;
  MAP.ox = (W - MAP.BW * MAP.s0) / 2; MAP.oy = padTop + (availH - MAP.BH * MAP.s0) / 2;
  MAP.zoom.extent([[0, 0], [W, H]]).translateExtent([[-W * 0.25, -H * 0.25], [W * 1.25, H * 1.25]]);
  if (c0 && isFinite(c0[0]) && isFinite(c0[1])) {
    const k = MAP.t.k, t = d3.zoomIdentity.translate(W / 2 - k * (MAP.s0 * c0[0] + MAP.ox), H / 2 - k * (MAP.s0 * c0[1] + MAP.oy)).scale(k);
    MAP.t = t; d3.select(MAP.cv).call(MAP.zoom.transform, t);
  }
  requestDraw();
}
function requestDraw() { if (MAP.raf) return; MAP.raf = requestAnimationFrame(() => { MAP.raf = 0; drawMap(); }); }
function viewTf() { const k = MAP.t.k; return { k, S: MAP.s0 * k, TX: MAP.t.x + MAP.ox * k, TY: MAP.t.y + MAP.oy * k }; }
function toBase(sx, sy) { const v = viewTf(); return [(sx - v.TX) / v.S, (sy - v.TY) / v.S]; }
function pt(e) { const r = MAP.cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
function popThreshold(k) { return 9e6 / (k * k); }
function drawMap() {
  const { ctx, dpr, W, H, pal: P } = MAP; if (!W) return;
  const v = viewTf();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.fillStyle = P.bg; ctx.fillRect(0, 0, W, H);
  ctx.setTransform(dpr * v.S, 0, 0, dpr * v.S, dpr * v.TX, dpr * v.TY);
  ctx.fillStyle = P.sea; ctx.fill(MAP.sphere);
  ctx.lineWidth = 0.5 / v.S; ctx.strokeStyle = P.line; ctx.globalAlpha = 0.35; ctx.stroke(MAP.grat); ctx.globalAlpha = 1;
  if (v.k >= 2.2) ensure50();
  const feats = v.k >= 2.2 && MAP.f50 ? MAP.f50 : MAP.f110;
  const [x0, y0] = toBase(0, 0), [x1, y1] = toBase(W, H);
  const vis = [];
  for (const f of feats) {
    if (f.bb[1][0] < x0 || f.bb[0][0] > x1 || f.bb[1][1] < y0 || f.bb[0][1] > y1) continue;
    vis.push(f); ctx.fillStyle = f.iso3 ? (MAP.col[f.iso3] || P.land) : P.na; ctx.fill(f.path);
  }
  ctx.lineWidth = 0.7 / v.S; ctx.strokeStyle = P.panel; ctx.lineJoin = 'round';
  for (const f of vis) ctx.stroke(f.path);
  // выделения: мои страны, выбранная
  for (const f of vis) {
    if (!f.iso3) continue; const key = 'C:' + f.iso3, own = ownerOf(f.iso3);
    if (UI.sel === key) { ctx.lineWidth = 2.4 / v.S; ctx.strokeStyle = P.ink; ctx.stroke(f.path); }
    else if (own) { ctx.lineWidth = 1.6 / v.S; ctx.strokeStyle = own === ACT.id ? P.accent : colorOf(own); ctx.stroke(f.path); }
  }
  drawPlaces(v, vis);
  const ml = $('#maploading'); if (ml && M.ready) ml.remove();
}
function drawPlaces(v, vis) {
  const { ctx, dpr, W, H, pal: P } = MAP;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const thr = popThreshold(v.k), dots = [], seen = new Set();
  const proj = MAP.proj;
  function add(p, active) {
    if (seen.has(p.key)) return; if (p.lon == null) return;
    if (p.bx === undefined) { const b = proj([p.lon, p.lat]); p.bx = b[0]; p.by = b[1]; }
    const sx = p.bx * v.S + v.TX, sy = p.by * v.S + v.TY;
    if (sx < -20 || sy < -20 || sx > W + 20 || sy > H + 20) return;
    seen.add(p.key); dots.push({ p, sx, sy, active, r: 1.6 + Math.max(0, Math.log10(Math.max(p.pop || 300, 300)) - 2.5) * (v.k > 30 ? 1.25 : 1.0) });
  }
  // активные места и свои сёла — всегда
  const sites = siteKeys();
  for (const key in sites) { const g = PL.byKey[key]; if (g && v.k >= 1.3) add(g, true); }
  if (DATA.blob && v.k >= 1.3) {
    // географические границы видимой области (с запасом) — быстрый отсев без проекции
    let gb = null;
    if (v.k >= 3) {
      const pts = [[0, 0], [W / 2, 0], [W, 0], [W, H / 2], [W, H], [W / 2, H], [0, H], [0, H / 2]].map(([x, y]) => proj.invert(toBase(x, y))).filter(q => q && isFinite(q[0]) && isFinite(q[1]));
      if (pts.length === 8) {
        let a = Math.min(...pts.map(q => q[0])), b = Math.max(...pts.map(q => q[0])), c = Math.min(...pts.map(q => q[1])), d = Math.max(...pts.map(q => q[1]));
        const mx = (b - a) * 0.08 + 0.05, my = (d - c) * 0.08 + 0.05; gb = [a - mx, b + mx, c - my, d + my];
      }
    }
    let budget = 3000;
    for (const f of vis) {
      if (!f.iso3 || budget <= 0) continue;
      const arr = placesOf(f.iso3);
      if (arr.capital === undefined) arr.capital = arr.find(p => p.cap === 2) || null;
      if (arr.capital) add(arr.capital, false);
      for (let i = 0; i < arr.length && budget > 0; i++) {
        const p = arr[i];
        if (p.pop < thr && !(p.cap === 2 && v.k >= 1.3) && !(p.cap === 1 && v.k >= 4)) { if (p.pop < thr / 4) break; else continue; }
        if (gb && (p.lon < gb[0] || p.lon > gb[1] || p.lat < gb[2] || p.lat > gb[3])) continue;
        const n0 = dots.length; add(p, false); if (dots.length > n0) budget--;
      }
    }
  }
  if (UI.sel && isLocal(UI.sel)) { const i = placeInfo(UI.sel); if (i.lon != null) add(Object.assign({ key: UI.sel }, i), true); }
  // точки
  for (const d of dots) {
    const own = null, sel = UI.sel === d.p.key;
    ctx.beginPath(); ctx.arc(d.sx, d.sy, d.r + (d.active ? 1 : 0), 0, 6.2832);
    const gl = M.ready && M.sum[curYear()] ? (sv(curYear(), d.p.cc, 'grid') || 0) : 0;
    ctx.fillStyle = d.active ? P.accent : (gl > 0.02 ? P.glow : P.muted); ctx.globalAlpha = d.active ? 0.95 : 0.25 + 0.7 * gl; ctx.fill(); ctx.globalAlpha = 1;
    if (own || sel) { ctx.lineWidth = sel ? 2.5 : 2; ctx.strokeStyle = sel ? P.ink : (own === ACT.id ? P.accent : colorOf(own)); ctx.beginPath(); ctx.arc(d.sx, d.sy, d.r + 3.5, 0, 6.2832); ctx.stroke(); }
  }
  // подписи без наложений
  const grid = new Set(), cell = 10;
  const occupied = (x, y, w, hgt) => { for (let gx = Math.floor(x / cell); gx <= Math.floor((x + w) / cell); gx++) for (let gy = Math.floor(y / cell); gy <= Math.floor((y + hgt) / cell); gy++) if (grid.has(gx + ':' + gy)) return true; return false; };
  const occupy = (x, y, w, hgt) => { for (let gx = Math.floor(x / cell); gx <= Math.floor((x + w) / cell); gx++) for (let gy = Math.floor(y / cell); gy <= Math.floor((y + hgt) / cell); gy++) grid.add(gx + ':' + gy); };
  const order = dots.slice().sort((a, b) => (b.active - a.active) || ((UI.sel === b.p.key) - (UI.sel === a.p.key)) || (b.p.pop - a.p.pop));
  let n = 0; const maxLabels = v.k < 3 ? 40 : 140;
  ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  for (const d of order) {
    if (n >= maxLabels) break;
    const big = d.p.cap === 2 || d.p.pop > 1e6;
    ctx.font = (big || d.active ? '600 ' : '500 ') + (big ? 13 : 12) + 'px ' + FONT_STACK;
    const name = d.p.name || ''; const w = ctx.measureText(name).width, hgt = 14;
    const x = d.sx + d.r + 4, y = d.sy - hgt / 2;
    if (x + w > W - 4) continue;
    if (occupied(x - 2, y, w + 4, hgt)) continue;
    occupy(x - 2, y, w + 4, hgt); n++;
    ctx.lineWidth = 3; ctx.strokeStyle = P.panel; ctx.globalAlpha = 0.9; ctx.strokeText(name, x, d.sy); ctx.globalAlpha = 1;
    ctx.fillStyle = d.active ? P.accent : P.ink; ctx.globalAlpha = 0.85; ctx.fillText(name, x, d.sy); ctx.globalAlpha = 1;
  }
  MAP.dots = dots;
}
function hitPlace(sx, sy) {
  let best = null, bd = 1e9;
  for (const d of MAP.dots) { const dd = Math.hypot(d.sx - sx, d.sy - sy); if (dd < d.r + 7 && dd < bd) { bd = dd; best = d; } }
  return best ? best.p : null;
}
function hitCountry(sx, sy) {
  const [bx, by] = toBase(sx, sy); const k = MAP.t.k;
  const feats = k >= 2.2 && MAP.f50 ? MAP.f50 : MAP.f110;
  for (const f of feats) { if (bx < f.bb[0][0] || bx > f.bb[1][0] || by < f.bb[0][1] || by > f.bb[1][1]) continue; if (MAP.hit.isPointInPath(f.path, bx, by)) return f; }
  return null;
}
function onMapClick(e) {
  const [sx, sy] = pt(e);
  const p = hitPlace(sx, sy);
  if (p) { select(p.key); return; }
  const f = hitCountry(sx, sy);
  if (f && f.iso3 && ECON[f.iso3]) select('C:' + f.iso3); else if (f) toast((f.name || 'Эта территория') + ': нет данных, в игре не участвует.'); else select(null);
}
function onMapMove(e) {
  if (e.buttons) return;
  const [sx, sy] = pt(e); const tip = $('#tip');
  const p = hitPlace(sx, sy); let html = null;
  if (p) {
    const site = siteKeys()[p.key];
    html = `<b>${esc(p.name)}</b><br><span class="muted">${esc(cname(p.cc))} · ${p.pop ? fmtPop(p.pop) + ' чел.' : 'население не указано'}${site ? ' · проект: ' + esc(site.title) : ''}</span>`;
  } else {
    const f = hitCountry(sx, sy);
    if (f && f.iso3 && ECON[f.iso3]) {
      const m = UI.metric; let val;
      if (m === 'who') { const o = ownerOf(f.iso3); val = o ? 'управляет ' + nameOf(o) : 'управляет ИИ'; }
      else { const x = MAPM[m].get(f.iso3); val = MAPM[m].short + ': ' + (x == null ? '—' : MAPM[m].fmt(x)); const o = ownerOf(f.iso3); if (o) val += ' · ' + nameOf(o); }
      html = `<b>${esc(f.name)}</b><br><span class="muted">${esc(val)}</span>`;
    } else if (f) html = `<b>${esc(f.name)}</b><br><span class="muted">нет данных</span>`;
  }
  MAP.cv.style.cursor = p ? 'pointer' : '';
  if (!html) { hideTip(); return; }
  tip.innerHTML = html; tip.style.display = 'block';
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  tip.style.left = Math.min(MAP.W - tw - 8, sx + 14) + 'px'; tip.style.top = Math.max(8, Math.min(MAP.H - th - 8, sy + 14)) + 'px';
}
function hideTip() { const t = $('#tip'); if (t) t.style.display = 'none'; }
function zoomToKey(key) {
  const info = placeInfo(key); let t;
  if (!isLocal(key)) {
    const f = (MAP.f110.find(x => x.iso3 === key.slice(2)) || (MAP.f50 || []).find(x => x.iso3 === key.slice(2)));
    if (!f) return;
    // для стран, растянутых через 180°, — по главному куску
    let [[bx0, by0], [bx1, by1]] = f.bb;
    if (bx1 - bx0 > MAP.BW * 0.4 || (bx1 - bx0) > 3 * (f.mb[1][0] - f.mb[0][0])) [[bx0, by0], [bx1, by1]] = f.mb;
    const cw = MAP.W < 900 ? MAP.W : MAP.W - 420, ch = MAP.W < 900 ? MAP.H * 0.5 : MAP.H;
    const k = Math.max(1, Math.min(40, 0.8 * Math.min(cw / ((bx1 - bx0) * MAP.s0 + 1), ch / ((by1 - by0) * MAP.s0 + 1))));
    const cx = (bx0 + bx1) / 2, cy = (by0 + by1) / 2;
    t = focusTf(cx, cy, k);
  } else {
    if (info.lon == null) return;
    const b = MAP.proj([info.lon, info.lat]);
    t = focusTf(b[0], b[1], Math.max(MAP.t.k, info.pop > 200000 ? 30 : 90));
  }
  d3.select(MAP.cv).transition().duration(dur(800)).call(MAP.zoom.transform, t);
}
function focusTf(bx, by, k) {
  const narrow = MAP.W < 900;
  const cx = narrow ? MAP.W / 2 : (MAP.W - 420) / 2, cy = narrow ? MAP.H * 0.3 : MAP.H / 2;
  const sx = MAP.s0 * bx + MAP.ox, sy = MAP.s0 * by + MAP.oy;
  return d3.zoomIdentity.translate(cx - k * sx, cy - k * sy).scale(k);
}
function nearestPlace(iso3, lon, lat, maxKm) {
  const arr = placesOf(iso3); let best = null, bd = 1e9;
  const cl = Math.cos(lat * Math.PI / 180);
  for (const p of arr) { const dx = (p.lon - lon) * cl, dy = p.lat - lat; const d = Math.sqrt(dx * dx + dy * dy) * 111.2; if (d < bd) { bd = d; best = p; } }
  return best && bd <= maxKm ? { p: best, km: bd } : null;
}
