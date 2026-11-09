const { GameEnv } = require('./env');
const pick = (o, s) => { const c = o.controls.find(c => c.includes(s)); return c && c.split(' ')[0]; };
(async () => {
  const e = await GameEnv.open('../games/reifenwerk/Reifenwerk.html', { seed: 1 }); let o = await e.observe();
  await e.act({ click: pick(o, 'Оптимальная схема') }); o = await e.observe(); console.log('вид до:', JSON.stringify(o.state.map.view));
  for (let i = 0; i < 3; i++) { await e.act({ click: pick(o, '🔍−') }); o = await e.observe(); } console.log('вид после 🔍−×3:', JSON.stringify(o.state.map.view));
  const st = o.state.map.objects.find(s => s.id === 'eingang') || o.state.map.objects[0];
  const r = await e.act({ map: [st.x + 2, st.y + 2] }); o = await e.observe(); console.log('клик', st.id, JSON.stringify(r), '→', (o.screen.selection || '').slice(0, 160).replace(/\n/g, ' | '));
  await e.act({ drag: [0.5, 0.5, 0.3, 0.5] }); o = await e.observe(); console.log('вид после drag:', JSON.stringify(o.state.map.view), 'ошибки', JSON.stringify(o.errors));
  await e.close();
})();
