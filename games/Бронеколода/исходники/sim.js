// Баланс: ИИ против ИИ по всем парам доктрин, обе очерёдности. node sim.js [партий на пару]
const E = require('./engine.js');
const N = +process.argv[2] || 200;
const D = ['A', 'B', 'C'];

function play(d0, d1, seed, first) {
  const s = E.newGame({ doctrines: [d0, d1], seed, first });
  E.mulligan(s, 0, E.AI.mulligan(s, 0)); E.mulligan(s, 1, E.AI.mulligan(s, 1));
  let steps = 0;
  while (s.phase === 'play' && steps < 3000) {
    const a = E.AI.choose(s, s.active);
    if (a) E.AI.apply(s, a); else E.endTurn(s);
    s.events.length = 0;
    steps++;
  }
  return { winner: s.winner, turns: s.turn };
}

const t0 = Date.now();
const win = { A: 0, B: 0, C: 0 }, games = { A: 0, B: 0, C: 0 };
let firstWins = 0, total = 0, draws = 0, turns = 0;
const pair = {};
let seed = 1000;
for (const d0 of D) for (const d1 of D) {
  if (d0 === d1) continue;
  let w0 = 0;
  for (let i = 0; i < N; i++) {
    const first = i % 2;
    const r = play(d0, d1, seed++, first);
    total++; turns += r.turns;
    if (r.winner === 'draw') { draws++; continue; }
    if (r.winner === first) firstWins++;
    const wd = r.winner === 0 ? d0 : d1;
    win[wd]++;
    if (r.winner === 0) w0++;
  }
  games[d0] += N; games[d1] += N;
  pair[d0 + '-' + d1] = w0 / N;
}
const out = {
  partiy: total, nichyi: draws, sredniy_hod: +(turns / total).toFixed(1),
  dolya_pobed_pervogo: +(firstWins / (total - draws)).toFixed(3),
  dolya_pobed_doktriny: Object.fromEntries(D.map(d => [d, +(win[d] / games[d]).toFixed(3)])),
  pary_dolya_pobed_levoy: Object.fromEntries(Object.entries(pair).map(([k, v]) => [k, +v.toFixed(3)])),
  sekund: +((Date.now() - t0) / 1000).toFixed(1)
};
console.log(JSON.stringify(out, null, 1));
