// TESTER-01, зонд среды: встраивается в страницу до её скриптов (page.addInitScript).
// Виртуальное время (performance.now, Date, requestAnimationFrame, таймеры) идёт только по команде __T.advance(мс);
// Math.random — с зерном (__seed в адресе); ошибки страницы собираются в __T.errors. Игру не меняет.
(() => {
  const P = new URLSearchParams(location.search);
  let seed = (Number(P.get('__seed')) || 1) >>> 0;
  Math.random = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  let now = 0; const T0 = Date.UTC(2026, 10, 9, 8, 0, 0), RD = Date;
  class VDate extends RD { constructor(...a) { if (a.length) super(...a); else super(T0 + Math.floor(now)); } static now() { return T0 + Math.floor(now); } }
  window.Date = VDate;
  performance.now = () => now;
  let raf = [], rafId = 0, timerId = 0; const timers = [];
  window.requestAnimationFrame = cb => { raf.push([++rafId, cb]); return rafId; };
  window.cancelAnimationFrame = id => { raf = raf.filter(([i]) => i !== id); };
  window.setTimeout = (cb, ms, ...a) => { timers.push({ id: ++timerId, at: now + (+ms || 0), cb, a }); return timerId; };
  window.setInterval = (cb, ms, ...a) => { timers.push({ id: ++timerId, at: now + (+ms || 0), cb, a, every: Math.max(1, +ms || 0) }); return timerId; };
  window.clearTimeout = window.clearInterval = id => { const i = timers.findIndex(t => t.id === id); if (i >= 0) timers.splice(i, 1); };
  const errors = []; let rafDead = false, skipDraw = false;
  // Промежуточные кадры: рисование на видимой карте (#cv) пропускается — её пиксели игра не читает
  // (getImageData в обеих играх — только по вспомогательным холстам спрайтов); последний кадр рисуется полностью.
  const C2 = CanvasRenderingContext2D.prototype;
  for (const m of ['fillRect', 'strokeRect', 'clearRect', 'fill', 'stroke', 'drawImage', 'fillText', 'strokeText', 'putImageData']) {
    const orig = C2[m]; if (typeof orig !== 'function') continue;
    C2[m] = function (...a) { if (skipDraw && this.canvas && this.canvas.id === 'cv') return; return orig.apply(this, a); };
  }
  const push = (kind, msg) => { if (errors.length < 500) errors.push({ kind, msg: String(msg).slice(0, 400), t: Math.round(now) }); };
  window.addEventListener('error', e => push('error', (e.message || e) + (e.lineno ? ' (строка ' + e.lineno + ')' : '')));
  window.addEventListener('unhandledrejection', e => push('rejection', (e.reason && e.reason.message) || e.reason));
  const ce = console.error.bind(console);
  console.error = (...a) => { push('console.error', a.map(x => (x && x.message) ? x.message : String(x)).join(' ')); ce(...a); };
  const runTimers = () => {
    for (let guard = 0; guard < 10000; guard++) {
      timers.sort((a, b) => a.at - b.at || a.id - b.id); const t = timers[0];
      if (!t || t.at > now) return;
      if (t.every) t.at += t.every; else timers.shift();
      try { typeof t.cb === 'function' ? t.cb(...t.a) : eval(String(t.cb)); } catch (e) { push('timer', (e && e.message) || e); }
    }
  };
  window.__T = {
    errors,
    now: () => now,
    rafPending: () => raf.length,
    // кадр каждые step мс виртуального времени; игра сама ограничивает шаг 0,1 с
    advance(ms, step = 100) {
      let left = Math.max(0, +ms || 0), frames = 0;
      while (left > 0) {
        const d = Math.min(step, left); now += d; left -= d; skipDraw = left > 0; runTimers();
        const q = raf; raf = [];
        for (const [, cb] of q) { try { cb(now); } catch (e) { push('frame', (e && e.message) || e); } }
        frames++;
      }
      skipDraw = false;
      rafDead = raf.length === 0;   // игра больше не просит кадр — главный цикл остановился
      return { frames, now, loopStopped: rafDead };
    },
  };
})();
