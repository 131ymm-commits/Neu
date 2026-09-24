const { chromium } = require('playwright');
const http = require('http'), fs = require('fs');
const srv = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); fs.createReadStream('/tmp/game/preview.html').pipe(res); }).listen(8765);
const mock = fs.readFileSync('/tmp/game/mock_claude.js', 'utf8');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 820 } });
  await ctx.addInitScript(mock);
  await ctx.route('**/fonts.g*/**', r => r.abort());
  const errs = [];
  async function open(uid) {
    const p = await ctx.newPage();
    p.on('pageerror', e => errs.push(uid + ' PAGEERROR ' + e.message));
    p.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !/ERR_FAILED|fonts/.test(m.text())) errs.push(uid + ' ' + m.type() + ': ' + m.text()); });
    await p.goto('http://localhost:8765/?uid=' + uid);
    await p.waitForFunction(() => typeof M !== 'undefined' && M.ready && game(), null, { timeout: 30000 });
    await p.evaluate(() => { try { localStorage.setItem('ef-welcome', '1'); } catch (e) {} closeDialog(); });
    return p;
  }
  const A = await open('u_alice');
  const B = await open('u_bob');
  const st = p => p.evaluate(() => ({ year: curYear(), remote: B.remote, actor: ACT.id, name: nameOf(ACT.id), places: Object.keys(M.c.places).length, patches: Object.keys(M.c.patches).length }));
  console.log('Алиса:', JSON.stringify(await st(A))); console.log('Борис:', JSON.stringify(await st(B)));
  // Алиса берёт Россию
  await A.evaluate(() => claim('C:RUS')); await A.waitForTimeout(300);
  // Борис пытается взять Россию
  await B.waitForTimeout(200);
  await B.evaluate(() => claim('C:RUS')); await B.waitForTimeout(300);
  console.log('владелец России:', await B.evaluate(() => nameOf(ownerOf('C:RUS'))), '| тост Бориса:', await B.$eval('#toast', e => e.textContent));
  // Борис берёт Казахстан, пишет патч и принимает
  await B.evaluate(() => claim('C:KAZ')); await B.waitForTimeout(300);
  const pid = await B.evaluate(() => createPatch({ tax: 1, invest: 1 }, 'W', 3, 'Вложения за счёт налогов').then(d => d && d.pid));
  await B.waitForTimeout(200);
  await B.evaluate(p => adopt('C:KAZ', p), pid); await B.waitForTimeout(300);
  // Алиса видит патч и принимает его в России
  await A.waitForTimeout(300);
  console.log('Алиса видит патч:', await A.evaluate(p => !!M.c.patches[p], pid));
  await A.evaluate(p => adopt('C:RUS', p), pid); await A.waitForTimeout(300);
  // Алиса считает год
  await A.evaluate(() => advanceYear()); await A.waitForTimeout(800);
  console.log('после хода: Алиса', await A.evaluate(() => curYear()), '| Борис', await B.evaluate(() => curYear()));
  // Борис сразу пытается — пауза
  await B.evaluate(() => advanceYear()); await B.waitForTimeout(300);
  console.log('Борис сразу после: год', await B.evaluate(() => curYear()), '| тост:', await B.$eval('#toast', e => e.textContent));
  // ещё три года с паузами
  for (let i = 0; i < 3; i++) { await A.waitForTimeout(15500); await (i % 2 ? A : B).evaluate(() => advanceYear()); await A.waitForTimeout(900); }
  const res = await B.evaluate(() => ({ year: curYear(), rus: rulesOf('C:RUS'), kaz: rulesOf('C:KAZ'), stats: M.c.meta.pstats, done: Object.keys(M.Y).map(y => [y, ((M.Y[y].C || {}).done || []).map(d => d.key + ':' + d.ok + ':' + d.d[d.metric])]), series: Object.keys((M.c.meta.series || {}).f || {}) }));
  console.log(JSON.stringify(res));
  // одновременный ход обоих
  await A.waitForTimeout(15500);
  await Promise.all([A.evaluate(() => advanceYear()), B.evaluate(() => advanceYear())]); await A.waitForTimeout(1200);
  console.log('одновременный ход → год', await A.evaluate(() => curYear()), await B.evaluate(() => curYear()));
  // вкладки в общем режиме
  for (const v of ['patches', 'log', 'compare', 'help', 'map']) { await B.click(`.tab[data-v=${v}]`); await B.waitForTimeout(500); if (v !== 'map') await B.screenshot({ path: `/tmp/game/shots/mp-${v}.png` }); }
  await B.evaluate(() => { select('C:KAZ'); zoomToKey('C:KAZ'); }); await B.waitForTimeout(1200);
  await B.screenshot({ path: '/tmp/game/shots/mp-kaz.png' });
  // выгрузка CSV
  await B.evaluate(() => exportCSV()); await B.waitForTimeout(200);
  const saved = await B.evaluate(() => window.__saved ? { f: window.__saved.filename, n: window.__saved.data.split('\n').length, head: window.__saved.data.split('\n').slice(0, 3).join(' | ') } : null);
  console.log('CSV:', JSON.stringify(saved).slice(0, 400));
  // сброс мира владельцем (после истечения аренды хода)
  await A.waitForTimeout(13000);
  await A.evaluate(() => resetWorld()); await A.waitForTimeout(2500);
  console.log('после сброса: Алиса год', await A.evaluate(() => curYear()), 'мест', await A.evaluate(() => Object.keys(M.c.places).length), '| Борис год', await B.evaluate(() => curYear()), 'мест', await B.evaluate(() => Object.keys(M.c.places).length));
  console.log('ошибки:', errs.length ? errs.join('\n') : 'нет');
  await browser.close(); srv.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e.message); process.exit(1); });
