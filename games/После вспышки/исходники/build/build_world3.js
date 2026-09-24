// Данные для модели «после вспышки»: из калиброванного мира второй версии + координаты столиц
const fs = require('fs');
const w = JSON.parse(fs.readFileSync('/tmp/game2/build/world_cal2.json', 'utf8'));
const countries = JSON.parse(fs.readFileSync('/tmp/game/build/countries.json', 'utf8'));
const places = JSON.parse(fs.readFileSync('/tmp/game/build/places.json', 'utf8'));
const S = w.S, iAGR = S.indexOf('AGR'), iFOD = S.indexOf('FOD'), iFUE = S.indexOf('FUE'), iENR = S.indexOf('ENR');
// геомагнитная широта: дипольное приближение, полюс 80,7° с. ш., 72,7° з. д. (IGRF-13, 2020)
const R = Math.PI / 180, LP = 80.7 * R, LNP = -72.7 * R;
function gmlat(lat, lon) { const a = lat * R, b = lon * R; return Math.asin(Math.sin(a) * Math.sin(LP) + Math.cos(a) * Math.cos(LP) * Math.cos(b - LNP)) / R; }
// столица (cap=2) или крупнейшее место
function capital(iso) {
  const s = places[iso]; if (!s) return null;
  let best = null;
  for (const line of s.split('\n')) { const f = line.split('|'); const p = { name: f[1], lon: +f[2], lat: +f[3], pop: +f[4], cap: +f[5] }; if (p.cap === 2) return p; if (!best || p.pop > best.pop) best = p; }
  return best;
}
// заводы силовых трансформаторов: доли мирового выпуска (оценка по отраслевым обзорам; см. страницу «Что известно»)
const FACT = { CHN: 0.34, IND: 0.09, DEU: 0.07, KOR: 0.07, JPN: 0.06, USA: 0.06, SWE: 0.03, BRA: 0.03, TUR: 0.03, ITA: 0.03, ESP: 0.02, MEX: 0.02, CAN: 0.02, RUS: 0.02, FRA: 0.02, POL: 0.01, CZE: 0.01, AUT: 0.01, IDN: 0.01, VNM: 0.01, EGY: 0.01, ZAF: 0.01, IRN: 0.01, AUS: 0.005, GBR: 0.005, HUN: 0.005, ROU: 0.005, THA: 0.005, MYS: 0.005, COL: 0.005 };
// космические державы: восстановление спутниковой связи
const SPACE = ['USA', 'CHN', 'RUS', 'IND', 'JPN', 'FRA', 'DEU', 'GBR', 'ITA', 'KOR', 'NZL', 'ISR'];
const out = { v: 1, iso: [], countries: [], fact: FACT, space: SPACE };
let miss = 0;
w.iso.forEach((iso, i) => {
  const c = w.countries[i], cc = countries[iso] || {};
  const cap = capital(iso); if (!cap) miss++;
  const lat = cap ? cap.lat : 0, lon = cap ? cap.lon : 0;
  const X = c.X, E = c.E, M = c.M, C = c.C;
  const foodOut = X[iAGR] + X[iFOD], foodUse = Math.max(1e-6, foodOut - E[iAGR] - E[iFOD] + M[iAGR] + M[iFOD]);
  const fuelOut = X[iFUE], fuelUse = Math.max(1e-6, fuelOut - E[iFUE] + M[iFUE]);
  const L = c.L.reduce((a, b) => a + b, 0);
  out.iso.push(iso);
  out.countries.push({
    iso, ru: cc.ru || iso, P: c.P / 1e6, gdp: c.gdp, lat: +lat.toFixed(2), lon: +lon.toFixed(2), gm: +gmlat(lat, lon).toFixed(1),
    foodSS: +Math.min(3, foodOut / foodUse).toFixed(3), fuelSS: +Math.min(6, fuelOut / fuelUse).toFixed(3),
    fuelUse: +fuelUse.toFixed(2), foodUse: +foodUse.toFixed(2), L: +L.toFixed(3), enr: +(X[iENR] || 0).toFixed(1), cap: cap ? cap.name : null
  });
});
fs.writeFileSync('/tmp/game3/build/world3.json', JSON.stringify(out));
const t = out.countries;
console.log('стран', t.length, '; без столицы', miss, '; пример', JSON.stringify(t[out.iso.indexOf('DEU')]));
console.log('геомагн. широта: CAN', t[out.iso.indexOf('CAN')].gm, 'SWE', t[out.iso.indexOf('SWE')].gm, 'BRA', t[out.iso.indexOf('BRA')].gm, 'IDN', t[out.iso.indexOf('IDN')].gm, 'ZAF', t[out.iso.indexOf('ZAF')].gm, 'RUS', t[out.iso.indexOf('RUS')].gm);
console.log('еда: USA', t[out.iso.indexOf('USA')].foodSS, 'EGY', t[out.iso.indexOf('EGY')].foodSS, 'JPN', t[out.iso.indexOf('JPN')].foodSS, 'UKR', t[out.iso.indexOf('UKR')].foodSS, '; топливо: SAU', t[out.iso.indexOf('SAU')].fuelSS, 'DEU', t[out.iso.indexOf('DEU')].fuelSS, 'JPN', t[out.iso.indexOf('JPN')].fuelSS);
console.log('доли заводов в сумме', Object.values(FACT).reduce((a, b) => a + b, 0).toFixed(3));
