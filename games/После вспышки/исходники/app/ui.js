// ════════════════════════ интерфейс: каркас, верхняя панель, карточка страны
let renderQueued = false;
function scheduleRender() { if (renderQueued) return; renderQueued = true; requestAnimationFrame(() => { renderQueued = false; renderAll(); }); }
function typingIn(sel) { const a = document.activeElement; return !!(a && a.closest && a.closest(sel) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)); }
function renderAll() {
  if (!M.ready) return;
  recolor(); renderTop(); renderSegs(); renderLegend(); if (!typingIn('#card')) renderCard();
  if (UI.view === 'patches') renderPatches();
  if (UI.view === 'world') renderWorld();
  if (UI.view === 'forks' && !typingIn('#forksPage') && !UI.forkBusy) renderForks();
  if (UI.view === 'known') renderKnown();
  if (UI.view === 'players') { if (typingIn('#playersPage')) refreshChat(); else renderPlayers(); }
  refreshProfiles();
}
function phaseBars() {
  const Y = curYear(), w = wv(Y), g = game(), ph = (g && g.ph) || {};
  return WORLD.PHASES.map(p => {
    const v = w ? w[p.k] : 0, done = ph[p.k] != null || (w && v >= p.goal && Y >= 1);
    return h('div', { class: 'ph' + (done ? ' done' : ''), title: `${p.ru}: ${p.hint}. Цель ${fmt(100 * p.goal, 0)} %` + (ph[p.k] != null ? `, достигнута в ${tLabel(ph[p.k])}` : '') },
      h('span', { class: 'ph-n', text: p.ru }), h('span', { class: 'ph-b' }, h('i', { style: `width:${(100 * Math.min(1, v / p.goal)).toFixed(0)}%` })), h('span', { class: 'ph-v', text: fmt(100 * v, 0) }));
  });
}
function renderTop() {
  const Y = curYear();
  $('#year').textContent = tLabel(Y); $('#ylbl').textContent = Y === 0 ? 'месяц бури' : 'месяц ' + Y;
  const nb = $('#nextYear');
  const sync = M.ready && syncApplies(), w = sync ? waitedList() : [], waiting = sync ? notReadyNames(w) : [];
  nb.disabled = !canAct() || M.busy || (sync && !iAmWaited() && waiting.length > 0);
  nb.classList.toggle('ready', sync && iAmWaited() && myReady());
  if (M.busy) nb.textContent = 'Считаю…';
  else if (sync && iAmWaited()) nb.textContent = myReady() ? `✓ Готов · ${w.filter(p => p.ready).length}/${w.length}` : 'Готов →';
  else if (sync && waiting.length) nb.textContent = 'Ждём игроков…';
  else nb.textContent = 'Следующий месяц →';
  nb.title = !canAct() ? (M.me.canWrite === false ? 'У вас доступ только на просмотр' : 'Мир загружается')
    : sync ? (waiting.length ? 'Месяц посчитается, когда нажмут «Готов»: ' + waiting.join(', ') : 'Все готовы — месяц считается') : `Посчитать ${tLabel(Y + 1)}: решения игроков, ИИ и модель`;
  const stg = $('#stage'); stg.innerHTML = '';
  const who = M.ready && !M.busy && B.remote ? computingBy() : null;
  if (M.stage) {
    stg.append(h('span', { class: 'spin' }), h('span', { text: M.stage }));
    if (AICTL) stg.append(h('button', { class: 'btn small ghost', onclick: () => AICTL && AICTL.abort() }, 'Не ждать ИИ'));
  } else if (who) stg.append(h('span', { class: 'spin' }), h('span', { text: nameOf(who) + ' считает ' + tLabel(Y + 1) + '…' }));
  else if (sync && myReady() && waiting.length) stg.append(h('span', { class: 'muted', text: 'ждём: ' + waiting.join(', ') }), canAct() ? h('button', { class: 'btn small ghost', onclick: forceYear }, 'Ходить без них') : null);
  setBadge('patches', M.ready ? openPatchesForMe() : 0);
  setBadge('players', M.ready && UI.view !== 'players' ? chatUnread() : 0);
  const wb = $('#worldbar'); wb.innerHTML = '';
  const wr = wv(Y);
  if (wr) wb.append(h('span', { class: 'wb-l', text: 'Мир' }), ...phaseBars(), h('span', { class: 'wb-s', title: 'Люди без воды и еды сейчас · потери сверх обычного с начала бури (оценка)' }, 'без снабжения ', h('b', { text: fmt(wr.P * (1 - wr.served), 0) + ' млн' }), ' · потери ', h('b', { text: fmtK(wr.losses) })));
  renderWho();
  const bn = $('#banner'); bn.innerHTML = '';
  if (M.me.canWrite === false) { bn.style.display = ''; bn.append(h('span', { text: 'У вас доступ только на просмотр: можно смотреть мир и прогнозы, но не ходить.' })); }
  else if (!UI.bannerOff && M.ready && !myCountries().length) {
    bn.style.display = '';
    bn.append(h('span', { text: 'Выберите страну на карте и возьмите её под управление. Первые месяцы решают всё: связь, вода, топливо — а потом свет для всех.' }),
      h('button', { class: 'bx', 'aria-label': 'Скрыть', onclick: () => { UI.bannerOff = true; lsSet('pv3-banner', '1'); renderTop(); } }, '×'));
  } else bn.style.display = 'none';
}
function renderWho() {
  const w = $('#who'); w.innerHTML = '';
  if (!ACT.id) return;
  const mine = myCountries();
  if (!B.remote) {
    const sel = h('select', { class: 'btn small', 'aria-label': 'Кто ходит', onchange: e => { if (e.target.value === '+') { addLocalPlayer(); return; } setActor(e.target.value); } },
      Object.keys(M.c.players).filter(id => id.startsWith('local:')).map(id => h('option', { value: id, selected: id === ACT.id }, M.c.players[id].nick)), h('option', { value: '+' }, '+ игрок'));
    w.append(sel);
  } else {
    const seats = seatIds();
    if (seats.length > 1) w.append(h('select', { class: 'btn small', 'aria-label': 'Кто ходит за этим экраном', onchange: e => switchSeat(e.target.value) }, seats.map(id => h('option', { value: id, selected: id === ACT.id }, nameOf(id)))));
    else w.append(h('button', { class: 'chip-me', title: 'Сменить имя', onclick: () => askName('Как вас называть в игре', (M.c.players[ACT.id] || {}).nick || nameOf(ACT.id), renameMe) }, h('span', { class: 'dot', style: 'background:' + colorOf(ACT.id), text: (nameOf(ACT.id) || '?').charAt(0).toUpperCase() }), h('span', { class: 'nm', text: nameOf(ACT.id) })));
    if (MP.room && MP.roomOk) {
      const ids = onlineIds(), others = ids.filter(id => id !== ACT.id);
      w.append(h('button', { class: 'chip-me online', 'aria-label': 'Сейчас в игре: ' + ids.length, title: others.length ? 'Сейчас в игре: ' + ids.map(nameOf).join(', ') : 'Сейчас в игре только вы — пригласите друзей', onclick: () => setView('players') }, h('i', { class: 'odot' }), h('span', { text: String(ids.length) })));
    }
  }
  mine.slice(0, 3).forEach(iso => w.append(h('button', { class: 'btn small', onclick: () => { setView('map'); select('C:' + iso); } }, cname(iso))));
}
function setActor(id) { ACT.id = id; lsSet('pv3-actor', id); UI.composer = null; renderAll(); requestDraw(); }
async function addLocalPlayer() {
  const n = Object.keys(M.c.players).length + 1, id = 'local:' + n + rid(3);
  M.c.players[id] = { nick: 'Игрок ' + n, host: 'local', seen: Date.now() }; saveLocal(); setActor(id);
  toast('Добавлен ' + M.c.players[id].nick + ' — ходите по очереди за одним экраном.');
}
function renderSegs() {
  const seg = $('#metricSeg'); if (!seg) return; seg.innerHTML = '';
  Object.keys(MAPM).forEach(k => seg.append(h('button', { class: UI.metric === k ? 'on' : '', title: MAPM[k].hint, onclick: () => { UI.metric = k; renderSegs(); renderLegend(); recolor(); } }, MAPM[k].short)));
}
function renderLegend() {
  const L = $('#legend'); if (!L) return; L.innerHTML = '';
  const m = MAPM[UI.metric], P = MAP.pal;
  L.append(h('div', { style: 'font-weight:600', text: m.name }), h('div', { class: 'muted', text: m.hint }));
  if (m.kind === 'who') {
    const others = []; Object.values(M.c.ctrl).forEach(d => { if (d && d.owner && d.owner !== ACT.id && !others.includes(d.owner)) others.push(d.owner); });
    L.append(h('div', { class: 'ends', style: 'gap:10px;justify-content:flex-start;margin-top:6px;flex-wrap:wrap' }, h('span', { html: `<i class="sw" style="background:${P.accent}"></i>вы` }),
      others.slice(0, 6).map(id => h('span', null, h('i', { class: 'sw', style: 'background:' + colorOf(id) }), nameOf(id))),
      h('span', { html: `<i class="sw" style="background:${interp(P.land, P.warn, .35)}"></i>ИИ что-то решил` }), h('span', { html: `<i class="sw" style="background:${P.land}"></i>как есть` }))); return;
  }
  const stops = [P.land, m.kind === 'glow' ? P.glow : m.kind === 'seqbad' ? P.bad : P.good], ends = [m.fmt(m.dom[0]), m.fmt(m.dom[1])];
  L.append(h('div', { class: 'bar', style: `background:linear-gradient(90deg,${stops.join(',')})` }), h('div', { class: 'ends' }, h('span', { text: ends[0] }), h('span', { text: ends[1] })));
}
function setView(v) {
  UI.view = v; $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.v === v)); $$('.view').forEach(s => s.classList.toggle('on', s.id === 'view-' + v));
  if (v === 'map') { resizeMap(); requestDraw(); }
  if (MP.room) setPresence({ view: v });
  renderAll();
}
function select(key, noZoom) {
  UI.sel = key; if (key && !isLocal(key)) { UI.tab = UI.tab || 'over'; loadSum(curYear()).then(() => scheduleRender()); }
  if (UI.view !== 'map') setView('map');
  if (MP.room) setPresence({ sel: key && !isLocal(key) ? key.slice(2) : null });
  renderCard(); requestDraw();
  if (key && !noZoom) zoomToKey(key);
}
// ── маленькие строительные блоки
function stat(k, v, sub, cls) { return h('div', { class: 'stat' }, h('div', { class: 'k', text: k }), h('div', { class: 'v' + (cls ? ' ' + cls : ''), text: v }), sub ? h('div', { class: 'd muted', text: sub }) : null); }
function pill(t, cls, title) { return h('span', { class: 'pill' + (cls ? ' ' + cls : ''), text: t, title: title || null }); }
function lineChart(series, o) {
  const w = o.w || 360, hh = o.h || 120, pl = 34, pr = 8, pt2 = 8, pb = 18;
  const all = series.flatMap(s => s.pts).filter(p => p[1] != null && isFinite(p[1])); if (!all.length) return h('div', { class: 'muted', style: 'font-size:13px', text: 'Появится после первого хода.' });
  let x0 = Math.min(...all.map(p => p[0])), x1 = Math.max(...all.map(p => p[0])); if (x1 === x0) x1 = x0 + 1;
  let y0 = o.y0 != null ? o.y0 : Math.min(...all.map(p => p[1])), y1 = o.y1 != null ? o.y1 : Math.max(...all.map(p => p[1])); if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  const pad = o.y0 != null ? 0 : (y1 - y0) * 0.1; y0 -= pad; y1 += pad;
  const X = x => pl + (x - x0) / (x1 - x0) * (w - pl - pr), Y = y => pt2 + (1 - (y - y0) / (y1 - y0)) * (hh - pt2 - pb);
  const NS2 = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS2, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${hh}`); svg.setAttribute('class', 'chart'); svg.setAttribute('role', 'img'); if (o.label) svg.setAttribute('aria-label', o.label);
  const mk = (t, a) => { const e = document.createElementNS(NS2, t); for (const k in a) e.setAttribute(k, a[k]); svg.appendChild(e); return e; };
  [y0 + pad, (y0 + y1) / 2, y1 - pad].forEach(v => { mk('line', { x1: pl, x2: w - pr, y1: Y(v), y2: Y(v), stroke: MAP.pal.line, 'stroke-width': 0.6, 'stroke-dasharray': '2 3' }); const t = mk('text', { x: pl - 4, y: Y(v) + 3.5, 'text-anchor': 'end' }); t.textContent = (o.fy || (x => fmt(x, 1)))(v); });
  [x0, x1].forEach((v, i) => { const t = mk('text', { x: X(v), y: hh - 4, 'text-anchor': i ? 'end' : 'start' }); t.textContent = (o.fx || (x => x))(v); });
  for (const s of series.slice().sort((a, b) => (a.dash ? 1 : 0) - (b.dash ? 1 : 0))) {
    const pts = s.pts.filter(p => p[1] != null && isFinite(p[1])); if (!pts.length) continue;
    mk('path', { d: pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join(''), fill: 'none', stroke: s.color, 'stroke-width': s.dash ? 1.6 : 2.2, 'stroke-dasharray': s.dash ? '5 4' : '', 'stroke-linejoin': 'round' });
    if (pts.length === 1) mk('circle', { cx: X(pts[0][0]), cy: Y(pts[0][1]), r: 3, fill: s.color });
  }
  return svg;
}
function legendRow(items) { return h('div', { class: 'lrow' }, items.map(([c, t, dash]) => h('span', null, h('i', { class: 'ln' + (dash ? ' dash' : ''), style: 'border-color:' + c }), t))); }
// ── окна
let lastFocus = null;
function openDialog(title, body, foot, wide) {
  lastFocus = document.activeElement;
  const d = $('#dlg'); d.innerHTML = ''; d.classList.toggle('wide', !!wide);
  d.append(h('div', { class: 'dlg-h' }, h('h2', { id: 'dlgTitle', text: title }), h('button', { class: 'card-x', style: 'position:static', 'aria-label': 'Закрыть', onclick: closeDialog }, '×')),
    h('div', { class: 'dlg-b' }, body), foot ? h('div', { class: 'dlg-f' }, foot) : null);
  $('#modal').classList.add('on');
  setTimeout(() => { const f = d.querySelector('input,select,textarea,button:not(.card-x)') || d.querySelector('button'); if (f) f.focus(); }, 0);
}
function closeDialog() {
  $('#modal').classList.remove('on'); UI.composer = null;
  const f = lastFocus; lastFocus = null;
  if (f && f.focus && document.contains(f)) { try { f.focus(); } catch (e) { } }
}
function askConfirm(title, text, okText, onOk, danger) {
  openDialog(title, h('p', { style: 'margin:0', text }), [
    h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'),
    h('button', { class: 'btn ' + (danger ? 'danger' : 'primary'), onclick: () => { closeDialog(); onOk(); } }, okText)]);
}
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeDialog(); });
document.addEventListener('keydown', e => {
  if (!$('#modal').classList.contains('on')) return;
  if (e.key === 'Escape') { closeDialog(); return; }
  if (e.key !== 'Tab') return;
  const f = $$('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])', $('#dlg'));
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

// ════════════════════════ карточка: страна или место
const CTABS = [['over', 'Обзор'], ['sup', 'Снабжение'], ['aid', 'Помощь'], ['places', 'Места'], ['dec', 'Решения']];
async function histOf(iso, keys, n = 24) {
  const Y = curYear(), ys = []; for (let y = Math.max(BASE, Y - n); y <= Y; y++) ys.push(y);
  await Promise.all(ys.map(y => loadSum(y)));
  const o = {}; keys.forEach(k => { o[k] = ys.map(y => [y, sv(y, iso, k)]).filter(p => p[1] != null); }); return o;
}
function renderCard() {
  const card = $('#card'); if (!card) return;
  const on = !!(UI.sel && UI.view === 'map');
  $('#view-map').classList.toggle('has-card', on);
  if (!on) { card.classList.remove('on'); card.innerHTML = ''; return; }
  card.classList.add('on');
  const keep = card.querySelector('.card-b'), scroll = keep ? keep.scrollTop : 0, prevSel = card.dataset.sel, prevTab = card.dataset.tab;
  card.innerHTML = ''; card.dataset.sel = UI.sel; card.dataset.tab = UI.tab;
  if (isLocal(UI.sel)) renderPlaceCard(card); else renderCountryCard(card, UI.sel.slice(2));
  const nb = card.querySelector('.card-b'); if (nb && prevSel === UI.sel && prevTab === UI.tab) nb.scrollTop = scroll;
}
function popRu(p) { return p ? fmtPop(p) + ' чел.' : 'население неизвестно'; }
function renderCountryCard(card, iso) {
  const Y = curYear(), C = WC(iso), own = ownerOf(iso), idle = isIdle(iso);
  const sub = [popRu(C.P * 1e6), WORLD.isFactory(iso) ? 'заводы трансформаторов: ' + fmt(100 * WORLD.factShare(iso), 0) + ' % мирового выпуска' : null, 'геомагн. широта ' + fmt(Math.abs(C.gm), 0) + '°'].filter(Boolean).join(' · ');
  const head = h('div', { class: 'card-h' }, h('h2', { text: cname(iso) }), h('div', { class: 'sub', text: sub }),
    h('div', { class: 'ruler' }, own ? h('span', { class: 'chip-me' }, h('span', { class: 'dot', style: 'background:' + colorOf(own), text: nameOf(own).charAt(0).toUpperCase() }), h('span', { text: (own === ACT.id ? 'Вы управляете' : 'Управляет ' + nameOf(own)) }))
      : h('span', { class: 'pill', title: 'Решения за страну принимает ИИ (раз в месяц) или она держит прежний курс', text: 'Управляет ИИ' }),
      idle ? pill('брошена', 'warn', 'Владелец полгода ничего не делал — страну можно перехватить') : null,
      (!own || idle) && canAct() ? h('button', { class: 'btn small primary', onclick: () => claimCountry(iso) }, idle ? 'Перехватить' : 'Взять управление') : null,
      own === ACT.id ? h('button', { class: 'btn small ghost', onclick: () => askConfirm('Отдать ИИ?', 'Отдать ' + cname(iso) + ' под управление ИИ? Ваша политика останется в силе, пока ИИ её не поменяет.', 'Отдать ИИ', () => releaseCountry(iso)) }, 'Отдать ИИ') : null,
      canAct() ? h('button', { class: 'btn small', onclick: () => openComposer(iso) }, own === ACT.id ? '+ Решение' : '+ Предложить патч') : null),
    h('button', { class: 'card-x', 'aria-label': 'Закрыть', onclick: () => select(null) }, '×'));
  const tabs = h('div', { class: 'ctabs', role: 'tablist' }, CTABS.map(([k, t]) => h('button', { class: 'ctab' + (UI.tab === k ? ' on' : ''), role: 'tab', onclick: () => { UI.tab = k; renderCard(); } }, t)));
  const body = h('div', { class: 'card-b' });
  card.append(head, tabs, body);
  if (!M.sum[Y]) {
    if (M.bad[Y]) { body.append(h('div', { class: 'muted', text: 'Не получилось восстановить мир за этот месяц.' })); return; }
    body.append(h('div', { class: 'muted', text: 'Загружаю данные месяца…' })); loadSum(Y).then(() => scheduleRender()); return;
  }
  ({ over: tabOverview, sup: tabSupply, aid: tabAid, places: tabPlaces, dec: tabDecisions })[UI.tab](body, iso, Y);
}
function tabOverview(el, iso, Y) {
  const v = k => sv(Y, iso, k), p = k => sv(Y - 1, iso, k);
  const d = (k, mul = 100, u = ' п.п.') => p(k) == null ? null : sgn(mul * (v(k) - p(k)), 1) + u + ' за месяц';
  el.append(h('div', { class: 'stats' },
    stat('Снабжение', pct(v('served')), d('served'), v('served') < 0.7 ? 'bad' : ''),
    stat('Свет', pct(v('grid')), d('grid'), v('grid') < 0.5 ? 'warn' : ''),
    stat('Связь', pct(v('comms')), d('comms'), v('comms') < 0.3 ? 'bad' : ''),
    stat('Логистика', pct(v('logi')), d('logi')),
    stat('Топливо', fmt(v('fuel'), 1) + ' мес.', 'запас при нынешнем расходе', v('fuel') < 0.5 ? 'bad' : ''),
    stat('Еда', fmt(v('food'), 1) + ' мес.', v('hungry') > 0.02 ? 'без еды ' + pct(v('hungry')) : 'еда доходит до всех', v('hungry') > 0.15 ? 'bad' : ''),
    stat('Бригады', fmt(v('crews'), 1) + ' тыс.', 'ремонтники и монтажники'),
    stat('Потери', fmtK(v('losses')), 'сверх обычного с начала бури (оценка)', v('losses') > 0 ? 'bad' : '')));
  const box = h('div'); el.append(h('h3', { text: 'Как менялось' }), box);
  histOf(iso, ['served', 'grid', 'comms']).then(H => {
    const P = MAP.pal, pc = a => a.map(([x, y]) => [x, 100 * y]);
    box.append(lineChart([{ pts: pc(H.served), color: P.good }, { pts: pc(H.grid), color: P.glow }, { pts: pc(H.comms), color: P.accent, dash: true }], { label: 'Снабжение, свет и связь по месяцам', y0: 0, y1: 100, fy: x => fmt(x, 0), fx: x => WORLD.labelShort(x) }),
      legendRow([[P.good, 'снабжение, %'], [P.glow, 'свет, %'], [P.accent, 'связь, %', true]]));
  });
  const news = ((M.news[Y] && M.news[Y].items) || []).filter(n => (n.iso || []).includes(iso));
  if (!M.news[Y]) loadNews(Y).then(() => scheduleRender());
  if (news.length) el.append(h('h3', { text: 'Новости' }), news.map(newsItem));
  el.append(h('p', { class: 'muted small', text: Y === BASE ? 'Первый месяц после бури: стартовые данные — население и хозяйство 2025 года, урон — по геомагнитной широте. Дальше — модель.' : 'Цифры посчитаны моделью по решениям игроков и ИИ. Что в ней от данных, а что — допущение, написано на вкладке «Что известно».' }));
}
function newsItem(n) {
  return h('div', { class: 'news ' + (n.src || '') }, h('div', { class: 'nt' }, n.src === 'ai' ? pill('ИИ', 'acc', 'Событие придумал ИИ, играющий за остальной мир') : n.src === 'check' ? pill('проверка', n.title.includes('не подтвердился') ? 'bad' : 'good') : pill('модель', '', 'Сообщение из цифр модели'), h('b', { text: ' ' + n.title })),
    n.text ? h('div', { class: 'muted', text: n.text }) : null,
    (n.iso || []).length ? h('div', { class: 'nlinks' }, n.iso.map(x => h('button', { class: 'lnk', onclick: () => select('C:' + x) }, cname(x)))) : null);
}
function tabSupply(el, iso, Y) {
  const v = k => sv(Y, iso, k), C = WC(iso), pol = ctrlOf(iso) ? polOf(iso) : ((M.dec[Y] && M.dec[Y].pol[iso]) || {});
  const pr = WORLD.priorities(pol);
  el.append(h('h3', { style: 'margin-top:0', text: 'Электросеть' }),
    h('div', { class: 'kv' },
      [h('span', { class: 'muted', text: 'Узлов сети всего' }), h('span', { text: fmt(v('Tt'), 0) })],
      [h('span', { class: 'muted', text: 'Выбито бурей' }), h('span', { text: pct(v('dmg')) + ' (по широте ' + fmt(Math.abs(C.gm), 0) + '°)' })],
      [h('span', { class: 'muted', text: 'Ещё не работает' }), h('span', { text: fmt(v('Td'), 0) + ': ремонт ' + fmt(v('Trep'), 0) + ', нужны новые ' + fmt(v('Tnew'), 0) })],
      [h('span', { class: 'muted', text: 'На руках' }), h('span', { text: 'запас ' + fmt(v('Tsp'), 0) + ' шт., в пути ' + fmt(v('Tin'), 0) + ' шт.' })],
      [h('span', { class: 'muted', text: 'Бригады' }), h('span', { text: fmt(v('crews'), 1) + ' тыс. чел., на сеть ' + pct(pr[2]) })],
      WORLD.isFactory(iso) ? [h('span', { class: 'muted', text: 'Заводы' }), h('span', { text: 'выпуск ' + fmt(v('prod'), 1) + ' шт./мес., на экспорт ' + pct(pol.exportT != null ? pol.exportT : LEV.exportT.def) })] : null),
    h('p', { class: 'muted small', text: 'Свет для больниц, насосов и связи держится на уцелевших узлах и генераторах — пока есть топливо. Полное восстановление — только новыми трансформаторами: их делают в двух десятках стран, и заводам самим нужен свет.' }));
  el.append(h('h3', { text: 'Топливо и еда' }),
    h('div', { class: 'kv' },
      [h('span', { class: 'muted', text: 'Топливо' }), h('span', { text: fmt(v('fuel'), 2) + ' мес. запаса; расход ' + pct(v('fuelUse')) + ' от обычного; своя добыча и переработка ' + pct(C.fuelSS) + ' потребности' })],
      [h('span', { class: 'muted', text: 'Нормирование' }), h('span', { text: pct(pol.ration != null ? pol.ration : LEV.ration.def) })],
      [h('span', { class: 'muted', text: 'Еда' }), h('span', { text: fmt(v('food'), 2) + ' мес. запаса; своё производство ' + pct(C.foodSS) + ' потребности' })],
      [h('span', { class: 'muted', text: 'Без еды' }), h('span', { class: v('hungry') > 0.15 ? 'bad' : '', text: pct(v('hungry')) + ' населения' })],
      [h('span', { class: 'muted', text: 'Вода' }), h('span', { class: v('water') < 0.5 ? 'bad' : '', text: pct(v('water')) + ' населения' })]),
    h('p', { class: 'muted small', text: 'Топливо: генераторы, подвоз, тракторы и рыбацкие лодки. Кончится — встанет всё сразу. Экспортёры продают излишки тем, с кем есть связь и у кого ходят суда и грузовики.' }));
  el.append(h('h3', { text: 'Связь' }),
    h('div', { class: 'kv' },
      [h('span', { class: 'muted', text: 'Радиосеть' }), h('span', { text: pct(v('radio')) })],
      [h('span', { class: 'muted', text: 'Сотовая и оптика' }), h('span', { text: pct(v('net')) + ' (нужны свет и ремонт)' })],
      [h('span', { class: 'muted', text: 'Спутники в мире' }), h('span', { text: pct(wv(Y) ? wv(Y).S : null) })]),
    h('p', { class: 'muted small', text: 'Без связи страна не может ни попросить, ни принять помощь. КВ-радио поднимается за недели, сотовая сеть — по мере света.' }));
  if (isMine(iso)) el.append(h('div', { class: 'row-btns' }, h('button', { class: 'btn small primary', onclick: () => openComposer(iso, { group: 'Приоритеты' }) }, 'Изменить приоритеты и нормирование')));
}
function tabAid(el, iso, Y) {
  const v = k => sv(Y, iso, k), mine = isMine(iso), req = M.c.req[iso];
  el.append(h('div', { class: 'stats' }, stat('Получено за месяц', fmt(v('aidIn'), 0) + ' шт.', 'трансформаторов (помощь и поставки заводов)'), stat('Отправлено', fmt(v('aidOut'), 0) + ' шт.', 'трансформаторов другим')));
  const items = ((M.sum[Y] && M.sum[Y].ev) || []).filter(e => (e.k === 'aid' || e.k === 'aidfail') && (e.from === iso || e.to === iso));
  el.append(h('h3', { text: 'Отправки за месяц' }));
  if (!items.length) el.append(h('div', { class: 'muted small', text: 'Ничего не отправлялось и не приходило.' }));
  items.forEach(e => el.append(h('div', { class: 'prow' }, pill(e.k === 'aid' ? (e.to === iso ? 'получено' : 'отправлено') : 'не дошло', e.k === 'aid' ? 'good' : 'bad'), h('span', { text: `${cname(e.from)} → ${cname(e.to)}: ${AIDRU[e.what]}${e.q != null ? ', ' + aidQ(e.what, e.q) : ''}` }))));
  el.append(h('h3', { text: 'Заявка о помощи' }));
  if (req && req.open) el.append(h('div', { class: 'reqbox' }, h('b', { text: 'Открыта с ' + tLabel(req.y) + ': ' }), h('span', { text: req.text || 'нужна помощь' })));
  else el.append(h('div', { class: 'muted small', text: 'Заявки нет. Открытая заявка видна всем игрокам на вкладке «Мир» и ИИ, который решает за остальной мир.' }));
  if (mine) {
    const ta = h('textarea', { class: 'inp', rows: 2, placeholder: 'Что нужно: например, «30 дней топлива и 20 трансформаторов, связь есть»', maxlength: 300 }, req && req.text ? req.text : '');
    el.append(ta, h('div', { class: 'row-btns' }, h('button', { class: 'btn small primary', onclick: () => setRequest(iso, ta.value, true) }, req && req.open ? 'Обновить заявку' : 'Опубликовать заявку'), req && req.open ? h('button', { class: 'btn small ghost', onclick: () => setRequest(iso, '', false) }, 'Снять') : null));
    el.append(h('h3', { text: 'Отправить помощь' }), h('p', { class: 'muted small', text: 'Помощь — разовое решение: трансформаторы из запаса, дни топлива или еды, бригады, радиокомплекты. Отправка возможна при связи ≥ 20 % у обеих сторон и логистике ≥ 20 % у отправителя; дойдёт через месяц.' }),
      h('div', { class: 'row-btns' }, h('button', { class: 'btn small primary', onclick: () => openComposer(iso, { group: 'Помощь другим' }) }, 'Отправить помощь')));
  } else if (canAct()) el.append(h('p', { class: 'muted small', text: 'Помочь этой стране можно из своей: откройте свою страну → «Помощь» → «Отправить помощь».' }));
  const reqs = Object.values(M.c.req).filter(q => q && q.open && q.iso !== iso).sort((a, b) => b.t - a.t).slice(0, 8);
  if (reqs.length) el.append(h('h3', { text: 'Просят помощи' }), reqs.map(q => h('div', { class: 'prow' }, h('button', { class: 'lnk', onclick: () => select('C:' + q.iso) }, cname(q.iso)), h('span', { class: 'muted small', text: q.text || 'нужна помощь' }))));
}
function tabPlaces(el, iso, Y) {
  if (!DATA.blob) { el.append(h('div', { class: 'muted', text: 'Распаковываю города и сёла…' })); return; }
  const arr = placesOf(iso), g = sv(Y, iso, 'grid') || 0, s = sv(Y, iso, 'served') || 0;
  el.append(h('p', { class: 'muted small', text: `Городов и сёл в стране: ${fmt(arr.length, 0)}. Свет вернулся примерно в ${pct(g)} мест, снабжение доходит до ${pct(s)} жителей — модель считает по стране в целом, а места показывают, где живут люди.` }));
  const q = h('input', { class: 'inp', placeholder: 'Найти город или село в стране', 'aria-label': 'Поиск места' });
  const list = h('div');
  const draw = () => {
    list.innerHTML = ''; const sq = q.value.trim().toLowerCase();
    const found = (sq ? arr.filter(p => p.name.toLowerCase().includes(sq)) : arr).slice(0, 40);
    found.forEach(p => list.append(h('div', { class: 'prow place' }, h('button', { class: 'lnk', onclick: () => select(p.key) }, p.name), h('span', { class: 'muted small', text: fmtPop(p.pop) + ' чел.' + (p.cap === 2 ? ' · столица' : '') }))));
    if (!found.length) list.append(h('div', { class: 'muted small', text: 'Ничего не нашлось.' }));
  };
  q.addEventListener('input', debounce(draw, 150)); draw();
  el.append(q, list);
}
function renderPlaceCard(card) {
  const i = placeInfo(UI.sel), Y = curYear();
  const head = h('div', { class: 'card-h' }, h('h2', { text: i.name }),
    h('div', { class: 'sub' }, i.cc ? h('button', { class: 'lnk', onclick: () => select('C:' + i.cc, true) }, cname(i.cc)) : h('span', { text: 'место не найдено в справочнике' }),
      ' · ' + popRu(i.pop) + (i.cap === 2 ? ' · столица' : '')),
    h('button', { class: 'card-x', 'aria-label': 'Закрыть', onclick: () => select(null) }, '×'));
  const body = h('div', { class: 'card-b' }); card.append(head, body);
  if (i.cc && M.sum[Y]) {
    const gr = sv(Y, i.cc, 'grid'), sr = sv(Y, i.cc, 'served'), cm = sv(Y, i.cc, 'comms');
    body.append(h('div', { class: 'stats' }, stat('Свет в стране', pct(gr)), stat('Снабжение', pct(sr)), stat('Связь', pct(cm)), stat('Жителей', fmtPop(i.pop))));
    body.append(h('p', { class: 'muted small', text: gr > 0.6 ? 'Скорее всего, здесь уже есть свет: большие города и узлы связи восстанавливают первыми.' : gr > 0.25 ? 'Свет — по графику и в отдельных районах; вода и больницы на генераторах.' : 'Здесь темно: свет только у больниц и узлов связи от генераторов, пока есть топливо.' }));
  }
  const site = siteKeys()[UI.sel];
  if (site) body.append(h('h3', { text: 'Проект здесь' }), h('div', null, h('b', { text: site.title }), ' ', pill(statusRu(site.status), statusCls(site.status))));
  body.append(h('div', { class: 'row-btns' },
    canAct() && i.cc ? h('button', { class: 'btn small primary', onclick: () => openComposer(i.cc, { site: UI.sel }) }, 'Решение с площадкой здесь') : null,
    isFinite(i.lat) && isFinite(i.lon) ? h('a', { class: 'btn small', href: `https://www.google.com/maps/search/?api=1&query=${i.lat},${i.lon}`, target: '_blank', rel: 'noopener' }, 'Открыть в Google Maps') : null));
}
function statusRu(s) { return ({ open: 'на рассмотрении', merged: 'принят', kept: 'подтвердился', failed: 'не подтвердился', reverted: 'откачен', neutral: 'ничего не изменил', stale: 'срок вышел', rejected: 'отклонён' })[s] || s; }
function statusCls(s) { return ({ merged: 'acc', kept: 'good', failed: 'bad', reverted: 'bad', neutral: '', stale: '', rejected: '' })[s] || ''; }
function levVal(L, v) {
  if (v == null) return '—';
  const n = x => L.unit === 'доля' ? fmt(100 * x, 0) + ' %' : fmt(x, L.step >= 1 ? 0 : 2) + ' ' + L.unit;
  if (L.kind === 'bool') return v ? 'да' : 'нет';
  if (L.kind === 'num') return n(v);
  if (L.kind === 'iso') return Object.keys(v).map(x => cname(x) + ' ' + n(v[x])).join(', ');
  return String(v);
}
function policyList(pol) {
  const ks = Object.keys(pol || {}).filter(k => LEV[k]); if (!ks.length) return h('div', { class: 'muted small', text: 'По умолчанию: приоритеты поровну, нормирование 60 %, заводы отдают на экспорт 30 %.' });
  return h('div', { class: 'kv' }, ks.map(k => [h('span', { class: 'muted', text: LEV[k].ru }), h('span', { text: levVal(LEV[k], pol[k]) })]));
}
function tabDecisions(el, iso, Y) {
  const own = ownerOf(iso), pol = own ? polOf(iso) : ((M.dec[Y] && M.dec[Y].pol[iso]) || {});
  el.append(h('h3', { style: 'margin-top:0', text: own ? 'Политика страны (со следующего месяца)' : 'Политика страны (как решил ИИ)' }), policyList(pol));
  const pats = Object.values(M.c.patch).filter(p => p && p.iso === iso).sort((a, b) => b.t - a.t);
  el.append(h('h3', { text: 'Патчи' }));
  if (!pats.length) el.append(h('div', { class: 'muted small', text: 'Патчей пока нет. Патч — предложение изменить решения страны с целью и сроком проверки: через срок мир сравнят с «тенью», где патча не было.' }));
  pats.slice(0, 30).forEach(p => el.append(patchCard(p, { compact: true })));
  if (canAct()) el.append(h('div', { class: 'row-btns' }, h('button', { class: 'btn small primary', onclick: () => openComposer(iso) }, own === ACT.id ? 'Новое решение' : 'Предложить патч')));
}
