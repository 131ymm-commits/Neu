// Города и сёла GeoNames (cities1000: ≥1000 жителей или центры районов). Для RU, BY, KZ, KG — кириллическое имя.
const fs = require('fs');
const countries = require('/tmp/game/build/countries.json');
const byA2 = {}; Object.values(countries).forEach(c => { byA2[c.iso2] = c.iso3; });
const SKIP = new Set(['PPLX', 'PPLH', 'PPLQ', 'PPLW', 'PPLCH']);
const CYR = new Set(['RU', 'BY', 'KZ', 'KG']);
const T = { а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'kh', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch', ъ: '', ы: 'y', ь: "'", э: 'e', ю: 'yu', я: 'ya' };
const VOW = new Set('аеёиоуыэюяьъ'.split(''));
function translit(s) {
  s = s.toLowerCase(); let o = '';
  for (let i = 0; i < s.length; i++) {
    const ch = s[i], pr = i ? s[i - 1] : ' ';
    const start = !/[а-яё]/.test(pr) || VOW.has(pr);
    if (ch === 'е') o += start ? 'ye' : 'e';
    else if (ch === 'ё') o += start ? 'yo' : 'e';
    else if (T[ch] !== undefined) o += T[ch]; else o += ch;
  }
  return o;
}
const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[’ʹ′`´]/g, "'").replace(/["”ʺ]/g, '');
function lev(a, b) {
  const m = a.length, n = b.length; if (!m) return n; if (!n) return m;
  let p = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) { const c = [i]; for (let j = 1; j <= n; j++) c[j] = Math.min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); p = c; }
  return p[n];
}
const RUONLY = /^[А-Яа-яЁё0-9 \-.()«»]+$/;
const EXO = { 524901: 'Москва', 498817: 'Санкт-Петербург', 2051523: 'Братск', 2014407: 'Улан-Удэ', 2019951: 'Мирный', 536206: 'Юбилейный', 526480: 'Минеральные Воды', 2122104: 'Петропавловск-Камчатский' };
const ISO = { а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'z', з: 'z', и: 'i', й: 'j', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'c', ч: 'c', ш: 's', щ: 'sc', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'ju', я: 'ja' };
const iso9 = s => s.toLowerCase().split('').map(ch => ISO[ch] !== undefined ? ISO[ch] : ch).join('');
const plain = s => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[’ʹ′`´'"”ʺ]/g, '');
// апостроф в конце слова GeoNames часто опускает («Kazan» = «Казань»), внутри слова — нет («Ul’yanovsk»)
const keyN = s => norm(s).replace(/'(?=$|[ -])/g, '');
function cyrName(id, name, ascii, alts) {
  if (EXO[id]) return EXO[id];
  const all = alts ? alts.split(',') : [];
  const cands = all.filter(a => RUONLY.test(a) && /[А-Яа-яЁё]/.test(a));
  if (!cands.length) return null;
  const latinA = new Set(all.filter(a => /[a-z]/i.test(a) && !/[А-Яа-яЁё]/.test(a)).map(norm).concat([norm(name), norm(ascii)]));
  const latinP = new Set([...latinA].map(x => x.replace(/'/g, '')));
  const strip = x => x.replace(/'/g, '');
  const T1 = strip(norm(name)), T2 = strip(norm(ascii)), nameKey = keyN(name);
  let best = null, bs = null;
  for (const c of cands) {
    const tA = norm(translit(c)), t = strip(tA);
    const d = Math.min(lev(t, T1), lev(t, T2));
    let adj = 0;
    if (/ь/i.test(c) && latinA.has(tA)) adj -= 0.3;      // мягкий знак подтверждён латинским двойником: Kazan', Noril'sk
    if (/ё/i.test(c)) adj -= 0.3;
    if (/(ськ|цьк|ець|ський|ъ|ски|ней|най|ние)(?=$|[ -])/i.test(c) || /ъ[^еёюя]/i.test(c) || /шч/i.test(c)) adj += 0.6;
    if (/[^ -]э/i.test(c)) adj += 0.1;
    if (/[нм]ь[сн]/i.test(c)) adj += 0.6;
    const twins = new Set([t, iso9(c)].filter(x => latinP.has(x))).size;
    const sc = [d + adj, -twins, /ц/i.test(c) ? 0 : 1, keyN(translit(c)) === nameKey ? 0 : 1];
    let better = !bs;
    for (let i = 0; !better && i < sc.length; i++) { if (sc[i] < bs[i]) better = true; else if (sc[i] > bs[i]) break; }
    if (better) { bs = sc; best = c; bs.d = d; }
  }
  return bs.d <= Math.max(2, Math.ceil(0.34 * T1.length)) ? best : null;
}
const AMB = [];
const rows = fs.readFileSync('/tmp/geo2/s/dist/cities1000.txt', 'utf8').split('\n');
const per = {}; let n = 0, cyrHit = 0, cyrTot = 0, skipped = 0;
for (const line of rows) {
  if (!line) continue;
  const f = line.split('\t');
  const [id, name, ascii, alts, lat, lon, fcl, fco, cc] = f; const popu = +f[14] || 0;
  if (fcl !== 'P' || SKIP.has(fco)) { skipped++; continue; }
  const iso3 = byA2[cc]; if (!iso3) { skipped++; continue; }
  let nm = name;
  if (CYR.has(cc)) { cyrTot++; const c = cyrName(+id, name, ascii, alts); if (c) { nm = c; cyrHit++; } }
  nm = nm.replace(/[|\n\t]/g, ' ');
  if (/^(Gorod|Horad|Город|Горад|Qala|Shahri) /i.test(nm) || /^(Gorod|Horad) /.test(name)) { skipped++; continue; }
  const cap = fco === 'PPLC' ? 2 : /^PPLA$/.test(fco) ? 1 : 0;
  (per[iso3] = per[iso3] || []).push([(+id).toString(36), nm, +(+lon).toFixed(3), +(+lat).toFixed(3), popu, cap]);
  n++;
}
Object.values(per).forEach(a => a.sort((x, y) => y[4] - x[4] || y[5] - x[5]));
if (process.env.AMB) { const popOf = {}; rows.forEach(l => { const f = l.split('\t'); popOf[f[0]] = +f[14]; }); AMB.filter(a => popOf[a[0]] >= 20000).sort((a, b) => popOf[b[0]] - popOf[a[0]]).forEach(a => console.log(a[0], a[1], popOf[a[0]], '→', a[2], '|', a[3])); }
console.log('мест:', n, 'пропущено:', skipped, 'кириллица:', cyrHit, '/', cyrTot);
// компактная строка на страну: id|имя|lon|lat|pop|cap ; строки через \n
const out = {}; let bytes = 0;
for (const [k, a] of Object.entries(per)) { out[k] = a.map(r => r.join('|')).join('\n'); bytes += out[k].length; }
fs.writeFileSync('/tmp/game/build/places.json', JSON.stringify(out));
console.log('байт (строки):', bytes);
for (const k of ['RUS', 'BLR', 'KAZ', 'KGZ']) console.log(k, per[k].length, per[k].slice(0, 12).map(r => r[1]).join(', '), '…', per[k].slice(-6).map(r => r[1]).join(', '));
console.log('USA', per.USA.length, 'CHN', per.CHN.length, 'IND', per.IND.length, 'DEU', per.DEU.length, 'ITA', per.ITA.length, 'FRA', per.FRA.length);
