// Детерминизм: один и тот же сценарий дважды (с наблюдениями) → одинаковые состояния; затем повтор следа без наблюдений головы.
const { GameEnv } = require('./env');
const crypto = require('crypto'); const h = o => crypto.createHash('sha256').update(JSON.stringify(o)).digest('hex').slice(0, 12);
async function run(file, plan, seed) {
  const e = await GameEnv.open(file, { seed }); const states = [];
  for (const step of plan) {
    const o = await e.observe();
    const find = s => { const c = o.controls.find(c => c.includes(s)); return c && c.split(' ')[0]; };
    let a = step;
    if (step.label) { const id = find(step.label); if (!id) { states.push('нет кнопки ' + step.label); continue; } a = { click: id }; }
    const r = await e.act(a); states.push(h((await e.peek()).state)); if (!r.ok) states.push('ОТКАЗ ' + r.error);
  }
  const last = await e.peek(); const trace = e.trace.slice(); await e.close(); return { states, last, trace };
}
(async () => {
  const [file, seed] = [process.argv[2], +(process.argv[3] || 1)];
  const plan = JSON.parse(process.argv[4]);
  const t0 = Date.now(); const r1 = await run(file, plan, seed); const t1 = Date.now(); const r2 = await run(file, plan, seed);
  const rep = await GameEnv.replay(file, r1.trace, { seed }); const t2 = Date.now();
  const repStates = rep.map(p => h(p.state));
  console.log('прогон 1 = прогон 2:', JSON.stringify(r1.states) === JSON.stringify(r2.states), '| повтор следа = прогон 1:', JSON.stringify(repStates) === JSON.stringify(r1.states.filter(s => !String(s).startsWith('ОТКАЗ') && !String(s).startsWith('нет'))));
  console.log('мс: прогон', t1 - t0, 'повтор', t2 - t1);
  console.log('итог:', JSON.stringify(r1.last.state.summary).slice(0, 600)); console.log('ошибки:', JSON.stringify(r1.last.errors).slice(0, 400));
  console.log('люди:', JSON.stringify(r1.last.state.map.people.slice(0, 3))); console.log('экран top:', (r1.last.screen.top || '').replace(/\n/g, ' | '));
  console.log('шаги:', JSON.stringify(r1.states));
})();
