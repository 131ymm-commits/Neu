const SIM = require('./sim.js'), ENGINE = require('./engine.js');
const C = require('./build/countries.json');
const countries = {}; Object.values(C).forEach(c => { countries[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0 }; });
// патч во всех странах (или в подмножестве), проверка движком: доля прошедших по каждой метрике
function trial(ch, H, seeds, filter) {
  const cnt = { W: 0, y: 0, u: 0, pi: 0, D: 0 }; let n = 0, sum = { W: 0, y: 0, u: 0, pi: 0, D: 0 };
  for (const seed of seeds) {
    let h = ENGINE.initialHistory(countries, 2026, seed);
    const rules = {}, patches = { p: { ch, metric: 'W', horizon: H } };
    for (const iso of Object.keys(countries)) if (!filter || filter(iso, h)) { rules['C:' + iso] = {}; for (const q in ch) rules['C:' + iso][q] = { pid: 'p', opt: ch[q], since: 2026 }; }
    for (let t = 0; t < H; t++) {
      const r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
      for (const d of h.done) { n++; for (const m in cnt) { if (d.d[m] > 0) cnt[m]++; sum[m] += d.d[m]; } }
    }
  }
  return Object.keys(cnt).map(m => (100 * cnt[m] / Math.max(1, n)).toFixed(0).padStart(4) + '%' + ('(' + (sum[m] / Math.max(1, n)).toFixed(2) + ')').padEnd(9)).join(' ') + ' n=' + n;
}
const P = [['rate+', { rate: 1 }], ['rate-', { rate: -1 }], ['tariff+', { tariff: 1 }], ['tariff-', { tariff: -1 }], ['tax+', { tax: 1 }], ['tax-', { tax: -1 }],
  ['invest+', { invest: 1 }], ['invest-', { invest: -1 }], ['social+', { social: 1 }], ['social-', { social: -1 }],
  ['invest+tax+', { invest: 1, tax: 1 }], ['social+tax+', { social: 1, tax: 1 }]];
for (const H of [1, 3, 10]) {
  console.log('\nгоризонт', H, '— доля «лучше тени» и средний сдвиг: W | y% | u | |π−цель| | D');
  for (const [nm, ch] of P) console.log('  ' + nm.padEnd(12), trial(ch, H, [1, 2, 3]));
}
const hiInf = (iso, h) => { const s = ENGINE.unpackC(h.cs[iso]); return s.pi - SIM.params(countries[iso]).piStar > 5; };
const hiU = (iso, h) => { const s = ENGINE.unpackC(h.cs[iso]); return s.u - SIM.params(countries[iso]).uStar > 1 || s.u > 10; };
console.log('\nтолько страны с инфляцией > цели + 5:');
for (const H of [1, 3, 5]) console.log('  rate+ H' + H, trial({ rate: 1 }, H, [1, 2, 3], hiInf));
console.log('только страны с высокой безработицей:');
for (const H of [1, 3]) console.log('  invest+ H' + H, trial({ invest: 1 }, H, [1, 2, 3], hiU), '\n  social+ H' + H, trial({ social: 1 }, H, [1, 2, 3], hiU));
