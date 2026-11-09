// TESTER-01, среда без снимков экрана: игра в Chromium (Playwright) с виртуальным временем; наблюдение — текстом;
// действия — по номерам кнопок, клеткам карты, клавишам; след (observe/act/advance) повторяется точно (replay).
const { chromium } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path');
const A = require('./adapters');
const PROBE = fs.readFileSync(path.join(__dirname, 'probe.js'), 'utf8');
const SETTLE_MS = 400;          // после действия: игры обновляют панель раз в 0,3 с
const MAX_WAIT_S = 600;         // одно ожидание — не больше 10 минут виртуального времени

function pageScreen() {   // в странице: тексты областей экрана и (если надо) номера элементов управления
  const vis = el => { if (!el) return false; const r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const txt = (id, n) => { const e = document.getElementById(id); return vis(e) ? (e.innerText || '').replace(/[ \t]+/g, ' ').replace(/\n{2,}/g, '\n').trim().slice(0, n) || undefined : undefined; };
  return { top: txt('topbar', 500), tip: txt('tip', 300), tutorial: txt('tut', 900), modal: txt('modal', 1500), buildBar: txt('buildBar', 600),
           selection: txt('sel', 900), tabs: txt('tabs', 300), panel: txt('panel', 3500), events: txt('evbar', 400) };
}
function pageControls() {   // в странице: заново пронумеровать видимые элементы управления
  const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  document.querySelectorAll('[data-tid]').forEach(e => e.removeAttribute('data-tid'));
  const out = []; let n = 0;
  // кнопки и поля, плюс любые внешние элементы с курсором-указателем (строки списков, карточки) — так ловятся клики, которые игра делегирует
  const BASE = 'button, input, select, textarea, a[href], [role=button], [onclick], [data-selw]';
  const set = new Set(document.querySelectorAll(BASE));
  for (const el of document.querySelectorAll('#side *, #topbar *, #tut *, #modal *, #buildBar *')) {
    if (set.has(el) || el.closest(BASE)) continue;
    if (getComputedStyle(el).cursor === 'pointer' && !(el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer')) set.add(el);
  }
  const all = [...set].sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  for (const el of all) {
    if (!vis(el)) continue;
    const kind = el.tagName === 'INPUT' ? 'i' : el.tagName === 'SELECT' ? 's' : (el.matches(BASE) ? 'b' : 'r'), id = kind + (++n);   // r — строка/карточка
    el.setAttribute('data-tid', id);
    const region = ['topbar', 'tut', 'modal', 'buildBar', 'tabs', 'sel', 'panel', 'evbar'].find(r => el.closest('#' + r)) || 'other';
    let label = (el.innerText || el.value || el.title || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 70);
    if (el.tagName === 'INPUT') label = `[${el.type}] ${el.name || el.id || ''} = ${el.type === 'checkbox' ? el.checked : el.value}`;
    if (el.tagName === 'SELECT') label = `[select] ${[...el.options].map(o => (o.selected ? '*' : '') + o.text).join(' | ').slice(0, 140)}`;
    out.push(`${id} ${region}${el.disabled ? ' (неактивна)' : ''}: ${label}`);
  }
  return out;
}
const fn = f => `(${f.toString()})`;

class GameEnv {
  static async open(file, opts = {}) { const e = new GameEnv(); await e._open(file, opts); return e; }
  async _open(file, { seed = 1, viewport = { width: 1280, height: 800 }, workDir = null } = {}) {
    const html = fs.readFileSync(file, 'utf8');
    this.file = file; this.seed = seed; this.game = A.detect(html); this.trace = []; this.reports = []; this.errSeen = 0;
    const g = A.GAMES[this.game];
    this.dir = workDir || fs.mkdtempSync(path.join(os.tmpdir(), 'tester01-')); fs.mkdirSync(this.dir, { recursive: true });
    this.pageFile = path.join(this.dir, 'game.html'); fs.writeFileSync(this.pageFile, g ? g.patch(html) : html);
    this.browser = await chromium.launch();
    this.ctx = await this.browser.newContext({ viewport, deviceScaleFactor: 1, locale: 'ru-RU', timezoneId: 'UTC' });
    this.page = await this.ctx.newPage(); await this.page.addInitScript({ content: PROBE });
    await this.page.goto('file://' + this.pageFile + (g ? g.query(seed) : '?') + `&__seed=${seed}`);
    await this._advance(SETTLE_MS);
  }
  async close() { try { await this.browser.close(); } catch (e) { /* уже закрыт */ } }
  async _advance(ms) { return this.page.evaluate(m => window.__T.advance(m), ms); }
  async _errors() { const e = await this.page.evaluate(k => window.__T.errors.slice(k), this.errSeen); this.errSeen += e.length; return e; }
  async _state() { return this.page.evaluate(([f, g]) => eval(f)(g), [fn(A.pageState), this.game]); }

  // Наблюдение для головы: экран текстом, элементы управления с номерами, состояние игры, новые ошибки.
  async observe() {
    this.trace.push({ op: 'observe' });
    const [screen, controls, state] = await Promise.all([this.page.evaluate(fn(pageScreen) + '()'), this.page.evaluate(fn(pageControls) + '()'), this._state()]);
    const t = await this.page.evaluate(() => window.__T.now());
    return { t_s: Math.round(t / 100) / 10, screen, controls, state, errors: await this._errors() };
  }
  // Подсмотр для оценки повтором: не трогает номера элементов, поэтому не меняет ход повтора.
  async peek() {
    const [screen, state, t, errs] = await Promise.all([this.page.evaluate(fn(pageScreen) + '()'), this._state(), this.page.evaluate(() => window.__T.now()), this.page.evaluate(() => window.__T.errors.slice())]);
    return { t_s: Math.round(t / 100) / 10, screen, state, errors: errs };
  }
  async screenshot() { return (await this.page.screenshot({ type: 'png' })).toString('base64'); }

  // Действие: {click:'b7'} | {map:[x,y], button?} | {drag:[x1,y1,x2,y2] доли холста} | {key:'r'} | {fill:['i3','текст']} | {select:['s2','пункт']} | {click_xy:[x,y]} | {wait:секунд}
  async act(a) {
    const P = this.page; let note = null;
    if (a.click || a.fill || a.select) {
      const id = a.click || (a.fill || a.select)[0];
      const ok = await P.evaluate(id => { const el = document.querySelector(`[data-tid="${id}"]`); if (!el) return false; el.scrollIntoView({ block: 'center', inline: 'center' }); return (el.innerText || el.value || el.title || '').replace(/\s+/g, ' ').trim().slice(0, 80) || '(без подписи)'; }, id);
      if (!ok) return { ok: false, error: `элемента ${id} нет: номера даёт последнее observe` };
      this.lastLabel = ok;
      const L = P.locator(`[data-tid="${id}"]`);
      if (a.click) { const b = await L.boundingBox(); if (!b) return { ok: false, error: `элемент ${id} не виден` }; await P.mouse.click(b.x + b.width / 2, b.y + b.height / 2); }
      else if (a.fill) await L.fill(String(a.fill[1]), { timeout: 2000 });
      else await L.selectOption({ label: String(a.select[1]) }, { timeout: 2000 });
    } else if (a.map) {
      const p = await P.evaluate(([f, g, x, y]) => eval(f)(g, x, y), [fn(A.pageTileToScreen), this.game, +a.map[0], +a.map[1]]);
      if (!p) return { ok: false, error: 'у этой игры нет карты' };
      if (p.off) return { ok: false, error: 'клетка вне видимой части карты', view: p.view };
      await P.mouse.click(p.x, p.y, { button: a.button === 'right' ? 'right' : 'left' });
    } else if (a.drag) {   // перетащить по холсту карты: [x1, y1, x2, y2] в долях холста 0..1
      const b = await P.locator('#cv').boundingBox(); if (!b) return { ok: false, error: 'у этой игры нет карты' };
      const [x1, y1, x2, y2] = a.drag.map(Number), X = f => b.x + f * b.width, Y = f => b.y + f * b.height;
      await P.mouse.move(X(x1), Y(y1)); await P.mouse.down(); for (let i = 1; i <= 8; i++) await P.mouse.move(X(x1 + (x2 - x1) * i / 8), Y(y1 + (y2 - y1) * i / 8)); await P.mouse.up();
    } else if (a.key) await P.keyboard.press(String(a.key));
    else if (a.click_xy) await P.mouse.click(+a.click_xy[0], +a.click_xy[1]);
    else if (a.wait === undefined) return { ok: false, error: 'неизвестное действие' };
    const ms = a.wait !== undefined ? Math.min(MAX_WAIT_S, Math.max(0, +a.wait)) * 1000 : SETTLE_MS;
    if (a.wait !== undefined && +a.wait > MAX_WAIT_S) note = `ожидание урезано до ${MAX_WAIT_S} с`;
    this.trace.push({ op: 'act', a });
    const r = await this._advance(ms);
    const label = this.lastLabel; this.lastLabel = null;
    return { ok: true, t_s: Math.round(r.now / 100) / 10, loopStopped: r.loopStopped, note, ...(label ? { label } : {}) };
  }
  report(r) { const rec = { ...r, step: this.trace.length }; this.reports.push(rec); return rec; }

  // Повтор следа на другой копии игры (мутант или чистая): возвращает подсмотры после каждого шага.
  static async replay(file, trace, { seed = 1, upTo = null } = {}) {
    const e = await GameEnv.open(file, { seed }); const peeks = [];
    try {
      const n = upTo === null ? trace.length : Math.min(upTo, trace.length);
      for (let i = 0; i < n; i++) {
        const s = trace[i];
        if (s.op === 'observe') await e.page.evaluate(fn(pageControls) + '()');
        else if (s.op === 'act') { const r = await e.act(s.a); peeks.push({ step: i + 1, act: s.a, result: r, ...(await e.peek()) }); }
      }
    } finally { await e.close(); }
    return peeks;
  }
}
module.exports = { GameEnv, SETTLE_MS, MAX_WAIT_S };
