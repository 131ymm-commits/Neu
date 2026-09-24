// Проверка многопользовательской части: присутствие, «Готов», подстраховка хода, чат, уведомления, второе место, значки
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 850 }, deviceScaleFactor: 1 });
  const errors = [], out = [];
  const log = (...a) => { console.log(...a); out.push(a.join(' ')); };
  const mk = async (uid, extra) => {
    const p = await ctx.newPage();
    p.on('pageerror', e => errors.push(uid + ' PAGEERROR: ' + e.message + ' ' + (e.stack || '').split('\n').slice(1, 3).join(' ')));
    p.on('console', m => { if (m.type() === 'error' && !m.text().includes('Failed to load resource')) errors.push(uid + ' ' + m.text()); });
    await p.route('**/fonts.g*/**', r => r.abort());
    await p.goto('file:///tmp/game3/preview_mock.html?uid=' + uid + (extra || ''));
    await p.waitForFunction(() => typeof M !== 'undefined' && M.ready && game() && game().v === 3, null, { timeout: 60000 });
    return p;
  };
  const pre = await ctx.newPage(); await pre.goto('file:///tmp/game3/blank.html');
  await pre.evaluate(() => { localStorage.clear(); localStorage.setItem('pv3-welcome', '1'); }); await pre.close();
  const A = await mk('u_alice'), Bp = await mk('u_bob');
  await A.waitForTimeout(600);
  const btn = p => p.evaluate(() => $('#nextYear').textContent.trim());
  const toastOf = p => p.evaluate(() => $('#toast').textContent);
  log('1. в игре (у Алисы):', await A.evaluate(() => onlineIds().join(', ')), '| чип:', await A.evaluate(() => ($('.chip-me.online') || {}).textContent));
  log('   кнопка без стран:', await btn(A));
  await A.evaluate(() => claimCountry('DEU')); await Bp.evaluate(() => claimCountry('CHN')); await A.waitForTimeout(500);
  log('2. страны взяты; кнопка у Алисы:', await btn(A), '| у Бориса:', await btn(Bp), '| ждём (Алиса):', await A.evaluate(() => notReadyNames().join(',')));
  // Алиса готова
  await A.click('#nextYear'); await A.waitForTimeout(400);
  log('3. Алиса нажала: кнопка', await btn(A), '| статус:', await A.evaluate(() => $('#stage').textContent), '| у Бориса видно готовность Алисы:', await Bp.evaluate(() => roomPlayers().u_alice && roomPlayers().u_alice.ready));
  await A.screenshot({ path: '/tmp/game3/shots/mp-01-alice-ready.png' });
  // Борис нажимает — считает он (последний)
  await Bp.click('#nextYear');
  await Bp.waitForFunction(() => curYear() === 1 && !M.busy, null, { timeout: 90000 });
  await A.waitForFunction(() => curYear() === 1, null, { timeout: 30000 }); await A.waitForTimeout(700);
  log('4. год у обоих:', await A.evaluate(() => curYear()), await Bp.evaluate(() => curYear()), '| кто посчитал:', await A.evaluate(() => nameOf(game().lastBy)), '| уведомление у Алисы:', JSON.stringify(await toastOf(A)), '| кнопка Алисы:', await btn(A), '| ready сброшен:', await A.evaluate(() => MP.me.ready == null));
  // подстраховка: Борис «готов» без запуска хода (как будто его вкладка зависла) — год должен посчитать Алиса
  await A.waitForTimeout(12500);
  await A.click('#nextYear'); await A.waitForTimeout(300);
  await Bp.evaluate(() => { window.__adv = advanceYear; advanceYear = async () => { window.__blocked = (window.__blocked || 0) + 1; }; });   // «зависшая» вкладка Бориса
  await Bp.evaluate(() => setPresence({ ready: curYear(), readyAt: Date.now() }));
  const t0 = Date.now();
  await A.waitForFunction(() => curYear() === 2 && !M.busy, null, { timeout: 90000 });
  log('5. подстраховка: год 2027 посчитал', await A.evaluate(() => nameOf(game().lastBy)), 'через', Math.round((Date.now() - t0) / 100) / 10, 'с; заблокированных попыток у Бориса:', await Bp.evaluate(() => window.__blocked || 0));
  await Bp.evaluate(() => { advanceYear = window.__adv; });
  await Bp.waitForFunction(() => curYear() === 2, null, { timeout: 30000 });
  // чат: Борис пишет с вкладки «Игроки», Алиса на карте получает уведомление и значок
  await Bp.click('.tab[data-v=players]'); await Bp.waitForTimeout(500);
  await Bp.screenshot({ path: '/tmp/game3/shots/mp-02-bob-players.png' });
  await Bp.fill('#playersPage .chat-in input', 'Привет! Предлагаю Германии свободную торговлю.'); await Bp.keyboard.press('Enter'); await Bp.waitForTimeout(700);
  log('6. чат: сообщений у Бориса:', await Bp.evaluate(() => chatList().length), '| уведомление у Алисы:', JSON.stringify(await toastOf(A)), '| значок «Игроки» у Алисы:', await A.evaluate(() => ($('.tab[data-v=players] .badge') || {}).textContent));
  // патч Германии от Бориса → уведомление и значок «Патчи»
  await Bp.evaluate(() => createPatch('DEU', { prC: 0.6 }, { m: 'comms', h: 2 }, 'Германии: связь', 'тест', null));
  await A.waitForTimeout(700);
  log('7. патч: уведомление у Алисы:', JSON.stringify(await toastOf(A)), '| значок «Патчи»:', await A.evaluate(() => ($('.tab[data-v=patches] .badge') || {}).textContent));
  await A.screenshot({ path: '/tmp/game3/shots/mp-03-alice-badges.png' });
  // заявка: Борис просит помощи для Китая; Алиса шлёт радио и топливо
  await Bp.evaluate(() => setRequest('CHN', 'Нужны радио и топливо', true)); await A.waitForTimeout(600);
  log('8. заявка у Алисы видна:', await A.evaluate(() => !!(M.c.req.CHN && M.c.req.CHN.open)), '| текст:', await A.evaluate(() => M.c.req.CHN.text));
  await A.evaluate(() => createPatch('DEU', { aidR: { CHN: 2 }, aidF: { CHN: 20 } }, { m: 'comms', h: 2, iso: 'CHN' }, 'Китаю: радио и топливо', '', null).then(p => mergePatch(p.pid)));
  await A.waitForTimeout(500);
  log('   патч помощи:', await A.evaluate(() => Object.values(M.c.patch).filter(p => p.title.startsWith('Китаю')).map(p => p.status + ' цель у ' + (p.goal.iso || '—')).join(', ')));
  // Алиса открывает «Игроки»: значок гаснет, чат виден
  await A.click('.tab[data-v=players]'); await A.waitForTimeout(600);
  log('9. вкладка «Игроки» у Алисы: значок:', await A.evaluate(() => ($('.tab[data-v=players] .badge') || { textContent: 'нет' }).textContent), '| строк в таблице:', await A.evaluate(() => $$('#playersPage tbody tr').length), '| состояние Бориса:', await A.evaluate(() => $$('#playersPage tbody tr')[1].children[2].textContent));
  await A.screenshot({ path: '/tmp/game3/shots/mp-04-alice-players.png' });
  // второе место за экраном Алисы
  await A.evaluate(() => addSeat('Света')); await A.waitForTimeout(600);
  log('10. места:', await A.evaluate(() => seatIds().join(', ')), '| ходит:', await A.evaluate(() => nameOf(ACT.id)), '| в шапке select:', await A.evaluate(() => !!$('#who select')));
  await A.evaluate(() => claimCountry('FRA')); await A.waitForTimeout(600);
  log('    ждут (у Бориса):', await Bp.evaluate(() => waitedList().map(p => nameOf(p.uid)).join(', ')));
  await A.click('.tab[data-v=map]'); await A.waitForTimeout(400);
  await A.screenshot({ path: '/tmp/game3/shots/mp-05-alice-seat.png' });
  // переименование
  await A.evaluate(() => renameMe('Светлана')); await Bp.waitForTimeout(600);
  log('11. имя у Бориса:', await Bp.evaluate(() => nameOf('u_alice~2')));
  // «ходить без них»: Борис не готов, Света готова и форсирует
  await A.waitForTimeout(12500);
  await A.click('#nextYear'); await A.waitForTimeout(300);
  log('12. статус ожидания у Светы:', await A.evaluate(() => $('#stage').textContent));
  await A.evaluate(() => advanceYear());
  await A.waitForFunction(() => curYear() === 3 && !M.busy, null, { timeout: 90000 });
  await Bp.waitForFunction(() => curYear() === 3, null, { timeout: 30000 });
  log('    год 2028 посчитал(а):', await A.evaluate(() => nameOf(game().lastBy)));
  // выключить ожидание
  await Bp.evaluate(() => setSync(false)); await A.waitForTimeout(600);
  log('13. ожидание выкл.: кнопка у Алисы:', await btn(A), '| у Бориса:', await btn(Bp));
  // вкладка без комнаты: игрок невидим и не задерживает
  const C = await mk('u_bob', '&room=0'); await C.waitForTimeout(500);
  log('14. без комнаты: в игре (у Алисы):', await A.evaluate(() => onlineIds().join(', ')), '| кнопка у C:', await btn(C));
  await C.close();
  // мобильная шапка
  await A.setViewportSize({ width: 390, height: 780 }); await A.waitForTimeout(500);
  await A.screenshot({ path: '/tmp/game3/shots/mp-06-mobile-head.png' });
  await A.evaluate(() => select('C:FRA')); await A.waitForTimeout(1000);
  await A.screenshot({ path: '/tmp/game3/shots/mp-07-mobile-card.png' });
  log('15. вкладки карточки на телефоне видны:', await A.evaluate(() => { const r = $('#card .ctabs').getBoundingClientRect(); return r.height > 20 && $$('#card .ctab').every(b => b.getBoundingClientRect().height > 10); }));
  log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
