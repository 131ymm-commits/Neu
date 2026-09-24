// Прогон модели: базовый путь без решений и несколько политик — для калибровки
const fs = require('fs'), vm = require('vm');
const ctx = {}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync('/tmp/game3/world3.js', 'utf8') + '\nthis.WORLD = WORLD;', ctx);
const W = ctx.WORLD; const data = JSON.parse(fs.readFileSync('/tmp/game3/build/world3.json', 'utf8'));
W.setup(data);
const ISO = data.iso, N = ISO.length;
function run(polFn, months = 60, seed = 7, calm = false) {
  let st = W.init(seed); const rows = [W.world(st)];
  for (let t = 1; t <= months; t++) { const pol = polFn ? polFn(st, t) : {}; st = W.step(st, pol, calm ? { calm: true } : {}).st; rows.push(W.world(st)); }
  return { st, rows };
}
function show(name, res) {
  const r = res.rows, f = x => (100 * x).toFixed(0);
  const at = m => r[Math.min(m, r.length - 1)];
  console.log(`\n${name}`);
  console.log(' мес | связь логи снабж свет экон | голод | потери тыс | S');
  for (const m of [0, 1, 3, 6, 12, 18, 24, 36, 48, 60]) { const x = at(m); console.log(String(m).padStart(4), '|', f(x.comms).padStart(5), f(x.logi).padStart(4), f(x.served).padStart(5), f(x.grid).padStart(4), f(x.econ).padStart(4), '|', f(x.hungry).padStart(5), '|', x.losses.toFixed(0).padStart(10), '|', x.S.toFixed(2)); }
  const first = k => { const ph = W.PHASES.find(p => p.k === k); const i = r.findIndex(x => x[k] >= ph.goal); return i < 0 ? '—' : i; };
  console.log(' фазы (месяц достижения):', W.PHASES.map(p => p.ru + ' ' + first(p.k)).join(', '), '| выпуск ед./мес в конце', res.st.prodM.toFixed(0), '| буря-2:', res.st.storm2 || 'нет');
}
const base = run(null); show('Базовый путь: приоритеты поровну, нормирование 0,6, экспорт 30 %', base);
// страны крупнейшие по населению без снабжения в конце
const st = base.st; const rows = ISO.map((iso, c) => ({ iso, P: st.P[c], served: st.served[c], grid: st.grid[c], comms: st.comms[c], fuel: st.fuel[c], food: st.food[c], losses: st.losses[c], Tnew: st.Tnew[c], Tt: st.Tt[c] })).sort((a, b) => b.P * (1 - b.served) - a.P * (1 - a.served)).slice(0, 12);
console.log('\nхуже всего к 60-му месяцу:'); rows.forEach(x => console.log(' ', x.iso, 'P', x.P.toFixed(0), 'снабж', (100 * x.served).toFixed(0) + '%', 'свет', (100 * x.grid).toFixed(0) + '%', 'связь', (100 * x.comms).toFixed(0) + '%', 'топливо', x.fuel.toFixed(2), 'еда', x.food.toFixed(2), 'потери', x.losses.toFixed(0), 'нужно новых', x.Tnew.toFixed(0), '/', x.Tt));
// политика «сначала связь, потом свет»: всем приоритет связь 0,5 первые 6 мес, потом сеть 0,5; экспорт 60 % у заводов
const coop = run((s, t) => { const pol = {}; for (let c = 0; c < N; c++) pol[c] = t <= 6 ? { prC: 0.5, prW: 0.3, prG: 0.1, prL: 0.1, ration: 0.8, exportT: 0.6 } : { prC: 0.15, prW: 0.25, prG: 0.45, prL: 0.15, ration: 0.7, exportT: 0.6 }; return pol; });
show('Кооперация: связь → сеть, экспорт 60 %, жёсткое нормирование', coop);
const selfish = run((s, t) => { const pol = {}; for (let c = 0; c < N; c++) pol[c] = { prC: 0.1, prW: 0.3, prG: 0.5, prL: 0.1, ration: 0.3, exportT: 0 }; return pol; });
show('Каждый за себя: экспорт 0, нормирования почти нет', selfish);
const seeds = [1, 2, 3, 4, 5].map(sd => run(null, 60, sd).st.losses.reduce((a, b) => a + b, 0));
console.log('\nпотери по сидам (базовый путь):', seeds.map(x => x.toFixed(0)).join(', '));
console.log('время шага:', (() => { const t0 = Date.now(); run(null, 60, 9); return ((Date.now() - t0) / 60).toFixed(1) + ' мс'; })());
