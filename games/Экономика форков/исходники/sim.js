// ── Модель мира «Экономика форков». Чистые функции без DOM: одинаково работают в браузере и в Node.
// Модель игрушечная. Она показывает механику решений, а не предсказывает экономику.
var SIM = (function () {
  var Q = [
    { id: 'rate', name: 'Ключевая ставка', short: 'Ставка', level: 'country',
      opts: { '-1': 'снизить на 1,5 п.п.', '0': 'как было', '1': 'повысить на 1,5 п.п.' } },
    { id: 'tariff', name: 'Пошлины на импорт', short: 'Пошлины', level: 'country',
      opts: { '-1': 'снизить на 5 п.п.', '0': 'как было', '1': 'поднять на 10 п.п.' } },
    { id: 'tax', name: 'Налоги', short: 'Налоги', level: 'any',
      opts: { '-1': 'снизить на 2% дохода', '0': 'как было', '1': 'поднять на 2% дохода' } },
    { id: 'invest', name: 'Вложения в дороги, школы, сети', short: 'Вложения', level: 'any',
      opts: { '-1': 'урезать на 1% дохода', '0': 'как было', '1': 'добавить 2% дохода' } },
    { id: 'social', name: 'Поддержка тех, кому трудно', short: 'Поддержка', level: 'any',
      opts: { '-1': 'урезать на 1% дохода', '0': 'как было', '1': 'добавить 2% дохода' } }
  ];
  var QI = {}; Q.forEach(function (q, i) { QI[q.id] = i; });
  // Как проверяется решение: mean — среднее за срок, end — значение в конце срока (y — в процентах к тени)
  var METRICS = {
    W: { name: 'благополучие', better: 1, mode: 'mean', unit: '' },
    y: { name: 'доход на человека', better: 1, mode: 'end', rel: true, unit: '%' },
    u: { name: 'безработица', better: -1, mode: 'mean', unit: ' п.п.' },
    pi: { name: 'инфляция (отклонение от цели)', better: -1, mode: 'mean', unit: ' п.п.' },
    D: { name: 'долг', better: -1, mode: 'end', unit: '% дохода' }
  };
  // величина решения в процентных пунктах
  function mag(q, o) {
    o = +o || 0;
    if (q === 'rate') return 1.5 * o;
    if (q === 'tariff') return o > 0 ? 10 : o < 0 ? -5 : 0;
    if (q === 'tax') return 2 * o;
    return o > 0 ? 2 : o < 0 ? -1 : 0; // invest, social
  }
  // ГСЧ с зерном
  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0; var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }

  // Постоянные параметры страны из данных
  function params(c) {
    var y = c.y || 10000;
    var gdp = y * (c.P || 1e6);
    var open = clamp(0.3 + 0.07 * (12.5 - Math.log10(Math.max(gdp, 1e8))), 0.15, 0.75);
    var conv = 1.2 + 2.6 * (1 - Math.min(1, y / 60000));
    var g0 = c.g0 == null ? conv : c.g0;
    var gStar = clamp(0.5 * clamp(g0, -3, 9) + 0.5 * conv, 0, 6.5);
    var x0 = clamp(0.5 * (clamp(g0, -6, 10) - gStar), -3, 3);
    var u0 = c.u0 == null ? 6 : c.u0;
    return {
      open: open, gStar: gStar, x0: x0,
      uStar: clamp(u0 + 0.5 * x0, 1, 35),
      piStar: y > 20000 ? 2 : 3,
      popg: c.pg != null ? clamp(c.pg, -1.5, 3.5) : 0.2 + 1.8 * (1 - Math.min(1, y / 30000)),
      boost: 1 + 0.8 * (1 - Math.min(1, y / 40000)),
      vol: y > 20000 ? 0.7 : 1.2
    };
  }
  // Начальное состояние страны
  function initState(c) {
    var p = params(c);
    var g = c.g0 == null ? p.gStar : clamp(c.g0, -10, 20), pi = c.pi0 == null ? 3 : clamp(c.pi0, -5, 80), u = c.u0 == null ? 6 : c.u0;
    // стартовое благополучие — по той же формуле, что и дальше (долга ещё нет)
    var W = (g - p.popg) - 0.5 * Math.max(0, u - p.uStar) - 0.25 * Math.abs(pi - p.piStar);
    return { x: p.x0, g: g, pi: pi, u: u, D: 0, K: 0, y: c.y || 10000, P: c.P || 1e6, W: W, lv: [0, 0, 0, 0, 0] };
  }
  // Общие потрясения года
  function shocks(seed, year) {
    var r = rng(hash('world:' + seed + ':' + year));
    var G = 0.6 * gauss(r), Pi = 0.5 * gauss(r), ev = [];
    if (r() < 0.07) { G -= 2.5; ev.push('crisis'); }
    if (r() < 0.08) { Pi += 2; ev.push('oil'); }
    if (r() < 0.05) { G += 1.2; ev.push('boom'); }
    return { G: G, Pi: Pi, ev: ev };
  }
  function ownShock(seed, year, key) {
    var r = rng(hash(key + ':' + seed + ':' + year));
    return { eg: gauss(r), ep: gauss(r), eu: gauss(r) };
  }
  // Один год одной страны. lv — уровни решений [ставка, пошлины, налоги, вложения, поддержка] в п.п.
  function stepCountry(c, s, lv, world, seed, year) {
    var p = params(c), sh = ownShock(seed, year, c.iso3);
    var prev = s.lv || [0, 0, 0, 0, 0];
    var slack = Math.max(0, s.u - p.uStar);
    var m = Math.min(1.2, 0.5 + 0.12 * slack);
    // импульс: изменение уровней бюджета в этом году
    var dInv = lv[3] - prev[3], dSoc = lv[4] - prev[4], dTax = lv[2] - prev[2];
    var impulse = m * (dInv + 0.7 * dSoc - 0.5 * dTax);
    var expo = 0.6 + 0.8 * p.open;
    var x = 0.5 * s.x + impulse - 0.45 * lv[0] + 0.012 * p.open * lv[1]
      + expo * world.G + 0.5 * p.vol * sh.eg;
    var K = 0.9 * s.K + lv[3];
    var D0 = s.D;
    var gPot = p.gStar + 0.02 * K * p.boost - 0.04 * lv[2] - 0.015 * lv[1]
      - 0.05 * p.open * world.tariff - 0.01 * Math.max(0, D0 - 30) - 0.03 * Math.max(0, lv[4]);
    var g = gPot + (x - s.x);
    var piT = p.piStar;
    var pi = s.pi + 0.15 * (piT - s.pi) - 0.2 * lv[0] + 0.35 * x + 0.02 * lv[1] * p.open + world.Pi * expo * 0.8 + 0.35 * p.vol * sh.ep;
    var uStar = p.uStar + 0.08 * Math.max(0, lv[4]);
    var u = clamp(0.5 * s.u + 0.5 * (uStar - 0.5 * x) + 0.15 * sh.eu, 0.3, 45);
    var deficit = lv[3] + lv[4] - lv[2] - 0.3 * x;
    var D = D0 * (1 + (2 + lv[0] - g) / 100) + deficit;
    var popg = p.popg;
    var y = s.y * (1 + (g - popg) / 100);
    var P = s.P * (1 + popg / 100);
    var W = (g - popg) - 0.5 * Math.max(0, u - p.uStar) - 0.25 * Math.abs(pi - piT) - 0.015 * Math.max(0, D) + 0.2 * Math.max(0, lv[4]) - 0.2 * Math.max(0, -lv[4]);
    return { x: x, g: g, pi: pi, u: u, D: D, K: K, y: y, P: P, W: W, lv: lv.slice() };
  }
  // Один год места внутри страны (город, село). cs — состояние страны в этом году, ls — место, lv — местные уровни [налоги, вложения, поддержка]
  function stepLocal(key, cParams, cs, ls, lv, seed, year) {
    var sh = ownShock(seed, year, key);
    var prev = ls.lv || [0, 0, 0];
    var dTax = lv[0] - prev[0], dInv = lv[1] - prev[1], dSoc = lv[2] - prev[2];
    var xl = 0.5 * ls.xl + 0.5 * (dInv + 0.7 * dSoc - 0.5 * dTax) + 0.3 * sh.eg;
    var K = 0.9 * ls.K + lv[1];
    var dgPot = 0.012 * K * cParams.boost - 0.03 * lv[0] - 0.02 * Math.max(0, lv[2]);
    var dg = dgPot + (xl - ls.xl);
    var du = clamp(0.6 * ls.du - 0.3 * xl + 0.05 * Math.max(0, lv[2]) + 0.1 * sh.eu, -8, 15);
    var B = ls.B * (1 + (2 - cs.g) / 100) + lv[1] + lv[2] - lv[0] - 0.2 * xl;
    var W = cs.W + dg - 0.5 * Math.max(0, du) + 0.2 * Math.max(0, lv[2]) - 0.2 * Math.max(0, -lv[2]) - 0.015 * Math.max(0, B);
    var mig = clamp(0.25 * (W - cs.W), -2, 2);
    var y = ls.y * (1 + (cs.g + dg - cParams.popg) / 100);
    var P = Math.max(1, ls.P * (1 + (cParams.popg + mig) / 100));
    return { xl: xl, K: K, dg: dg, g: cs.g + dg, du: du, u: clamp(cs.u + du, 0.3, 50), pi: cs.pi, B: B, D: B, y: y, P: P, W: W, lv: lv.slice() };
  }
  function initLocal(cs, pop) {
    return { xl: 0, K: 0, dg: 0, g: cs.g, du: 0, u: cs.u, pi: cs.pi, B: 0, D: 0, y: cs.y, P: pop || 1000, W: cs.W, lv: [0, 0, 0] };
  }
  function metricValue(st, metric, piStar) {
    if (metric === 'pi') return Math.abs(st.pi - piStar);
    return st[metric];
  }
  return { Q: Q, QI: QI, METRICS: METRICS, mag: mag, params: params, initState: initState, shocks: shocks,
    stepCountry: stepCountry, stepLocal: stepLocal, initLocal: initLocal, metricValue: metricValue, clamp: clamp, hash: hash, rng: rng };
})();
if (typeof module !== 'undefined') module.exports = SIM;
