const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  const t0 = Date.now();
  await page.route('**/fonts.googleapis.com/**', r => r.abort()); await page.route('**/fonts.gstatic.com/**', r => r.abort());
  setTimeout(() => { if (errors.length) console.log('ранние ошибки:', errors.join('\n')); }, 20000);
  await page.goto('file:///tmp/game/preview.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready, null, { timeout: 30000 });
  console.log('готово за', Date.now() - t0, 'мс');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/game/shots/01-welcome.png' });
  await page.click('text=Начать');
  await page.waitForTimeout(400);
  await page.screenshot({ path: '/tmp/game/shots/02-map.png' });
  // выбрать Россию через поиск
  await page.fill('#q', 'Росс'); await page.waitForTimeout(600);
  await page.keyboard.press('Enter'); await page.waitForTimeout(1300);
  await page.screenshot({ path: '/tmp/game/shots/03-russia.png' });
  await page.click('text=Взять под управление'); await page.waitForTimeout(400);
  // написать патч и принять
  await page.click('#card >> text=Написать'); await page.waitForTimeout(300);
  const q = (i, j) => page.locator('.qrow').nth(i).locator('button').nth(j).click();
  await q(0, 2); await q(2, 2); await q(3, 2);
  await page.locator('.dlg select').nth(0).selectOption('W');
  await page.locator('.dlg select').nth(1).selectOption('2');
  await page.fill('.dlg textarea', 'Сбить инфляцию и вложиться в дороги за счёт налогов');
  await page.screenshot({ path: '/tmp/game/shots/04-composer.png' });
  await page.click('text=/Создать и принять/'); await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/game/shots/05-adopted.png' });
  // несколько лет
  for (let i = 0; i < 6; i++) { await page.click('#nextYear'); await page.waitForTimeout(350); }
  await page.waitForTimeout(600);
  await page.screenshot({ path: '/tmp/game/shots/06-after-years.png' });
  const st = await page.evaluate(() => ({ year: curYear(), rules: rulesOf('C:RUS'), done: Object.keys(M.c.histc).map(y => [y, (M.c.histc[y].done || []).length]), agg: rec(curYear()).agg }));
  console.log(JSON.stringify(st));
  // город: Казань
  await page.fill('#q', 'Казань'); await page.waitForTimeout(700);
  await page.keyboard.press('Enter'); await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/game/shots/07-kazan.png' });
  await page.click('text=Взять под управление'); await page.waitForTimeout(300);
  await page.click('#card >> text=Принять патч'); await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/game/shots/08-adopt-dialog.png' });
  await page.click('.dlg >> text=Написать свой'); await page.waitForTimeout(300);
  await q(2, 2); // поддержка ↑
  await page.click('text=/Создать и принять/'); await page.waitForTimeout(400);
  for (let i = 0; i < 4; i++) { await page.click('#nextYear'); await page.waitForTimeout(300); }
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/game/shots/09-kazan-years.png' });
  // вкладки
  for (const [v, n] of [['patches', 10], ['log', 11], ['compare', 12], ['help', 13]]) {
    await page.click(`.tab[data-v=${v}]`); await page.waitForTimeout(500);
    await page.screenshot({ path: `/tmp/game/shots/${n}-${v}.png`, fullPage: false });
  }
  await page.click('.tab[data-v=map]'); await page.waitForTimeout(300);
  // приближение до сёл вокруг Казани
  await page.evaluate(() => { const b = MAP.proj([49.1, 55.8]); d3.select(MAP.cv).call(MAP.zoom.transform, focusTf(b[0], b[1], 160)); });
  await page.waitForTimeout(800);
  await page.screenshot({ path: '/tmp/game/shots/14-villages.png' });
  // своё село
  await page.click('#addVillage'); await page.waitForTimeout(200);
  await page.mouse.click(300, 500); await page.waitForTimeout(400);
  const dlgTitle = await page.$eval('#dlg h2', e => e.textContent).catch(() => null);
  console.log('окно:', dlgTitle);
  if (dlgTitle === 'Добавить населённый пункт') { await page.fill('.dlg input[type=text]', 'Верхние Выселки'); await page.fill('.dlg input[type=number]', '240'); await page.screenshot({ path: '/tmp/game/shots/15-village-dialog.png' }); await page.click('.dlg-f >> text=Добавить'); await page.waitForTimeout(500); }
  await page.screenshot({ path: '/tmp/game/shots/16-village-card.png' });
  // игроки: добавить второго
  await page.click('.chip-me'); await page.waitForTimeout(300);
  await page.fill('.dlg input[type=text]', 'Маша'); await page.click('.dlg-b >> button:has-text("Добавить")'); await page.waitForTimeout(300);
  const actor = await page.evaluate(() => nameOf(ACT.id));
  console.log('ходит:', actor);
  // тёмная тема и режимы карты
  await page.emulateMedia({ colorScheme: 'dark' }); await page.waitForTimeout(300);
  await page.evaluate(() => { select('C:BRA'); zoomToKey('C:BRA'); UI.metric = 'y'; UI.world = 'diff'; renderAll(); });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/game/shots/17-dark-diff.png' });
  // сохранение и перезагрузка
  await page.waitForTimeout(800);
  const size = await page.evaluate(() => (localStorage.getItem('ekonomika-forkov-v1') || '').length);
  console.log('сохранено байт:', size);
  await page.reload(); await page.waitForFunction(() => typeof M !== 'undefined' && M.ready, null, { timeout: 30000 });
  console.log('после перезагрузки год:', await page.evaluate(() => curYear()), 'мест:', await page.evaluate(() => Object.keys(M.c.places).length));
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e.message); process.exit(1); });
