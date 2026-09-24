const { chromium, devices } = require('playwright');
const SP = '/tmp/claude-0/-home-claude/5ed67756-d768-5a71-a9d2-3c3ffc5829de/scratchpad/';
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game/ekonomika-forkov.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready && DATA.blob, null, { timeout: 30000 });
  await page.evaluate(() => closeDialog());
  await page.evaluate(async () => {
    await claim('C:RUS'); const p = await createPatch({ rate: 1, tax: 1, invest: 1 }, 'W', 5, 'Длинное пояснение к патчу, чтобы проверить перенос строк на узком экране телефона'); await adopt('C:RUS', p);
    await claim('C:KAZ'); const p2 = await createPatch({ social: -1 }, 'pi', 1, ''); await adopt('C:KAZ', p2);
    for (let i = 0; i < 3; i++) await advanceYear();
    await addSeatPlayer('Очень длинное имя игрока номер два');
  });
  await page.waitForTimeout(5600);
  const over = () => page.evaluate(() => {
    const out = [];
    const docW = document.documentElement.clientWidth;
    for (const e of document.querySelectorAll('.page, .card-b, .dlg-b, .dlg-f, .top, .tabs, .banner, .toolbar, table, .formula, .plist, .patch')) {
      const cs = getComputedStyle(e); if (cs.display === 'none' || !e.offsetParent && e.tagName !== 'BODY') continue;
      const r = e.getBoundingClientRect();
      if (e.scrollWidth > e.clientWidth + 1 && !/(auto|scroll)/.test(cs.overflowX)) out.push((e.className || e.tagName) + ' scroll ' + e.scrollWidth + '>' + e.clientWidth);
      if (r.right > docW + 1) out.push((e.className || e.tagName) + ' вылет справа до ' + Math.round(r.right));
      if (e.scrollWidth > e.clientWidth + 1 && /(auto|scroll)/.test(cs.overflowX) && /page|card-b|dlg-b/.test(e.className)) out.push(e.className + ' гориз. прокрутка ' + e.scrollWidth + '>' + e.clientWidth);
    }
    return out;
  });
  const shot = async n => { await page.screenshot({ path: SP + n + '.png' }); const o = await over(); console.log(n, o.length ? o.join('; ') : 'без вылетов'); };
  await page.evaluate(() => { select('C:RUS'); zoomToKey('C:RUS'); }); await page.waitForTimeout(900); await shot('m-card');
  await page.evaluate(() => { $('#card .card-b').scrollTop = 400; }); await page.waitForTimeout(100); await shot('m-card2');
  await page.evaluate(() => openComposer('C:RUS')); await page.waitForTimeout(200); await shot('m-composer');
  await page.evaluate(() => { closeDialog(); openAdopt('C:RUS'); }); await page.waitForTimeout(200); await shot('m-adopt');
  await page.evaluate(() => { closeDialog(); openPlayers(); }); await page.waitForTimeout(200); await shot('m-players');
  await page.evaluate(() => { closeDialog(); }); 
  for (const v of ['patches', 'log', 'compare', 'help']) { await page.evaluate(v => setView(v), v); await page.waitForTimeout(300); await shot('m-' + v); }
  await page.evaluate(() => { const d = document.querySelector('#helpPage details'); if (d) d.open = true; document.querySelector('#view-help .page').scrollTop = 99999; }); await page.waitForTimeout(200); await shot('m-help-formulas');
  // шапка в общем режиме: кнопка с отсчётом
  await page.evaluate(() => { setView('map'); $('#nextYear').textContent = 'Следующий год · 15 с'; }); await shot('m-header-wait');
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
