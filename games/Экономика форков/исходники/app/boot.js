// ════════════════════════ запуск
let logUnsub = null;
async function onYearChanged(fresh) {
  const y = curYear();
  try { await loadYear(y, !!fresh); if (y > YEAR0) await loadYear(y - 1, !!fresh, 'HL'); } catch (e) { console.warn('год', e); }
  if (B.remote) {
    if (logUnsub) logUnsub();
    logUnsub = DB.doc('log/' + y).onSnapshot(s => { M.c.log[y] = s.exists ? s.data() : {}; scheduleRender(); }, err => console.warn('хроника', err));
    for (let yy = y - 1; yy >= Math.max(YEAR0, y - 3); yy--) if (!M.c.log[yy]) B.get('log/' + yy).then(d => { if (d) { M.c.log[yy] = d; scheduleRender(); } }).catch(() => {});
    if (y > YEAR0) loadYear(y - 1, false, 'C').then(() => scheduleRender()).catch(() => {});
  }
  M.ready = true; renderAll(); requestDraw();
}
// мир начали заново — всё закэшированное от прежнего мира выбрасывается
function worldChanged() {
  M.Y = {}; M.c.log = {}; loadingYears.clear(); UI.sel = null;
}
async function startLocal() {
  B.remote = false; M.remote = false;
  const saved = lsGet(LOCAL_KEY);
  if (saved) { try { const o = JSON.parse(saved); for (const k in M.c) if (o[k]) M.c[k] = o[k]; } catch (e) { console.warn('сохранение', e); } }
  M.me = { id: null, isOwner: true, canWrite: true };
  const localIds = Object.keys(M.c.players).filter(id => id.startsWith('local:'));
  if (!localIds.length) { const id = 'local:1'; M.c.players[id] = { nick: 'Игрок 1', host: 'local', seen: Date.now() }; localIds.push(id); }
  const want = lsGet('ef-actor'); ACT.id = want && M.c.players[want] ? want : localIds[0];
  if (!game()) await createWorld(ACT.id);
  saveLocal();
  await onYearChanged();
}
async function startRemote() {
  B.remote = true; M.remote = true; M.mode = 'db';
  let me = null, canW = null;
  if (USER) { try { me = await USER.me(); canW = await USER.can('data.write'); } catch (e) { } }
  M.me.id = me && me.id ? me.id : null; M.me.isOwner = !!(me && me.isOwner); M.me.canWrite = canW === false ? false : true;
  if (!M.me.id) { let a = lsGet('ef-anon'); if (!a) { a = 'anon:' + rid(8); lsSet('ef-anon', a); } M.me.id = a; }
  let want = lsGet('ef-actor'); ACT.id = M.me.id;
  const err = e => { console.warn('база', e); if (e && e.code === 'revoked') { M.me.canWrite = false; renderTop(); } };
  let first = true, worldId = null;
  DB.doc('game/state').onSnapshot(async s => {
    const d = s.exists ? s.data() : null;
    const had = game() && game().year;
    M.c.game.state = d && d.year != null ? d : null;
    if (!M.c.game.state) {
      if (first && M.me.canWrite && !(s.metadata && s.metadata.fromCache)) { first = false; await ensureWorld(); }
      renderTop();
      return;
    }
    first = false;
    const id = d.seed + ':' + d.started;
    const changed = worldId !== null && worldId !== id; worldId = id;
    if (changed) { worldChanged(); await onYearChanged(true); }
    else if (M.c.game.state.year !== had) await onYearChanged(); else scheduleRender();
  }, err);
  DB.collection('places').onSnapshot(qs => { qs.docChanges().forEach(ch => { if (ch.type === 'removed') delete M.c.places[ch.doc.id]; else M.c.places[ch.doc.id] = ch.doc.data(); }); scheduleRender(); }, err);
  DB.collection('patches').orderBy('t', 'desc').limit(1000).onSnapshot(qs => { qs.docChanges().forEach(ch => { if (ch.type === 'removed') delete M.c.patches[ch.doc.id]; else M.c.patches[ch.doc.id] = ch.doc.data(); }); scheduleRender(); }, err);
  DB.doc('meta/series').onSnapshot(s => { M.c.meta.series = s.exists ? s.data() : { f: {}, p: {} }; if (UI.view === 'compare') scheduleRender(); }, err);
  DB.doc('meta/pstats').onSnapshot(s => { M.c.meta.pstats = s.exists ? s.data() : {}; scheduleRender(); }, err);
  DB.collection('players').onSnapshot(qs => {
    qs.docChanges().forEach(ch => { if (ch.type === 'removed') delete M.c.players[ch.doc.id]; else M.c.players[ch.doc.id] = ch.doc.data(); });
    if (want && M.c.players[want]) { if (want !== ACT.id && M.c.players[want].host === M.me.id) ACT.id = want; want = null; }
    scheduleRender();
  }, err);
  renderTop();
}
async function ensureWorld() {
  if (!(await B.lock('game/state', 8000))) return;
  const st = await B.get('game/state');
  if (st && st.year != null) return;
  try { await createWorld(ACT.id); } catch (e) { failWrite(e, 'Не получилось создать мир'); }
}
function welcome() {
  if (lsGet('ef-welcome') === '1') return;
  const body = h('div',
    h('p', { style: 'margin-top:0', text: `Весь мир — ${Object.keys(ECON).length} стран с настоящими стартовыми данными и больше 135 тысяч городов и сёл. У каждого места может быть свой управляющий и своё решение по каждому вопросу.` }),
    h('ol', { style: 'padding-left:20px;margin:8px 0' },
      h('li', { text: 'Нажмите на страну, город или село и возьмите его под управление.' }),
      h('li', { text: 'Примите чужой патч или напишите свой: что меняем, что должно улучшиться, когда проверить.' }),
      h('li', { text: 'Нажмите «Следующий год». Когда срок выйдет, место сравнят с его «тенью» без патча — не лучше, значит откат.' }),
      h('li', { text: 'Сравнивайте мир форков с «единым планом», где всем одно решение.' })),
    h('p', { class: 'muted', text: 'Модель игрушечная: она показывает механику решений, а не предсказывает экономику.' }));
  openDialog('Экономика форков', body, [h('button', { class: 'btn', onclick: () => { lsSet('ef-welcome', '1'); closeDialog(); setView('help'); } }, 'Подробные правила'), h('button', { class: 'btn primary', onclick: () => { lsSet('ef-welcome', '1'); closeDialog(); } }, 'Начать')]);
}
async function boot() {
  UI.bannerOff = lsGet('ef-banner') === '1';
  initMap(); initSearch();
  $$('.tab').forEach(t => t.addEventListener('click', () => setView(t.dataset.v)));
  $('#nextYear').addEventListener('click', advanceYear);
  $('#addVillage').addEventListener('click', startPick);
  const mq = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;
  if (mq && mq.addEventListener) mq.addEventListener('change', () => { readPalette(); renderAll(); requestDraw(); });
  renderTop();
  loadBlob().then(() => { ensure50(); requestDraw(); if (UI.view === 'help') renderHelp(); }).catch(e => { console.error(e); toast('Не удалось распаковать города и сёла: ' + e.message, 6000); });
  let db = null, user = null, dl = null;
  const cl = window.claude;
  if (cl && typeof cl.use === 'function') {
    try { [db, user, dl] = await Promise.all([cl.use('db').catch(() => null), cl.use('user').catch(() => null), cl.use('downloads').catch(() => null)]); } catch (e) { }
  }
  USER = user; DL = dl; DB = db;
  if (DL) $('.mapui.br').insertBefore(h('button', { class: 'btn small fab', title: 'Сохранить CSV для импорта в Google My Maps', onclick: exportCSV }, '⤓ Google My Maps'), $('#addVillage'));
  if (DB) await startRemote(); else await startLocal();
  const hot = window.claude && window.claude.hot;
  if (hot && typeof hot.snapshot === 'function') { try { hot.snapshot(() => ({ view: UI.view, sel: UI.sel, metric: UI.metric, world: UI.world })); } catch (e) { } }
  const saved = hot && hot.data;
  if (saved && saved.view) { UI.metric = saved.metric || UI.metric; UI.world = saved.world || UI.world; setView(saved.view); if (saved.sel) select(saved.sel); lsSet('ef-welcome', '1'); }
  welcome();
}
boot();
