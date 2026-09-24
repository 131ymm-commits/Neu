const SIM = require('./sim.js'), ENGINE = require('./engine.js');
const C = require('./build/countries.json');
const countries = {}; Object.values(C).forEach(c => { countries[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0, pg: c.pg }; });
let h = ENGINE.initialHistory(countries, 2026, 7);
const patches = { P: { ch: { rate: 1 }, metric: 'W', horizon: 1 } };
const rules = { 'C:DEU': { rate: { pid: 'P', opt: 1, since: 2026, m: 'W', h: 1 } } };
let r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
console.log('2027 проверки завершены:', h.done.map(d => d.key + ' ok=' + d.ok), 'откаты:', r.reverts.length, 'rp:', JSON.stringify(h.rp['C:DEU']), 'copt DEU:', h.copt.DEU.join(','));
ENGINE.applyReverts(rules, r.reverts, h.year);
console.log('правила после отката:', JSON.stringify(rules['C:DEU'] || {}));
// тот же патч принят снова в том же году
rules['C:DEU'] = { rate: { pid: 'P', opt: 1, since: 2027, m: 'W', h: 1 } };
r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
console.log('2028: проверка повторного принятия:', h.done.map(d => d.key + ' ok=' + d.ok + ' prev=' + d.prev), '| живых:', h.chk.length);
// решение с устаревшим since (записано во время расчёта)
rules['C:FRA'] = { invest: { pid: 'Q', opt: 1, since: 2026, m: 'y', h: 2 } }; patches.Q = { ch: { invest: 1 }, metric: 'y', horizon: 2 };
r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
console.log('2029: живые проверки:', h.chk.map(k => k.key + ':' + k.pid + ' до ' + k.due));
// частичное снятие: патч из двух вопросов, один снят
rules['C:ITA'] = { tax: { pid: 'R', opt: 1, since: 2029, m: 'D', h: 3 }, invest: { pid: 'R', opt: 1, since: 2029, m: 'D', h: 3 } }; patches.R = { ch: { tax: 1, invest: 1 }, metric: 'D', horizon: 3 };
r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
rules['C:ITA'].invest = null;
r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
console.log('2031: проверка ITA после частичного снятия жива:', h.chk.some(k => k.key === 'C:ITA'));
// село с родителем: «было» берётся у родителя
const locals = { 'P:1': { cc: 'RUS', pop: 100000, parent: null } };
rules['P:1'] = { social: { pid: 'S', opt: 1, since: 2031, m: 'W', h: 2 } }; patches.S = { ch: { social: 1 }, metric: 'W', horizon: 2 };
r = ENGINE.step(h, countries, locals, rules, patches); h = r.hist;
locals['U:v'] = { cc: 'RUS', pop: 300, parent: 'P:1' };
rules['U:v'] = { social: { pid: 'T', opt: -1, since: 2032, m: 'W', h: 1 } }; patches.T = { ch: { social: -1 }, metric: 'W', horizon: 1 };
r = ENGINE.step(h, countries, locals, rules, patches); h = r.hist;
console.log('2033: село — прежний вариант у тени:', JSON.stringify(h.done.filter(d => d.key === 'U:v').map(d => d.prev)), '(должно быть [1] — унаследовано от родителя)');
