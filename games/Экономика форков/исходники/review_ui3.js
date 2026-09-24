const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
  const page = await ctx.newPage(); const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game/ekonomika-forkov.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready && DATA.blob, null, { timeout: 30000 });
  await page.evaluate(() => closeDialog());
  // повторное принятие после отката: что показывает карточка
  const r = await page.evaluate(async () => {
    await claim('C:DEU'); const p = await createPatch({ social: -1 }, 'W', 1, ''); await adopt('C:DEU', p);
    await advanceYear(); const afterRevert = JSON.stringify(rulesOf('C:DEU'));
    await adopt('C:DEU', p); await advanceYear(); await advanceYear();
    select('C:DEU'); const pills = Array.from(document.querySelectorAll('#card .q .pill')).map(e => e.textContent);
    return { afterRevert, rule: rulesOf('C:DEU').social, pills, live: (rec(curYear()).chk || []).length };
  });
  console.log('после отката:', r.afterRevert, '| повторно принят, 2 года спустя: правило', JSON.stringify(r.rule), '| плашки', JSON.stringify(r.pills), '| живых проверок', r.live);
  // дробный срок
  const fr = await page.evaluate(async () => { await claim('C:ITA'); const p = await createPatch({ tax: 1 }, 'W', 2.5, ''); await adopt('C:ITA', p); await advanceYear(); select('C:ITA'); return Array.from(document.querySelectorAll('#card .q .pill')).map(e => e.textContent); });
  console.log('срок 2.5:', JSON.stringify(fr));
  // столицы при масштабе 1.5: рисуется ли Вашингтон, Оттава, Канберра
  const caps = await page.evaluate(async () => { select(null); UI.metric = 'W'; const b = MAP.proj([-77, 39]); d3.select(MAP.cv).call(MAP.zoom.transform, focusTf(b[0], b[1], 1.6)); await new Promise(r => setTimeout(r, 300)); drawMap(); return ['Washington', 'Ottawa'].map(n => n + ':' + MAP.dots.some(d => d.p.name === n)).join(' ') + ' | столиц на экране: ' + MAP.dots.filter(d => d.p.cap === 2).map(d => d.p.name).join(', '); });
  console.log('k=1.6 над Америкой:', caps);
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
