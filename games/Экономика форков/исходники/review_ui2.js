const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game/ekonomika-forkov.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready && DATA.blob, null, { timeout: 30000 });
  await page.evaluate(() => closeDialog());
  await page.evaluate(async () => {
    await claim('C:CHN'); const p1 = await createPatch({ rate: -1 }, 'W', 10, ''); await adopt('C:CHN', p1);
    await claim('C:RUS'); const p2 = await createPatch({ rate: 1 }, 'W', 10, ''); await adopt('C:RUS', p2);
  });
  for (let i = 0; i < 3; i++) { await page.evaluate(() => advanceYear()); await page.waitForTimeout(120); }
  // навести мышь на Россию в режиме «форки − план», метрика «безработица»
  await page.evaluate(() => { UI.world = 'diff'; UI.metric = 'u'; renderAll(); zoomToKey('C:RUS'); });
  await page.waitForTimeout(1200);
  const pt = await page.evaluate(() => { const c = CENTROID.RUS; const b = MAP.proj(c); const v = viewTf(); return [b[0] * v.S + v.TX, b[1] * v.S + v.TY]; });
  const box = await page.$eval('#map', e => { const r = e.getBoundingClientRect(); return [r.left, r.top]; });
  await page.mouse.move(box[0] + pt[0], box[1] + pt[1]); await page.waitForTimeout(200);
  const tip = await page.$eval('#tip', e => e.textContent);
  const st = await page.evaluate(() => { const a = stateOf('C:RUS', 'forks'), b = stateOf('C:RUS', 'plan'); return { f: a.u, p: b.u, fD: a.D, pD: b.D }; });
  console.log('подсказка:', JSON.stringify(tip));
  console.log('безработица: форки', st.f.toFixed(2), 'план', st.p.toFixed(2), '→ форки − план =', (st.f - st.p).toFixed(2));
  console.log('долг: форки', st.fD.toFixed(2), 'план', st.pD.toFixed(2), '→ форки − план =', (st.fD - st.pD).toFixed(2), '| в подсказке было бы', (st.pD - st.fD).toFixed(2));
  // «Что сейчас в едином плане»: колонка плана против голосов
  await page.evaluate(() => { setView('compare'); });
  const rows = await page.$$eval('#comparePage table >> nth=1', () => null).catch(() => null);
  const planRows = await page.evaluate(() => Array.from(document.querySelectorAll('#comparePage .box')[1].querySelectorAll('tbody tr')).map(tr => Array.from(tr.children).map(td => td.textContent).join(' | ')));
  console.log('план:', planRows[0]);
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
