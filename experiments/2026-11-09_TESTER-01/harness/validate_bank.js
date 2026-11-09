// Проверка банка: для каждой копии собрать мутант; эталонный сценарий каждого бага прогнать на мутанте и на чистой копии;
// детектор бага должен сработать на мутанте и молчать на чистой; заодно — какие детекторы копии срабатывают (перекрёстные).
//   node validate_bank.js <спецификация.js> [--out <каталог мутантов>] [--only B3]
const fs = require('fs'), path = require('path');
const T = require('./bank_tools');
(async () => {
  const spec = require(path.resolve(process.argv[2])); const out = process.argv.includes('--out') ? process.argv[process.argv.indexOf('--out') + 1] : null;
  const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;
  const clean = fs.readFileSync(spec.clean, 'utf8'); const res = [];
  for (const cp of [...spec.copies, ...(spec.pilot || [])]) {
    const html = T.makeMutant(clean, cp.bugs.map(b => ({ id: b.id, find: b.find, replace: b.replace })));
    const mfile = path.join(out || '/tmp/claude-0', `${spec.game}_${cp.id}.html`); fs.mkdirSync(path.dirname(mfile), { recursive: true }); fs.writeFileSync(mfile, html);
    const dets = cp.bugs.map(b => [b.id, T.detectorFn(b.det)]);
    for (const b of cp.bugs) {
      if (only && b.id !== only) continue;
      const fire = run => run.map((s, i) => dets.filter(([, d]) => { try { return d(s.truth, i ? run[i - 1].truth : null, s.act || {}); } catch (e) { return false; } }).map(([id]) => id));
      const m = await T.runMacro(mfile, b.ref), c = await T.runMacro(spec.clean, b.ref);
      const fm = fire(m), fc = fire(c), hitM = fm.some(f => f.includes(b.id)), hitC = fc.some(f => f.includes(b.id));
      const miss = [...m, ...c].filter(s => s.error).map(s => s.error);
      res.push({ copy: cp.id, bug: b.id, mutant: hitM, clean: hitC, ok: hitM && !hitC, firstStep: fm.findIndex(f => f.includes(b.id)), crossM: [...new Set(fm.flat())].filter(x => x !== b.id), crossC: [...new Set(fc.flat())], miss: [...new Set(miss)] });
      console.log(JSON.stringify(res[res.length - 1]));
    }
    console.log(`копия ${cp.id}: sha256 ${T.sha(html).slice(0, 16)}… → ${mfile}`);
  }
  console.log('итог:', res.filter(r => r.ok).length, 'из', res.length, 'багов подтверждены');
})();
