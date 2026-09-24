// ════════════════════════ редактор решений (патч), прогноз, патчи, мир, форки
const isPct = L => L.unit === 'доля';
const toUI = (L, v) => v == null ? '' : isPct(L) ? +(100 * v).toFixed(1) : +(+v).toFixed(2);
const fromUI = (L, x) => { if (x === '' || x == null || !isFinite(+x)) return null; const v = isPct(L) ? +x / 100 : +x; return Math.max(L.min, Math.min(L.max, v)); };
const uiUnit = L => isPct(L) ? '%' : L.unit || '';

// редактор значений рычагов: общий для патча и форка. st — { ch }, base — действующая политика
function leverEditor(L, st, base, iso, onChange) {
  const cur = base[L.k], ch = st.ch;
  const box = h('div', { class: 'lev' + (ch[L.k] !== undefined ? ' changed' : '') });
  box.append(h('div', { class: 'lev-h' }, h('b', { text: L.ru }), h('span', { class: 'muted small', text: ' · ' + L.hint }),
    cur != null ? h('div', { class: 'small', text: 'Сейчас: ' + levVal(L, cur) }) : (L.def != null ? h('div', { class: 'small muted', text: 'Сейчас: по умолчанию ' + levVal(L, L.def) }) : null),
    ch[L.k] !== undefined ? h('button', { class: 'lnk small', onclick: () => { delete ch[L.k]; onChange(); } }, 'не менять') : null,
    cur != null && ch[L.k] !== null ? h('button', { class: 'lnk small', onclick: () => { ch[L.k] = null; onChange(); } }, 'вернуть по умолчанию') : null));
  if (ch[L.k] === null) { box.append(h('div', { class: 'small bad', text: 'Решение будет снято.' })); return box; }
  const numInput = (val, set, ph, lab) => {
    const i = h('input', { class: 'inp num', type: 'number', step: isPct(L) ? 100 * L.step : L.step, min: isPct(L) ? 100 * L.min : L.min, max: isPct(L) ? 100 * L.max : L.max, value: val, placeholder: ph || '', 'aria-label': lab || L.ru });
    i.addEventListener('change', () => { set(fromUI(L, i.value)); onChange(); }); return i;
  };
  if (L.kind === 'num') {
    const v = ch[L.k] !== undefined ? ch[L.k] : (cur != null ? cur : L.def);
    const rng = h('input', { type: 'range', min: isPct(L) ? 100 * L.min : L.min, max: isPct(L) ? 100 * L.max : L.max, step: isPct(L) ? 100 * L.step : L.step, value: toUI(L, v), 'aria-label': L.ru });
    const num = numInput(toUI(L, v), x => { if (x == null) delete ch[L.k]; else ch[L.k] = x; }, '', L.ru);
    rng.addEventListener('input', () => { num.value = rng.value; });
    rng.addEventListener('change', () => { const x = fromUI(L, rng.value); if (x == null) delete ch[L.k]; else ch[L.k] = x; onChange(); });
    box.append(h('div', { class: 'lev-in' }, rng, num, h('span', { class: 'muted', text: uiUnit(L) }), h('span', { class: 'muted small', text: `от ${toUI(L, L.min)} до ${toUI(L, L.max)}` })));
  } else if (L.kind === 'iso') {
    const list = Object.assign({}, cur || {}, ch[L.k] || {});
    const rows = h('div');
    Object.keys(list).forEach(x => { if (list[x] == null) return; rows.append(h('div', { class: 'prow' }, h('span', { text: cname(x) }), numInput(toUI(L, list[x]), v => { ch[L.k] = Object.assign({}, ch[L.k] || {}); ch[L.k][x] = v == null || v === 0 ? null : v; }, '', L.ru + ': ' + cname(x)), h('span', { class: 'muted', text: uiUnit(L) }), h('button', { class: 'lnk small', onclick: () => { ch[L.k] = Object.assign({}, ch[L.k] || {}); ch[L.k][x] = null; onChange(); } }, 'убрать'))); });
    const reqs = Object.values(M.c.req).filter(q => q && q.open && q.iso !== iso).map(q => q.iso);
    const rest = ISO.filter(x => x !== iso && !(x in list) && !reqs.includes(x)).sort((a, b) => cname(a).localeCompare(cname(b), 'ru'));
    const pick = h('select', { class: 'btn small', 'aria-label': 'Страна-получатель' }, h('option', { value: '' }, 'кому…'), reqs.length ? h('optgroup', { label: 'просят помощи' }, reqs.filter(x => !(x in list)).map(x => h('option', { value: x }, cname(x)))) : null, rest.map(x => h('option', { value: x }, cname(x))));
    pick.addEventListener('change', () => { if (!pick.value) return; ch[L.k] = Object.assign({}, ch[L.k] || {}); ch[L.k][pick.value] = L.k === 'aidT' ? 10 : L.k === 'aidC' ? 5 : L.k === 'aidR' ? 2 : 30; onChange(); });
    box.append(rows, pick);
  }
  return box;
}
function chChips(ch) {
  const ks = Object.keys(ch || {}); if (!ks.length) return h('span', { class: 'muted small', text: 'пока ничего не меняется' });
  return ks.map(k => LEV[k] ? pill(LEV[k].ru + ': ' + (ch[k] === null ? 'снять' : levVal(LEV[k], ch[k])), 'acc') : null);
}
// ── прогноз: мир «с решением» против «без» на hz месяцев (остальные держат курс, случайности те же)
async function project(changes, hz, opts) {
  opts = opts || {};
  const Y = curYear(), st0 = await stateAt(Y, opts.onProgress);
  const d0 = (await getDec(Y)) || { pol: {}, src: {} };
  const dec = assemble(Y + 1, null, d0);
  const polB = clone(dec.pol);
  for (const iso in changes) {
    const p = WORLD.sanitize(applyCh(polB[iso] || {}, changes[iso]), iso);
    if (chEmpty(p)) delete polB[iso]; else polB[iso] = p;
  }
  let a = st0, b = st0; const A = [st0], Bs = [st0];
  const wA = Object.assign({}, dec.wev, opts.calm ? { calm: true } : {});
  const onceStrip = P => { const o = {}; for (const iso in P) { const p = stripOnce(P[iso]); if (!chEmpty(p)) o[iso] = p; } return o; };
  for (let t = 0; t < hz; t++) {
    const pa = t ? onceStrip(dec.pol) : dec.pol, pb = t ? onceStrip(polB) : polB;
    a = WORLD.step(a, polArr(pa), wA).st; b = WORLD.step(b, polArr(pb), wA).st;
    A.push(a); Bs.push(b);
    if (opts.onProgress) opts.onProgress(Y + t + 1, Y + hz);
    await sleep(0);
  }
  return { Y, A, B: Bs };
}
function projRows(P, iso) {
  const c = IDX[iso], a = P.A[P.A.length - 1], b = P.B[P.B.length - 1];
  return [
    ['Снабжение', 100 * (b.served[c] - a.served[c]), 'п.п.', 1],
    ['Свет', 100 * (b.grid[c] - a.grid[c]), 'п.п.', 1],
    ['Связь', 100 * (b.comms[c] - a.comms[c]), 'п.п.', 1],
    ['Логистика', 100 * (b.logi[c] - a.logi[c]), 'п.п.', 1],
    ['Без еды', 100 * (b.hungry[c] - a.hungry[c]), 'п.п.', -1],
    ['Топливо', b.fuel[c] - a.fuel[c], 'мес.', 1],
    ['Потери', b.losses[c] - a.losses[c], 'тыс. чел.', -1],
    ['Экономика', 100 * (b.econ[c] - a.econ[c]), 'п.п.', 1]
  ];
}
function worldRows(P) {
  const a = WORLD.world(P.A[P.A.length - 1]), b = WORLD.world(P.B[P.B.length - 1]);
  return [['Мир: снабжение', 100 * (b.served - a.served), 'п.п.', 1], ['Мир: свет', 100 * (b.grid - a.grid), 'п.п.', 1], ['Мир: связь', 100 * (b.comms - a.comms), 'п.п.', 1], ['Мир: потери', (b.losses - a.losses) / 1000, 'млн чел.', -1]];
}
function projTable(P, iso, extra) {
  const rows = projRows(P, iso).concat(extra ? worldRows(P) : []);
  const cell = (v, u, dir) => { const good = v * dir > 0.005 ? 'good' : v * dir < -0.005 ? 'bad' : ''; return h('td', { class: 'r ' + good, text: sgn(v, Math.abs(v) < 10 ? 2 : 1) + ' ' + u }); };
  return h('div', null,
    h('table', { class: 'tbl' }, h('thead', null, h('tr', null, h('th', { text: `${cname(iso)} к ${tLabel(P.Y + P.A.length - 1)}` }), h('th', { class: 'r', text: 'с решением − без' }))),
      h('tbody', null, rows.map(([n, v, u, dir]) => h('tr', null, h('td', { text: n }), cell(v, u, dir))))),
    h('p', { class: 'muted small', text: 'Прогноз «при прочих равных»: остальные страны держат нынешний курс, случайности те же. Реальный ход будет другим — ИИ и игроки тоже принимают решения.' }));
}
// ── окно решения (патча)
function openComposer(iso, opts) {
  opts = opts || {};
  const own = ownerOf(iso), mine = own === ACT.id;
  const base = own ? polOf(iso) : ((M.dec[curYear()] && M.dec[curYear()].pol[iso]) || {});
  const st = UI.composer = { iso, ch: {}, goal: { m: 'served', h: 3 }, title: '', note: '', site: opts.site || null, group: opts.group || 'Приоритеты', autoRevert: true };
  const body = h('div', { class: 'composer' });
  const draw = () => {
    body.innerHTML = '';
    if (!mine) body.append(h('p', { class: 'muted small', text: own ? `Страной управляет ${nameOf(own)}: ваш патч попадёт к нему на рассмотрение.` : 'Страной сейчас управляет ИИ: патч можно предложить, а принять — тому, кто возьмёт страну.' }));
    const title = h('input', { class: 'inp', placeholder: 'Название, например «Сначала связь»', value: st.title, maxlength: 90, 'aria-label': 'Название' });
    title.addEventListener('input', () => { st.title = title.value; });
    body.append(title);
    if (st.site) body.append(h('div', { class: 'small', style: 'margin:6px 0' }, 'Площадка: ', h('b', { text: placeInfo(st.site).name }), ' ', h('button', { class: 'lnk small', onclick: () => { st.site = null; draw(); } }, 'убрать')));
    body.append(h('div', { class: 'gtabs' }, LEVGROUPS.map(g => h('button', { class: 'ctab' + (st.group === g.ru ? ' on' : ''), onclick: () => { st.group = g.ru; draw(); } }, g.ru, Object.keys(st.ch).some(k => g.ks.includes(k)) ? h('i', { class: 'mark' }) : null))));
    const grp = LEVGROUPS.find(g => g.ru === st.group);
    if (grp.ru === 'Приоритеты') body.append(h('p', { class: 'muted small', text: 'Четыре приоритета делят бригады и топливо; в сумме они нормируются на 100 %. Нормирование бережёт топливо, но замедляет всё остальное.' }));
    if (grp.ru === 'Заводы' && !WORLD.isFactory(iso)) body.append(h('p', { class: 'muted small', text: 'У этой страны нет заводов силовых трансформаторов — экспортировать нечего. Новые единицы приходят от заводов других стран и как помощь.' }));
    if (grp.ru === 'Помощь другим') body.append(h('p', { class: 'muted small', text: 'Разовые отправки этого месяца. Нужны связь ≥ 20 % у обеих сторон и логистика ≥ 20 % у отправителя; груз доедет через месяц. Трансформаторы уходят из запаса (вкладка «Снабжение»).' }));
    grp.ks.forEach(k => { const L = LEV[k]; if (!L) return; if (k === 'exportT' && !WORLD.isFactory(iso)) return; body.append(leverEditor(L, st, base, iso, draw)); });
    if (grp.ru === 'Приоритеты') { const pr = WORLD.priorities(Object.assign({}, base, Object.fromEntries(Object.entries(st.ch).filter(([k, v]) => v != null)))); body.append(h('div', { class: 'small muted', style: 'margin:4px 0 8px' }, 'После нормировки: ', h('b', { text: `связь ${fmt(100 * pr[0], 0)} % · вода и еда ${fmt(100 * pr[1], 0)} % · сеть ${fmt(100 * pr[2], 0)} % · логистика ${fmt(100 * pr[3], 0)} %` }))); }
    body.append(h('div', { class: 'chips' }, h('span', { class: 'muted small', text: 'Изменения: ' }), chChips(st.ch)));
    const gm = h('select', { class: 'btn small', 'aria-label': 'Цель' }, Object.keys(GOALS).map(k => h('option', { value: k, selected: st.goal.m === k }, GOALS[k].ru)));
    gm.addEventListener('change', () => { st.goal.m = gm.value; });
    const hz = h('select', { class: 'btn small', 'aria-label': 'Срок проверки' }, [1, 2, 3, 4, 6, 9, 12].map(n => h('option', { value: n, selected: st.goal.h === n }, 'через ' + months(n))));
    hz.addEventListener('change', () => { st.goal.h = +hz.value; });
    const ar = h('input', { type: 'checkbox', checked: st.autoRevert ? true : null }); ar.addEventListener('change', () => { st.autoRevert = ar.checked; });
    // цель можно измерять у получателя помощи
    const recips = []; ['aidT', 'aidF', 'aidFood', 'aidC', 'aidR'].forEach(k => { if (st.ch[k]) Object.keys(st.ch[k]).forEach(x => { if (st.ch[k][x] != null && !recips.includes(x)) recips.push(x); }); });
    if (!recips.includes(st.goal.iso)) st.goal.iso = recips.length && !st.goal.isoSet ? recips[0] : null;
    const gi = recips.length ? h('select', { class: 'btn small', 'aria-label': 'У кого измерять' }, h('option', { value: '', selected: !st.goal.iso }, 'у ' + cname(iso)), recips.map(x => h('option', { value: x, selected: st.goal.iso === x }, 'у ' + cname(x)))) : null;
    if (gi) gi.addEventListener('change', () => { st.goal.iso = gi.value || null; st.goal.isoSet = true; });
    body.append(h('div', { class: 'goal' }, h('span', { text: 'Что должно улучшиться: ' }), gm, gi, hz, h('label', { class: 'small' }, ar, ' откатить, если не подтвердится')),
      h('p', { class: 'muted small', style: 'margin:2px 0 8px', text: 'Связь и вода отзываются за месяц-два, сеть — за полгода, потери накапливаются. Для целей по сети берите срок от шести месяцев.' }));
    const note = h('textarea', { class: 'inp', rows: 2, placeholder: 'Зачем это нужно (необязательно)', maxlength: 600 }, st.note); note.addEventListener('input', () => { st.note = note.value; });
    body.append(note);
    const pv = h('div', { class: 'preview' });
    body.append(h('div', { class: 'row-btns' }, h('button', { class: 'btn small', onclick: async e => {
      if (chEmpty(st.ch)) { toast('Сначала что-нибудь измените.'); return; }
      e.target.disabled = true; pv.innerHTML = ''; pv.append(h('div', { class: 'muted small', text: 'Считаю прогноз…' }));
      try { const P = await project({ [iso]: st.ch }, Math.max(st.goal.h, 2), { onProgress: (y, t) => { pv.firstChild.textContent = 'Считаю прогноз: ' + tLabel(y) + '…'; } }); pv.innerHTML = ''; pv.append(projTable(P, iso, Object.keys(st.ch).some(k => LEV[k].kind === 'iso' || k === 'exportT'))); if (st.goal.iso) pv.append(projTable(P, st.goal.iso)); }
      catch (err) { console.error(err); pv.innerHTML = ''; pv.append(h('div', { class: 'bad small', text: 'Не получилось посчитать: ' + (err.message || err) })); }
      finally { e.target.disabled = false; }
    } }, 'Прогноз: что будет с решением и без'), pv));
  };
  draw();
  const send = async merge => {
    if (chEmpty(st.ch)) { toast('Сначала что-нибудь измените.'); return; }
    const p = await createPatch(iso, st.ch, st.goal, st.title || autoTitle(st.ch), st.note, st.site, st.autoRevert);
    if (!p) return;
    if (merge) await mergePatch(p.pid);
    else toast('Патч отправлен на рассмотрение.');
    closeDialog(); scheduleRender();
  };
  openDialog((mine ? 'Решение: ' : 'Патч для страны: ') + cname(iso), body, [
    h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'),
    h('button', { class: 'btn', onclick: () => send(false), disabled: !canAct() ? true : null }, mine ? 'Сохранить как предложение' : 'Предложить'),
    mine ? h('button', { class: 'btn primary', onclick: () => send(true) }, 'Принять и применить') : null], true);
}
function autoTitle(ch) { const ks = Object.keys(ch); return ks.slice(0, 2).map(k => LEV[k] ? LEV[k].ru : k).join(', ') + (ks.length > 2 ? ' и др.' : ''); }
function patchCard(p, o) {
  o = o || {};
  const mineC = isMine(p.iso), res = p.res;
  return h('div', { class: 'patch' },
    h('div', { class: 'patch-h' }, h('b', { text: p.title }), pill(statusRu(p.status), statusCls(p.status)), o.compact ? null : h('button', { class: 'lnk', onclick: () => { setView('map'); select('C:' + p.iso); } }, cname(p.iso)),
      h('span', { class: 'muted small', text: nameOf(p.author) + ' · ' + (p.year != null ? 'принят: ' + tLabel(p.year) : 'создан: ' + tLabel(p.created)) })),
    h('div', { class: 'patch-ch' }, chChips(p.ch)),
    p.note ? h('div', { class: 'patch-note', text: p.note }) : null,
    h('div', { class: 'patch-f' }, h('span', { text: 'Цель: ' + goalRu(p.goal) + ', проверка через ' + months(p.goal.h) + (p.due != null && p.status === 'merged' ? ` (в конце: ${tLabel(p.due)})` : '') }),
      p.site ? h('button', { class: 'lnk small', onclick: () => select(p.site) }, 'площадка: ' + placeInfo(p.site).name) : null,
      res && res.res === 'stale' ? h('span', { class: 'muted', text: 'Проверить не успели: слишком много месяцев прошло' }) : null,
      res && res.res !== 'stale' ? h('span', { class: res.res === 'pass' ? 'good' : res.res === 'fail' ? 'bad' : 'muted', text: `Итог: ${sgn(res.d, 2)} ${goalUnit(p.goal)} против «тени»` + (res.res === 'neutral' ? ' — разницы нет' : '') }) : null,
      p.status === 'open' && mineC && canAct() ? h('button', { class: 'btn small primary', onclick: () => mergePatch(p.pid) }, 'Принять') : null,
      p.status === 'open' && (mineC || p.author === ACT.id) && canAct() ? h('button', { class: 'btn small ghost', onclick: () => rejectPatch(p.pid) }, p.author === ACT.id && !mineC ? 'Отозвать' : 'Отклонить') : null));
}
// ════════════════════════ страницы
function renderPatches() {
  const el = $('#patchesPage'); el.innerHTML = '';
  el.append(h('h1', { text: 'Патчи' }), h('p', { class: 'muted', text: 'Как в разработке Linux: любой игрок предлагает изменение решений страны (патч) с целью и сроком проверки; принимает тот, кто управляет страной. Когда срок выходит, мир сравнивают с его «тенью» — тем же миром, где затронутые решения остались прежними. Хуже — патч откатывается (если автор не отключил откат); разницы нет — патч остаётся, но в зачёт не идёт.' }));
  const F = [['open', 'На рассмотрении'], ['merged', 'Действуют'], ['done', 'Проверены'], ['all', 'Все']];
  el.append(h('div', { class: 'seg', style: 'display:inline-flex;margin-bottom:10px' }, F.map(([k, t]) => h('button', { class: UI.patchFilter === k ? 'on' : '', onclick: () => { UI.patchFilter = k; renderPatches(); } }, t))));
  let list = Object.values(M.c.patch).filter(Boolean);
  if (UI.patchFilter === 'open') list = list.filter(p => p.status === 'open');
  if (UI.patchFilter === 'merged') list = list.filter(p => p.status === 'merged');
  if (UI.patchFilter === 'done') list = list.filter(p => ['kept', 'failed', 'reverted', 'neutral', 'stale'].includes(p.status));
  list.sort((a, b) => b.t - a.t);
  if (!list.length) el.append(h('div', { class: 'muted', text: 'Здесь пока пусто.' }));
  const tr = {}; Object.values(M.c.patch).forEach(p => { if (!p || !p.res || p.res.res === 'stale') return; const t = tr[p.author] = tr[p.author] || { ok: 0, n: 0 }; t.n++; if (p.res.res === 'pass') t.ok++; });
  const trust = Object.keys(tr).map(id => [id, tr[id]]).sort((a, b) => b[1].ok / b[1].n - a[1].ok / a[1].n);
  if (trust.length) el.append(h('div', { class: 'small muted', style: 'margin-bottom:8px' }, 'Доля подтвердившихся патчей: ', trust.slice(0, 8).map(([id, t]) => h('span', { class: 'pill', style: 'margin-right:4px', text: nameOf(id) + ' ' + t.ok + '/' + t.n }))));
  el.append(h('div', { class: 'grid1' }, list.slice(0, 200).map(p => patchCard(p))));
}
function renderWorld() {
  const el = $('#worldPage'), Y = curYear(); el.innerHTML = '';
  const s = M.sum[Y]; if (!s) { el.append(h('div', { class: 'muted', text: 'Загружаю…' })); loadSum(Y).then(() => scheduleRender()); return; }
  const w = s.w, g = game(), ph = (g && g.ph) || {};
  el.append(h('h1', { text: tLabel(Y) + (Y ? ' — месяц ' + Y + ' после бури' : ' — месяц бури') }));
  // цель и фазы
  const done = WORLD.PHASES.filter(p => ph[p.k] != null).length;
  el.append(h('div', { class: 'panel goalbox' }, h('h3', { style: 'margin-top:0', text: 'Цель: вернуть миру связь, снабжение и свет' }),
    h('p', { class: 'small', style: 'margin:0 0 8px', text: `Пять фаз, каждая — порог по населению мира. Пройдено ${done} из 5. Счёт мира — люди без снабжения: ${fmt(w.pm, 0)} млн человеко-месяцев, потери сверх обычного ${fmtK(w.losses)} (грубая оценка). ${Y >= GAME_MONTHS ? 'Пять лет прошло — можно подводить итоги, но игра продолжается.' : 'До конца пятого года: ' + months(GAME_MONTHS - Y) + '.'}` }),
    h('div', { class: 'phases' }, WORLD.PHASES.map(p => { const v = w[p.k], hit = ph[p.k]; return h('div', { class: 'phase' + (hit != null ? ' done' : '') }, h('div', { class: 'ph-t' }, h('b', { text: p.ru }), h('span', { class: 'muted small', text: ' цель ' + fmt(100 * p.goal, 0) + ' %' })), h('div', { class: 'ph-bar' }, h('i', { style: `width:${(100 * Math.min(1, v / p.goal)).toFixed(0)}%` })), h('div', { class: 'small', text: fmt(100 * v, 0) + ' % · ' + (hit != null ? 'достигнута: ' + tLabel(hit) : p.hint) })); }))));
  el.append(h('div', { class: 'aibox' }, h('div', null, h('b', { text: 'ИИ-мир' }), ' — ', g && g.ai === false ? 'выключен: страны без игроков держат прежний курс.' : SAMPLE && M.aiOk !== false ? 'Claude раз в месяц решает за 18 стран без игроков, где хуже всего: приоритеты, нормирование, экспорт заводов, помощь — и пишет новости. Платит за вызов тот, кто нажал «Следующий месяц».' : 'недоступен в этом просмотре: страны без игроков держат прежний курс.'),
    canAct() && (SAMPLE || (g && g.ai === false)) ? h('button', { class: 'btn small', onclick: () => setAI(g && g.ai === false) }, g && g.ai === false ? 'Включить' : 'Выключить') : null));
  // мир по месяцам
  const box = h('div', { class: 'grid2' }); el.append(box);
  const c1 = h('div', { class: 'panel' }, h('h3', { style: 'margin-top:0', text: 'Мир по месяцам, % населения' })), c2 = h('div', { class: 'panel' }, h('h3', { style: 'margin-top:0', text: 'Трансформаторы: выпуск в мире, шт./мес.' }));
  box.append(c1, c2);
  (async () => {
    const ys = []; for (let y = Math.max(BASE, Y - 36); y <= Y; y++) ys.push(y); await Promise.all(ys.map(y => loadSum(y)));
    const P = MAP.pal, ser = k => ys.filter(y => M.sum[y]).map(y => [y, 100 * M.sum[y].w[k]]);
    c1.append(lineChart([{ pts: ser('served'), color: P.good }, { pts: ser('grid'), color: P.glow }, { pts: ser('comms'), color: P.accent, dash: true }, { pts: ser('logi'), color: P.muted, dash: true }], { w: 460, h: 200, y0: 0, y1: 100, fy: x => fmt(x, 0), fx: x => WORLD.labelShort(x), label: 'Мир по месяцам' }), legendRow([[P.good, 'снабжение'], [P.glow, 'свет'], [P.accent, 'связь', true], [P.muted, 'логистика', true]]));
    c2.append(lineChart([{ pts: ys.filter(y => M.sum[y]).map(y => [y, M.sum[y].w.prod]), color: P.glow }], { w: 460, h: 200, fy: x => fmt(x, 0), fx: x => WORLD.labelShort(x), label: 'Выпуск трансформаторов' }), h('p', { class: 'muted small', text: 'Заводам нужен свет и подвоз; мобилизация утраивает выпуск к полутора годам. Спутников на орбите: ' + pct(w.S) + ' от прежнего.' }));
  })();
  // где хуже всего
  const pi = s.k.indexOf('P'), si = s.k.indexOf('served'), gi = s.k.indexOf('grid'), ci = s.k.indexOf('comms'), fi = s.k.indexOf('fuel'), hi = s.k.indexOf('hungry'), li = s.k.indexOf('losses');
  const worst = ISO.slice().sort((a, b) => s.c[IDX[b]][pi] * (1 - s.c[IDX[b]][si]) - s.c[IDX[a]][pi] * (1 - s.c[IDX[a]][si])).slice(0, 20);
  el.append(h('h2', { text: 'Где хуже всего' }), h('p', { class: 'muted small', text: 'Страны, где больше всего людей без воды и еды. Здесь помощь возвращает больше всего.' }), h('div', { class: 'tblwrap' }, h('table', { class: 'tbl' },
    h('thead', null, h('tr', null, ['Страна', 'Без снабжения, млн', 'Снабжение', 'Свет', 'Связь', 'Топливо', 'Без еды', 'Потери', 'Кто'].map((t, i) => h('th', { class: i ? 'r' : '', text: t })))),
    h('tbody', null, worst.map(iso => { const r = s.c[IDX[iso]], o = ownerOf(iso), q = M.c.req[iso]; return h('tr', { class: o ? 'hl' : '' }, h('td', null, h('button', { class: 'lnk', onclick: () => select('C:' + iso) }, cname(iso)), q && q.open ? pill('просит помощи', 'warn') : null), h('td', { class: 'r', text: fmt(r[pi] * (1 - r[si]), 1) }), h('td', { class: 'r ' + (r[si] < 0.7 ? 'bad' : ''), text: pct(r[si]) }), h('td', { class: 'r', text: pct(r[gi]) }), h('td', { class: 'r', text: pct(r[ci]) }), h('td', { class: 'r ' + (r[fi] < 0.5 ? 'bad' : ''), text: fmt(r[fi], 1) + ' мес.' }), h('td', { class: 'r', text: pct(r[hi]) }), h('td', { class: 'r', text: fmtK(r[li]) }), h('td', { class: 'r', text: o ? nameOf(o) : 'ИИ' })); })))));
  // заводы
  const pr = s.k.indexOf('prod'), tsp = s.k.indexOf('Tsp'), tnew = s.k.indexOf('Tnew');
  const facts = ISO.filter(iso => WORLD.isFactory(iso)).sort((a, b) => WORLD.factShare(b) - WORLD.factShare(a));
  el.append(h('h2', { text: 'Заводы трансформаторов' }), h('p', { class: 'muted small', text: 'Узкое место всего восстановления. Экспортная часть выпуска уходит туда, где одна единица возвращает свет большему числу людей — но только в страны со связью и логистикой не ниже 25 %.' }), h('div', { class: 'tblwrap' }, h('table', { class: 'tbl' },
    h('thead', null, h('tr', null, ['Страна', 'Доля мира', 'Свет', 'Выпуск, шт./мес.', 'На экспорт', 'Своих нужно', 'Кто'].map((t, i) => h('th', { class: i ? 'r' : '', text: t })))),
    h('tbody', null, facts.map(iso => { const r = s.c[IDX[iso]], o = ownerOf(iso), pol = o ? polOf(iso) : ((M.dec[Y] && M.dec[Y].pol[iso]) || {}); return h('tr', { class: o ? 'hl' : '' }, h('td', null, h('button', { class: 'lnk', onclick: () => select('C:' + iso) }, cname(iso))), h('td', { class: 'r', text: pct(WORLD.factShare(iso)) }), h('td', { class: 'r', text: pct(r[gi]) }), h('td', { class: 'r', text: fmt(r[pr], 1) }), h('td', { class: 'r', text: pct(pol.exportT != null ? pol.exportT : LEV.exportT.def) }), h('td', { class: 'r', text: fmt(r[tnew], 0) }), h('td', { class: 'r', text: o ? nameOf(o) : 'ИИ' })); })))));
  // заявки
  const reqs = Object.values(M.c.req).filter(q => q && q.open).sort((a, b) => b.t - a.t);
  el.append(h('h2', { text: 'Заявки о помощи' }));
  if (!reqs.length) el.append(h('div', { class: 'muted', text: 'Открытых заявок нет. Заявку подаёт тот, кто управляет страной: карточка страны → «Помощь».' }));
  reqs.forEach(q => el.append(h('div', { class: 'prow' }, h('button', { class: 'lnk', onclick: () => select('C:' + q.iso) }, cname(q.iso)), h('span', { class: 'muted small', text: tLabel(q.y) + ' · ' + nameOf(q.by) }), h('span', { text: q.text || 'нужна помощь' }))));
  // новости
  el.append(h('h2', { text: 'Новости' }));
  const nb = h('div'); el.append(nb);
  Promise.all([Y, Y - 1, Y - 2].filter(y => y > BASE).map(y => loadNews(y).then(n => [y, n]))).then(arr => {
    let any = false;
    arr.forEach(([y, n]) => { if (!n.items.length) return; any = true; nb.append(h('h3', { text: tLabel(y) }), n.items.map(newsItem)); });
    if (!any) nb.append(h('div', { class: 'muted', text: 'Новости появятся после первого хода.' }));
  });
  // хроника
  el.append(h('h2', { text: 'Хроника игроков' }));
  const lb = h('div'); el.append(lb);
  (async () => {
    const ent = [], now = Date.now();
    for (const y of [Y, Y - 1]) {
      if (y < BASE) continue;
      const stale = !M.c.log2[y] || (B.remote && now - (UI.logAt || 0) > 20000);
      if (stale) { M.c.log2[y] = (await B.get('log2/' + y)) || {}; UI.logAt = now; }
      for (const id in M.c.log2[y]) ent.push(Object.assign({ y }, M.c.log2[y][id]));
    }
    ent.sort((a, b) => b.ts - a.ts);
    if (!ent.length) lb.append(h('div', { class: 'muted', text: 'Пока тихо.' }));
    ent.slice(0, 60).forEach(e => lb.append(h('div', { class: 'logline' }, h('span', { class: 'muted mono', text: WORLD.labelShort(e.y) + ' ' }), logText(e))));
  })();
  if (canAct() && (M.me.isOwner || !B.remote)) el.append(h('div', { class: 'row-btns', style: 'margin-top:24px' }, h('button', { class: 'btn small danger', onclick: () => askConfirm('Начать заново?', 'Мир будет удалён для всех игроков и создан заново: снова октябрь 2026.', 'Начать заново', resetWorld, true) }, 'Начать мир заново')));
}
function logText(e) {
  const who = nameOf(e.by), p = e.pid && M.c.patch[e.pid];
  switch (e.t) {
    case 'world': return 'Мир создан: буря.';
    case 'year': return `${who} посчитал(а) месяц.`;
    case 'claim': return `${who} взял(а) управление: ${cname(e.iso)}.`;
    case 'release': return `${who} отдал(а) ИИ: ${cname(e.iso)}.`;
    case 'patch': return `${who} предложил(а) патч «${p ? p.title : '…'}» для страны ${cname(e.iso)}.`;
    case 'merge': return `${who} принял(а) патч «${p ? p.title : '…'}» (${cname(e.iso)}).`;
    case 'reject': return `${who} отклонил(а) патч «${p ? p.title : '…'}».`;
    case 'check': return `Проверка патча «${p ? p.title : '…'}» (${cname(e.iso)}): ${statusRu(e.status || (e.ok ? 'kept' : 'failed'))}${e.status === 'reverted' ? ' (решение снято)' : ''}.`;
    case 'req': return `${cname(e.iso)} просит помощи.`;
    case 'unreq': return `${cname(e.iso)} сняла заявку о помощи.`;
    case 'fork': return `${who} опубликовал(а) форк «${e.name || ''}».`;
    default: return e.t;
  }
}
// ════════════════════════ форки: свой вариант мира на месяцы вперёд
const FORK_PRESETS = [
  { id: 'comms', name: 'Связь прежде всего', hint: 'все страны: связь 50 %, вода 30 %, нормирование 80 %', mk: () => { const o = {}; ISO.forEach(iso => { o[iso] = { prC: 0.5, prW: 0.3, prG: 0.1, prL: 0.1, ration: 0.8 }; }); return o; } },
  { id: 'fact', name: 'Заводы — первыми', hint: 'страны с заводами: сеть 50 %, экспорт 70 %; остальные — связь и вода', mk: () => { const o = {}; ISO.forEach(iso => { o[iso] = WORLD.isFactory(iso) ? { prC: 0.2, prW: 0.2, prG: 0.5, prL: 0.1, ration: 0.7, exportT: 0.7 } : { prC: 0.4, prW: 0.4, prG: 0.1, prL: 0.1, ration: 0.7 }; }); return o; } },
  { id: 'self', name: 'Каждый за себя', hint: 'экспорт 0 %, нормирования почти нет, сеть 50 %', mk: () => { const o = {}; ISO.forEach(iso => { o[iso] = { prC: 0.1, prW: 0.3, prG: 0.5, prL: 0.1, ration: 0.2, exportT: 0 }; }); return o; } }
];
function renderForks() {
  const el = $('#forksPage'); el.innerHTML = '';
  el.append(h('h1', { text: 'Форки' }), h('p', { class: 'muted', text: 'Сколько игроков — столько вариантов будущего. Форк — ваш сценарий: задайте решения любым странам (или всем сразу заготовкой) и посмотрите, куда придёт мир через 6–36 месяцев по сравнению с базовым путём, где все держат нынешний курс. Форк можно опубликовать — его увидят остальные.' }));
  const F = UI.fork = UI.fork || { name: '', pol: {}, cur: null, hz: 12, calm: false, preset: null, res: null };
  const ed = h('div', { class: 'panel' });
  el.append(ed);
  const drawEd = () => {
    ed.innerHTML = '';
    ed.append(h('div', { class: 'row-btns' }, h('b', { text: 'Заготовки: ' }),
      FORK_PRESETS.map(pr => h('button', { class: 'btn small' + (F.preset === pr.id ? ' primary' : ''), title: pr.hint, onclick: () => { F.preset = pr.id; F.pol = pr.mk(); F.cur = null; F.name = F.name || pr.name; drawEd(); } }, pr.name)),
      h('button', { class: 'btn small ghost', onclick: () => { UI.fork = null; renderForks(); } }, 'Очистить')));
    if (F.preset) ed.append(h('p', { class: 'small', text: FORK_PRESETS.find(p => p.id === F.preset).hint + ' — заготовка задаёт политику всем странам; поверх неё можно править отдельные.' }));
    const name = h('input', { class: 'inp', placeholder: 'Название форка', value: F.name, maxlength: 80 }); name.addEventListener('input', () => { F.name = name.value; });
    ed.append(name);
    const pick = h('select', { class: 'btn small', 'aria-label': 'Страна' }, h('option', { value: '' }, 'править страну…'), ISO.slice().sort((a, b) => cname(a).localeCompare(cname(b), 'ru')).map(x => h('option', { value: x }, cname(x))));
    pick.addEventListener('change', () => { if (!pick.value) return; F.pol[pick.value] = F.pol[pick.value] || {}; F.cur = pick.value; drawEd(); });
    const edited = F.preset ? Object.keys(F.touched || {}).concat(F.cur && !(F.touched || {})[F.cur] ? [F.cur] : []) : Object.keys(F.pol);
    ed.append(h('div', { class: 'chips' }, edited.slice(0, 30).map(x => h('button', { class: 'pill' + (F.cur === x ? ' acc' : ''), onclick: () => { F.cur = x; drawEd(); } }, cname(x) + (chEmpty(F.pol[x]) ? '' : ' •'))), F.preset && Object.keys(F.pol).length > 30 ? h('span', { class: 'muted small', text: `все ${Object.keys(F.pol).length} стран` }) : null, pick));
    if (F.cur) {
      const st = { ch: F.pol[F.cur] }; F.grp = F.grp || 'Приоритеты';
      const base = ctrlOf(F.cur) ? polOf(F.cur) : ((M.dec[curYear()] && M.dec[curYear()].pol[F.cur]) || {});
      ed.append(h('div', { class: 'gtabs' }, LEVGROUPS.map(g => h('button', { class: 'ctab' + (F.grp === g.ru ? ' on' : ''), onclick: () => { F.grp = g.ru; drawEd(); } }, g.ru))));
      LEVGROUPS.find(g => g.ru === F.grp).ks.forEach(k => { if (k === 'exportT' && !WORLD.isFactory(F.cur)) return; ed.append(leverEditor(LEV[k], st, base, F.cur, () => { F.touched = F.touched || {}; F.touched[F.cur] = 1; drawEd(); })); });
      ed.append(h('div', { class: 'chips' }, h('span', { class: 'muted small', text: cname(F.cur) + ': ' }), chChips(F.pol[F.cur]), h('button', { class: 'lnk small', onclick: () => { delete F.pol[F.cur]; F.cur = null; drawEd(); } }, 'убрать страну')));
    }
    const hz = h('select', { class: 'btn small', 'aria-label': 'Горизонт' }, [6, 12, 24, 36].map(n => h('option', { value: n, selected: F.hz === n }, 'на ' + months(n))));
    hz.addEventListener('change', () => { F.hz = +hz.value; });
    const calm = h('input', { type: 'checkbox', checked: F.calm ? true : null }); calm.addEventListener('change', () => { F.calm = calm.checked; });
    const out = h('div', { class: 'forkres' });
    ed.append(h('div', { class: 'row-btns' }, hz, h('label', { class: 'small' }, calm, ' без второй бури и зимы'),
      h('button', { class: 'btn primary', onclick: async e => { e.target.disabled = true; UI.forkBusy = true; try { await runForkUI(F, out); } finally { e.target.disabled = false; UI.forkBusy = false; renderForks(); } } }, 'Посчитать форк'),
      F.res && canAct() ? h('button', { class: 'btn', onclick: () => saveFork(F) }, 'Опубликовать') : null), out);
    if (F.res) drawForkRes(F, out);
  };
  drawEd();
  const saved = Object.values(M.c.fork).filter(Boolean).sort((a, b) => b.t - a.t);
  el.append(h('h2', { text: 'Опубликованные форки' }));
  if (!saved.length) el.append(h('div', { class: 'muted', text: 'Пока никто не публиковал.' }));
  saved.slice(0, 50).forEach(f => el.append(h('div', { class: 'patch' }, h('div', { class: 'patch-h' }, h('b', { text: f.name || 'Без названия' }), h('span', { class: 'muted small', text: nameOf(f.author) + ' · от ' + tLabel(f.base) + ' на ' + months(f.hz) })),
    h('div', { class: 'patch-ch' }, f.preset ? pill((FORK_PRESETS.find(p => p.id === f.preset) || {}).name || f.preset, 'acc') : null, Object.keys(f.pol || {}).slice(0, 8).map(x => pill(cname(x) + ': ' + Object.keys(f.pol[x]).map(k => LEV[k] ? LEV[k].ru : k).join(', '), 'acc')), Object.keys(f.pol || {}).length > 8 ? pill('ещё ' + (Object.keys(f.pol).length - 8) + ' стран') : null),
    f.sum ? h('div', { class: 'small' }, 'Мир к ' + tLabel(f.base + f.hz) + ': снабжение ', h('b', { class: f.sum.served >= 0 ? 'good' : 'bad', text: sgn(100 * f.sum.served, 1) + ' п.п.' }), ', свет ', h('b', { class: f.sum.grid >= 0 ? 'good' : 'bad', text: sgn(100 * f.sum.grid, 1) + ' п.п.' }), ', потери ', h('b', { class: f.sum.losses <= 0 ? 'good' : 'bad', text: sgn(f.sum.losses / 1000, 2) + ' млн' }), ' к базовому пути') : null,
    h('div', { class: 'patch-f' }, h('button', { class: 'btn small', onclick: () => { const pr = f.preset && FORK_PRESETS.find(p => p.id === f.preset); const pol = pr ? Object.assign(pr.mk(), clone(f.pol || {})) : clone(f.pol || {}); const touched = {}; Object.keys(f.pol || {}).forEach(x => { touched[x] = 1; }); UI.fork = { name: f.name, pol, cur: null, hz: f.hz, calm: !!f.calm, preset: f.preset || null, res: null, touched }; renderForks(); window.scrollTo(0, 0); } }, 'Открыть и пересчитать')))));
}
async function runForkUI(F, out) {
  out.innerHTML = ''; const msg = h('div', { class: 'muted small', text: 'Считаю…' }); out.append(msg);
  try {
    const P = await project(clone(F.pol), F.hz, { calm: F.calm, onProgress: (y, t) => { msg.textContent = 'Считаю: ' + tLabel(y) + '…'; } });
    F.res = P; drawForkRes(F, out);
  } catch (e) { console.error(e); out.innerHTML = ''; out.append(h('div', { class: 'bad', text: 'Не получилось: ' + (e.message || e) })); }
}
function forkDelta(P) { const a = WORLD.world(P.A[P.A.length - 1]), b = WORLD.world(P.B[P.B.length - 1]); return { served: b.served - a.served, grid: b.grid - a.grid, comms: b.comms - a.comms, losses: b.losses - a.losses, pm: b.pm - a.pm }; }
function drawForkRes(F, out) {
  const P = F.res; if (!P) return; out.innerHTML = '';
  const pal = MAP.pal, ts = P.A.map(s => s.t);
  const ser = (arr, k) => ts.map((t, i) => [t, 100 * WORLD.world(arr[i])[k]]);
  const d = forkDelta(P);
  out.append(h('h3', { text: 'Мир: форк против базового пути' }),
    lineChart([{ pts: ser(P.A, 'served'), color: pal.muted, dash: true }, { pts: ser(P.B, 'served'), color: pal.good }, { pts: ser(P.A, 'grid'), color: pal.muted, dash: true }, { pts: ser(P.B, 'grid'), color: pal.glow }], { w: 760, h: 240, y0: 0, y1: 100, fy: x => fmt(x, 0), fx: x => WORLD.labelShort(x), label: 'Снабжение и свет: форк и базовый путь' }),
    legendRow([[pal.good, 'снабжение, форк'], [pal.glow, 'свет, форк'], [pal.muted, 'базовый путь', true]]),
    h('div', { class: 'small' }, 'К ' + tLabel(ts[ts.length - 1]) + ': снабжение ', h('b', { class: d.served >= 0 ? 'good' : 'bad', text: sgn(100 * d.served, 1) + ' п.п.' }), ', свет ', h('b', { class: d.grid >= 0 ? 'good' : 'bad', text: sgn(100 * d.grid, 1) + ' п.п.' }), ', связь ', h('b', { class: d.comms >= 0 ? 'good' : 'bad', text: sgn(100 * d.comms, 1) + ' п.п.' }), ', потери ', h('b', { class: d.losses <= 0 ? 'good' : 'bad', text: sgn(d.losses / 1000, 2) + ' млн' }), ' к базовому пути.'));
  const focus = Object.keys(F.pol).length && Object.keys(F.pol).length <= 8 ? Object.keys(F.pol) : ['USA', 'CHN', 'IND', 'DEU', 'BRA', 'NGA', 'RUS', 'EGY'];
  out.append(h('div', { class: 'tblwrap' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, ['Страна', 'Снабжение', 'Свет', 'Связь', 'Без еды', 'Потери, тыс.'].map((t, i) => h('th', { class: i ? 'r' : '', text: t })))),
    h('tbody', null, focus.map(iso => { const r = projRows(P, iso); const c = (i, dd) => { const v = r[i][1], cls = v * r[i][3] > 0.005 ? 'good' : v * r[i][3] < -0.005 ? 'bad' : ''; return h('td', { class: 'r ' + cls, text: sgn(v, dd) }); };
      return h('tr', null, h('td', null, h('button', { class: 'lnk', onclick: () => select('C:' + iso) }, cname(iso))), c(0, 1), c(1, 1), c(2, 1), c(4, 1), c(6, 0)); })))),
    h('p', { class: 'muted small', text: 'Разница «форк − базовый путь» к концу горизонта, в п.п. (потери — в тысячах человек).' }));
}
async function saveFork(F) {
  if (!F.res || !canAct()) return;
  const id = 'f' + rid(8), d = forkDelta(F.res);
  const pol = {}; Object.keys(F.pol).forEach(iso => { if (!chEmpty(F.pol[iso])) pol[iso] = F.pol[iso]; });
  const doc = { id, author: ACT.id, t: Date.now(), name: String(F.name || 'Форк').slice(0, 80), base: F.res.Y, hz: F.hz, calm: !!F.calm, preset: F.preset || null, pol: F.preset ? {} : clone(pol), sum: { served: +d.served.toFixed(4), grid: +d.grid.toFixed(4), losses: +d.losses.toFixed(1) } };
  if (F.preset) { const touched = F.touched || {}; Object.keys(touched).forEach(iso => { if (pol[iso]) doc.pol[iso] = clone(pol[iso]); }); }
  try { await B.set('fork/' + id, doc); await logAdd({ t: 'fork', name: doc.name }); toast('Форк опубликован.'); scheduleRender(); } catch (e) { failWrite(e, 'Не получилось опубликовать'); }
}
