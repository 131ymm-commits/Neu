const SIM = require('./sim.js'), ENGINE = require('./engine.js');
const C = require('./build/countries.json');
const countries = {}; Object.values(C).forEach(c => { countries[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0, pg: c.pg }; });
const isos = Object.keys(countries);
const QS = ['rate', 'tariff', 'tax', 'invest', 'social'], MS = ['W', 'y', 'u', 'pi', 'D'];
function run(policy, years, seed, withLocals) {
  let h = ENGINE.initialHistory(countries, 2026, seed);
  const rules = {}, patches = {}, locals = {};
  if (withLocals) { // 300 мест в 30 странах, у части — родитель
    const rnd = SIM.rng(99);
    for (let i = 0; i < 300; i++) { const cc = isos[Math.floor(rnd() * 30) * 7 % isos.length]; const key = 'P:' + i; locals[key] = { cc, pop: Math.round(1000 + rnd() * 500000), parent: i > 50 && rnd() < 0.3 ? 'P:' + Math.floor(rnd() * 50) : null }; }
  }
  let pid = 0; const stats = { checks: 0, pass: 0, fail: 0, reverted: 0, byQ: {} };
  const rnd = SIM.rng(seed * 7 + 1), series = [];
  let maxBytes = 0;
  for (let t = 0; t < years; t++) {
    policy(h, rules, patches, rnd, () => 'p' + (pid++), locals);
    const r = ENGINE.step(h, countries, locals, rules, patches);
    h = r.hist;
    maxBytes = Math.max(maxBytes, JSON.stringify(h).length);
    for (const d of h.done) { stats.checks++; d.ok ? stats.pass++ : stats.fail++; const k = d.qs.map((q, i) => q + (d.opts[i] > 0 ? '+' : '-')).join('&') + ':' + d.metric; stats.byQ[k] = stats.byQ[k] || [0, 0]; stats.byQ[k][d.ok ? 0 : 1]++; }
    stats.reverted += ENGINE.applyReverts(rules, r.reverts, h.year).length;
    series.push({ y: h.year, f: h.agg.forks, p: h.agg.plan });
  }
  return { h, stats, series, maxBytes, rules, locals };
}
const none = () => {};
function adopt(rules, key, id, ch, year, pa) { rules[key] = rules[key] || {}; for (const q in ch) rules[key][q] = { pid: id, opt: ch[q], since: year, m: pa && pa.metric, h: pa && pa.horizon }; }
const random = (h, rules, patches, rnd, newId, locals) => {
  for (let i = 0; i < 25; i++) {
    const iso = isos[Math.floor(rnd() * isos.length)], ch = {};
    const nq = 1 + Math.floor(rnd() * 2);
    for (let j = 0; j < nq; j++) ch[QS[Math.floor(rnd() * 5)]] = rnd() < 0.5 ? -1 : 1;
    const id = newId(); patches[id] = { ch, metric: MS[Math.floor(rnd() * 5)], horizon: 1 + Math.floor(rnd() * 5) };
    adopt(rules, 'C:' + iso, id, ch, h.year, patches[id]);
  }
  const lk = Object.keys(locals);
  for (let i = 0; lk.length && i < 10; i++) {
    const key = lk[Math.floor(rnd() * lk.length)], ch = { [ENGINE.LOCALQ[Math.floor(rnd() * 3)]]: rnd() < 0.5 ? -1 : 1 };
    const id = newId(); patches[id] = { ch, metric: MS[Math.floor(rnd() * 5)], horizon: 1 + Math.floor(rnd() * 5) };
    adopt(rules, key, id, ch, h.year, patches[id]);
  }
};
const smart = (h, rules, patches, rnd, newId) => {
  for (let i = 0; i < 25; i++) {
    const iso = isos[Math.floor(rnd() * isos.length)];
    const s = ENGINE.unpackC(h.cs[iso]), p = SIM.params(countries[iso]);
    const cur = ENGINE.countryOpts(rules, iso);
    let ch, metric = 'W', horizon = 5;
    if (s.pi - p.piStar > 3) { ch = { rate: 1 }; metric = 'pi'; horizon = 3; }
    else if (cur[0] === 1 && s.pi - p.piStar < 1) { ch = { rate: 0 }; }
    else if (s.pi - p.piStar < -1.5) { ch = { rate: -1 }; }
    else if (s.D > 30) { ch = { tax: 1 }; metric = 'D'; }
    else { ch = { invest: 1, tax: 1 }; horizon = 8; }
    if (Object.keys(ch).every(q => cur[SIM.QI[q]] === ch[q])) continue;
    const id = newId(); patches[id] = { ch, metric, horizon };
    adopt(rules, 'C:' + iso, id, ch, h.year, patches[id]);
  }
};
const fmt = a => `W=${a.W.toFixed(2)} g=${a.g.toFixed(2)} u=${a.u.toFixed(2)} π=${a.pi.toFixed(2)} D=${a.D.toFixed(1)} y=${a.y}`;
for (const [name, pol, loc] of [['без решений', none, false], ['случайные + места', random, true], ['разумные', smart, false]]) {
  for (const seed of [1, 2]) {
    const { h, stats, series, maxBytes, rules, locals } = run(pol, 30, seed, loc);
    const mean = k => (series.reduce((a, s) => a + s[k].W, 0) / series.length).toFixed(3);
    console.log(`\n== ${name}, зерно ${seed}: 30 лет; запись года до ${(maxBytes / 1024).toFixed(0)} КБ`);
    console.log('  форки:', fmt(series[29].f), '| средн. W', mean('f'));
    console.log('  план :', fmt(series[29].p), '| средн. W', mean('p'), '| план:', JSON.stringify(h.plan.opts));
    console.log('  проверок', stats.checks, 'прошло', stats.pass, 'не прошло', stats.fail, 'мест с откатами', stats.reverted);
    const bq = Object.entries(stats.byQ).sort((a, b) => (b[1][0] + b[1][1]) - (a[1][0] + a[1][1])).slice(0, 12).map(([k, v]) => `${k} ${v[0]}/${v[0] + v[1]}`).join('  ');
    if (bq) console.log('  частые:', bq);
    const all = isos.map(k => [k, ENGINE.unpackC(h.cs[k])]);
    const ext = (f) => all.reduce((a, b) => f(b[1]) > f(a[1]) ? b : a);
    console.log('  крайности: max π', ext(s => s.pi)[0], ext(s => s.pi)[1].pi.toFixed(1), '| min π', ext(s => -s.pi)[0], ext(s => -s.pi)[1].pi.toFixed(1), '| max D', ext(s => s.D)[0], ext(s => s.D)[1].D.toFixed(0), '| max u', ext(s => s.u)[0], ext(s => s.u)[1].u.toFixed(1), '| min W', ext(s => -s.W)[0], ext(s => -s.W)[1].W.toFixed(1));
    if (loc) { const L = Object.keys(h.ls).map(k => ENGINE.unpackL(h.ls[k])); const Ps = L.map(l => l.P / 1); console.log('  места:', L.length, 'W от', Math.min(...L.map(l => l.W)).toFixed(1), 'до', Math.max(...L.map(l => l.W)).toFixed(1), '| B max', Math.max(...L.map(l => l.B)).toFixed(0)); }
  }
}
