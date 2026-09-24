// ════════════════════════ вместе: присутствие (room), готовность к ходу, чат, уведомления, места за одним экраном
const MP = { room: null, roomOk: false, peers: [], me: {}, primed: Object.create(null), pst: Object.create(null), dst: Object.create(null),
  chatSeen: +(lsGet('pv3-chatseen') || 0), retry: null, syncT: null, lastTouch: 0, hello: Object.create(null) };
const WAIT_STEP = 4000;

// ── присутствие: кто сейчас открыл игру, что смотрит, готов ли к ходу
function setPresence(patch) {
  for (const k in patch) { if (patch[k] == null) delete MP.me[k]; else MP.me[k] = patch[k]; }
  if (MP.room) { try { MP.room.presence(patch).catch(() => { }); } catch (e) { } }
  if (typeof renderTop === 'function' && M.ready) renderTop();
}
function presenceBase() { return { uid: ACT.id, view: UI.view, sel: UI.sel && !isLocal(UI.sel) ? UI.sel.slice(2) : null }; }
function initRoom(room) {
  MP.room = room || null; if (!room) return;
  const dead = e => { console.warn('комната', e); MP.room = null; MP.roomOk = false; MP.peers = []; if (M.ready) renderTop(); };
  try {
    room.onPeers(ch => { MP.peers = ch.peers || []; MP.roomOk = true; syncCheck(); if (M.ready) { renderTop(); if (UI.view === 'players') scheduleRender(); } }, dead);
  } catch (e) { dead(e); }
  setPresence(presenceBase());
}
// игроки, которые сейчас в игре (по присутствию); две вкладки одного игрока — один игрок
function roomPlayers() {
  const o = Object.create(null), Y = curYear();
  for (const p of MP.peers) {
    if (!p || p.kind !== 'viewer') continue;
    let pr = p.presence || {}; const uid = typeof pr.uid === 'string' && pr.uid.length < 120 ? pr.uid : null; if (!uid) continue;
    if (uid === ACT.id) pr = Object.assign({}, pr, MP.me);
    const ready = pr.ready === Y, readyAt = ready ? (+pr.readyAt || 0) : 0, busy = pr.busy === Y + 1;
    const cur = o[uid];
    if (!cur) o[uid] = { uid, view: pr.view, sel: pr.sel, tabs: 1, ready, readyAt, busy, updatedAt: p.updatedAt || 0 };
    else { cur.tabs++; if (ready) { cur.ready = true; cur.readyAt = Math.max(cur.readyAt, readyAt); } if (busy) cur.busy = true; if ((p.updatedAt || 0) > cur.updatedAt) { cur.updatedAt = p.updatedAt; cur.view = pr.view; cur.sel = pr.sel; } }
  }
  if (MP.room && MP.roomOk && ACT.id && !o[ACT.id]) o[ACT.id] = Object.assign({ uid: ACT.id, tabs: 1, ready: MP.me.ready === Y, readyAt: +MP.me.readyAt || 0, busy: MP.me.busy === Y + 1, updatedAt: Date.now() }, { view: UI.view, sel: null });
  return o;
}
function onlineIds() { return Object.keys(roomPlayers()); }
function isOnline(id) { return !!roomPlayers()[id]; }
function computingBy() { const rp = roomPlayers(); for (const id in rp) if (rp[id].busy && id !== ACT.id) return id; return null; }

// ── синхронный ход: год считается, когда все, кто в игре и ведёт страну, нажали «Готов»
function syncOn() { const g = game(); return !!(B.remote && MP.room && MP.roomOk && g && g.sync !== false); }
function waitedList() { if (!syncOn()) return []; return Object.values(roomPlayers()).filter(p => myCountriesOf(p.uid).length > 0); }
function syncApplies() { return waitedList().length >= 2; }
function iAmWaited() { return waitedList().some(p => p.uid === ACT.id); }
function myReady() { return MP.me.ready === curYear(); }
function notReadyNames(w) { return (w || waitedList()).filter(p => !p.ready).map(p => p.uid === ACT.id ? 'вы' : nameOf(p.uid)); }
async function onNextYear() {
  if (M.busy || !canAct()) return;
  if (!syncApplies()) { advanceYear(); return; }
  const w = waitedList();
  if (iAmWaited()) {
    if (myReady()) { setPresence({ ready: null, readyAt: null }); toast('Готовность снята.'); return; }
    setPresence({ ready: curYear(), readyAt: Date.now() });
    const rest = notReadyNames(w).filter(n => n !== 'вы');
    if (rest.length) toast('Вы готовы. Месяц посчитается, когда нажмут «Готов»: ' + rest.join(', ') + '.', 5000);
    syncCheck();
  } else if (w.every(p => p.ready)) advanceYear();
  else toast('Месяц считается, когда все игроки со странами нажмут «Готов». Ждём: ' + notReadyNames(w).join(', ') + '.', 5000);
}
// все готовы — считает последний нажавший; остальные подстраховывают через 4, 8, … секунд
function syncCheck() {
  clearTimeout(MP.syncT); MP.syncT = null;
  if (!syncApplies() || M.busy || !canAct()) return;
  const w = waitedList(); if (!w.every(p => p.ready)) return;
  if (!iAmWaited() || !myReady()) return;
  const order = w.slice().sort((a, b) => b.readyAt - a.readyAt), idx = order.findIndex(p => p.uid === ACT.id); if (idx < 0) return;
  const Y = curYear();
  MP.syncT = setTimeout(() => { MP.syncT = null; if (curYear() === Y && !M.busy && syncApplies() && waitedList().every(p => p.ready)) advanceYear({ auto: true, forYear: Y }); }, idx * WAIT_STEP + 200);
}
function forceYear() {
  const names = notReadyNames().filter(n => n !== 'вы');
  askConfirm('Ходить, не дожидаясь?', (names.length ? 'Не готовы: ' + names.join(', ') + '. ' : '') + 'Месяц будет посчитан с их нынешними решениями.', 'Посчитать месяц', () => advanceYear());
}
async function setSync(on) {
  if (!canAct()) return;
  try { await B.update('game/state', { sync: !!on }); toast(on ? 'Теперь месяц ждёт всех игроков со странами.' : 'Теперь месяц может посчитать любой, не дожидаясь остальных.'); } catch (e) { failWrite(e, 'Не получилось'); }
}

// ── список игроков в базе: «был в игре» пишется только по настоящим действиям
async function touchSeen(extra) {
  if (!B.remote || !ACT.id || M.me.canWrite === false) return;
  const now = Date.now();
  if (!extra && now - MP.lastTouch < 60000) return;
  MP.lastTouch = now;
  const cur = M.c.players[ACT.id];
  const doc = Object.assign({}, cur || { id: ACT.id, joined: now, base: seatBase(ACT.id) }, extra || {}, { seen: now });
  M.c.players[ACT.id] = doc;
  try { await B.set('players/' + ACT.id, doc); } catch (e) { console.warn('игрок', e); }
}
function seatBase(id) { return id && id.includes('~') ? id.slice(0, id.indexOf('~')) : id; }
function lastSeenRu(p) {
  const t = p && p.seen; if (!t) return 'давно';
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 2) return 'только что'; if (m < 60) return m + ' мин назад';
  const hh = Math.round(m / 60); if (hh < 24) return hh + ' ч назад';
  const d = Math.round(hh / 24); return d + ' ' + plural(d, 'день', 'дня', 'дней') + ' назад';
}
// все, кого знает мир: записи игроков плюс владельцы стран и авторы патчей
function knownPlayers() {
  const ids = Object.create(null);
  Object.keys(M.c.players).forEach(id => { if (M.c.players[id] && !id.startsWith('local:')) ids[id] = 1; });
  Object.values(M.c.ctrl).forEach(d => { if (d && d.owner) ids[d.owner] = 1; });
  Object.values(M.c.patch).forEach(p => { if (p && p.author && p.author !== 'ai') ids[p.author] = 1; });
  const rp = roomPlayers(), Y = curYear();
  return Object.keys(ids).map(id => {
    const cs = myCountriesOf(id), on = rp[id] || null;
    const Ws = cs.map(iso => sv(Y, iso, 'served')).filter(v => v != null);
    let ok = 0, n = 0; Object.values(M.c.patch).forEach(p => { if (p && p.author === id && p.res && p.res.res !== 'stale') { n++; if (p.res.res === 'pass') ok++; } });
    return { id, p: M.c.players[id] || null, on, countries: cs, W: Ws.length ? Ws.reduce((a, b) => a + b, 0) / Ws.length : null, ok, n };
  }).sort((a, b) => (b.on ? 1 : 0) - (a.on ? 1 : 0) || (b.countries.length ? 1 : 0) - (a.countries.length ? 1 : 0) || ((b.p && b.p.seen) || 0) - ((a.p && a.p.seen) || 0));
}
// имя и «места» — второй игрок за тем же экраном и той же учётной записью
function seatIds() { if (!B.remote || !M.me.id) return []; return [M.me.id].concat(Object.keys(M.c.players).filter(id => id.startsWith(M.me.id + '~') && M.c.players[id]).sort()); }
function switchSeat(id) {
  ACT.id = id; lsSet('pv3-seat:' + M.me.id, id); UI.composer = null;
  setPresence({ uid: id, ready: null, readyAt: null });
  renderAll(); requestDraw();
}
async function addSeat(nick) {
  nick = String(nick || '').trim().slice(0, 40); if (!nick || !canAct()) return;
  const ids = seatIds(); let n = 2; while (ids.includes(M.me.id + '~' + n)) n++;
  const id = M.me.id + '~' + n, doc = { id, base: M.me.id, nick, joined: Date.now(), seen: Date.now() };
  try { await B.set('players/' + id, doc); M.c.players[id] = doc; switchSeat(id); toast('Добавлен игрок «' + nick + '» — ходите по очереди за этим экраном.'); }
  catch (e) { failWrite(e, 'Не получилось добавить игрока'); }
}
async function renameMe(nick) {
  nick = String(nick || '').trim().slice(0, 40); if (!nick) return;
  if (!B.remote) { const p = M.c.players[ACT.id]; if (p) { p.nick = nick; saveLocal(); } renderAll(); return; }
  await touchSeen({ nick }); renderAll();
}
function askName(title, cur, onOk) {
  const inp = h('input', { class: 'inp', value: cur || '', maxlength: 40, placeholder: 'Имя в игре', 'aria-label': 'Имя' });
  const ok = () => { const v = inp.value.trim(); if (!v) { toast('Введите имя.'); return; } closeDialog(); onOk(v); };
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') ok(); });
  openDialog(title, h('div', null, inp), [h('button', { class: 'btn', onclick: closeDialog }, 'Отмена'), h('button', { class: 'btn primary', onclick: ok }, 'Готово')]);
}
const SHARE_URL = 'https://claude.ai/artifact/2bMf7fSAf2eb7zbx7x5iZs';   // опубликованная страница игры; внутри рамки location — не она
function inviteDialog() {
  const url = location.protocol === 'file:' ? location.href.split('#')[0] : SHARE_URL;
  const inp = h('input', { class: 'inp', value: url, readonly: true, 'aria-label': 'Ссылка' });
  const copy = h('button', { class: 'btn small', onclick: async () => { try { await navigator.clipboard.writeText(url); toast('Ссылка скопирована.'); } catch (e) { inp.select(); toast('Скопируйте ссылку из поля.'); } } }, 'Копировать');
  openDialog('Пригласить в этот мир', h('div', null,
    h('p', { style: 'margin-top:0', text: 'Мир один на всех, кто открывает эту страницу с правом взаимодействия. Отправьте ссылку и откройте доступ в меню «Поделиться»: приглашённому по e-mail нужен уровень «может редактировать», участнику вашей организации достаточно «может взаимодействовать». Кто открыл только для просмотра — увидит мир, но ходить не сможет.' }),
    h('div', { class: 'row-btns chat-in' }, inp, copy),
    h('p', { class: 'muted small', text: 'Второй человек за этим же экраном и той же учётной записью — кнопка «+ Игрок за этим экраном» на вкладке «Игроки».' })),
    [h('button', { class: 'btn primary', onclick: closeDialog }, 'Понятно')]);
}

// ── чат
async function sendChat(text) {
  text = String(text || '').replace(/\s+/g, ' ').trim().slice(0, CHAT_LEN); if (!text || !canAct()) return false;
  const id = 'm' + Date.now().toString(36) + rid(3), doc = { id, by: ACT.id, t: Date.now(), y: curYear(), text };
  try { await B.set('chat/' + id, doc); if (B.remote) M.c.chat[id] = doc; touchSeen(); markChatSeen(); return true; }
  catch (e) { failWrite(e, 'Не получилось отправить'); return false; }
}
function chatList() { return Object.values(M.c.chat || {}).filter(m => m && m.text).sort((a, b) => a.t - b.t); }
function chatUnread() { return chatList().filter(m => m.t > MP.chatSeen && m.by !== ACT.id).length; }
function markChatSeen() { const l = chatList(); if (l.length) MP.chatSeen = Math.max(MP.chatSeen, l[l.length - 1].t); lsSet('pv3-chatseen', String(MP.chatSeen)); }

// ── уведомления о чужих действиях (после первого снимка каждой коллекции)
function noteChange(coll, ch) {
  const d = ch.doc.data(), id = ch.doc.id, primed = MP.primed[coll] && !M.busy;   // пока сам считаю год — без всплывающих сообщений
  if (coll === 'patch') {
    const prev = MP.pst[id]; MP.pst[id] = d ? d.status : null;
    if (!primed || !d) return;
    if (ch.type === 'added' && d.status === 'open' && d.author !== ACT.id && isMine(d.iso)) toast(`${nameOf(d.author)} предлагает патч «${d.title}» для страны ${cname(d.iso)} — вкладка «Патчи».`, 7000);
    else if (ch.type === 'modified' && prev && prev !== d.status) {
      if (prev === 'open' && d.author === ACT.id && !isMine(d.iso)) toast(`Ваш патч «${d.title}» (${cname(d.iso)}): ${statusRu(d.status)}.`, 6000);
      else if (prev === 'merged' && (isMine(d.iso) || d.author === ACT.id) && d.status !== 'merged') toast(`Проверка патча «${d.title}» (${cname(d.iso)}): ${statusRu(d.status)}.`, 6000);
    }
  } else if (coll === 'deal') {
    const prev = MP.dst[id]; MP.dst[id] = d ? d.status : null;
    if (!primed || !d) return;
    if (ch.type === 'added' && d.status === 'open' && isMine(d.to) && d.by !== ACT.id) toast(`${cname(d.from)} → ${cname(d.to)}: предложение о свободной торговле. Ответить — в карточке страны, вкладка «Торговля».`, 7000);
    else if (ch.type === 'modified' && prev === 'open' && d.status !== 'open' && isMine(d.from) && d.by2 !== ACT.id) toast(`${cname(d.to)} ${d.status === 'accepted' ? 'приняла' : 'отклонила'} предложение о свободной торговле.`, 6000);
  } else if (coll === 'chat') {
    if (!primed || !d || ch.type !== 'added' || d.by === ACT.id) return;
    if (UI.view === 'players') markChatSeen(); else toast(`${nameOf(d.by)}: ${String(d.text).slice(0, 140)}`, 5000);
  } else if (coll === 'players') {
    if (!primed || !d || d.id === ACT.id || ch.type !== 'added') return;
    if (!MP.hello[d.id]) { MP.hello[d.id] = 1; toast(`В мир вошёл новый игрок: ${nameOf(d.id)}.`, 4000); }
  }
}
function openPatchesForMe() { return Object.values(M.c.patch).filter(p => p && p.status === 'open' && p.author !== ACT.id && isMine(p.iso)).length; }
function openDealsForMe() { return Object.values(M.c.deal).filter(d => d && d.status === 'open' && isMine(d.to)).length; }
function setBadge(v, n) {
  const t = $('.tab[data-v=' + v + ']'); if (!t) return;
  let b = t.querySelector('.badge');
  if (!n) { if (b) b.remove(); return; }
  if (!b) { b = h('i', { class: 'badge' }); t.append(b); }
  b.textContent = n > 99 ? '99+' : String(n);
}

// ════════════════════════ вкладка «Игроки»
function buildChat() {
  const box = h('div', { class: 'chat' });
  const msgs = chatList().slice(-120);
  if (!msgs.length) box.append(h('div', { class: 'muted small', style: 'padding:8px', text: 'Пока тихо. Договаривайтесь, кому что везти, здесь.' }));
  msgs.forEach(m => box.append(h('div', { class: 'msg' + (m.by === ACT.id ? ' me' : '') }, h('div', { class: 'msg-h' }, h('span', { class: 'dot', style: 'background:' + colorOf(m.by), text: nameOf(m.by).charAt(0).toUpperCase() }), h('b', { text: nameOf(m.by) }), h('span', { class: 'muted small', text: (m.y != null ? WORLD.labelShort(m.y) + ' · ' : '') + new Date(m.t).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) })), h('div', { class: 'msg-t', text: m.text }))));
  return box;
}
// пока человек печатает, обновляется только лента сообщений
function refreshChat() {
  const old = $('#playersPage .chat'); if (!old) return;
  const n = chatList().length; if (old.dataset.n === String(n)) return;
  const box = buildChat(); box.dataset.n = String(n); old.replaceWith(box); box.scrollTop = box.scrollHeight;
  markChatSeen(); setBadge('players', 0);
}
// сводка по своим странам за год — для сообщения о смене года
function myDigest(Y) {
  const mine = myCountries().slice(0, 3); if (!mine.length || !M.sum[Y]) return '';
  return ' ' + mine.map(iso => { const s = sv(Y, iso, 'served'), g = sv(Y, iso, 'grid'), c = sv(Y, iso, 'comms'); return s == null ? null : `${cname(iso)}: снабжение ${pct(s)}, свет ${pct(g)}, связь ${pct(c)}`; }).filter(Boolean).join('; ') + '.';
}
function renderPlayers() {
  const el = $('#playersPage'); if (!el) return; el.innerHTML = '';
  const Y = curYear(), g = game();
  el.append(h('h1', { text: 'Игроки' }));
  if (!B.remote) {
    el.append(h('p', { class: 'muted', text: 'Сейчас мир живёт только в этом браузере: за одним экраном можно ходить по очереди. Общий мир для нескольких человек работает на опубликованной странице с общей базой.' }));
    const ids = Object.keys(M.c.players).filter(id => id.startsWith('local:'));
    el.append(h('div', { class: 'panel' }, h('h3', { style: 'margin-top:0', text: 'За этим экраном' }),
      ids.map(id => h('div', { class: 'prow' }, h('span', { class: 'dot', style: 'background:' + colorOf(id), text: nameOf(id).charAt(0).toUpperCase() }), h('b', { text: nameOf(id) }), id === ACT.id ? pill('ходит сейчас', 'acc') : h('button', { class: 'lnk small', onclick: () => setActor(id) }, 'ходить за него'),
        h('span', { class: 'muted small', text: myCountriesOf(id).map(cname).join(', ') || 'без стран' }), h('button', { class: 'lnk small', onclick: () => askName('Имя игрока', nameOf(id), v => { M.c.players[id].nick = v; saveLocal(); renderAll(); }) }, 'переименовать'))),
      h('div', { class: 'row-btns' }, h('button', { class: 'btn small', onclick: addLocalPlayer }, '+ Игрок'))));
    return;
  }
  const rp = roomPlayers(), online = Object.keys(rp), w = waitedList();
  // строка состояния хода
  const sync = g && g.sync !== false;
  const st = h('div', { class: 'panel' });
  st.append(h('div', { class: 'row-btns', style: 'margin:0 0 6px' }, h('b', { text: 'Ход' }),
    canAct() ? h('label', { class: 'small' }, (() => { const cb = h('input', { type: 'checkbox', checked: sync ? true : null }); cb.addEventListener('change', () => setSync(cb.checked)); return cb; })(), ' ждать всех игроков со странами перед ходом') : pill(sync ? 'месяц ждёт всех игроков' : 'ходит любой', '')));
  if (!MP.room || !MP.roomOk) st.append(h('p', { class: 'muted small', style: 'margin:0', text: 'Присутствие в этом просмотре недоступно: кто сейчас в игре, не видно, и месяц считает тот, кто нажал «Следующий месяц».' }));
  else if (syncApplies()) {
    st.append(h('p', { class: 'small', style: 'margin:0' }, `В игре ${w.length} ${plural(w.length, 'игрок', 'игрока', 'игроков')} со странами. Готовы: ${w.filter(p => p.ready).length} из ${w.length}` + (notReadyNames(w).length ? ` — ждём: ${notReadyNames(w).join(', ')}.` : ' — месяц считается.')),
      canAct() ? h('div', { class: 'row-btns', style: 'margin:8px 0 0' }, iAmWaited() ? h('button', { class: 'btn small ' + (myReady() ? '' : 'primary'), onclick: onNextYear }, myReady() ? 'Снять готовность' : 'Готов к следующему месяцу') : null, h('button', { class: 'btn small ghost', onclick: forceYear }, 'Ходить, не дожидаясь')) : null);
  } else st.append(h('p', { class: 'muted small', style: 'margin:0', text: online.length > 1 ? 'Ждать некого: страну ведёт только один из тех, кто сейчас в игре.' : 'Сейчас в игре только вы — месяц считаете вы.' }));
  el.append(st);
  // кнопки
  el.append(h('div', { class: 'row-btns' },
    h('button', { class: 'btn small', onclick: inviteDialog }, 'Пригласить'),
    canAct() ? h('button', { class: 'btn small', onclick: () => askName('Как вас называть в игре', (M.c.players[ACT.id] || {}).nick || nameOf(ACT.id), renameMe) }, 'Сменить имя') : null,
    canAct() ? h('button', { class: 'btn small', onclick: () => askName('Имя второго игрока', '', addSeat) }, '+ Игрок за этим экраном') : null));
  // таблица игроков
  const list = knownPlayers();
  const tb = h('tbody');
  list.forEach(r => {
    const on = r.on, name = nameOf(r.id);
    tb.append(h('tr', { class: r.id === ACT.id ? 'hl' : '' },
      h('td', null, h('span', { class: 'pl-name' }, h('span', { class: 'dot', style: 'background:' + colorOf(r.id), text: name.charAt(0).toUpperCase() }), h('b', { text: name }), r.id === ACT.id ? h('span', { class: 'muted small', text: ' (вы)' }) : null)),
      h('td', null, r.countries.length ? r.countries.map(iso => h('button', { class: 'lnk', style: 'margin-right:6px', onclick: () => { setView('map'); select('C:' + iso); } }, cname(iso))) : h('span', { class: 'muted small', text: '—' })),
      h('td', null, on ? h('span', null, pill(on.busy ? 'считает год' : on.ready ? 'готов ✓' : 'в игре', on.busy || on.ready ? 'good' : 'acc'), on.sel && on.sel !== 'null' && IDX[on.sel] != null ? h('span', { class: 'muted small', text: ' смотрит ' + cname(on.sel) }) : null) : h('span', { class: 'muted small', text: lastSeenRu(r.p) })),
      h('td', { class: 'r', text: r.W == null ? '—' : pct(r.W) }),
      h('td', { class: 'r', text: r.n ? r.ok + '/' + r.n : '—' })));
  });
  el.append(h('h2', { text: 'Кто в мире' }), h('div', { class: 'tblwrap' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, ['Игрок', 'Страны', 'Состояние', 'Снабжение', 'Патчи'].map((t, i) => h('th', { class: i >= 3 ? 'r' : '', text: t, title: i === 3 ? 'Среднее снабжение стран игрока в этом месяце' : i === 4 ? 'Подтвердившиеся патчи / проверенные' : null })))), tb)),
    h('p', { class: 'muted small', text: 'Снабжение — средняя доля жителей стран игрока, до которых доходят вода и еда. Патчи — сколько его патчей подтвердились проверкой против «тени».' }));
  // чат
  el.append(h('h2', { text: 'Чат' }));
  const box = buildChat();
  el.append(box);
  markChatSeen(); setBadge('players', 0);
  if (canAct()) {
    const inp = h('input', { class: 'inp', placeholder: 'Сообщение всем игрокам', maxlength: CHAT_LEN, 'aria-label': 'Сообщение' });
    const send = async () => { const t = inp.value; if (!t.trim()) return; inp.value = ''; if (await sendChat(t)) { scheduleRender(); } else inp.value = t; };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); send(); } });
    el.append(h('div', { class: 'row-btns chat-in' }, inp, h('button', { class: 'btn primary', onclick: send }, 'Отправить')));
  } else el.append(h('p', { class: 'muted small', text: 'Писать в чат можно с правом взаимодействия.' }));
  setTimeout(() => { box.scrollTop = box.scrollHeight; }, 0);
}
