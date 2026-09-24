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
  const r = await page.evaluate(async () => {
    placesOf('RUS'); const kazan = PL.byC.RUS.find(p => p.name === 'Казань');
    select(kazan.key); await claim(kazan.key); await advanceYear(); select(kazan.key);
    const stats = Array.from(document.querySelectorAll('#card .stat')).map(s => s.querySelector('.k').textContent + ': ' + s.querySelector('.v').textContent + ' ' + (s.querySelector('.d') ? s.querySelector('.d').textContent : ''));
    return stats;
  });
  console.log(r.join('\n'));
  // «Форки и план»: строка «Инфляция» при дефляции в плане
  const infl = await page.evaluate(() => { const f = { pi: 2.4 }, p = { pi: -1.5 }; const d = -1 * (f.pi - p.pi); return d > 0 ? 'форки лучше' : 'план лучше'; });
  console.log('таблица «Форки и план» при π форков 2,4% и π плана −1,5% (цель 2–3%):', infl);
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
