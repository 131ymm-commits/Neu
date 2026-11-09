// Проверка ключевых слов банка на отчётах пилота: отчёты пилота написаны о пилотных копиях, тестовых багов в них нет.
// Поэтому совпадение «категория + ключевые слова» тестового бага с отчётом пилота — кандидат в ложное засчитывание.
//   node kw_check.js <банк.js> <session.json>... [--out файл]
const fs = require('fs'), path = require('path'), { matchText, kwMatch } = require('./score');
const a = process.argv.slice(2), out = a.includes('--out') ? a[a.indexOf('--out') + 1] : null;
const files = a.filter((x, i) => x.endsWith('.json') && a[i - 1] !== '--out');
const spec = require(path.resolve(a[0]));
const reps = files.flatMap(f => { const s = JSON.parse(fs.readFileSync(f, 'utf8')); return (s.reports || []).map(r => ({ arm: s.arm, r })); });
const res = [];
for (const cp of [...spec.copies, ...(a.includes('--pilot') ? spec.pilot || [] : [])]) for (const b of cp.bugs) {
  const groups = Array.isArray(b.kw) ? b.kw : [b.kw];
  const hits = reps.filter(({ r }) => b.cat.includes(r.category) && kwMatch(b, matchText(r))).map(({ arm, r }) => ({ arm, cat: r.category, title: r.title, kw: groups.map(g => (matchText(r).match(new RegExp(g, 'i')) || [])[0]).join(' + ') }));
  res.push({ copy: cp.id, bug: b.id, hits: hits.length, of: reps.length, examples: hits });
}
const s = JSON.stringify({ reports: reps.length, bugs: res }, null, 1); if (out) fs.writeFileSync(out, s);
for (const x of res) console.log(x.copy, x.bug, `${x.hits}/${x.of}`, x.examples.map(e => `[${e.arm} «${e.kw}»] ${e.title.slice(0, 70)}`).join(' | '));
