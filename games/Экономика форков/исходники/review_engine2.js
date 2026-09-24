const SIM = require('./sim.js'), ENGINE = require('./engine.js');
const C = require('./build/countries.json');
const countries = {}; Object.values(C).forEach(c => { countries[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0, pg: c.pg }; });
// Тень села, которое стало активным в том же году, когда приняло патч; у родителя своё решение по тому же вопросу
let h = ENGINE.initialHistory(countries, 2026, 9);
const par = { 'P:par': { cc: 'RUS', pop: 500000, parent: null } };
const rules = { 'P:par': { social: { pid: 'pp', opt: 1, since: 2020 } } };
let r = ENGINE.step(h, countries, par, rules, {}); h = r.hist;               // 2027: родитель «поддержка ↑», села ещё нет
const locals = Object.assign({ 'U:kid': { cc: 'RUS', pop: 800, parent: 'P:par' } }, par);
rules['U:kid'] = { social: { pid: 'k1', opt: -1, since: h.year, m: 'W', h: 2 } };  // село добавлено в 2027 и сразу «поддержка ↓»
r = ENGINE.step(h, countries, locals, rules, { k1: { ch: { social: -1 }, metric: 'W', horizon: 2 } }); h = r.hist;
const k = h.chk.find(c => c.key === 'U:kid');
console.log('село стало активным и приняло патч в том же году: prev в проверке =', JSON.stringify(k && k.prev), '(без патча было бы унаследованное +1)');
// то же, но село было активным годом раньше
let h2 = ENGINE.initialHistory(countries, 2026, 9);
const rules2 = { 'P:par': { social: { pid: 'pp', opt: 1, since: 2020 } } };
r = ENGINE.step(h2, countries, locals, rules2, {}); h2 = r.hist;
rules2['U:kid'] = { social: { pid: 'k1', opt: -1, since: h2.year, m: 'W', h: 2 } };
r = ENGINE.step(h2, countries, locals, rules2, { k1: { ch: { social: -1 }, metric: 'W', horizon: 2 } }); h2 = r.hist;
const k2 = h2.chk.find(c => c.key === 'U:kid');
console.log('село было активно годом раньше: prev =', JSON.stringify(k2 && k2.prev));
// Откат села при наследуемом значении: что записывается в правило
for (let i = 0; i < 2; i++) { r = ENGINE.step(h2, countries, locals, rules2, { k1: { ch: { social: -1 }, metric: 'W', horizon: 2 } }); h2 = r.hist; if (r.reverts.length) { console.log('откат:', JSON.stringify(r.reverts)); ENGINE.applyReverts(rules2, r.reverts, h2.year); console.log('правило села после отката:', JSON.stringify(rules2['U:kid']), '— закреплено +1, а не «наследовать у родителя»'); } }
console.log('итоги:', JSON.stringify(h2.done.map(d => [d.key, d.ok, d.d.W])));
