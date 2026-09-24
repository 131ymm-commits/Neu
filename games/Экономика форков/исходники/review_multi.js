// Временная проверка общего режима (ревью): гонки и кэш. Сервер на 8766, отдельный контекст.
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs');
const srv = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); fs.createReadStream('/tmp/game/ekonomika-forkov.html').pipe(res); }).listen(8766);
const mock = fs.readFileSync('/tmp/game/mock_claude.js', 'utf8');
const skew = `(() => { const rn = Date.now.bind(Date); window.__skew = 0; Date.now = () => rn() + window.__skew; })();`;
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 820 } });
  await ctx.addInitScript(mock); await ctx.addInitScript(skew);
  await ctx.route('**/fonts.g*/**', r => r.abort());
  const errs = [];
  async function open(uid) {
    const p = await ctx.newPage();
    p.on('pageerror', e => errs.push(uid + ' PAGEERROR ' + e.message));
    p.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !/ERR_FAILED|fonts/.test(m.text())) errs.push(uid + ' ' + m.type() + ': ' + m.text()); });
    await p.goto('http://localhost:8766/?uid=' + uid);
    await p.waitForFunction(() => typeof M !== 'undefined' && M.ready && game(), null, { timeout: 30000 });
    await p.evaluate(() => { try { localStorage.setItem('ef-welcome', '1'); } catch (e) {} closeDialog(); });
    return p;
  }
  const A = await open('u_alice'), Bp = await open('u_bob');
  const adv = async () => { await A.evaluate(async () => { window.__skew += 16000; await advanceYear(); }); await A.waitForTimeout(400); };
  const toastOf = p => p.$eval('#toast', e => e.textContent);

  // (а) «Создать и принять» в общем режиме: сразу после createPatch патча может ещё не быть в M.c.patches
  const isos = ['FRA', 'DEU', 'ITA', 'ESP', 'POL', 'NLD', 'BEL', 'SWE', 'AUT', 'CHE', 'NOR', 'DNK'];
  let ok = 0, miss = 0;
  for (const iso of isos) {
    await A.evaluate(k => claim(k), 'C:' + iso); await A.waitForTimeout(60);
    const r = await A.evaluate(async k => { const pid = await createPatch({ tax: 1 }, 'W', 3, ''); const seen = !!M.c.patches[pid]; await adopt(k, pid); return { pid, seen }; }, 'C:' + iso);
    await A.waitForTimeout(80);
    const rule = await A.evaluate(k => rulesOf(k).tax || null, 'C:' + iso);
    if (rule && rule.pid === r.pid) ok++; else miss++;
  }
  console.log('(а) «Создать и принять»: принято', ok, 'из', isos.length, '; молча не принято', miss);

  // (б) ходящий игрок сам переключается обратно на того, кто был в ef-actor при загрузке
  const seat = await A.evaluate(async () => { const id = await addSeatPlayer('Маша'); setActor(id); return id; });
  await A.waitForTimeout(100);
  await A.reload(); await A.waitForFunction(() => typeof M !== 'undefined' && M.ready && game(), null, { timeout: 30000 }); await A.evaluate(() => closeDialog());
  await A.waitForTimeout(300);
  const a1 = await A.evaluate(() => ACT.id);
  await A.evaluate(() => setActor(M.me.id)); await A.waitForTimeout(100);
  const a2 = await A.evaluate(() => ACT.id);
  await Bp.evaluate(() => addSeatPlayer('Петя')); await A.waitForTimeout(300); // любая запись в players у другого игрока
  const a3 = await A.evaluate(() => ACT.id);
  console.log('(б) после загрузки ходит', a1 === seat ? 'Маша' : a1, '| выбрал себя →', a2, '| после записи Бориса в players ходит', a3 === seat ? 'СНОВА Маша (ошибка)' : a3);
  await A.evaluate(() => setActor(M.me.id));

  // (в) устаревший since: Борис принимает патч, пока Алиса считает год
  await Bp.evaluate(() => claim('C:KAZ')); await Bp.waitForTimeout(100);
  const pidK = await Bp.evaluate(() => createPatch({ invest: 1 }, 'W', 2, 'в гонке'));
  await Bp.waitForTimeout(100);
  await A.evaluate(() => { const orig = B.list.bind(B); B.list = async c => { const r = await orig(c); if (c === 'places') await new Promise(res => setTimeout(res, 400)); return r; }; window.__origList = orig; });
  const pAdv = adv();
  await Bp.waitForTimeout(150);
  await Bp.evaluate(p => adopt('C:KAZ', p), pidK);
  await pAdv; await A.waitForTimeout(300);
  await A.evaluate(() => { B.list = window.__origList; });
  const since = await Bp.evaluate(() => ({ y: curYear(), r: rulesOf('C:KAZ').invest }));
  await adv(); await adv(); await adv();
  const chkK = await A.evaluate(p => { const out = []; for (const y in M.c.histc) { (M.c.histc[y].chk || []).concat(M.c.histc[y].done || []).forEach(k => { if (k.pid === p) out.push(y + ':' + (k.ok === undefined ? 'идёт' : k.ok)); }); } return out; }, pidK);
  console.log('(в) принят во время расчёта: since =', since.r && since.r.since, 'текущий год', since.y, '| проверки этого патча за 3 года:', chkK.length ? chkK.join(',') : 'НЕТ — патч без проверки');

  // (г) откат перетирает свежее решение, принятое во время расчёта года
  await Bp.evaluate(() => claim('C:UZB')); await Bp.waitForTimeout(100);
  const bad = await Bp.evaluate(async () => { const p = await createPatch({ social: -1 }, 'W', 1, 'плохой'); return p; });
  await Bp.waitForTimeout(100); await Bp.evaluate(p => adopt('C:UZB', p), bad); await Bp.waitForTimeout(100);
  const good = await Bp.evaluate(() => createPatch({ social: 1 }, 'u', 3, 'новый'));
  await Bp.waitForTimeout(100);
  await A.evaluate(() => { const orig = window.__origList; B.list = async c => { const r = await orig(c); if (c === 'places') await new Promise(res => setTimeout(res, 400)); return r; }; });
  const pAdv2 = adv(); await Bp.waitForTimeout(150);
  await Bp.evaluate(p => adopt('C:UZB', p), good);
  await pAdv2; await A.waitForTimeout(400);
  await A.evaluate(() => { B.list = window.__origList; });
  const uzb = await Bp.evaluate(() => rulesOf('C:UZB').social || null);
  const doneBad = await A.evaluate(p => { for (const y in M.c.histc) for (const d of (M.c.histc[y].done || [])) if (d.pid === p) return d.ok; return null; }, bad);
  console.log('(г) плохой патч прошёл?', doneBad, '| правило «поддержка» у Узбекистана после хода:', JSON.stringify(uzb), uzb && uzb.pid === good ? '(новое решение цело)' : '→ НОВОЕ РЕШЕНИЕ ПОТЕРЯНО');

  // (д) сброс мира: у второго игрока остаются записи старого мира в кэше
  const before = await Bp.evaluate(() => ({ y: curYear(), seed: game().seed, cached: Object.keys(M.c.hist) }));
  await A.evaluate(async () => { window.__skew += 60000; await resetWorld(); });
  await A.waitForTimeout(800);
  console.log('(д) тост Алисы после сброса:', await toastOf(A));
  await adv(); await A.waitForTimeout(600);
  const aS = await A.evaluate(() => ({ y: curYear(), seed: game().seed, rusW: stateOf('C:RUS', 'forks').W, rec: rec(curYear()).seed }));
  const bS = await Bp.evaluate(() => ({ y: curYear(), seed: game().seed, rusW: stateOf('C:RUS', 'forks').W, rec: rec(curYear()).seed }));
  console.log('    до сброса у Бориса: год', before.y, 'кэш лет', before.cached.join(','));
  console.log('    Алиса: год', aS.y, 'seed', aS.seed, 'запись года seed', aS.rec, 'W России', aS.rusW);
  console.log('    Борис: год', bS.y, 'seed', bS.seed, 'запись года seed', bS.rec, 'W России', bS.rusW, bS.rec !== bS.seed ? '→ ПОКАЗЫВАЕТ ГОД СТАРОГО МИРА' : '');
  console.log('ошибки:', errs.length ? errs.join('\n') : 'нет');
  await browser.close(); srv.close();
})().catch(e => { console.error('ТЕСТ УПАЛ', e); process.exit(1); });
