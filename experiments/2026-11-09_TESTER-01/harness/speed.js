const { GameEnv } = require('./env');
(async () => { for (const f of ['../games/baeckerei/index.html', '../games/reifenwerk/Reifenwerk.html']) {
  const e = await GameEnv.open(f, { seed: 1 }); const t0 = Date.now(); await e.act({ wait: 60 }); const dt = Date.now() - t0;
  const errs = (await e.peek()).errors; console.log(f.split('/').pop(), '60 с виртуальных (600 кадров):', dt, 'мс реальных; ошибок', errs.length); await e.close(); } })();
