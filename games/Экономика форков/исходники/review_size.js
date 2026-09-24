const { chromium } = require('playwright');
const http = require('http'), fs = require('fs');
const srv = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); fs.createReadStream('/tmp/game/ekonomika-forkov.html').pipe(res); }).listen(8767);
const mock = fs.readFileSync('/tmp/game/mock_claude.js', 'utf8');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 820 } });
  await ctx.addInitScript(mock); await ctx.route('**/fonts.g*/**', r => r.abort());
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
  await p.goto('http://localhost:8767/?uid=u_alice');
  await p.waitForFunction(() => typeof M !== 'undefined' && M.ready && game(), null, { timeout: 30000 });
  await p.evaluate(() => closeDialog());
  // у каждой страны 5 решений из 5 разных патчей, принятых в этом году
  await p.evaluate(async () => {
    const qs = ['rate', 'tariff', 'tax', 'invest', 'social'];
    for (const iso of Object.keys(ECON)) {
      const rules = {}; qs.forEach((q, i) => { rules[q] = { pid: (iso + i).toLowerCase().padEnd(7, 'x').slice(0, 7), opt: 1, since: curYear(), m: 'W', h: 5, by: 'u_alice' }; });
      await DB.doc('places/C:' + iso).set({ key: 'C:' + iso, kind: 'C', cc: iso, owner: 'u_alice', rules });
    }
  });
  await p.waitForTimeout(500);
  await p.evaluate(() => advanceYear()); await p.waitForTimeout(800);
  const r = await p.evaluate(async () => ({ year: curYear(), canWrite: M.me.canWrite, toast: $('#toast').textContent, banner: $('#banner').textContent,
    h27: (await DB.doc('hist/2027').get()).exists, l27: (await DB.doc('histl/2027').get()).exists, c27: (await DB.doc('histc/2027').get()).exists, btn: $('#nextYear').disabled }));
  console.log(JSON.stringify(r, null, 1));
  console.log('ошибки:', errs.length ? errs.join('\n') : 'нет');
  await browser.close(); srv.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
