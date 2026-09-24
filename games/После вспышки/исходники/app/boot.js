// ════════════════════════ запуск
async function onYearChanged(fresh) {
  const y = curYear();
  if (fresh) { M.sum = {}; M.news = {}; M.chk = {}; M.dec = {}; M.bad = {}; }
  if (MP.me.ready != null) setPresence({ ready: null, readyAt: null });
  clearTimeout(MP.syncT); MP.syncT = null;
  try { await Promise.all([loadSum(y), y > BASE ? loadSum(y - 1) : null, loadNews(y), loadChk(y), getDec(y)]); }
  catch (e) { console.warn('месяц', e); }
  finally { setStage(''); }
  if (!M.sum[y]) toast('Не получилось восстановить мир за ' + tLabel(y) + ' — не хватает записи решений.', 8000);
  M.yearOk = true; checkReady();
  renderAll(); requestDraw();
}
function checkReady() {
  if (M.ready || !M.yearOk || !game()) return;
  if (B.remote && !['ctrl', 'pol', 'patch', 'req'].every(k => M.seen[k])) return;
  M.ready = true; renderAll(); requestDraw();
}
async function fxChanged(y) {
  delete M.news[y]; delete M.chk[y];
  try { await Promise.all([loadNews(y), loadChk(y)]); } catch (e) { }
  scheduleRender();
}
function worldChanged() { M.sum = {}; M.news = {}; M.chk = {}; M.dec = {}; M.bad = {}; M.snaps = {}; M.st = null; M.stY = null; UI.sel = null; UI.fork = null; }
async function startLocal() {
  B.remote = false; M.remote = false;
  const saved = lsGet(LOCAL_KEY);
  if (saved) { try { const o = JSON.parse(saved); for (const k in o) M.c[k] = o[k]; } catch (e) { console.warn('сохранение', e); } }
  ['dec', 'news', 'chk', 'ai', 'log2', 'ctrl', 'pol', 'patch', 'fork', 'players', 'game', 'chat', 'req'].forEach(k => { M.c[k] = M.c[k] || {}; });
  M.me = { id: null, isOwner: true, canWrite: true, canKnown: true };
  ['ctrl', 'pol', 'patch', 'req'].forEach(k => { M.seen[k] = true; });
  const localIds = Object.keys(M.c.players).filter(id => id.startsWith('local:'));
  if (!localIds.length) { const id = 'local:1'; M.c.players[id] = { nick: 'Игрок 1', host: 'local', seen: Date.now() }; localIds.push(id); }
  const want = lsGet('pv3-actor'); ACT.id = want && M.c.players[want] ? want : localIds[0];
  if (!game() || game().v !== 3) await createWorld(ACT.id);
  saveLocal();
  await onYearChanged();
}
async function startRemote() {
  B.remote = true; M.remote = true;
  let me = null, canW = null;
  if (USER) { try { me = await USER.me(); canW = await USER.can('data.write'); } catch (e) { } }
  M.me.id = me && me.id ? me.id : null; M.me.isOwner = !!(me && me.isOwner);
  M.me.canKnown = canW === true || canW === false; M.me.canWrite = canW === false ? false : true;
  if (!M.me.id) { let a = lsGet('pv3-anon'); if (!a) { a = 'anon:' + rid(8); lsSet('pv3-anon', a); } M.me.id = a; }
  if (me && me.id) PROFILES[me.id] = me;
  ACT.id = M.me.id;
  const err = e => { console.warn('база', e); if (e && e.code === 'revoked') { M.me.canWrite = false; renderTop(); } };
  let first = true, worldId = null, fx = null, warned = false;
  DB.doc('game/state').onSnapshot(async s => {
    const d = s.exists ? s.data() : null;
    const had = game() && game().year;
    if (!d || d.year == null || d.v !== 3) {
      M.c.game.state = null;
      if (first && M.me.canWrite && !(s.metadata && s.metadata.fromCache)) { first = false; await ensureWorld(); }
      else if (d && d.v !== 3 && !M.me.canWrite) setStage('Мир переходит на новую версию — нужен игрок с правом записи.');
      renderTop(); return;
    }
    first = false;
    M.c.game.state = d;
    if (d.mv && d.mv !== WORLD.MODELV && !warned) { warned = true; toast('Мир считался другой версией модели — прошлые месяцы пересчитаются, цифры могут слегка измениться.', 8000); }
    const id = d.seed + ':' + d.started, changed = worldId !== null && worldId !== id; worldId = id;
    if (changed) { worldChanged(); fx = d.fx; await onYearChanged(true); }
    else if (d.year !== had) {
      fx = d.fx;
      const other = had != null && d.lastBy && d.lastBy !== ACT.id && !M.busy;
      await onYearChanged();
      if (other) toast(`${nameOf(d.lastBy)} посчитал(а) ${tLabel(d.year)}: ${worldLine(d.year)}` + myDigest(d.year), 9000);
    }
    else { if (d.fx !== fx && d.fx === d.year) { fx = d.fx; await fxChanged(d.year); } else fx = d.fx; scheduleRender(); }
  }, err);
  const coll = (name, q, seenKey) => (q || DB.collection(name)).onSnapshot(qs => {
    qs.docChanges().forEach(ch => {
      if (ch.type === 'removed') delete M.c[name][ch.doc.id]; else M.c[name][ch.doc.id] = ch.doc.data();
      try { noteChange(name, ch); } catch (e) { console.warn('уведомление', e); }
    });
    MP.primed[name] = true;
    if (name === 'players' && !MP.seatDone) {
      MP.seatDone = true;
      const want = lsGet('pv3-seat:' + M.me.id);
      if (want && want.startsWith(M.me.id + '~') && M.c.players[want]) { ACT.id = want; setPresence({ uid: want }); }
    }
    M.seen[seenKey || name] = true; checkReady(); scheduleRender(); requestDraw();
  }, err);
  coll('ctrl'); coll('pol'); coll('req');
  coll('patch', DB.collection('patch').orderBy('t', 'desc').limit(1000));
  coll('fork', DB.collection('fork').orderBy('t', 'desc').limit(200));
  coll('players', DB.collection('players').limit(1000));
  coll('chat', DB.collection('chat').orderBy('t', 'desc').limit(150));
  renderTop();
}
async function ensureWorld() {
  if (!(await B.lock('game/state', 30000))) return;
  const st = await B.get('game/state');
  if (st && st.year != null && st.v === 3) return;
  try { setStage('Создаю мир…'); await createWorld(ACT.id); }
  catch (e) { failWrite(e, 'Не получилось создать мир'); }
  finally { setStage(''); }
}
function welcome() {
  if (lsGet('pv3-welcome') === '1') return;
  const body = h('div',
    h('p', { style: 'margin-top:0', text: 'Первого октября 2026 года сверхбуря выжгла электросети планеты. Трансформаторы сгорели, спутники сошли с орбит, дальняя связь умолкла. Свет остался у больниц и узлов связи — от генераторов, пока есть топливо.' }),
    h('p', { text: `${ISO.length} стран с настоящими данными и больше 135 тысяч городов и сёл. Ваша задача — вместе с другими вернуть миру связь, дороги, воду, еду и свет. Пять фаз, пять лет, помесячно.` }),
    h('ol', { style: 'padding-left:20px;margin:8px 0' },
      h('li', { text: 'Возьмите страну на карте.' }),
      h('li', { text: 'Расставьте приоритеты: связь, вода и еда, сеть, логистика. Нормируйте топливо.' }),
      h('li', { text: 'Просите и посылайте помощь: трансформаторы, топливо, еду, бригады, радио. Без связи помощь не дойдёт.' }),
      h('li', { text: 'Нажмите «Следующий месяц». Решения оформляются как патчи и проверяются против «тени».' })),
    h('p', { class: 'muted', text: 'Игра играет худший случай, который специалисты считают маловероятным; где кончаются данные и начинаются допущения — на вкладке «Что известно».' }));
  openDialog('После вспышки', body, [h('button', { class: 'btn', onclick: () => { lsSet('pv3-welcome', '1'); closeDialog(); setView('help'); } }, 'Подробные правила'), h('button', { class: 'btn primary', onclick: () => { lsSet('pv3-welcome', '1'); closeDialog(); } }, 'Начать')]);
}
async function boot() {
  document.documentElement.dataset.theme = 'dark';   // мир без света — всегда ночь
  UI.bannerOff = lsGet('pv3-banner') === '1';
  initMap(); initSearch();
  $$('.tab').forEach(t => t.addEventListener('click', () => { setView(t.dataset.v); if (t.dataset.v === 'help') renderHelp(); }));
  $('#nextYear').addEventListener('click', onNextYear);
  renderTop();
  try { await loadWorld(); } catch (e) { console.error(e); toast('Не удалось распаковать данные мира: ' + e.message, 9000); return; }
  recolor();
  loadBlob().then(() => { ensure50(); requestDraw(); if (UI.sel) renderCard(); }).catch(e => { console.error(e); toast('Не удалось распаковать города и сёла: ' + e.message, 6000); });
  let db = null, user = null, dl = null, smp = null, room = null;
  const cl = window.claude;
  if (cl && typeof cl.use === 'function') {
    try { [db, user, dl, smp, room] = await Promise.all(['db', 'user', 'downloads', 'sample', 'room'].map(n => cl.use(n).catch(() => null))); } catch (e) { }
  }
  USER = user; DL = dl; DB = db; SAMPLE = smp;
  if (DL) $('.mapui.br').insertBefore(h('button', { class: 'btn small fab', title: 'Сохранить CSV для импорта в Google My Maps', onclick: exportCSV }, '⤓ Google My Maps'), $('.zoombtns'));
  if (DB) { await startRemote(); initRoom(room); touchSeen(); } else await startLocal();
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && M.ready) { renderTop(); syncCheck(); } });
  renderHelp();
  welcome();
}
boot();
