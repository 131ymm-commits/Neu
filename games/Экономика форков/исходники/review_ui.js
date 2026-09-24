// Временная проверка интерфейса (ревью), локальный режим, свой профиль браузера.
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !/ERR_FAILED/.test(m.text())) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.route('**/fonts.g*/**', r => r.abort());
  await page.goto('file:///tmp/game/ekonomika-forkov.html');
  await page.waitForFunction(() => typeof M !== 'undefined' && M.ready && DATA.blob, null, { timeout: 30000 });
  // 1. приветствие
  const w = await page.evaluate(() => ({ text: $('#dlg .dlg-b').textContent.slice(0, 80), hasWorld: $('#dlg .dlg-b').textContent.includes('Весь мир'), junk: $('#dlg .dlg-b > div').attributes.length }));
  console.log('1) приветствие начинается с:', JSON.stringify(w.text), '| есть «Весь мир…»:', w.hasWorld, '| мусорных атрибутов у div:', w.junk);
  await page.evaluate(() => closeDialog());
  // 2. окно своего села
  await page.evaluate(() => openVillageDialog('RUS', 49.1, 55.8));
  const v = await page.evaluate(() => $('#dlg .dlg-b').textContent.includes('GeoNames есть места'));
  console.log('2) в окне села есть пояснение про GeoNames:', v);
  await page.evaluate(() => closeDialog());
  // 3. маленькие страны без контура в topo110
  const sg = await page.evaluate(() => { const t0 = MAP.t.k; zoomToKey('C:SGP'); return { info: placeInfo('C:SGP'), k0: t0, f110: !!MAP.f110.find(f => f.iso3 === 'SGP'), f50: !!MAP.f50 }; });
  await page.waitForTimeout(900);
  const k1 = await page.evaluate(() => MAP.t.k);
  console.log('3) Сингапур: lat/lon', sg.info.lat, sg.info.lon, '| контур в f110:', sg.f110, '| f50 построен:', sg.f50, '| масштаб до/после zoomToKey:', sg.k0, k1);
  // 4. поиск «Кипр»
  const cy = await page.evaluate(() => ({ name: cname('CYP'), found: Object.keys(ECON).filter(i => cname(i).toLowerCase().includes('кипр')) , places: placesOf('CYP').length }));
  console.log('4) Кипр: имя в игре', JSON.stringify(cy.name), '| поиск «кипр» по странам:', JSON.stringify(cy.found), '| городов:', cy.places);
  // 5. подсказка «форки − план» по безработице
  await page.evaluate(async () => { await claim('C:RUS'); const pid = await createPatch({ rate: 1, social: 1 }, 'u', 10, ''); await adopt('C:RUS', pid); });
  for (let i = 0; i < 3; i++) { await page.evaluate(() => advanceYear()); await page.waitForTimeout(150); }
  const d = await page.evaluate(() => { UI.world = 'diff'; UI.metric = 'u'; renderAll(); const a = stateOf('C:RUS', 'forks'), b = stateOf('C:RUS', 'plan'); return { forks: a.u, plan: b.u, shown: metricValue('C:RUS', 'u', 'diff') }; });
  console.log('5) Россия, безработица: форки', d.forks.toFixed(2), 'план', d.plan.toFixed(2), '| форки − план =', (d.forks - d.plan).toFixed(2), '| в подсказке «(форки − план)» будет', d.shown.toFixed(2));
  // 6. поле «проверить через, лет»
  await page.evaluate(() => { UI.world = 'forks'; UI.metric = 'W'; openComposer('C:RUS'); });
  await page.click('.qrow >> nth=2 >> button >> nth=2');
  for (const val of ['0', '2.5', '15']) { await page.fill('.dlg input[type=number]', val); await page.waitForTimeout(50); console.log('6) ввод', val, '→ в тексте:', await page.$eval('.preview', e => e.textContent.match(/(за|через) [^—]+/)[0].trim())); }
  await page.evaluate(() => closeDialog());
  // 7. текст сравнения с тенью при равенстве
  console.log('7) checkText(pi, 0):', await page.evaluate(() => checkText('pi', 0)), '| checkText(W, 0):', await page.evaluate(() => checkText('W', 0)));
  // 8. тост года с проверками
  await page.evaluate(async () => { await claim('C:DEU'); const p = await createPatch({ social: -1 }, 'W', 1, ''); await adopt('C:DEU', p); await advanceYear(); });
  console.log('8) тост:', await page.$eval('#toast', e => e.textContent));
  // 9. CSV: координаты маленьких стран (эмуляция DL)
  const csv = await page.evaluate(async () => { let got = null; DL = { save: async r => { got = r.data; return { status: 'saved' }; } }; await exportCSV(); DL = null; return got.split('\r\n').filter(l => /^(Сингапур|Мальта|Гонконг|Бахрейн),/.test(l)).map(l => l.split(',').slice(0, 5).join(',')); });
  console.log('9) CSV:', csv.join(' | '));
  console.log('ошибки:', errors.length ? errors.join('\n') : 'нет');
  await browser.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
