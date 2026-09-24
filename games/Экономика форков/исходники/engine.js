// ── Движок года: форки (у каждого места своё) и параллельный мир «единый план». Без DOM.
// Патч может менять сразу несколько вопросов; проверка по итогам сравнивает место с «тенью» —
// тем же местом в том же мире, где этот патч не принят.
var ENGINE = (function (SIM) {
  var R = function (x) { return Math.round(x * 1e4) / 1e4; };
  var LOCALQ = ['tax', 'invest', 'social'];
  function isCountry(key) { return key.charAt(0) === 'C'; }
  function countryOpts(rules, iso3) {
    var r = rules['C:' + iso3] || {};
    return SIM.Q.map(function (q) { return r[q.id] ? +r[q.id].opt : 0; });
  }
  // местные варианты: своё решение, иначе решение ближайшего места выше, иначе 0 (только общая политика страны)
  function localOpts(rules, locals, key) {
    var out = [0, 0, 0], set = [false, false, false], k = key, guard = 0;
    while (k && !isCountry(k) && guard++ < 20) {
      var r = rules[k] || {};
      LOCALQ.forEach(function (q, i) { if (!set[i] && r[q]) { out[i] = +r[q].opt; set[i] = true; } });
      k = locals[k] ? locals[k].parent : null;
    }
    return out;
  }
  function packC(s) { return [R(s.x), R(s.g), R(s.pi), R(s.u), R(s.D), R(s.K), Math.round(s.y), Math.round(s.P), R(s.W)].concat(s.lv.map(R)); }
  function unpackC(a) { return { x: a[0], g: a[1], pi: a[2], u: a[3], D: a[4], K: a[5], y: a[6], P: a[7], W: a[8], lv: a.slice(9, 14) }; }
  function packL(s) { return [R(s.xl), R(s.K), R(s.dg), R(s.du), R(s.B), Math.round(s.y), Math.round(s.P), R(s.W), R(s.g), R(s.u), R(s.pi)].concat(s.lv.map(R)); }
  function unpackL(a) { return { xl: a[0], K: a[1], dg: a[2], du: a[3], B: a[4], D: a[4], y: a[5], P: a[6], W: a[7], g: a[8], u: a[9], pi: a[10], lv: a.slice(11, 14) }; }
  function lvCountry(opts) { return SIM.Q.map(function (q, i) { return SIM.mag(q.id, opts[i]); }); }
  function lvLocal(opts) { return LOCALQ.map(function (q, i) { return SIM.mag(q, opts[i]); }); }
  // «Единый план»: по каждому вопросу — вариант, за которым больше всего людей среди стран, где решение принято явно
  function planOptions(rules, countries, cstate) {
    return SIM.Q.map(function (q) {
      var w = { '-1': 0, '0': 0, '1': 0 }, any = false;
      Object.keys(countries).forEach(function (iso3) {
        var r = rules['C:' + iso3];
        if (r && r[q.id]) { any = true; w[String(+r[q.id].opt)] += (cstate[iso3] ? cstate[iso3].P : 1); }
      });
      if (!any) return 0;
      var best = '0'; ['-1', '1'].forEach(function (k) { if (w[k] > w[best]) best = k; });
      return +best;
    });
  }
  function worldTariff(states, lvOf) {
    var num = 0, den = 0;
    Object.keys(states).forEach(function (iso3) { var s = states[iso3], gdp = s.y * s.P; num += gdp * lvOf(iso3)[1]; den += gdp; });
    return den ? num / den : 0;
  }
  function aggregate(states) {
    var P = 0, W = 0, g = 0, u = 0, pi = 0, D = 0, Y = 0;
    Object.keys(states).forEach(function (k) { var s = states[k]; P += s.P; W += s.W * s.P; g += s.g * s.P; u += s.u * s.P; pi += s.pi * s.P; D += s.D * s.P; Y += s.y * s.P; });
    return P ? { W: R(W / P), g: R(g / P), u: R(u / P), pi: R(pi / P), D: R(D / P), y: Math.round(Y / P), P: Math.round(P) } : null;
  }
  function initialHistory(countries, year0, seed) {
    var cs = {}, pcs = {}, cu = {};
    Object.keys(countries).forEach(function (iso3) { var s = SIM.initState(countries[iso3]); cs[iso3] = packC(s); pcs[iso3] = packC(s); cu[iso3] = s; });
    var a = aggregate(cu);
    return { year: year0, seed: seed, cs: cs, ls: {}, lopt: {}, copt: {}, plan: { cs: pcs, ls: {}, opts: [0, 0, 0, 0, 0] },
      chk: [], done: [], ev: [], agg: { forks: a, plan: a } };
  }
  function metricAll(st, piStar) { var o = {}; Object.keys(SIM.METRICS).forEach(function (m) { o[m] = SIM.metricValue(st, m, piStar); }); return o; }
  /*
   Один шаг. prev — запись прошлого года; countries — данные стран; locals — активные места {key: {cc, pop, parent}};
   rules — {key: {q: {pid, opt, since}}}; patches — {pid: {ch: {q: opt}, metric, horizon}}.
   Возвращает { hist, reverts }: новую запись и откаты [{ key, pid, qs, prev }].
  */
  function step(prev, countries, locals, rules, patches) {
    var year = prev.year + 1, seed = prev.seed, world = SIM.shocks(seed, year);
    var cur = {}, curPlan = {};
    Object.keys(countries).forEach(function (iso3) {
      cur[iso3] = prev.cs[iso3] ? unpackC(prev.cs[iso3]) : SIM.initState(countries[iso3]);
      curPlan[iso3] = prev.plan.cs[iso3] ? unpackC(prev.plan.cs[iso3]) : SIM.initState(countries[iso3]);
    });
    var optsC = {}; Object.keys(countries).forEach(function (iso3) { optsC[iso3] = countryOpts(rules, iso3); });
    var pOpts = planOptions(rules, countries, cur);
    var wT = worldTariff(cur, function (k) { return lvCountry(optsC[k]); });
    var wTp = worldTariff(curPlan, function () { return lvCountry(pOpts); });
    var ev = []; world.ev.forEach(function (e) { ev.push({ t: e }); });
    var nextC = {}, nextP = {};
    Object.keys(countries).forEach(function (iso3) {
      var c = countries[iso3];
      nextC[iso3] = SIM.stepCountry(c, cur[iso3], lvCountry(optsC[iso3]), { G: world.G, Pi: world.Pi, tariff: wT }, seed, year);
      nextP[iso3] = SIM.stepCountry(c, curPlan[iso3], lvCountry(pOpts), { G: world.G, Pi: world.Pi, tariff: wTp }, seed, year);
    });
    var nextL = {}, nextLP = {}, lopt = {};
    Object.keys(locals).forEach(function (key) {
      var L = locals[key], iso3 = L.cc; if (!countries[iso3]) return;
      var cp = SIM.params(countries[iso3]);
      var ls = prev.ls[key] ? unpackL(prev.ls[key]) : SIM.initLocal(cur[iso3], L.pop);
      var lsp = prev.plan.ls[key] ? unpackL(prev.plan.ls[key]) : SIM.initLocal(curPlan[iso3], L.pop);
      var o = localOpts(rules, locals, key); lopt[key] = o;
      nextL[key] = SIM.stepLocal(key, cp, nextC[iso3], ls, lvLocal(o), seed, year);
      nextLP[key] = SIM.stepLocal(key, cp, nextP[iso3], lsp, [0, 0, 0], seed, year);
    });
    // новые патчи с прошлого шага → новые проверки (одна на место и патч).
    // Новое — это смена патча по вопросу относительно прошлого шага (с учётом откатов), а не год в since:
    // так проверяются и решения, записанные во время расчёта года, и патч, принятый снова сразу после отката.
    var chk = (prev.chk || []).slice(), fresh = {};
    var copt = prev.copt || {}, loptPrev = prev.lopt || {}, rpPrev = prev.rp || {};
    function wasLocal(key, qi) {
      var k = key, g = 0;
      while (k && !isCountry(k) && g++ < 20) { if (loptPrev[k]) return loptPrev[k][qi]; k = locals[k] ? locals[k].parent : null; }
      return 0;
    }
    Object.keys(rules).forEach(function (key) {
      var r = rules[key], isC = isCountry(key), last = rpPrev[key] || {};
      Object.keys(r).forEach(function (q) {
        var rr = r[q]; if (!rr || rr.pid === last[q]) return;
        var pa = patches && patches[rr.pid]; if (!rr.m && !pa) return; // откаты и ручные снятия не проверяются
        var qi = isC ? SIM.QI[q] : LOCALQ.indexOf(q); if (qi < 0 || qi === undefined) return;
        var was = isC ? ((copt[key.slice(2)] || [0, 0, 0, 0, 0])[qi]) : wasLocal(key, qi);
        var id = key + '|' + rr.pid;
        var f = fresh[id] || (fresh[id] = { key: key, pid: rr.pid, qs: [], opts: [], prev: [], own: [] });
        f.qs.push(q); f.opts.push(+rr.opt); f.prev.push(+was); f.own.push(!!last[q]); // own: было ли своё решение (иначе — унаследованное)
        f.m = rr.m || (pa && pa.metric) || 'W'; f.h = rr.h || (pa && pa.horizon) || 3;
      });
    });
    Object.keys(fresh).forEach(function (id) {
      var f = fresh[id], isC = isCountry(f.key);
      if (f.opts.every(function (o, i) { return o === f.prev[i]; })) return;
      var shadow = isC ? prev.cs[f.key.slice(2)] : prev.ls[f.key];
      if (!shadow && !isC) { var L = locals[f.key]; if (!L || !countries[L.cc]) return; shadow = packL(SIM.initLocal(cur[L.cc], L.pop)); }
      if (!shadow) return;
      chk = chk.filter(function (k) { return !(k.key === f.key && k.pid === f.pid); });
      chk.push({ key: f.key, pid: f.pid, qs: f.qs, opts: f.opts, prev: f.prev, own: f.own, from: year,
        due: year + Math.max(1, Math.min(10, +f.h || 3)) - 1, metric: SIM.METRICS[f.m] ? f.m : 'W',
        sh: shadow, aR: {}, aS: {}, n: 0 });
    });
    var done = [], reverts = [], keep = [];
    chk.forEach(function (k) {
      var isC = isCountry(k.key), st, real, piStar;
      // патч сняли или заменили раньше срока — проверка снимается; если сняли часть вопросов — проверяются оставшиеся
      var gov = k.qs.map(function (q, i) { var rr = (rules[k.key] || {})[q]; return !!(rr && rr.pid === k.pid && +rr.opt === k.opts[i]); });
      if (!gov.some(Boolean)) return;
      if (isC) {
        var iso3 = k.key.slice(2); if (!countries[iso3]) return;
        var o = optsC[iso3].slice(); k.qs.forEach(function (q, i) { if (gov[i]) o[SIM.QI[q]] = k.prev[i]; });
        st = SIM.stepCountry(countries[iso3], unpackC(k.sh), lvCountry(o), { G: world.G, Pi: world.Pi, tariff: wT }, seed, year);
        k.sh = packC(st); real = nextC[iso3]; piStar = SIM.params(countries[iso3]).piStar;
      } else {
        var L = locals[k.key]; if (!L || !countries[L.cc] || !nextL[k.key]) return;
        var o2 = (lopt[k.key] || [0, 0, 0]).slice(); k.qs.forEach(function (q, i) { if (gov[i]) o2[LOCALQ.indexOf(q)] = k.prev[i]; });
        st = SIM.stepLocal(k.key, SIM.params(countries[L.cc]), nextC[L.cc], unpackL(k.sh), lvLocal(o2), seed, year);
        k.sh = packL(st); real = nextL[k.key]; piStar = SIM.params(countries[L.cc]).piStar;
      }
      var mr = metricAll(real, piStar), ms = metricAll(st, piStar);
      Object.keys(mr).forEach(function (m) { k.aR[m] = R((k.aR[m] || 0) + mr[m]); k.aS[m] = R((k.aS[m] || 0) + ms[m]); });
      k.n += 1;
      if (year >= k.due) {
        var d = {};
        Object.keys(SIM.METRICS).forEach(function (m) {
          var M = SIM.METRICS[m];
          d[m] = R(M.mode === 'mean' ? M.better * (k.aR[m] - k.aS[m]) / k.n
            : M.rel ? M.better * (mr[m] / Math.max(1e-9, ms[m]) - 1) * 100 : M.better * (mr[m] - ms[m]));
        });
        var ok = d[k.metric] > 0;
        done.push({ key: k.key, pid: k.pid, qs: k.qs, opts: k.opts, prev: k.prev, metric: k.metric, d: d, ok: ok, from: k.from, year: year });
        ev.push({ t: ok ? 'pass' : 'fail', key: k.key, pid: k.pid, metric: k.metric, diff: d[k.metric] });
        if (!ok) reverts.push({ key: k.key, pid: k.pid, qs: k.qs.filter(function (q, i) { return gov[i]; }), prev: k.prev.filter(function (v, i) { return gov[i]; }),
          own: (k.own || k.qs.map(function () { return true; })).filter(function (v, i) { return gov[i]; }) });
      } else keep.push(k);
    });
    // что действует после откатов: патч по каждому вопросу (rp) и варианты (copt, lopt)
    var rp = {};
    Object.keys(rules).forEach(function (key) { var r = rules[key], o = {}, any = false; Object.keys(r).forEach(function (q) { if (r[q]) { o[q] = r[q].pid; any = true; } }); if (any) rp[key] = o; });
    reverts.forEach(function (rv) {
      rv.qs.forEach(function (q, i) {
        if (rp[rv.key] && rp[rv.key][q] === rv.pid) rp[rv.key][q] = 'revert:' + rv.pid;
        if (isCountry(rv.key)) { var a = optsC[rv.key.slice(2)]; if (a) a[SIM.QI[q]] = +rv.prev[i]; }
        else if (lopt[rv.key]) lopt[rv.key][LOCALQ.indexOf(q)] = +rv.prev[i];
      });
    });
    var cs = {}, ls = {}, pcs = {}, pls = {};
    Object.keys(nextC).forEach(function (k) { cs[k] = packC(nextC[k]); pcs[k] = packC(nextP[k]); });
    Object.keys(nextL).forEach(function (k) { ls[k] = packL(nextL[k]); pls[k] = packL(nextLP[k]); });
    return { hist: { year: year, seed: seed, cs: cs, ls: ls, copt: optsC, lopt: lopt, rp: rp,
      plan: { cs: pcs, ls: pls, opts: pOpts }, chk: keep, done: done, ev: ev,
      shock: { G: R(world.G), Pi: R(world.Pi), T: R(wT) }, agg: { forks: aggregate(nextC), plan: aggregate(nextP) } }, reverts: reverts };
  }
  // применить откаты к правилам (возвращает изменённые ключи)
  function applyReverts(rules, reverts, year) {
    var touched = {};
    reverts.forEach(function (rv) {
      var r = rules[rv.key]; if (!r) return;
      rv.qs.forEach(function (q, i) {
        if (!r[q] || r[q].pid !== rv.pid) return;
        if (+rv.prev[i] === 0 || (rv.own && !rv.own[i])) delete r[q]; else r[q] = { pid: 'revert:' + rv.pid, opt: +rv.prev[i], since: year };
        touched[rv.key] = true;
      });
    });
    return Object.keys(touched);
  }
  return { step: step, initialHistory: initialHistory, unpackC: unpackC, unpackL: unpackL, packC: packC, packL: packL,
    countryOpts: countryOpts, localOpts: localOpts, planOptions: planOptions, LOCALQ: LOCALQ, aggregate: aggregate,
    applyReverts: applyReverts, isCountry: isCountry };
})(typeof SIM !== 'undefined' ? SIM : require('./sim.js'));
if (typeof module !== 'undefined') module.exports = ENGINE;
