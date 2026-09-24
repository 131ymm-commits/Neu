// Сборка стран: Всемирный банк (последние значения) + контуры world-atlas + русские названия CLDR.
const fs = require('fs');
const iso = require('/tmp/game/build/iso.json');
const t50 = require('/tmp/geo/node_modules/world-atlas/countries-50m.json');
const cldr = require('/tmp/geo/node_modules/cldr-localenames-modern/main/ru/territories.json').main.ru.localeDisplayNames.territories;
const wb = {};
for (const f of ['growth', 'inflation', 'unemployment', 'gdppc']) {
  for (const line of fs.readFileSync('/tmp/econ/wb/' + f + '.csv', 'utf8').trim().split(/\r?\n/)) {
    const [a3, yr, v] = line.split(','); (wb[a3] = wb[a3] || {})[f] = [+yr, +v];
  }
}
const pop = {}, popAll = {};
for (const line of fs.readFileSync('/tmp/econ/wb/population_mirror.csv', 'utf8').trim().split(/\r?\n/).slice(1)) {
  const m = line.match(/,([A-Z0-9]{3}),(\d{4}),([\d.]+)$/); if (!m) continue;
  const [, a3, yr, v] = m; (popAll[a3] = popAll[a3] || {})[+yr] = +v; if (!pop[a3] || +yr > pop[a3][0]) pop[a3] = [+yr, +v];
}
const RU = { US: 'США', KR: 'Южная Корея', CD: 'ДР Конго', CG: 'Республика Конго', MM: 'Мьянма', HK: 'Гонконг', MO: 'Макао',
  CF: 'ЦАР', PS: 'Палестина', FK: 'Фолклендские острова', BA: 'Босния и Герцеговина', VC: 'Сент-Винсент и Гренадины',
  KN: 'Сент-Китс и Невис', TC: 'Тёркс и Кайкос', VG: 'Британские Виргинские острова', VI: 'Виргинские острова (США)',
  MP: 'Северные Марианские острова', UM: 'Внешние малые острова США' };
// особые случаи без данных ВБ
const EXTRA = {
  TWN: { a2: 'TW', P: [2022, 23196178], y: [2026, 42103], g0: [2025, 8.68], u0: [2025, 3.35], pi0: [2025, 1.66],
    note: 'данных ВБ нет; рост 8,68% (2025) — DGBAS; ВВП на душу 42 103 $ — оценка на 2026; безработица 3,35% (2025); инфляция 1,66% (апрель 2025); население — май 2022' },
  PRK: { a2: 'KP', y: [2024, 1260], g0: [2024, 3.7],
    note: 'данных ВБ о ВВП нет; рост 3,7% (2024) и ВНД на душу 1,72 млн вон (≈1 260 $) — оценка Банка Кореи; инфляция — условно' }
};
const NOID = { 'Kosovo': 'XKX', 'Somaliland': 'SOM', 'N. Cyprus': 'CYP' };
const A2 = { XKX: 'XK' };
const out = {}, geomToIso = {}, gray = [];
// сначала геометрии с кодом ISO, потом без кода (Косово, Сомалиленд, Северный Кипр) — чтобы запись страны создавалась по её собственной геометрии
const geoms = t50.objects.countries.geometries.slice().sort((a, b) => (a.id == null) - (b.id == null));
for (const g of geoms) {
  let a3 = g.id != null && iso[g.id] ? iso[g.id].a3 : NOID[g.properties.name];
  const key = g.id != null ? g.id : g.properties.name;
  if (!a3) { gray.push(g.properties.name); continue; }
  const w = wb[a3] || {}, ex = EXTRA[a3] || {};
  const P = pop[a3] || ex.P, y = w.gdppc || ex.y;
  if (!P || !y) { gray.push(g.properties.name + ' (' + a3 + ')'); continue; }
  geomToIso[key] = a3;
  if (out[a3]) continue;
  const a2 = (iso[g.id] && iso[g.id].a2) || A2[a3] || ex.a2;
  const gr = w.growth || ex.g0, inf = w.inflation || ex.pi0, un = w.unemployment || ex.u0;
  out[a3] = { iso3: a3, iso2: a2, ru: RU[a2] || cldr[a2] || g.properties.name,
    P: Math.round(P[1]), y: Math.round(y[1]), g0: gr ? +gr[1].toFixed(2) : null, pi0: inf ? +inf[1].toFixed(2) : null, u0: un ? +un[1].toFixed(2) : null,
    yr: [P[0], y[0], gr ? gr[0] : 0, inf ? inf[0] : 0, un ? un[0] : 0], note: ex.note || '',
    pg: (() => { const A = popAll[a3]; if (!A) return null; const ys = Object.keys(A).map(Number).sort((a, b) => b - a); const y1 = ys[0], y0 = y1 - 5; if (!A[y0]) return null; return +((Math.pow(A[y1] / A[y0], 1 / 5) - 1) * 100).toFixed(2); })() };
}
fs.writeFileSync('/tmp/game/build/countries.json', JSON.stringify(out));
fs.writeFileSync('/tmp/game/build/geom_iso.json', JSON.stringify(geomToIso));
console.log('страны:', Object.keys(out).length, 'серые:', gray.length, gray.join('; '));
const miss = k => Object.values(out).filter(c => c[k] == null).map(c => c.iso3);
console.log('без роста:', miss('g0').join(' ')); console.log('без инфляции:', miss('pi0').join(' ')); console.log('без безработицы:', miss('u0').join(' '));
const yrs = {}; Object.values(out).forEach(c => c.yr.forEach((v, i) => { const k = i + ':' + v; yrs[k] = (yrs[k] || 0) + 1; }));
console.log('годы (поле:год → число):', JSON.stringify(yrs));
for (const k of ['RUS', 'USA', 'CHN', 'DEU', 'IND', 'TWN', 'PRK', 'XKX', 'ARG', 'TUR']) console.log(JSON.stringify(out[k]));
