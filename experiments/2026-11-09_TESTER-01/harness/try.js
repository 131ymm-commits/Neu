// Ручная проверка среды: node try.js <игра.html> '<JSON-список действий>' [зерно]  → последнее наблюдение
const { GameEnv } = require('./env');
(async () => {
  const [file, acts, seed] = [process.argv[2], JSON.parse(process.argv[3] || '[]'), +(process.argv[4] || 1)];
  const t0 = Date.now(); const e = await GameEnv.open(file, { seed }); let o = await e.observe();
  for (const a of acts) { const r = await e.act(a); if (!r.ok) console.log('ОТКАЗ', JSON.stringify(a), r.error); o = await e.observe(); }
  console.log(JSON.stringify(o, null, 1)); console.error('шагов', acts.length, 'реальных мс', Date.now() - t0, 'след', e.trace.length);
  await e.close();
})();
