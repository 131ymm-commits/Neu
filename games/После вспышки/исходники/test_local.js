// Локальный прогон «После вспышки»: страна, решение с прогнозом, ходы, вкладки, форк, перезагрузка
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !m.text().includes('Failed to load resource')) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 4).join('\n')));
  const t0 = Date.now();
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game3/preview.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready, null, { timeout: 60000 }).catch(e => { console.log('не дождался:', errors.join('\n')); throw e; });
  console.log('готово за', Date.now() - t0, 'мс');
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/game3/shots/01-welcome.png' });
  await page.click('.dlg >> text=Начать'); await page.waitForTimeout(400);
  await page.screenshot({ path: '/tmp/game3/shots/02-map.png' });
  await page.fill('#q', 'Герман'); await page.waitForTimeout(500); await page.keyboard.press('Enter'); await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/game3/shots/03-germany.png' });
  await page.click('#card >> text=Взять управление'); await page.waitForTimeout(400);
  for (const [t, n] of [['Снабжение', '04'], ['Помощь', '05'], ['Места', '06'], ['Решения', '07']]) { await page.click(`#card .ctab:has-text("${t}")`); await page.waitForTimeout(500); await page.screenshot({ path: `/tmp/game3/shots/${n}-tab.png` }); }
  // решение: связь 50 %
  await page.click('#card >> text=+ Решение'); await page.waitForTimeout(300);
  await page.fill('.dlg input.inp', 'Сначала связь');
  const lev = page.locator('.lev').first();
  await lev.locator('input.num').fill('50'); await lev.locator('input.num').dispatchEvent('change'); await page.waitForTimeout(200);
  await page.locator('.dlg .goal select').first().selectOption('comms');
  await page.click('.dlg >> text=Прогноз: что будет с решением и без'); await page.waitForSelector('.preview table', { timeout: 30000 });
  await page.screenshot({ path: '/tmp/game3/shots/08-composer.png' });
  await page.evaluate(() => { const b = $$('.dlg-f button').find(x => x.textContent.trim() === 'Принять и применить'); b.click(); }); await page.waitForTimeout(500);
  console.log('политика DEU:', JSON.stringify(await page.evaluate(() => polOf('DEU'))));
  // помощь: Германия → Польша, топливо 30 дней и радио
  await page.evaluate(() => createPatch('DEU', { aidF: { POL: 30 }, aidR: { POL: 2 } }, { m: 'served', h: 2 }, 'Польше: топливо и радио', '', null).then(p => mergePatch(p.pid)));
  await page.waitForTimeout(400);
  for (let i = 0; i < 4; i++) { await page.click('#nextYear'); await page.waitForFunction(() => !M.busy, null, { timeout: 60000 }); await page.waitForTimeout(200); }
  await page.evaluate(() => select('C:DEU')); await page.waitForTimeout(800);
  await page.screenshot({ path: '/tmp/game3/shots/09-after-months.png' });
  const st = await page.evaluate(() => ({ month: curYear(), label: tLabel(), patch: Object.values(M.c.patch).map(p => [p.title, p.status, p.res && p.res.d]), deu: { served: sv(curYear(), 'DEU', 'served'), comms: sv(curYear(), 'DEU', 'comms'), grid: sv(curYear(), 'DEU', 'grid'), fuel: sv(curYear(), 'DEU', 'fuel') }, pol: { fuel: sv(curYear(), 'POL', 'fuel'), radio: sv(curYear(), 'POL', 'radio') }, world: wv(curYear()), ph: game().ph, news: (M.news[curYear()] || { items: [] }).items.map(n => n.title) }));
  console.log(JSON.stringify(st, null, 1));
  for (const [v, n] of [['world', 11], ['patches', 12], ['forks', 13], ['players', 14], ['help', 15], ['known', 16]]) { await page.click(`.tab[data-v=${v}]`); await page.waitForTimeout(700); await page.screenshot({ path: `/tmp/game3/shots/${n}-${v}.png` }); }
  await page.click('.tab[data-v=forks]'); await page.waitForTimeout(300);
  await page.click('text=Заводы — первыми'); await page.waitForTimeout(200);
  await page.click('text=Посчитать форк'); await page.waitForSelector('.forkres table', { timeout: 90000 });
  await page.screenshot({ path: '/tmp/game3/shots/17-fork.png' });
  await page.click('.tab[data-v=map]'); await page.waitForTimeout(300);
  await page.evaluate(() => { UI.metric = 'served'; renderSegs(); renderLegend(); recolor(); select(null); }); await page.waitForTimeout(600);
  await page.screenshot({ path: '/tmp/game3/shots/18-served.png' });
  await page.fill('#q', 'Warsaw'); await page.waitForTimeout(800); await page.keyboard.press('Enter'); await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/game3/shots/19-warsaw.png' });
  const size = await page.evaluate(() => (localStorage.getItem('posle-vspyshki-v3') || '').length);
  console.log('сохранено байт:', size);
  await page.reload(); await page.waitForFunction(() => typeof M !== 'undefined' && M.ready, null, { timeout: 60000 });
  console.log('после перезагрузки месяц:', await page.evaluate(() => curYear()), 'сводка есть:', await page.evaluate(() => !!M.sum[curYear()]), 'DEU снабжение:', await page.evaluate(() => sv(curYear(), 'DEU', 'served')));
  // мобильный вид
  await page.setViewportSize({ width: 390, height: 780 }); await page.waitForTimeout(600);
  await page.evaluate(() => select('C:DEU')); await page.waitForTimeout(1000);
  await page.screenshot({ path: '/tmp/game3/shots/20-mobile.png' });
  console.log('горизонтальная прокрутка:', await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth));
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e.message); process.exit(1); });
