// Временная проверка движка (ревью). Ничего не меняет в игре.
const SIM = require('./sim.js'), ENGINE = require('./engine.js');
const C = require('./build/countries.json');
const countries = {}; Object.values(C).forEach(c => { countries[c.iso3] = { iso3: c.iso3, P: c.P, y: c.y, g0: c.g0, pi0: c.pi0, u0: c.u0, pg: c.pg }; });
const log = (...a) => console.log(...a);
// ── 1. Повторное принятие того же патча сразу после отката: создаётся ли проверка?
{
  let h = ENGINE.initialHistory(countries, 2026, 7);
  const patches = { bad: { ch: { social: -1 }, metric: 'W', horizon: 1 } };
  const rules = { 'C:RUS': { social: { pid: 'bad', opt: -1, since: 2026, m: 'W', h: 1 } } };
  let r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
  log('1) год', h.year, 'итог проверки:', JSON.stringify(h.done.map(d => [d.key, d.pid, d.ok, d.d.W])), 'откаты:', r.reverts.length);
  ENGINE.applyReverts(rules, r.reverts, h.year);
  log('   правило после отката:', JSON.stringify(rules['C:RUS']));
  // управляющий в том же 2027 году снова принимает тот же патч
  rules['C:RUS'] = { social: { pid: 'bad', opt: -1, since: h.year, m: 'W', h: 1 } };
  r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
  log('   после повторного принятия: год', h.year, 'проверок в работе', h.chk.length, 'завершено', h.done.length, '→', h.chk.length + h.done.length === 0 ? 'ПРОВЕРКИ НЕТ (дыра)' : 'проверка есть');
  for (let i = 0; i < 3; i++) { r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist; }
  log('   ещё 3 года: правило', JSON.stringify(rules['C:RUS'].social), 'проверок', h.chk.length, h.done.length);
}
// ── 2. Устаревший since (клиент ещё видит прошлый год): проверка не создаётся никогда
{
  let h = ENGINE.initialHistory(countries, 2026, 3);
  let r = ENGINE.step(h, countries, {}, {}, {}); h = r.hist; // 2027
  const patches = { p1: { ch: { tax: 1 }, metric: 'W', horizon: 2 } };
  const rules = { 'C:DEU': { tax: { pid: 'p1', opt: 1, since: 2026, m: 'W', h: 2 } } }; // принят в 2027, но клиент записал since=2026
  let created = 0;
  for (let i = 0; i < 4; i++) { r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist; created += h.chk.length + h.done.length; }
  log('2) since на год меньше текущего: проверок за 4 года =', created, created ? '' : '→ патч действует без проверки');
}
// ── 3. Частичное снятие патча из двух вопросов: проверка снимается, второй вопрос живёт без проверки
{
  let h = ENGINE.initialHistory(countries, 2026, 5);
  const patches = { p2: { ch: { tax: -1, social: -1 }, metric: 'W', horizon: 3 } };
  const rules = { 'C:FRA': { tax: { pid: 'p2', opt: -1, since: 2026, m: 'W', h: 3 }, social: { pid: 'p2', opt: -1, since: 2026, m: 'W', h: 3 } } };
  let r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist;
  log('3) проверок после первого года:', h.chk.length);
  delete rules['C:FRA'].tax; // снял один вопрос
  for (let i = 0; i < 4; i++) { r = ENGINE.step(h, countries, {}, rules, patches); h = r.hist; }
  log('   после снятия одного вопроса: проверок', h.chk.length, 'итогов', h.done.length, 'правило social живо:', !!rules['C:FRA'].social);
}
// ── 4. Тень села с родителем: наследуемое решение родителя в тени не учитывается (was=0)
{
  let h = ENGINE.initialHistory(countries, 2026, 9);
  const locals = { 'P:par': { cc: 'RUS', pop: 500000, parent: null }, 'U:kid': { cc: 'RUS', pop: 800, parent: 'P:par' } };
  const rules = { 'P:par': { social: { pid: 'pp', opt: 1, since: 2025 } } };
  let r = ENGINE.step(h, countries, { 'P:par': locals['P:par'] }, rules, {}); h = r.hist; // 2027: у родителя поддержка ↑, села ещё нет
  rules['U:kid'] = { social: { pid: 'k1', opt: 0, since: h.year, m: 'W', h: 2 } }; // село добавлено и сразу «= как было»
  r = ENGINE.step(h, countries, locals, rules, { k1: { ch: { social: 0 }, metric: 'W', horizon: 2 } }); h = r.hist;
  const k = h.chk.find(c => c.key === 'U:kid');
  log('4) село: lopt', JSON.stringify(h.lopt['U:kid']), '| проверка:', k ? 'prev=' + JSON.stringify(k.prev) + ' opts=' + JSON.stringify(k.opts) : 'нет');
  log('   (без патча село унаследовало бы у родителя social=+1, а тень считается с prev=0)');
}
// ── 5. Размеры документов при большом мире: 700 мест + все страны, у всех проверки
{
  let h = ENGINE.initialHistory(countries, 2026, 11);
  const isos = Object.keys(countries), locals = {}, rules = {}, patches = {};
  for (let i = 0; i < 700; i++) locals['P:' + (1000000 + i).toString(36)] = { cc: isos[i % isos.length], pop: 5000 + i * 37, parent: null };
  const qsC = ['rate', 'tariff', 'tax', 'invest', 'social'];
  let pid = 0;
  const adoptAll = year => {
    isos.forEach(iso => { rules['C:' + iso] = {}; qsC.forEach(q => { const id = 'c' + (pid++); patches[id] = { ch: { [q]: 1 }, metric: 'W', horizon: 10 }; rules['C:' + iso][q] = { pid: id, opt: year % 2 ? 1 : -1, since: year, m: 'W', h: 10 }; }); });
    Object.keys(locals).forEach(k => { rules[k] = {}; ENGINE.LOCALQ.forEach(q => { const id = 'l' + (pid++); patches[id] = { ch: { [q]: 1 }, metric: 'W', horizon: 10 }; rules[k][q] = { pid: id, opt: year % 2 ? 1 : -1, since: year, m: 'W', h: 10 }; }); });
  };
  adoptAll(2026);
  const r = ENGINE.step(h, countries, locals, rules, patches); h = r.hist;
  const hist = { year: h.year, seed: h.seed, cs: h.cs, copt: h.copt, plan: { cs: h.plan.cs, opts: h.plan.opts }, ev: h.ev, shock: h.shock, agg: h.agg };
  const histl = { ls: h.ls, pls: h.plan.ls, lopt: h.lopt }, histc = { chk: h.chk, done: h.done };
  const kb = o => (JSON.stringify(o).length / 1024).toFixed(0) + ' КиБ';
  log('5) проверок', h.chk.length, '| hist', kb(hist), '| histl', kb(histl), '| histc', kb(histc), '| одна проверка ≈', JSON.stringify(h.chk[0]).length, 'байт');
  log('   лимит 256 КиБ: histc превышен при ≈', Math.floor(256 * 1024 / JSON.stringify(h.chk[0]).length), 'живых проверках');
}
// ── 6. Только места (без проверок): histl при 700 местах + родители
{
  let h = ENGINE.initialHistory(countries, 2026, 12);
  const isos = Object.keys(countries), locals = {};
  for (let i = 0; i < 700; i++) locals['P:' + (1000000 + i).toString(36)] = { cc: isos[i % isos.length], pop: 5000 + i * 37, parent: null };
  let r; for (let i = 0; i < 3; i++) { r = ENGINE.step(h, countries, locals, {}, {}); h = r.hist; }
  const histl = { ls: h.ls, pls: h.plan.ls, lopt: h.lopt };
  log('6) histl при 700 местах:', (JSON.stringify(histl).length / 1024).toFixed(0), 'КиБ; на место ≈', Math.round(JSON.stringify(histl).length / 700), 'байт → предел ≈', Math.floor(256 * 1024 / (JSON.stringify(histl).length / 700)), 'мест');
}
