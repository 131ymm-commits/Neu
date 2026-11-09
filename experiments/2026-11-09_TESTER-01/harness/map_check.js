// Проверка кликов по карте: Bäckerei — поставить весы через интерфейс; Reifenwerk — выбрать станок кликом по клетке.
const { GameEnv } = require('./env');
const pick = (o, s) => { const c = o.controls.find(c => c.includes(s)); return c && c.split(' ')[0]; };
(async () => {
  let e = await GameEnv.open('../games/baeckerei/index.html', { seed: 1 }); let o = await e.observe();
  await e.act({ click: pick(o, 'Пропустить') }); o = await e.observe();
  await e.act({ click: pick(o, 'tabs: 🏗 Стройка') }); o = await e.observe();
  console.log('B каталог:', o.controls.filter(c => c.includes('build') || c.includes('panel')).slice(0, 12).join(' ; '));
  const w = pick(o, 'Весы'); console.log('B кнопка весов:', w);
  if (w) { await e.act({ click: w }); o = await e.observe(); console.log('B подсказка:', o.screen.buildBar, '|', o.screen.tip);
    const r = await e.act({ map: [5, 11] }); o = await e.observe(); console.log('B клик карты:', JSON.stringify(r), '→ предметов', o.state.map.objects.length, JSON.stringify(o.state.map.objects[0]), 'деньги', o.state.summary.money, 'ошибки', JSON.stringify(o.errors)); }
  await e.close();
  e = await GameEnv.open('../games/reifenwerk/Reifenwerk.html', { seed: 1 }); o = await e.observe();
  const ga = o.controls.find(c => c.includes('Оптимальная схема')); await e.act({ click: ga.split(' ')[0] }); o = await e.observe();
  const st = o.state.map.objects.find(s => s.w >= 2); console.log('R станок:', JSON.stringify(st));
  const r2 = await e.act({ map: [st.x + 1, st.y + 1] }); o = await e.observe(); console.log('R клик карты:', JSON.stringify(r2), '→ выбор:', (o.screen.selection || '').slice(0, 200).replace(/\n/g, ' | '), 'ошибки', JSON.stringify(o.errors));
  await e.close();
})();
