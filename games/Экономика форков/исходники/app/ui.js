// ════════════════════════ интерфейс
let renderQueued = false;
function scheduleRender() { if (renderQueued) return; renderQueued = true; requestAnimationFrame(() => { renderQueued = false; renderAll(); }); }
function renderAll() {
  if (!M.ready) return;
  recolor(); renderTop(); renderSegs(); renderLegend(); renderCard();
  if (UI.view === 'patches') renderPatches();
  if (UI.view === 'log') renderLog();
  if (UI.view === 'compare') renderCompare();
  refreshProfiles();
}
function checkText(metric, v) {
  const up = v > 0, a = Math.abs(v);
  if (a < 0.005) return `${MNAME[metric]}: как у тени — улучшения нет`;
  switch (metric) {
    case 'W': return `благополучие ${up ? 'выше' : 'ниже'} тени на ${fmt(a, 2)}`;
    case 'y': return `доход на человека ${up ? 'выше' : 'ниже'} тени на ${fmt(a, 1)}%`;
    case 'u': return `безработица ${up ? 'ниже' : 'выше'} тени на ${fmt(a, 2)} п.п.`;
    case 'pi': return `инфляция ${up ? 'ближе к цели' : 'дальше от цели'}, чем у тени, на ${fmt(a, 2)} п.п.`;
    case 'D': return `долг ${up ? 'меньше' : 'больше'}, чем у тени, на ${fmt(a, 1)} п.п. дохода`;
  }
  return sgn(v, 2);
}
// ── шапка
let gapTimer = null;
function renderTop() {
  const g = game();
  $('#year').textContent = g ? g.year : '—';
  const btn = $('#nextYear');
  let wait = 0;
  if (g && B.remote) wait = Math.ceil((MIN_GAP - (Date.now() - (g.lastAt || 0))) / 1000);
  btn.disabled = !canAct() || M.busy || wait > 0;
  btn.textContent = M.busy ? 'Считаю год…' : wait > 0 ? `Следующий год · ${wait} с` : 'Следующий год →';
  btn.title = canAct() ? 'Посчитать мир на год вперёд — для всех игроков сразу' : 'Нужен доступ к игре';
  clearTimeout(gapTimer); if (wait > 0) gapTimer = setTimeout(renderTop, 1000);
  const R = rec(curYear()), wb = $('#worldbar'); wb.innerHTML = '';
  if (R && R.agg) {
    const f = R.agg.forks, p = R.agg.plan;
    wb.title = 'Благополучие в среднем по людям мира. Проверок идёт: ' + (R.chk || []).length;
    wb.append(h('span', null, 'Форки ', h('b', { text: fmt(f.W, 2) })), h('span', null, 'План ', h('b', { text: fmt(p.W, 2) })));
  }
  const who = $('#who'); who.innerHTML = '';
  if (ACT.id) {
    who.append(h('button', { class: 'chip-me', onclick: openPlayers, title: 'Кто сейчас ходит: сменить или добавить игрока' },
      h('span', { class: 'dot', style: 'background:' + colorOf(ACT.id), text: (nameOf(ACT.id)[0] || '?').toUpperCase() }),
      h('span', { class: 'nm', text: nameOf(ACT.id) }), h('span', { class: 'muted', text: '▾' })));
  }
  const bn = $('#banner');
  let msg = '', closable = false;
  if (!M.ready) msg = B.remote && M.me.canWrite === false ? 'Мир ещё не создан: его создаст первый игрок, у которого есть право ходить.' : 'Загружаю мир…';
  else if (M.me.canWrite === false) msg = 'У вас доступ только на просмотр: смотреть можно, ходить — нет.';
  else if (!B.remote && !UI.bannerOff) { msg = 'Одиночный режим: мир хранится только в этом браузере. Играть вместе можно по очереди — добавьте игроков в меню справа.'; closable = true; }
  bn.innerHTML = '';
  if (msg) { bn.append(h('span', { text: msg })); if (closable) bn.append(h('button', { class: 'bx', 'aria-label': 'Скрыть', onclick: () => { UI.bannerOff = true; lsSet('ef-banner', '1'); renderTop(); resizeMap(); } }, '×')); }
}
// ── переключатели карты
function renderSegs() {
  const ms = $('#metricSeg'); ms.innerHTML = '';
  for (const k of ['W', 'y', 'g', 'u', 'pi', 'D', 'dec']) ms.append(h('button', { class: UI.metric === k ? 'on' : '', title: MAPM[k].hint, onclick: () => { UI.metric = k; if (k === 'dec' && UI.world === 'diff') UI.world = 'forks'; renderAll(); } }, MAPM[k].short));
  const ws = $('#worldSeg'); ws.innerHTML = '';
  const W = [['forks', 'Мир форков', 'Каждое место живёт по своим решениям'], ['plan', 'Единый план', 'Параллельный мир: всем странам — один вариант по каждому вопросу'], ['diff', 'Форки − план', 'Где мир форков лучше (зелёный) или хуже (красный) единого плана']];
  for (const [k, t, tt] of W) { if (k === 'diff' && UI.metric === 'dec') continue; ws.append(h('button', { class: UI.world === k ? 'on' : '', title: tt, onclick: () => { UI.world = k; renderAll(); } }, t)); }
}
function renderLegend() {
  const L = $('#legend'); L.innerHTML = ''; const P = MAP.pal, m = MAPM[UI.metric];
  if (UI.metric === 'dec') {
    L.append(h('div', null, h('b', { text: 'Решения' }), h('span', { class: 'muted', text: ' · сколько вопросов решено' })),
      h('div', { class: 'bar', style: `background:linear-gradient(90deg,${P.land},${interp(P.land, P.accent, 0.98)})` }),
      h('div', { class: 'ends' }, h('span', { text: '0' }), h('span', { text: '5' })),
      h('div', { class: 'muted', style: 'margin-top:4px', text: 'Контур — у места есть управляющий' }));
    return;
  }
  let a, b, grad, title = m.name + (UI.world === 'plan' ? ' · единый план' : UI.world === 'diff' ? ' · форки минус план' : '');
  if (UI.world === 'diff') { grad = `${P.bad},${P.land},${P.good}`; a = 'хуже плана'; b = 'лучше плана'; }
  else if (m.kind === 'div') { grad = `${P.bad},${P.land},${P.good}`; a = m.fmt(m.dom[0]); b = m.fmt(m.dom[2]); }
  else if (m.kind === 'divbad') { grad = `${P.good},${P.land},${P.bad}`; a = m.fmt(m.dom[0]); b = m.fmt(m.dom[2]); }
  else if (m.kind === 'seqbad') { grad = `${P.land},${P.bad}`; a = m.fmt(m.dom[0]); b = m.fmt(m.dom[1]); }
  else if (m.kind === 'dev') { grad = `${P.land},${P.bad}`; a = 'у цели'; b = 'далеко от цели'; }
  else { grad = `${P.land},${P.accent}`; a = fmtMoney(m.dom[0]); b = fmtMoney(m.dom[1]); }
  L.append(h('div', null, h('b', { text: title })), h('div', { class: 'bar', style: `background:linear-gradient(90deg,${grad})` }),
    h('div', { class: 'ends' }, h('span', { text: a }), h('span', { text: b })), h('div', { class: 'muted', style: 'margin-top:3px', text: m.hint }));
}
// ── выбор места
function select(key) {
  UI.sel = key || null; renderCard(); requestDraw();
  if (key && B.remote) ensureRecent(15, isLocal(key)).then(() => { if (UI.sel === key) renderCard(); });
}
const loadingYears = new Set();
async function ensureRecent(n, withLocals) {
  const y1 = curYear(), jobs = [], what = withLocals ? 'HLC' : 'HC';
  for (let y = y1; y >= Math.max(YEAR0, y1 - n + 1); y--) {
    const tag = y + what; if (loadingYears.has(tag)) continue; loadingYears.add(tag);
    jobs.push(loadYear(y, false, what).catch(() => loadingYears.delete(tag)));
  }
  if (jobs.length) await Promise.all(jobs);
}
async function ensureLogYears(n) {
  const y1 = curYear(), jobs = [];
  for (let y = y1; y >= Math.max(YEAR0, y1 - n + 1); y--) {
    if (!loadingYears.has(y + 'HC')) { loadingYears.add(y + 'HC'); jobs.push(loadYear(y, false, 'HC').catch(() => loadingYears.delete(y + 'HC'))); }
    if (!M.c.log[y] && !loadingYears.has('log' + y)) { loadingYears.add('log' + y); jobs.push(B.get('log/' + y).then(d => { if (d) M.c.log[y] = d; }).catch(() => {})); }
  }
  if (jobs.length) await Promise.all(jobs);
}
function historyOf(key) {
  const out = []; const y1 = curYear();
  for (let y = YEAR0; y <= y1; y++) { if (!yearH(y)) continue; const a = stateOf(key, 'forks', y), b = stateOf(key, 'plan', y); if (a && b && !(isLocal(key) && a.inherited)) out.push([y, a, b]); }
  return out;
}
function checkFor(key, r) {
  const R = rec(curYear());
  const live = R && (R.chk || []).find(k => k.key === key && k.pid === r.pid);
  if (live) return { live: true, due: live.due, metric: live.metric };
  for (let y = curYear(); y >= Math.max(YEAR0, curYear() - 12); y--) {
    const C = yearC(y); if (!C || !C.done) continue;
    const d = C.done.find(x => x.key === key && x.pid === r.pid && x.from > r.since); if (d) return { done: true, ok: d.ok, d: d.d, metric: d.metric, year: d.year };
  }
  return null;
}
function renderCard() {
  const card = $('#card'); const key = UI.sel;
  const vm = $('#view-map');
  if (!key || UI.view !== 'map') { card.classList.remove('on'); vm.classList.remove('has-card'); return; }
  const info = placeInfo(key);
  if (!info.cc || !ECON[info.cc]) { card.classList.remove('on'); vm.classList.remove('has-card'); return; }
  card.classList.add('on'); vm.classList.add('has-card'); card.innerHTML = '';
  const local = isLocal(key), own = ownerOf(key), mine = own && own === ACT.id;
  const st = stateOf(key, 'forks'), pst = stateOf(key, 'plan');
  let prevSt = stateOf(key, 'forks', curYear() - 1);
  if (prevSt && st && !!prevSt.inherited !== !!st.inherited) prevSt = null;
  const sub = local ? `${kindLabel(info)} · ${cname(info.cc)} · ${info.pop ? fmtPop(info.pop) + ' чел.' + (info.kind === 'P' ? ' (по GeoNames)' : '') : 'население не указано'}`
    : `Страна · ${fmtPop(st ? st.P : info.pop)} чел.`;
  card.append(h('div', { class: 'card-h' }, h('h2', { text: info.name }), h('div', { class: 'sub', text: sub }),
    h('button', { class: 'card-x', 'aria-label': 'Закрыть', onclick: () => select(null) }, '×')));
  const b = h('div', { class: 'card-b' }); card.append(b);
  // управляющий
  const ob = h('div', { class: 'own' });
  if (!own) {
    ob.append(h('span', { class: 'grow' }, 'Никто не управляет'));
    if (canAct()) ob.append(h('button', { class: 'btn primary small', onclick: () => claim(key) }, 'Взять под управление'));
  } else {
    ob.append(h('span', { class: 'dot', style: 'background:' + colorOf(own), text: (nameOf(own)[0] || '?').toUpperCase() }),
      h('span', { class: 'grow' }, mine ? 'Вы управляете' : 'Управляет: ' + nameOf(own), place(key).since ? h('span', { class: 'muted', text: ' · с ' + place(key).since }) : null));
    if (mine) ob.append(h('button', { class: 'btn small', onclick: () => release(key) }, 'Отказаться'));
  }
  b.append(ob);
  // показатели
  if (st) {
    if (st.inherited) b.append(h('p', { class: 'note', style: 'margin-top:0', text: isActive(key)
      ? `Место стало отдельным миром: свои показатели у него появятся в ${curYear() + 1} году, после расчёта года. Пока ниже — показатели страны.`
      : 'Место пока живёт по правилам страны — ниже показатели страны. Своим миром оно станет, как только его возьмут под управление: тогда местные решения начнут менять его благополучие и население.' }));
    const d = (a, bb, dec) => prevSt && a != null && bb != null ? sgn(a - bb, dec) : '';
    const statsBox = h('div', { class: 'stats' },
      stat('Благополучие', fmt(st.W, 2), d(st.W, prevSt && prevSt.W, 2), pst ? 'план: ' + fmt(pst.W, 2) : ''),
      stat('Доход на человека', fmtMoney(st.y), prevSt ? sgn((st.y / prevSt.y - 1) * 100, 1) + '%' : '', pst ? 'план: ' + fmtMoney(pst.y) : ''),
      stat('Рост', fmt(st.g, 1) + '%', '', pst ? 'план: ' + fmt(pst.g, 1) + '%' : ''),
      stat('Безработица', fmt(st.u, 1) + '%', d(st.u, prevSt && prevSt.u, 1), pst ? 'план: ' + fmt(pst.u, 1) + '%' : ''),
      stat('Инфляция', fmt(st.pi, 1) + '%', '', 'цель ' + piStarOf(key) + '%' + (pst ? ' · план: ' + fmt(pst.pi, 1) + '%' : '')),
      stat(local ? 'Долг бюджета места' : 'Долг', sgn(st.D, 1) + ' п.п.', '', 'добавлен за игру, % дохода'));
    if (local && !st.inherited) statsBox.append(stat('Население', fmtPop(st.P), prevSt ? sgn((st.P / prevSt.P - 1) * 100, 1) + '%' : '', 'люди едут туда, где лучше'));
    b.append(statsBox);
    const hist = historyOf(key);
    if (hist.length >= 2) {
      b.append(h('div', { class: 'spark' }, lineChart([
        { name: 'Мир форков', color: MAP.pal.accent, pts: hist.map(r => [r[0], r[1].W]) },
        { name: 'Единый план', color: MAP.pal.muted, dash: true, pts: hist.map(r => [r[0], r[2].W]) }], { w: 360, h: 110, fy: v => fmt(v, 1) })),
        h('div', { class: 'lg' }, h('span', null, h('i', { style: 'background:' + MAP.pal.accent }), 'благополучие, мир форков'), h('span', null, h('i', { style: 'background:' + MAP.pal.muted }), 'единый план')));
    }
  }
  // решения
  const qs = local ? ENGINE.LOCALQ : SIM.Q.map(q => q.id);
  const rules = rulesOf(key);
  const sec = h('div', { class: 'sect' });
  sec.append(h('h3', { text: local ? 'Местные решения' : 'Решения страны' }));
  if (mine) sec.append(h('div', { class: 'actions', style: 'margin:0 0 8px' }, h('button', { class: 'btn small primary', onclick: () => openAdopt(key) }, 'Принять патч'), h('button', { class: 'btn small', onclick: () => openComposer(key) }, 'Написать свой')));
  else if (canAct()) sec.append(h('div', { class: 'actions', style: 'margin:0 0 8px' }, h('button', { class: 'btn small', onclick: () => openComposer(key) }, 'Предложить патч'),
    !own ? h('span', { class: 'muted', style: 'font-size:12px;align-self:center', text: 'принять может только управляющий' }) : null));
  for (const q of qs) {
    const r = rules[q]; let inh = null;
    if (!r && local) { let k = place(key) && place(key).parent, g = 0; while (k && g++ < 5) { const rr = rulesOf(k)[q]; if (rr) { inh = { key: k, r: rr }; break; } k = place(k) && place(k).parent; } }
    const eff = r || (inh && inh.r);
    const row = h('div', { class: 'q' });
    row.append(h('div', { class: 'q-top' }, h('span', { class: 'q-name', text: qName(q) }),
      h('span', { class: 'q-val' + (eff && +eff.opt !== 0 ? '' : ' muted'), text: eff ? optText(q, eff.opt) : 'как было' })));
    const meta = h('div', { class: 'q-meta' });
    if (r) {
      const isRev = String(r.pid).startsWith('revert:');
      if (isRev) meta.append(h('span', { class: 'pill bad', text: 'откат ' + r.pid.slice(7) }), h('span', { text: 'с ' + r.since }));
      else {
        meta.append(h('button', { class: 'hash', onclick: () => openPatch(r.pid), text: r.pid }), h('span', { text: 'с ' + r.since + (r.by ? ' · ' + nameOf(r.by) : '') }));
        const c = checkFor(key, r);
        if (c && c.live) meta.append(h('span', { class: 'pill acc', text: `проверка в ${c.due}: ${MNAME[c.metric]}` }));
        else if (c && c.done) meta.append(h('span', { class: 'pill ' + (c.ok ? 'good' : 'bad'), title: checkText(c.metric, c.d[c.metric]), text: (c.ok ? '✓ проверка пройдена ' : '✗ не прошла ') + c.year }));
        else if (r.since === curYear()) meta.append(h('span', { class: 'pill acc', text: `начнёт действовать в ${curYear() + 1}` }));
      }
      if (mine) meta.append(h('button', { class: 'btn ghost small', onclick: () => dropRule(key, q), title: 'Вернуть «как было»' }, 'снять'));
    } else if (inh) meta.append(h('span', { text: 'как решено в: ' }), h('button', { class: 'btn ghost small', onclick: () => select(inh.key) }, placeInfo(inh.key).name));
    else if (!local && q !== 'rate' && q !== 'tariff') { /* ничего */ }
    if (meta.childNodes.length) row.append(meta);
    sec.append(row);
  }
  if (local) sec.append(h('p', { class: 'note', html: 'Ставка и пошлины — решения страны. Здесь действуют общие решения страны (<a href="#" data-k="C:' + info.cc + '">' + esc(cname(info.cc)) + '</a>) плюс местные.' }));
  b.append(sec);
  const lnk = sec.querySelector('a[data-k]'); if (lnk) lnk.onclick = e => { e.preventDefault(); select(lnk.dataset.k); zoomToKey(lnk.dataset.k); };
  // места страны под управлением
  if (!local) {
    const mine2 = Object.keys(M.c.places).filter(k => isLocal(k) && M.c.places[k].cc === info.cc && isActive(k));
    if (mine2.length) {
      const s2 = h('div', { class: 'sect' }, h('h3', { text: 'Города и сёла в игре' }));
      const wrap = h('div', { class: 'actions' });
      mine2.slice(0, 24).forEach(k => wrap.append(h('button', { class: 'btn small', onclick: () => { select(k); zoomToKey(k); } }, placeInfo(k).name)));
      if (mine2.length > 24) wrap.append(h('span', { class: 'muted', text: 'и ещё ' + (mine2.length - 24) }));
      s2.append(wrap); b.append(s2);
    }
  }
  // летопись места
  const ent = [];
  for (const y in M.c.log) for (const id in (M.c.log[y] || {})) { const e = M.c.log[y][id]; if (e && e.key === key) ent.push(Object.assign({ y: +y }, e)); }
  for (let y = curYear(); y >= Math.max(YEAR0, curYear() - 12); y--) { const C = yearC(y); if (C && C.done) C.done.filter(d => d.key === key).forEach(d => ent.push({ y, t: d.ok ? 'pass' : 'fail', pid: d.pid, d })); }
  if (ent.length) {
    ent.sort((a, b2) => (b2.y - a.y) || ((b2.ts || 0) - (a.ts || 0)));
    const s3 = h('div', { class: 'sect' }, h('h3', { text: 'История места' }));
    ent.slice(0, 12).forEach(e => s3.append(h('div', { class: 'q-meta', style: 'margin:4px 0' }, h('span', { class: 'mono', text: e.y }), logLine(e, true))));
    b.append(s3);
  }
  // источники и ссылки
  const c = DATA.countries[info.cc];
  const src = info.kind === 'U'
    ? `Место добавил игрок ${nameOf(info.by)}; координаты (${fmt(info.lat, 4)}, ${fmt(info.lon, 4)}) и население указаны им. Экономика места считается от экономики страны.`
    : local ? `Население и координаты — GeoNames (${fmt(info.lat, 3)}, ${fmt(info.lon, 3)}). Экономика места считается от экономики страны.`
    : (c.note ? `Стартовые данные: ${c.note}.` : `Стартовые данные: Всемирный банк — население ${c.yr[0]}, доход на человека ${c.yr[1]}, рост ${c.yr[2] || '—'}, инфляция ${c.yr[3] || 'нет данных'}, безработица ${c.yr[4] || 'нет данных'}.`);
  const gq = local || info.kind === 'U' ? `${info.lat},${info.lon}` : encodeURIComponent(info.name);
  b.append(h('p', { class: 'note' }, src + ' ', h('a', { href: 'https://www.google.com/maps/search/?api=1&query=' + gq, target: '_blank', rel: 'noopener' }, 'Открыть в Google Maps ↗')));
}
function stat(k, v, dlt, sub) {
  return h('div', { class: 'stat' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }),
    (dlt || sub) ? h('div', { class: 'd muted' }, dlt ? h('span', { text: dlt + ' за год' + (sub ? ' · ' : '') }) : null, sub || '') : null);
}
// ── график
function lineChart(series, o) {
  const w = o.w || 360, hh = o.h || 120, pl = 34, pr = 8, pt2 = 8, pb = 18;
  const all = series.flatMap(s => s.pts); if (!all.length) return h('div');
  let x0 = Math.min(...all.map(p => p[0])), x1 = Math.max(...all.map(p => p[0])); if (x1 === x0) x1 = x0 + 1;
  let y0 = Math.min(...all.map(p => p[1])), y1 = Math.max(...all.map(p => p[1])); if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  const pad = (y1 - y0) * 0.1; y0 -= pad; y1 += pad;
  const X = x => pl + (x - x0) / (x1 - x0) * (w - pl - pr), Y = y => pt2 + (1 - (y - y0) / (y1 - y0)) * (hh - pt2 - pb);
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${hh}`); svg.setAttribute('class', 'chart');
  const mk = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); svg.appendChild(e); return e; };
  [y0 + pad, (y0 + y1) / 2, y1 - pad].forEach(v => { mk('line', { x1: pl, x2: w - pr, y1: Y(v), y2: Y(v), stroke: MAP.pal.line, 'stroke-width': 0.6, 'stroke-dasharray': '2 3' }); const t = mk('text', { x: pl - 4, y: Y(v) + 3.5, 'text-anchor': 'end' }); t.textContent = (o.fy || (x => fmt(x, 1)))(v); });
  if (y0 < 0 && y1 > 0) mk('line', { x1: pl, x2: w - pr, y1: Y(0), y2: Y(0), stroke: MAP.pal.line, 'stroke-width': 1 });
  [x0, x1].forEach((v, i) => { const t = mk('text', { x: X(v), y: hh - 4, 'text-anchor': i ? 'end' : 'start' }); t.textContent = v; });
  for (const s of series.slice().sort((a, b) => (a.dash ? 1 : 0) - (b.dash ? 1 : 0))) {
    if (!s.pts.length) continue;
    mk('path', { d: s.pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join(''), fill: 'none', stroke: s.color, 'stroke-width': s.dash ? 1.6 : 2.2, 'stroke-dasharray': s.dash ? '5 4' : '', 'stroke-linejoin': 'round' });
  }
  return svg;
}
// ── окна
function openDialog(title, body, foot) {
  const d = $('#dlg'); d.innerHTML = '';
  d.append(h('div', { class: 'dlg-h' }, h('h2', { text: title }), h('button', { class: 'card-x', style: 'position:static', 'aria-label': 'Закрыть', onclick: closeDialog }, '×')),
    h('div', { class: 'dlg-b' }, body), foot ? h('div', { class: 'dlg-f' }, foot) : null);
  $('#modal').classList.add('on');
}
function closeDialog() { $('#modal').classList.remove('on'); }
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeDialog(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { if ($('#modal').classList.contains('on')) closeDialog(); else if (UI.pick) { UI.pick = false; MAP.cv.classList.remove('pick'); $('#addVillage').classList.remove('primary'); } } });
// ── написать патч
function openComposer(fromKey) {
  const local = fromKey && isLocal(fromKey);
  const qs = SIM.Q.filter(q => !local || q.level === 'any');
  const ch = {}; let metric = 'W', hz = 3;
  const body = h('div');
  body.append(h('p', { class: 'muted', style: 'margin-top:0', text: 'Патч — предложение решения. Выберите, что он меняет (можно несколько вопросов сразу), что должно улучшиться и когда проверить. Принять патч может только управляющий места; писать может любой.' }));
  const rowsBox = h('div');
  const prev = h('div', { class: 'preview' });
  function redraw() {
    rowsBox.innerHTML = '';
    for (const q of qs) {
      const cur = ch[q.id];
      const ctl = h('div', { class: 'opt3' });
      [['-1', '↓ ' + (q.id === 'rate' || q.id === 'tariff' || q.id === 'tax' ? 'снизить' : 'урезать')], ['0', '= как было'], ['1', '↑ ' + (q.id === 'invest' || q.id === 'social' ? 'добавить' : q.id === 'rate' ? 'повысить' : 'поднять')]].forEach(([o, t]) => {
        ctl.append(h('button', { class: cur === +o ? 'on' : '', title: q.opts[o], onclick: () => { if (ch[q.id] === +o) delete ch[q.id]; else ch[q.id] = +o; redraw(); } }, t));
      });
      rowsBox.append(h('div', { class: 'qrow' }, h('div', null, h('div', { class: 'qn', text: q.name }), h('div', { class: 'qd', text: cur == null ? 'не трогать' : q.opts[String(cur)] + (q.level === 'country' ? ' · только для стран' : '') })), ctl));
    }
    const n = Object.keys(ch).length;
    prev.textContent = n ? `Изменит: ${chText(ch)}. Проверка: ${MNAME[metric]} ${SIM.METRICS[metric].mode === 'mean' ? 'в среднем за ' + years(hz) : 'через ' + years(hz)} — должно быть лучше, чем у «тени» (того же места в том же мире, но без патча). Не лучше — откат.`
        + (metric === 'pi' ? ' Инфляция общая для всей страны: в городе или селе такой патч проверку не пройдёт.' : '')
      : 'Выберите хотя бы один вопрос.';
    for (const bt of $$('.need-ch', $('#dlg'))) bt.disabled = !n;
  }
  body.append(rowsBox);
  const mSel = h('select', { id: 'cmp-metric', onchange: e => { metric = e.target.value; redraw(); } }, Object.keys(SIM.METRICS).map(m => h('option', { value: m, selected: m === metric }, MNAME[m][0].toUpperCase() + MNAME[m].slice(1))));
  const hIn = h('select', { id: 'cmp-horizon', onchange: e => { hz = +e.target.value; redraw(); } }, Array.from({ length: 10 }, (_, i) => h('option', { value: i + 1, selected: i + 1 === hz }, years(i + 1))));
  const note = h('textarea', { id: 'cmp-note', rows: 2, maxlength: 240, placeholder: 'Зачем этот патч (необязательно)' });
  body.append(h('div', { class: 'grid2', style: 'margin-top:12px;gap:10px' }, h('div', { class: 'field' }, h('label', { text: 'Что должно улучшиться' }), mSel), h('div', { class: 'field' }, h('label', { text: 'Когда проверить' }), hIn)),
    h('div', { class: 'field' }, h('label', { text: 'Пояснение' }), note), prev);
  const foot = [h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'),
    h('button', { class: 'btn need-ch', onclick: async () => { const doc = await createPatch(Object.assign({}, ch), metric, hz, note.value.trim()); if (doc) { closeDialog(); toast('Патч ' + doc.pid + ' создан. Его может принять ' + (doc.lvl === 'C' ? 'управляющий любой страны.' : 'управляющий любого места.')); } } }, 'Создать патч')];
  if (fromKey && ownerOf(fromKey) === ACT.id) foot.push(h('button', { class: 'btn primary need-ch', onclick: async () => { const doc = await createPatch(Object.assign({}, ch), metric, hz, note.value.trim()); if (doc) { closeDialog(); await adopt(fromKey, doc.pid, doc); } } }, 'Создать и принять: ' + placeInfo(fromKey).name));
  openDialog('Новый патч', body, foot); redraw();
}
// ── принять патч
function trustScore(pid) { const s = patchStats(pid); return (s.ok + 1) / (s.ok + s.fail + 2); }
function patchCard(pa, opts) {
  opts = opts || {};
  const s = patchStats(pa.pid), at = authorTrust(pa.by);
  const el = h('div', { class: 'patch' });
  el.append(h('div', { class: 'patch-h' }, h('button', { class: 'hash', onclick: () => openPatch(pa.pid), text: pa.pid }),
    h('span', { class: 'dot', style: 'width:18px;height:18px;font-size:10px;background:' + colorOf(pa.by), text: (nameOf(pa.by)[0] || '?').toUpperCase() }),
    h('span', { text: nameOf(pa.by) }), h('span', { class: 'muted', text: '· ' + pa.year + (pa.lvl === 'C' ? ' · только для стран' : '') })));
  const chs = h('div', { class: 'patch-ch' });
  Object.keys(pa.ch).sort((a, b) => SIM.QI[a] - SIM.QI[b]).forEach(q => chs.append(h('span', { class: 'chg' + (+pa.ch[q] !== 0 ? ' up' : ''), title: optText(q, pa.ch[q]) }, qShort(q) + ': ' + optText(q, pa.ch[q]))));
  el.append(chs);
  if (pa.note) el.append(h('div', { class: 'patch-note', text: '«' + pa.note + '»' }));
  const f = h('div', { class: 'patch-f' },
    h('span', { text: `проверка: ${MNAME[pa.m]}, ${years(pa.h)}` }),
    h('span', { class: 'pill' + (s.ok ? ' good' : ''), text: '✓ ' + s.ok }), h('span', { class: 'pill' + (s.fail ? ' bad' : ''), text: '✗ ' + s.fail }),
    h('span', { text: s.live ? 'действует в ' + s.live + ' ' + plural(s.live, 'месте', 'местах', 'местах') : 'пока нигде не действует' }),
    at.share != null ? h('span', { title: 'Доля пройденных проверок у всех патчей автора', text: 'автору доверяют на ' + Math.round(at.share * 100) + '%' }) : null);
  el.append(f);
  if (opts.actions) el.append(h('div', { class: 'actions' }, opts.actions));
  return el;
}
function openAdopt(key) {
  const list = Object.values(M.c.patches).filter(pa => canAdoptAt(pa, key)).sort((a, b) => (trustScore(b.pid) - trustScore(a.pid)) || (patchStats(b.pid).live - patchStats(a.pid).live) || (b.t - a.t));
  const body = h('div');
  body.append(h('p', { class: 'muted', style: 'margin-top:0', text: `Выберите патч для места «${placeInfo(key).name}». Сверху — патчи, которые чаще проходили проверки. Патч начнёт действовать со следующего года.` }));
  if (!list.length) body.append(h('div', { class: 'empty', text: 'Подходящих патчей пока нет — напишите первый.' }));
  const box = h('div', { class: 'plist' }); body.append(box);
  list.slice(0, 40).forEach(pa => box.append(patchCard(pa, { actions: h('button', { class: 'btn primary small', onclick: async () => { closeDialog(); await adopt(key, pa.pid); } }, 'Принять') })));
  openDialog('Принять патч', body, [h('button', { class: 'btn', onclick: () => { closeDialog(); openComposer(key); } }, 'Написать свой'), h('button', { class: 'btn', onclick: closeDialog }, 'Закрыть')]);
}
function myPlacesFor(pa) { return Object.keys(M.c.places).filter(k => ownerOf(k) === ACT.id && canAdoptAt(pa, k)); }
function adoptActions(pa) {
  const mineK = myPlacesFor(pa); if (!canAct() || !mineK.length) return null;
  const sel = h('select', { class: 'btn small' }, mineK.map(k => h('option', { value: k }, placeInfo(k).name)));
  return [sel, h('button', { class: 'btn small primary', onclick: () => adopt(sel.value, pa.pid) }, 'Принять')];
}
function openPatch(pid) {
  const pa = M.c.patches[pid];
  if (!pa) { toast(String(pid).startsWith('revert:') ? 'Это автоматический откат.' : 'Этого патча нет в загруженном списке (старый патч).'); return; }
  const body = h('div');
  body.append(patchCard(pa, { actions: adoptActions(pa) }));
  const s = patchStats(pid);
  if (s.where.length) { const w = h('div', { class: 'actions' }); s.where.slice(0, 30).forEach(k => w.append(h('button', { class: 'btn small', onclick: () => { closeDialog(); showMap(); select(k); zoomToKey(k); } }, placeInfo(k).name))); body.append(h('h3', { text: 'Где действует' }), w); }
  const res = [];
  for (const y in M.Y) ((M.Y[y].C || {}).done || []).forEach(d => { if (d.pid === pid) res.push(d); });
  if (res.length) {
    body.append(h('h3', { text: 'Проверки по итогам' }));
    res.sort((a, b) => b.year - a.year).slice(0, 20).forEach(d => body.append(h('div', { class: 'q-meta', style: 'margin:4px 0' }, h('span', { class: 'pill ' + (d.ok ? 'good' : 'bad'), text: (d.ok ? '✓ ' : '✗ ') + d.year }), h('span', { text: placeInfo(d.key).name + ': ' + checkText(d.metric, d.d[d.metric]) }))));
  }
  openDialog('Патч ' + pid, body, [h('button', { class: 'btn', onclick: closeDialog }, 'Закрыть')]);
}
// ── своё село
function openVillageDialog(iso3, lon, lat) {
  const near = nearestPlace(iso3, lon, lat, 30);
  const nm = h('input', { id: 'vil-name', type: 'text', maxlength: 60, placeholder: 'Например: Верхние Выселки' });
  const pop = h('input', { id: 'vil-pop', type: 'number', min: 1, max: 999999, placeholder: 'необязательно' });
  const par = near ? h('input', { type: 'checkbox', checked: true }) : null;
  const own = h('input', { type: 'checkbox', checked: true });
  const body = h('div',
    h('p', { class: 'muted', style: 'margin-top:0', text: `${cname(iso3)}, точка ${fmt(lat, 4)}, ${fmt(lon, 4)}. В списке GeoNames есть места от 1000 жителей и центры районов; остальные можно добавить так.` }),
    h('div', { class: 'field' }, h('label', { text: 'Название' }), nm),
    h('div', { class: 'field' }, h('label', { text: 'Сколько жителей' }), pop),
    near ? h('label', { class: 'field', style: 'display:flex;gap:8px;align-items:center' }, par, h('span', { text: `Входит в «${near.p.name}» (${fmt(near.km, 0)} км): пока у села нет своих решений, действуют решения этого места` })) : null,
    h('label', { class: 'field', style: 'display:flex;gap:8px;align-items:center' }, own, h('span', { text: 'Сразу взять под управление' })));
  openDialog('Добавить населённый пункт', body, [h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'),
    h('button', { class: 'btn primary', onclick: async () => {
      const name = nm.value.trim(); if (!name) { nm.focus(); return; }
      const key = await addVillage({ name, cc: iso3, lon, lat, pop: Math.max(0, Math.round(+pop.value || 0)), parent: par && par.checked ? near.p.key : null, parentPop: par && par.checked ? near.p.pop : 0, own: own.checked });
      if (key) { closeDialog(); select(key); toast('Добавлено: ' + name + '.'); }
    } }, 'Добавить')]);
  setTimeout(() => nm.focus(), 50);
}
// ── игроки
function openPlayers() {
  const body = h('div');
  const mineIds = [];
  if (M.me.id) mineIds.push(M.me.id);
  Object.keys(M.c.players).forEach(id => { const p = M.c.players[id]; if (p && p.nick && (p.host === (M.me.id || 'local'))) mineIds.push(id); });
  if (!mineIds.length && ACT.id) mineIds.push(ACT.id);
  body.append(h('p', { class: 'muted', style: 'margin-top:0', text: 'Кто ходит сейчас. За одним устройством можно играть по очереди: у каждого игрока свои места и патчи.' }));
  const list = h('div', { class: 'plist' });
  mineIds.forEach(id => list.append(h('div', { class: 'own', style: 'margin:0' },
    h('span', { class: 'dot', style: 'background:' + colorOf(id), text: (nameOf(id)[0] || '?').toUpperCase() }),
    h('span', { class: 'grow', text: nameOf(id) + (id === ACT.id ? ' — ходит сейчас' : '') }),
    id !== ACT.id ? h('button', { class: 'btn small', onclick: () => { setActor(id); closeDialog(); } }, 'Передать ход') : null)));
  body.append(list);
  if (canAct() || !B.remote) {
    const nick = h('input', { id: 'pl-nick', type: 'text', maxlength: 32, placeholder: 'Имя игрока' });
    body.append(h('div', { class: 'field', style: 'margin-top:14px' }, h('label', { text: 'Добавить игрока за этим устройством' }), h('div', { style: 'display:flex;gap:8px' }, nick,
      h('button', { class: 'btn', onclick: async () => { const n = nick.value.trim(); if (!n) return; const id = await addSeatPlayer(n); if (id) { setActor(id); closeDialog(); toast('Теперь ходит: ' + n); } } }, 'Добавить'))));
  }
  const seenIds = new Set(Object.keys(M.c.players));
  Object.values(M.c.places).forEach(p => p.owner && seenIds.add(p.owner)); Object.values(M.c.patches).forEach(p => p.by && seenIds.add(p.by));
  const others = [...seenIds].filter(id => !mineIds.includes(id));
  if (B.remote && others.length) {
    body.append(h('h3', { text: 'Другие игроки' }));
    const w = h('div', { class: 'actions' }); others.slice(0, 40).forEach(id => w.append(h('span', { class: 'pill', text: nameOf(id) }))); body.append(w);
  }
  const foot = [h('button', { class: 'btn', onclick: closeDialog }, 'Закрыть')];
  if (M.me.isOwner || !B.remote) foot.unshift(h('button', { class: 'btn danger', onclick: () => { closeDialog(); confirmReset(); } }, 'Начать мир заново'));
  openDialog('Игроки', body, foot);
}
function setActor(id) { ACT.id = id; lsSet('ef-actor', id); renderAll(); requestDraw(); }
function confirmReset() {
  openDialog('Начать мир заново?', h('p', { text: 'Все места, патчи, решения и история будут удалены, мир вернётся к данным 2026 года. Отменить это нельзя.' }),
    [h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'), h('button', { class: 'btn danger', onclick: async () => { closeDialog(); await resetWorld(); } }, 'Удалить всё и начать заново')]);
}
// ── поиск
function initSearch() {
  const q = $('#q'), sug = $('#sug'); let items = [], hl = -1;
  const run = debounce(() => {
    const s = q.value.trim().toLowerCase(); sug.innerHTML = ''; items = []; hl = -1;
    if (s.length < 2) { sug.classList.remove('on'); return; }
    decodeAll();
    const res = [];
    for (const iso3 in ECON) { const n = cname(iso3).toLowerCase(); if (n.includes(s)) res.push({ key: 'C:' + iso3, name: cname(iso3), kind: 'страна', score: (n.startsWith(s) ? 3 : 1) * 1e12 }); }
    for (const key in M.c.places) if (key.startsWith('U:')) { const d = M.c.places[key]; if ((d.name || '').toLowerCase().includes(s)) res.push({ key, name: d.name, kind: 'добавлено · ' + cname(d.cc), score: 1e11 }); }
    for (const iso3 in PL.byC) for (const p of PL.byC[iso3]) { const n = p.name.toLowerCase(); if (n.startsWith(s) || (s.length >= 3 && n.includes(s))) res.push({ key: p.key, name: p.name, kind: cname(iso3) + (p.pop ? ' · ' + fmtPop(p.pop) : ''), score: (n === s ? 4 : n.startsWith(s) ? 2 : 1) * 1e9 + p.pop }); }
    res.sort((a, b) => b.score - a.score); items = res.slice(0, 12);
    if (!items.length) sug.append(h('div', { class: 'muted', style: 'padding:9px 12px', text: 'Не нашлось. Если вашего села нет в списке — добавьте его: «+ Своё село».' }));
    items.forEach((it, i) => sug.append(h('button', { onclick: () => choose(i) }, h('span', { text: it.name }), h('span', { class: 's-kind', text: it.kind }))));
    sug.classList.add('on');
  }, 120);
  function choose(i) { const it = items[i]; if (!it) return; sug.classList.remove('on'); q.value = it.name; q.blur(); showMap(); select(it.key); zoomToKey(it.key); }
  q.addEventListener('input', run);
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); hl = Math.max(0, Math.min(items.length - 1, hl + (e.key === 'ArrowDown' ? 1 : -1))); $$('button', sug).forEach((b, i) => b.classList.toggle('hl', i === hl)); }
    else if (e.key === 'Enter') choose(hl >= 0 ? hl : 0);
    else if (e.key === 'Escape') { sug.classList.remove('on'); q.blur(); }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) sug.classList.remove('on'); });
}
// ── вкладки
function showMap() { setView('map'); }
function setView(v) {
  UI.view = v; $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.v === v)); $$('.view').forEach(s => s.classList.toggle('on', s.id === 'view-' + v));
  if (v === 'map') { resizeMap(); renderCard(); }
  if (v === 'patches') renderPatches();
  if (v === 'log') { renderLog(); if (B.remote) ensureLogYears(20).then(() => UI.view === 'log' && renderLog()); }
  if (v === 'compare') { renderCompare(); if (B.remote) ensureLogYears(1).then(() => UI.view === 'compare' && renderCompare()); }
  if (v === 'help') renderHelp();
}
// ── патчи
function renderPatches() {
  const P = $('#patchesPage'); P.innerHTML = '';
  P.append(h('h1', { text: 'Патчи' }), h('p', { class: 'muted', text: 'Как в Линуксе: предложить изменение может любой, принять к себе — управляющий места, а итог проверяет не начальник, а результат. Один патч может действовать в разных местах, и у каждого места своя история — это и есть форки.' }));
  const tb = h('div', { class: 'toolbar' });
  const fs = h('div', { class: 'seg' });
  [['all', 'Все'], ['mine', 'Мои'], ['C', 'Для стран'], ['A', 'Для любых мест']].forEach(([k, t]) => fs.append(h('button', { class: UI.patchFilter === k ? 'on' : '', onclick: () => { UI.patchFilter = k; renderPatches(); } }, t)));
  const qsSeg = h('div', { class: 'seg' }); qsSeg.append(h('button', { class: !UI.patchQ ? 'on' : '', onclick: () => { UI.patchQ = ''; renderPatches(); } }, 'Все вопросы'));
  SIM.Q.forEach(q => qsSeg.append(h('button', { class: UI.patchQ === q.id ? 'on' : '', onclick: () => { UI.patchQ = q.id; renderPatches(); } }, q.short)));
  const so = h('select', { class: 'btn small', onchange: e => { UI.patchSort = e.target.value; renderPatches(); } },
    [['trust', 'Сначала надёжные'], ['new', 'Сначала новые'], ['live', 'Сначала популярные']].map(([v, t]) => h('option', { value: v, selected: UI.patchSort === v }, t)));
  tb.append(fs, qsSeg, so, canAct() ? h('button', { class: 'btn primary', onclick: () => openComposer(null) }, 'Новый патч') : null);
  P.append(tb);
  let list = Object.values(M.c.patches);
  if (UI.patchFilter === 'mine') list = list.filter(p => p.by === ACT.id);
  if (UI.patchFilter === 'C') list = list.filter(p => p.lvl === 'C');
  if (UI.patchFilter === 'A') list = list.filter(p => p.lvl === 'A');
  if (UI.patchQ) list = list.filter(p => p.ch && UI.patchQ in p.ch);
  const sorters = { trust: (a, b) => (trustScore(b.pid) - trustScore(a.pid)) || (b.t - a.t), new: (a, b) => b.t - a.t, live: (a, b) => (patchStats(b.pid).live - patchStats(a.pid).live) || (b.t - a.t) };
  list.sort(sorters[UI.patchSort] || sorters.trust);
  if (!list.length) { P.append(h('div', { class: 'empty', text: Object.keys(M.c.patches).length ? 'С такими условиями патчей нет.' : 'Патчей пока нет. Напишите первый — например, «налоги ↑, вложения ↑» с проверкой по благополучию через 5 лет.' })); return; }
  const box = h('div', { class: 'plist' }); list.slice(0, 200).forEach(pa => box.append(patchCard(pa, { actions: adoptActions(pa) }))); P.append(box);
}
// ── хроника
function logLine(e, short) {
  const who = e.by ? nameOf(e.by) : '';
  const pl = e.key ? placeInfo(e.key).name : '';
  const hashBtn = pid => h('button', { class: 'hash', onclick: () => openPatch(pid), text: pid });
  const span = (...k) => h('span', null, ...k);
  switch (e.t) {
    case 'world': return span(`${who} создал(а) мир по данным Всемирного банка`);
    case 'year': return span(`год посчитал(а): ${who}`);
    case 'claim': return span(short ? `${who} взял(а) под управление` : `${who} взял(а) под управление: ${pl}`);
    case 'release': return span(short ? `${who} отказался(ась) от управления` : `${who} отказался(ась) от управления: ${pl}`);
    case 'patch': { const pa = M.c.patches[e.pid]; return span(`${who} написал(а) патч `, hashBtn(e.pid), pa ? ` (${chText(pa.ch)})` : ''); }
    case 'adopt': { const pa = M.c.patches[e.pid]; return span(`${who} принял(а) `, hashBtn(e.pid), pa ? ` (${chText(pa.ch)})` : '', short ? '' : ` в: ${pl}`); }
    case 'drop': return span(`${who} снял(а) решение «${qShort(e.q)}»` + (short ? '' : ` в: ${pl}`));
    case 'village': return span(`${who} добавил(а) на карту: ${pl}`);
    case 'pass': case 'fail': { const d = e.d; return span(short ? h('span', { class: e.t === 'pass' ? 'good' : 'bad', text: e.t === 'pass' ? '✓ ' : '✗ ' }) : null, hashBtn(d.pid), ' ' + (short ? '' : pl + ': ') + checkText(d.metric, d.d[d.metric]) + (d.ok ? '' : ' → откат')); }
  }
  return span(e.t);
}
function renderLog() {
  const P = $('#logPage'); P.innerHTML = '';
  P.append(h('h1', { text: 'Хроника' }), h('p', { class: 'muted', text: 'Всё, что происходило в мире: кризисы, решения игроков и проверки по итогам. Проверка сравнивает место с его «тенью» — тем же местом в том же мире, где патч не принят.' }));
  const y1 = curYear(); let any = false;
  for (let y = y1; y >= Math.max(YEAR0, y1 - 40); y--) {
    const H = yearH(y), C = yearC(y), L = M.c.log[y];
    if (!H && !C && !L) continue;
    any = true;
    const sec = h('div', { class: 'log-y' });
    const yearBy = L ? Object.values(L).find(e => e && e.t === 'year') : null;
    sec.append(h('h2', null, String(y), yearBy ? h('span', { class: 'muted', style: 'font:400 13px var(--sans)', text: 'посчитал(а) ' + nameOf(yearBy.by) }) : null));
    const rows = [];
    (H && H.ev || []).forEach(e => { if (EVT[e.t]) rows.push([EVT[e.t].ic, h('span', { text: EVT[e.t].text })]); });
    (C && C.done || []).forEach(d => rows.push([d.ok ? '✓' : '✗', logLine({ t: d.ok ? 'pass' : 'fail', key: d.key, d }, false)]));
    const acts = L ? Object.values(L).filter(e => e && e.t !== 'year').sort((a, b) => (a.ts || 0) - (b.ts || 0)) : [];
    acts.forEach(e => rows.push([{ claim: '⚑', release: '⚐', patch: '✎', adopt: '⇄', drop: '↺', village: '⌂', world: '◎' }[e.t] || '·', logLine(e, false)]));
    if (!rows.length) rows.push(['·', h('span', { class: 'muted', text: 'тихий год' })]);
    rows.forEach(([ic, node]) => sec.append(h('div', { class: 'log-e' }, h('span', { class: 'ic' + (ic === '✓' ? ' good' : ic === '✗' ? ' bad' : ''), text: ic }), node)));
    P.append(sec);
  }
  if (!any) P.append(h('div', { class: 'empty', text: 'Пока пусто.' }));
}
// ── форки и план
function renderCompare() {
  const P = $('#comparePage'); P.innerHTML = '';
  P.append(h('h1', { text: 'Мир форков и единый план' }),
    h('p', { text: 'Игра всё время считает два мира с одними и теми же кризисами и удачами. В мире форков каждое место живёт по своим решениям. В мире единого плана по каждому вопросу для всех стран действует один вариант — тот, за которым больше всего людей (по населению стран, где решение принято), а местных решений нет. Так видно, что даёт разнообразие решений против одного решения на всех.' }),
    h('p', { class: 'note', text: 'Средние по миру считаются по странам с весом населения. Решения городов и сёл меняют сами эти места и в средние по миру не входят.' }));
  const S = M.c.meta.series || { f: {}, p: {} };
  const ys = Object.keys(S.f || {}).map(Number).sort((a, b) => a - b);
  const R = rec(curYear());
  if (R && R.agg) {
    const f = R.agg.forks, p = R.agg.plan;
    const devOf = w => { let n = 0, d = 0; for (const iso3 in ECON) { const s0 = stateOf('C:' + iso3, w); if (!s0) continue; n += s0.P; d += s0.P * Math.abs(s0.pi - SIM.params(ECON[iso3]).piStar); } return n ? d / n : 0; };
    const row = (name, a, b, better, fm) => { const d = better * (a - b); return h('tr', null, h('td', { text: name }), h('td', { class: 'n', text: fm(a) }), h('td', { class: 'n', text: fm(b) }), h('td', { class: 'n ' + (Math.abs(d) < 1e-6 ? 'muted' : d > 0 ? 'good' : 'bad'), text: Math.abs(d) < 1e-6 ? 'поровну' : d > 0 ? 'форки лучше' : 'план лучше' })); };
    P.append(h('div', { class: 'box' }, h('h3', { text: curYear() + ' год, в среднем по людям мира' }),
      h('table', null, h('thead', null, h('tr', null, h('th', { text: 'Показатель' }), h('th', { class: 'n', text: 'Форки' }), h('th', { class: 'n', text: 'План' }), h('th', { class: 'n', text: '' }))),
        h('tbody', null, row('Благополучие', f.W, p.W, 1, v => fmt(v, 2)), row('Доход на человека', f.y, p.y, 1, fmtMoney), row('Рост', f.g, p.g, 1, v => fmt(v, 2) + '%'),
          row('Безработица', f.u, p.u, -1, v => fmt(v, 2) + '%'), row('Инфляция: отклонение от цели', devOf('forks'), devOf('plan'), -1, v => fmt(v, 2) + ' п.п.'), row('Добавленный долг', f.D, p.D, -1, v => sgn(v, 1) + ' п.п.')))));
    // план по вопросам
    const tb = h('tbody');
    SIM.Q.forEach((q, i) => {
      const w = { '-1': 0, '0': 0, '1': 0 }; let any = false;
      for (const iso3 in ECON) { const r = rulesOf('C:' + iso3)[q.id]; if (r) { any = true; const s = stateOf('C:' + iso3, 'forks'); w[String(+r.opt)] += s ? s.P : 0; } }
      const tot = w['-1'] + w['0'] + w['1'];
      const cur = R.plan && R.plan.opts ? R.plan.opts[i] : 0;
      tb.append(h('tr', null, h('td', { text: q.name }), h('td', { text: optText(q.id, cur) }),
        h('td', { class: 'muted', text: any ? ['-1', '0', '1'].map(k => `${arrow(+k)} ${fmt(100 * w[k] / tot, 0)}%`).join(' · ') : 'ни одна страна не решила' })));
    });
    P.append(h('div', { class: 'box', style: 'margin-top:12px' }, h('h3', { text: 'Что сейчас в едином плане' }),
      h('table', null, h('thead', null, h('tr', null, h('th', { text: 'Вопрос' }), h('th', { text: 'Для всех стран' }), h('th', { text: 'Голоса по населению' }))), tb),
      h('p', { class: 'note', text: 'Голос страны весит столько, сколько в ней людей. Вариант вступает в силу со следующего года.' })));
  }
  if (ys.length >= 2) {
    const g = h('div', { class: 'grid2', style: 'margin-top:12px' });
    const mk = (title, sel, fy) => h('div', { class: 'box' }, h('h3', { text: title }), lineChart([
      { name: 'Форки', color: MAP.pal.accent, pts: ys.map(y => [y, sel(S.f[y])]) }, { name: 'План', color: MAP.pal.muted, dash: true, pts: ys.map(y => [y, sel(S.p[y])]) }], { w: 420, h: 150, fy }),
      h('div', { class: 'lg' }, h('span', null, h('i', { style: 'background:' + MAP.pal.accent }), 'мир форков'), h('span', null, h('i', { style: 'background:' + MAP.pal.muted }), 'единый план')));
    g.append(mk('Благополучие', a => a.W, v => fmt(v, 1)), mk('Доход на человека, $', a => a.y || 0, v => fmt(v / 1000, 1) + 'k'), mk('Безработица, %', a => a.u, v => fmt(v, 1)), mk('Инфляция, %', a => a.pi, v => fmt(v, 1)), mk('Добавленный долг, п.п.', a => a.D, v => fmt(v, 0)));
    P.append(g);
  } else P.append(h('p', { class: 'muted', text: 'Графики появятся, когда пройдёт хотя бы один год.' }));
}
// ── как играть
function renderHelp() {
  const P = $('#helpPage'); P.innerHTML = '';
  const nC = Object.keys(ECON).length, nP = DATA.blob ? Object.values(DATA.blob.places).reduce((a, s) => a + s.split('\n').length, 0) : 135103;
  P.innerHTML = `
<h1>Как играть</h1>
<p>Это общая экономика всего мира: ${nC} ${plural(nC, 'страна', 'страны', 'стран')} с реальными стартовыми данными и ${fmt(nP, 0)} ${plural(nP, 'город', 'города', 'городов')} и ${plural(nP, 'село', 'села', 'сёл')}. Каждым местом может управлять игрок, и у каждого места может быть своё решение по каждому вопросу — сколько игроков, столько вариантов. Решения оформляются как патчи в Линуксе, а проверяет их итог, а не начальник.</p>
<div class="grid2 g4">
 <div class="box"><h3>1. Возьмите место</h3><p>Нажмите на страну, город или село на карте (или найдите через поиск) и выберите «Взять под управление». У места один управляющий. Если вашего села нет в списке — «+ Своё село» и нажмите на карту.</p></div>
 <div class="box"><h3>2. Патч</h3><p>Патч — предложение: какие вопросы он меняет, что должно улучшиться и через сколько лет проверить. Написать патч может любой, принять к себе — только управляющий. Один патч может действовать в разных местах.</p></div>
 <div class="box"><h3>3. Год</h3><p>«Следующий год» считает весь мир на год вперёд — для всех игроков сразу. Принятый патч начинает действовать со следующего года.</p></div>
 <div class="box"><h3>4. Проверка по итогам</h3><p>Когда срок патча выходит, место сравнивается со своей «тенью» — тем же местом в том же мире, с теми же кризисами и удачей, но без этого патча. Если выбранный показатель не лучше, чем у тени, патч откатывается сам.</p></div>
</div>
<h2>Вопросы</h2>
<table><thead><tr><th>Вопрос</th><th>Где решается</th><th>Варианты</th></tr></thead><tbody>
${SIM.Q.map(q => `<tr><td>${q.name}</td><td>${q.level === 'country' ? 'только страна' : 'страна, город, село'}</td><td>${['-1', '0', '1'].map(o => q.opts[o]).join(' · ')}</td></tr>`).join('')}
</tbody></table>
<p class="note">Местные налоги, вложения и поддержка добавляются к общим решениям страны. Ставка и пошлины решаются только на уровне страны.</p>
<h2>Единый план</h2>
<p>Параллельно игра считает второй мир — «единый план». В нём по каждому вопросу для всех стран действует один вариант: тот, за которым больше всего людей среди стран, где решение принято (голос страны весит по её населению). Местных решений там нет. Оба мира проходят одни и те же кризисы, поэтому их можно честно сравнить: вкладка «Форки и план» и переключатель на карте.</p>
<h2>Показатели</h2>
<div class="kv">
<b>Благополучие</b><span>рост дохода на человека минус потери от безработицы выше естественной, от инфляции вдали от цели и от добавленного долга, плюс поддержка тех, кому трудно. Главный показатель игры.</span>
<b>Доход на человека</b><span>долларов в год; старт — данные Всемирного банка.</span>
<b>Рост, безработица, инфляция</b><span>старт — последние данные Всемирного банка по стране.</span>
<b>Долг</b><span>добавленный за время игры, в процентах годового дохода (реальный стартовый долг не учитывается).</span>
<b>Население</b><span>страны растут так же, как за 2019–2024 годы по данным Всемирного банка; население города или села ещё и меняется от переезда: люди едут туда, где благополучие выше, чем в среднем по стране.</span>
</div>
<details><summary>Формулы модели</summary>
<p class="note">Модель игрушечная: несколько уравнений с подобранными вручную коэффициентами. Она показывает механику решений и проверок, а не предсказывает настоящую экономику. Её допущения видны здесь — с ними можно спорить.</p>
<div class="formula">спрос:      x = 0,5·x₋₁ + импульс − 0,45·ставка + 0,012·открытость·пошлины + мировой спрос + случайность
импульс:    m·(Δвложения + 0,7·Δподдержка − 0,5·Δналоги), m растёт при высокой безработице
потенциал:  g* + 0,02·K·(1..1,8 для бедных) − 0,04·налоги − 0,015·пошлины − потери от мировых пошлин − 0,01·(долг−30)⁺ − 0,03·поддержка⁺
рост:       потенциал + (x − x₋₁)
инфляция:   π + 0,15·(цель − π) − 0,2·ставка + 0,35·x + пошлины + мировые цены + случайность
безработица: 0,5·u₋₁ + 0,5·(u* − 0,5·x)
долг:       D·(1 + (2 + ставка − рост)/100) + вложения + поддержка − налоги − 0,3·x
благополучие: (рост − рост населения) − 0,5·(u − u*)⁺ − 0,25·|π − цель| − 0,015·долг⁺ ± 0,2·поддержка</div>
<p class="note">Стартовые числа: рост, инфляция, безработица, доход на человека и население — Всемирный банк (последние доступные годы, указаны в карточке страны). Для Тайваня (данных Всемирного банка нет) — DGBAS и оценки на 2026 год; для КНДР — оценка Банка Кореи. Где данных нет, стартовое значение условное. Города и сёла — GeoNames (места от 1000 жителей и центры районов), для России, Беларуси, Казахстана и Киргизии названия даны кириллицей.</p>
</details>
<h2>Google Maps</h2>
<p>Встроить карту Google прямо сюда нельзя: для неё нужны ключ доступа и загрузка карты с серверов Google, а эта страница такого не позволяет. Поэтому карта своя, а у каждого места есть ссылка «Открыть в Google Maps».${DL ? ' Кнопка «⤓ Google My Maps» на карте сохраняет таблицу CSV со всеми странами и местами в игре: в Google My Maps выберите «Импорт», укажите файл и колонки «Широта» и «Долгота» — получится слой с решениями и показателями.' : ''}</p>
<h2>Вместе</h2>
<p>${B.remote ? 'Этот мир общий: его видят и в нём ходят все, кому доступна эта страница, в том числе с разных устройств. Год считает тот, кто нажал «Следующий год»; между годами — пауза в несколько секунд, чтобы все увидели итоги.' : 'Сейчас мир живёт только в этом браузере. Играйте по очереди: добавьте игроков в меню справа вверху и передавайте ход.'} За одним устройством можно играть по очереди и в общем мире.</p>`;
}
// ── выгрузка для Google My Maps
async function exportCSV() {
  if (!DL) return;
  const rows = [['Название', 'Тип', 'Страна', 'Широта', 'Долгота', 'Управляет', 'Решения', 'Благополучие', 'Доход на человека, $', 'Рост, %', 'Безработица, %', 'Инфляция, %', 'Добавленный долг, п.п.', 'Благополучие в едином плане', 'Год']];
  const keys = Object.keys(ECON).map(i => 'C:' + i).concat(Object.keys(M.c.places).filter(k => isLocal(k) && isActive(k)));
  for (const key of keys) {
    const i = placeInfo(key), s = stateOf(key, 'forks'), p = stateOf(key, 'plan'); if (!s || i.lat == null) continue;
    const r = rulesOf(key); const dec = Object.keys(r).map(q => qShort(q) + ': ' + optText(q, r[q].opt)).join('; ');
    rows.push([i.name, kindLabel(i), cname(i.cc), (+i.lat).toFixed(5), (+i.lon).toFixed(5), ownerOf(key) ? nameOf(ownerOf(key)) : '', dec,
      s.W.toFixed(2), Math.round(s.y), s.g.toFixed(2), s.u.toFixed(2), s.pi.toFixed(2), s.D.toFixed(1), p ? p.W.toFixed(2) : '', curYear()]);
  }
  const csv = '﻿' + rows.map(r => r.map(v => { const t = String(v); return /[",;\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; }).join(',')).join('\r\n');
  try { await DL.save({ filename: `ekonomika-forkov-${curYear()}.csv`, data: csv }); toast('Файл сохранён. В Google My Maps: «Импорт» → этот файл → колонки «Широта» и «Долгота».', 6000); }
  catch (e) { if (e && e.code === 'declined') return; toast('Не получилось сохранить файл' + (e && e.message ? ': ' + e.message : '.')); }
}
