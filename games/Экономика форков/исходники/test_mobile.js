const { chromium, devices } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 13'] });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/ERR_FAILED/.test(m.text())) errors.push(m.text()); });
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game/preview.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready, null, { timeout: 30000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: '/tmp/game/shots/m1-welcome.png' });
  await page.click('text=Начать'); await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/game/shots/m2-map.png' });
  await page.fill('#q', 'Новосиб'); await page.waitForTimeout(600); await page.keyboard.press('Enter'); await page.waitForTimeout(1300);
  await page.screenshot({ path: '/tmp/game/shots/m3-card.png' });
  // приближение к сёлам
  await page.evaluate(() => { const b = MAP.proj([82.9, 55.0]); d3.select(MAP.cv).call(MAP.zoom.transform, focusTf(b[0], b[1], 120)); });
  await page.waitForTimeout(700);
  await page.screenshot({ path: '/tmp/game/shots/m4-villages.png' });
  const dots = await page.evaluate(() => MAP.dots.length);
  console.log('точек на экране:', dots);
  await page.click('.tab[data-v=compare]'); await page.waitForTimeout(400);
  await page.screenshot({ path: '/tmp/game/shots/m5-compare.png' });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log('горизонтальный вылет:', overflow, '| ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e.message); process.exit(1); });
