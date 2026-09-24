'use strict';
// ════════════════════════ «После вспышки» — модель восстановления мира, шаг = месяц
// Состояние + решения → следующее состояние. Детерминировано по сиду: одна и та же история решений даёт тот же мир.
const WORLD = (() => {
  const MODELV = '3.0.1';
  let D = null, N = 0, ISO = [], C = [], FACT = [], SPACE = [];
  const clamp = (x, a, b) => x < a ? a : x > b ? b : x;
  const sat = x => x <= 0 ? 0 : x >= 1 ? 1 : x;
  // ── календарь: вспышка 1 октября 2026 (месяц 0 — первые тридцать дней после неё)
  const M0 = 9, Y0 = 2026;
  const MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];
  const MONTHS_G = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  function cal(t) { const m = (M0 + t) % 12, y = Y0 + Math.floor((M0 + t) / 12); return { m, y }; }
  function label(t) { const c = cal(t); return MONTHS[c.m] + ' ' + c.y; }
  function labelShort(t) { const c = cal(t); return MONTHS[c.m].slice(0, 3) + ' ' + c.y; }
  // ── рычаги решений
  const LEVERS = [
    { k: 'prC', ru: 'Приоритет: связь', hint: 'доля бригад и топлива на радиосеть, вышки и узлы связи', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.25 },
    { k: 'prW', ru: 'Приоритет: вода и еда', hint: 'насосы, склады, раздача, полевые кухни', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.25 },
    { k: 'prG', ru: 'Приоритет: электросеть', hint: 'ремонт и монтаж трансформаторов, линии', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.25 },
    { k: 'prL', ru: 'Приоритет: логистика', hint: 'топливо на транспорт, порты, склады, дороги', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.25 },
    { k: 'ration', ru: 'Нормирование топлива', hint: '0 — как обычно (запас кончится быстро), 1 — только больницы, вода, связь и подвоз', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.6 },
    { k: 'exportT', ru: 'Доля трансформаторов на экспорт', hint: 'какую часть выпуска заводов страна отдаёт другим (только страны с заводами)', kind: 'num', min: 0, max: 1, step: 0.05, unit: 'доля', def: 0.3 },
    { k: 'aidT', ru: 'Отправить трансформаторы', hint: 'штук из своих запасов и полученных поставок; доедут за месяц', kind: 'iso', min: 0, max: 500, step: 1, unit: 'шт.', once: true },
    { k: 'aidF', ru: 'Отправить топливо', hint: 'в днях критического потребления получателя', kind: 'iso', min: 0, max: 180, step: 5, unit: 'дней', once: true },
    { k: 'aidFood', ru: 'Отправить продовольствие', hint: 'в днях потребления получателя', kind: 'iso', min: 0, max: 180, step: 5, unit: 'дней', once: true },
    { k: 'aidC', ru: 'Отправить бригады', hint: 'тысяч человек ремонтных бригад; работают у получателя, пока их не вернут', kind: 'iso', min: 0, max: 200, step: 1, unit: 'тыс. чел.', once: true },
    { k: 'aidR', ru: 'Отправить радиокомплекты', hint: 'наборы КВ-радио и спутниковых терминалов: быстрая связь для страны без сети', kind: 'iso', min: 0, max: 10, step: 1, unit: 'компл.', once: true }
  ];
  const LEV = {}; LEVERS.forEach(l => { LEV[l.k] = l; });
  function setup(data) {
    D = data; ISO = data.iso; N = ISO.length; C = data.countries;
    FACT = ISO.map(iso => data.fact[iso] || 0); SPACE = ISO.map(iso => data.space.includes(iso));
  }
  // ── случайность, воспроизводимая по сиду
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  // ── стартовое состояние: сразу после бури
  function init(seed) {
    const r = rng(seed);
    const st = { t: 0, seed, S: 0.3, rs: 0, prodM: 0, ev: [], storm2: 0 };
    const F = k => (st[k] = new Float64Array(N));
    ['P', 'gdp', 'Tt', 'Td', 'Trep', 'Tnew', 'Tsp', 'Tin', 'crews', 'crewsHome', 'fuel', 'fuelProd', 'fuelIn', 'food', 'foodProd', 'foodIn', 'radio', 'netRep', 'net', 'comms', 'logi', 'water', 'grid', 'pcrit', 'served', 'hungry', 'losses', 'pm', 'econ', 'prod', 'dmg', 'kits', 'fuelUse', 'aidOut', 'aidIn', 'dry'].forEach(F);
    for (let c = 0; c < N; c++) {
      const k = C[c];
      st.P[c] = k.P; st.gdp[c] = k.gdp;
      const Tt = Math.round(20 + k.gdp / 10);
      // урон: сильнее на высоких геомагнитных широтах; худший случай — везде больше половины узлов
      const dmg = clamp(0.55 + 0.42 * sat((Math.abs(k.gm) - 30) / 30) + (r() - 0.5) * 0.08, 0.5, 0.97);
      st.Tt[c] = Tt; st.dmg[c] = dmg;
      const Td = dmg * Tt; st.Trep[c] = Td * 0.25; st.Tnew[c] = Td * 0.75; st.Td[c] = Td;
      st.Tsp[c] = Tt * 0.03;
      st.crews[c] = st.crewsHome[c] = Math.max(0.6, 1.5 * k.L, 0.03 * Tt); // тысяч человек ремонтных бригад (0,15 % рабочей силы, не меньше трёх на сотню узлов)
      const ypc = k.gdp / Math.max(0.01, k.P);                              // тыс. $ на человека
      st.fuel[c] = 1.0 + 1.5 * Math.min(1, k.fuelSS) + 0.5 * sat(ypc / 40); // месяцев обычного потребления
      st.fuelProd[c] = k.fuelSS;                                             // месяцев обычного потребления в месяц при полной мощности
      st.food[c] = 1.0 + 2 * Math.min(1, k.foodSS) + 0.8 * sat(ypc / 40);
      st.foodProd[c] = k.foodSS;
      st.radio[c] = 0.05; st.netRep[c] = 0.05; st.grid[c] = 1 - Td / Tt; st.econ[c] = 0.3;
    }
    st.rs = Math.floor(r() * 2 ** 31);
    derive(st);
    for (let c = 0; c < N; c++) { st.water[c] = clamp(0.3 + 0.7 * st.pcrit[c] + 0.05, 0, 1); st.served[c] = st.water[c]; st.hungry[c] = 0; }
    return st;
  }
  // производные величины (после шага и на старте)
  function derive(st) {
    for (let c = 0; c < N; c++) {
      st.grid[c] = clamp(1 - st.Td[c] / st.Tt[c], 0, 1);
      const fuelAv = sat(st.fuel[c] / 0.5);
      st.pcrit[c] = Math.min(1, st.grid[c] * 1.6 + 0.4 * fuelAv * (1 - st.grid[c]));
      st.net[c] = st.pcrit[c] * sat(st.netRep[c]);
      st.comms[c] = clamp(0.3 * st.radio[c] + 0.5 * st.net[c] + 0.2 * st.S, 0, 1);
      st.logi[c] = clamp((0.15 + 0.85 * fuelAv) * (0.5 + 0.5 * st.comms[c]) * (0.6 + 0.4 * st.pcrit[c]), 0, 1);
      st.water[c] = clamp(0.3 + 0.7 * st.pcrit[c] + st.water[c] * 0, 0, 1);
    }
  }
  // сезон урожая: доля годового производства, приходящаяся на месяц m (0 — январь)
  function harvest(lat, m) {
    if (Math.abs(lat) < 20) return 1 / 12;
    const north = lat >= 0, mm = north ? m : (m + 6) % 12;   // юг — сдвиг на полгода
    return (mm >= 6 && mm <= 9) ? 0.14 : 0.055;             // июль–октябрь: 56 % года
  }
  function priorities(p) {
    const a = ['prC', 'prW', 'prG', 'prL'].map(k => p && p[k] != null ? +p[k] : 0.25), s = a.reduce((x, y) => x + y, 0) || 1;
    return a.map(x => x / s);
  }
  function isoIdx(iso) { return ISO.indexOf(iso); }
  // ── шаг: от месяца t к t+1
  function step(st0, polArr, wev) {
    wev = wev || {};
    const st = cloneSt(st0), t = st0.t + 1, cm = cal(t).m, r = rng(st0.rs ^ (t * 2654435761)), calm = !!wev.calm;
    st.t = t; st.ev = []; st.prodM = 0;
    const pol = polArr || {};
    const fuelAv0 = new Float64Array(N), pri = [];
    for (let c = 0; c < N; c++) { fuelAv0[c] = sat(st0.fuel[c] / 0.5); pri.push(priorities(pol[c])); st.aidIn[c] = 0; st.aidOut[c] = 0; st.prod[c] = 0; }
    // 0) спутники: запуски возобновляются, когда у космических держав есть свет и логистика
    let sp = 0, ns = 0; for (let c = 0; c < N; c++) if (SPACE[c]) { sp += st0.econ[c]; ns++; }
    if (t >= 3) st.S = Math.min(1, st0.S + 0.02 * (sp / Math.max(1, ns)));
    // 1) события: вторая буря, зима
    let storm2 = false;
    if (!calm && t >= 2 && st0.storm2 === 0 && r() < 0.01) { storm2 = true; st.storm2 = t; st.ev.push({ k: 'storm2', t }); }
    // 2) поступления в пути (помощь и поставки прошлого месяца) уже лежат в *In — зачисляем
    for (let c = 0; c < N; c++) {
      if (st.Tin[c] > 0) { st.Tnew[c] -= 0; }   // трансформаторы зачисляются при монтаже ниже
      st.fuel[c] += st.fuelIn[c]; st.fuelIn[c] = 0;
      st.food[c] += st.foodIn[c]; st.foodIn[c] = 0;
    }
    // 3) связь: радиосеть быстро, сотовая и оптика — по мере питания и ремонта
    for (let c = 0; c < N; c++) {
      const cf = 0.5 + 0.5 * sat(st0.crews[c] / Math.max(0.3, st0.crewsHome[c]));
      const kits = st.kits[c] > 0 ? 0.08 * st.kits[c] : 0; st.kits[c] = 0;
      st.radio[c] = clamp(st0.radio[c] + 0.12 * (0.3 + 2 * pri[c][0]) * cf + kits, 0, 0.9);
      st.netRep[c] = clamp(st0.netRep[c] + 0.06 * (0.3 + 2 * pri[c][0]) * cf * (0.4 + 0.6 * fuelAv0[c]), 0, 1);
    }
    // 4) топливо: добыча и переработка требуют света; потребление — по нормированию; рынок — по логистике
    const need = new Float64Array(N), surplus = new Float64Array(N); let sumNeed = 0, sumSur = 0;
    for (let c = 0; c < N; c++) {
      const p = pol[c] || {}, ration = p.ration != null ? +p.ration : LEV.ration.def;
      const useN = (0.35 + 0.65 * (1 - ration)) * (0.5 + 0.5 * st0.logi[c]);
      const winter = (!calm && Math.abs(C[c].lat) > 45 && (cm === 11 || cm === 0 || cm === 1)) ? 1.3 : 1;
      const use = useN * winter;
      const prod = st0.fuelProd[c] * (0.15 + 0.85 * sat(st0.pcrit[c] * 1.2)) * (0.6 + 0.4 * st0.logi[c]);
      st.fuelUse[c] = use;
      st.fuel[c] = Math.min(6, st.fuel[c] + prod - use);   // хранилищ больше чем на полгода нет
      if (st.fuel[c] < 0) { st.fuel[c] = 0; }
      // рынок: экспортёры предлагают избыток сверх трёх месяцев запаса, импортёры просят до месяца запаса
      if (st.fuel[c] > 3 && st0.fuelProd[c] > 1.1) { surplus[c] = (st.fuel[c] - 3) * 0.5 * st0.logi[c]; sumSur += surplus[c] * C[c].fuelUse; }
      else if (st.fuel[c] < 1) { need[c] = (1 - st.fuel[c]) * st0.logi[c] * (0.3 + 0.7 * st0.comms[c]); sumNeed += need[c] * C[c].fuelUse; }
    }
    if (sumSur > 0 && sumNeed > 0) {
      const f = Math.min(1, sumSur / sumNeed);   // доля потребностей, которую рынок закрывает
      for (let c = 0; c < N; c++) if (need[c] > 0) st.fuel[c] += need[c] * f;
      const g = Math.min(1, sumNeed / sumSur);
      for (let c = 0; c < N; c++) if (surplus[c] > 0) st.fuel[c] -= surplus[c] * g;
    }
    // 5) еда: производство по сезону, топливу и питанию; раздача — по логистике; рынок — как топливо
    const fneed = new Float64Array(N), fsur = new Float64Array(N); let sfn = 0, sfs = 0;
    for (let c = 0; c < N; c++) {
      const prod = st0.foodProd[c] * 12 * harvest(C[c].lat, cm) * (0.4 + 0.6 * fuelAv0[c]) * (0.7 + 0.3 * st0.pcrit[c]);
      st.food[c] = Math.min(8, st.food[c] + prod);
      if (st.food[c] > 3 && st0.foodProd[c] > 1.05) { fsur[c] = (st.food[c] - 3) * 0.5 * st0.logi[c]; sfs += fsur[c] * C[c].foodUse; }
      else if (st.food[c] < 1) { fneed[c] = (1 - st.food[c]) * st0.logi[c] * (0.3 + 0.7 * st0.comms[c]); sfn += fneed[c] * C[c].foodUse; }
    }
    if (sfs > 0 && sfn > 0) {
      const f = Math.min(1, sfs / sfn), g = Math.min(1, sfn / sfs);
      for (let c = 0; c < N; c++) { if (fneed[c] > 0) st.food[c] += fneed[c] * f; if (fsur[c] > 0) st.food[c] -= fsur[c] * g; }
    }
    for (let c = 0; c < N; c++) {
      const dist = 0.35 + 0.65 * st0.logi[c] + 0.15 * pri[c][1];
      const delivered = Math.min(st.food[c], Math.min(1, dist));
      st.hungry[c] = clamp(1 - delivered, 0, 1);
      st.food[c] = Math.max(0, st.food[c] - delivered);
    }
    // 6) помощь по решениям: трансформаторы, топливо, еда, бригады, радиокомплекты (приходят через месяц)
    for (let c = 0; c < N; c++) {
      const p = pol[c]; if (!p) continue;
      const canSend = st0.logi[c] >= 0.2 && st0.comms[c] >= 0.2;
      const each = (key, fn) => { const m = p[key]; if (!m || typeof m !== 'object') return; for (const iso in m) { const d = isoIdx(iso); if (d < 0 || d === c) continue; const v = +m[iso]; if (!(v > 0)) continue; if (!canSend || st0.comms[d] < 0.15) { st.ev.push({ k: 'aidfail', from: ISO[c], to: iso, what: key }); continue; } fn(d, v); } };
      each('aidT', (d, v) => { const avail = st.Tsp[c]; const q = Math.min(v, avail); if (q <= 0) return; st.Tsp[c] -= q; st.Tin[d] += q; st.aidOut[c] += q; st.aidIn[d] += q; st.ev.push({ k: 'aid', from: ISO[c], to: ISO[d], what: 'T', q }); });
      each('aidF', (d, v) => { const months = v / 30 * (C[d].fuelUse / Math.max(1e-6, C[c].fuelUse)); const q = Math.min(months, Math.max(0, st.fuel[c] - 0.5)); if (q <= 0) return; st.fuel[c] -= q; st.fuelIn[d] += q * C[c].fuelUse / Math.max(1e-6, C[d].fuelUse); st.ev.push({ k: 'aid', from: ISO[c], to: ISO[d], what: 'F', q: v }); });
      each('aidFood', (d, v) => { const months = v / 30 * (C[d].foodUse / Math.max(1e-6, C[c].foodUse)); const q = Math.min(months, Math.max(0, st.food[c] - 0.7)); if (q <= 0) return; st.food[c] -= q; st.foodIn[d] += q * C[c].foodUse / Math.max(1e-6, C[d].foodUse); st.ev.push({ k: 'aid', from: ISO[c], to: ISO[d], what: 'Food', q: v }); });
      each('aidC', (d, v) => { const q = Math.min(v, Math.max(0, st.crews[c] - 0.3)); if (q <= 0) return; st.crews[c] -= q; st.crews[d] += q; st.ev.push({ k: 'aid', from: ISO[c], to: ISO[d], what: 'C', q }); });
      each('aidR', (d, v) => { if (st0.econ[c] < 0.25) return; const q = Math.min(v, 5); st.kits[d] += q; st.ev.push({ k: 'aid', from: ISO[c], to: ISO[d], what: 'R', q }); });
    }
    // 7) ремонт и монтаж: бригады по приоритету «сеть»; запасные и полученные единицы ставятся первыми
    for (let c = 0; c < N; c++) {
      const crews = st.crews[c] * (0.25 + 0.75 * pri[c][2]) * (0.5 + 0.5 * st0.logi[c]);
      let cap = crews * 2.0;                       // монтажных единиц в месяц (на тысячу человек)
      let pool = st.Tsp[c] + st.Tin[c];             // что есть на руках
      const inst = Math.min(cap, pool, st.Tnew[c]);
      if (inst > 0) { st.Tnew[c] -= inst; cap -= inst; if (st.Tin[c] >= inst) st.Tin[c] -= inst; else { const rest = inst - st.Tin[c]; st.Tin[c] = 0; st.Tsp[c] -= rest; } }
      const rep = Math.min(cap * 0.5, st.Trep[c]);
      st.Trep[c] -= rep;
      st.Td[c] = st.Trep[c] + st.Tnew[c];
    }
    // 8) заводы: выпуск требует света и подвоза; мобилизация — до ×3 к 18-му месяцу; экспорт по решению
    const ramp = 1 + 2 * sat(t / 18), base = 34;   // единиц в месяц в мире при полной мощности до мобилизации (~2,6 % парка в год)
    const exportPool = []; let poolQ = 0;
    for (let c = 0; c < N; c++) {
      if (!FACT[c]) continue;
      const out = base * ramp * FACT[c] * (0.1 + 0.9 * st0.pcrit[c]) * (0.5 + 0.5 * st0.logi[c]);
      st.prod[c] = out; st.prodM += out;
      const p = pol[c] || {}, ex = p.exportT != null ? +p.exportT : LEV.exportT.def;
      const own = Math.min(out * (1 - ex), Math.max(0, st.Tnew[c] - st.Tsp[c] - st.Tin[c]));
      st.Tsp[c] += own;
      const q = out - own; if (q > 0) { poolQ += q; }
    }
    // распределение экспорта: туда, где одна единица возвращает свет большему числу людей, и куда можно довезти
    if (poolQ > 0) {
      const w = [];
      for (let c = 0; c < N; c++) { const lack = st.Tnew[c] - st.Tsp[c] - st.Tin[c]; if (lack <= 0 || st0.comms[c] < 0.25 || st0.logi[c] < 0.25) continue; w.push([c, st0.P[c] * (1 - st0.grid[c]) / st0.Tt[c]]); }
      const sw = w.reduce((a, x) => a + x[1], 0);
      if (sw > 0) for (const [c, wt] of w) { const q = poolQ * wt / sw; st.Tin[c] += q; st.aidIn[c] += q; }
      else for (let c = 0; c < N; c++) if (FACT[c]) st.Tsp[c] += poolQ * FACT[c];
    }
    // 9) вторая буря: часть восстановленного ломается снова на высоких широтах
    if (storm2) for (let c = 0; c < N; c++) { if (Math.abs(C[c].gm) > 45) { const d = (st.Tt[c] - st.Td[c]) * 0.08; st.Tnew[c] += d * 0.5; st.Trep[c] += d * 0.5; st.Td[c] = st.Trep[c] + st.Tnew[c]; st.netRep[c] *= 0.85; } }
    // 10) вода, снабжение, потери
    derive(st);
    for (let c = 0; c < N; c++) {
      st.water[c] = clamp(0.3 + 0.7 * st.pcrit[c] + 0.2 * pri[c][1], 0, 1);
      st.served[c] = clamp(st.water[c] * (1 - st.hungry[c]), 0, 1);
      st.dry[c] = st.water[c] < 0.5 ? st0.dry[c] + 1 : 0;
      const rate = 0.0004 * (1 - st.served[c]) + 0.0006 * st.hungry[c] + (st.dry[c] >= 2 ? 0.0006 : 0);   // избыточная смертность в месяц — грубая оценка
      st.losses[c] = st0.losses[c] + st.P[c] * 1000 * rate;   // тысяч человек
      st.pm[c] = st0.pm[c] + st.P[c] * (1 - st.served[c]);      // человеко-месяцев без снабжения, млн
      st.econ[c] = clamp(0.15 + 0.85 * st.grid[c] * (0.5 + 0.5 * st.logi[c]) * (0.7 + 0.3 * st.comms[c]), 0, 1);
    }
    st.rs = Math.floor(r() * 2 ** 31);
    return { st };
  }
  function cloneSt(s) {
    const o = {};
    for (const k in s) { const v = s[k]; o[k] = v instanceof Float64Array ? new Float64Array(v) : Array.isArray(v) ? v.slice() : v; }
    return o;
  }
  // ── сводка для интерфейса и хранения
  const KEYS = ['grid', 'comms', 'logi', 'served', 'hungry', 'food', 'fuel', 'water', 'losses', 'pm', 'econ', 'Tt', 'Td', 'Trep', 'Tnew', 'Tsp', 'Tin', 'crews', 'radio', 'net', 'pcrit', 'prod', 'aidIn', 'aidOut', 'P', 'dmg', 'fuelUse'];
  function summary(st) {
    const c = [];
    for (let i = 0; i < N; i++) c.push(KEYS.map(k => +(+st[k][i]).toFixed(4)));
    const w = world(st);
    return { k: KEYS, c, w, ev: st.ev.slice(0, 40), t: st.t };
  }
  function world(st) {
    let P = 0, g = 0, cm = 0, lg = 0, sv = 0, ec = 0, L = 0, pm = 0, hungry = 0, Td = 0, Tt = 0, prod = 0;
    for (let c = 0; c < N; c++) { const p = st.P[c]; P += p; g += p * st.grid[c]; cm += p * st.comms[c]; lg += p * st.logi[c]; sv += p * st.served[c]; ec += p * st.econ[c]; L += st.losses[c]; pm += st.pm[c]; hungry += p * st.hungry[c]; Td += st.Td[c]; Tt += st.Tt[c]; prod += st.prod[c]; }
    return { P, grid: g / P, comms: cm / P, logi: lg / P, served: sv / P, econ: ec / P, losses: L, pm, hungry: hungry / P, Td, Tt, prod, S: st.S, storm2: st.storm2 };
  }
  // фазы восстановления: цель проекта
  const PHASES = [
    { k: 'comms', ru: 'Связь', goal: 0.6, hint: 'радиосеть, вышки и спутники: мир снова слышит друг друга' },
    { k: 'logi', ru: 'Логистика', goal: 0.6, hint: 'топливо, порты, склады: грузы снова ходят' },
    { k: 'served', ru: 'Снабжение', goal: 0.9, hint: 'вода и еда доходят до людей' },
    { k: 'grid', ru: 'Свет', goal: 0.8, hint: 'электросеть восстановлена в основном' },
    { k: 'econ', ru: 'Восстановление', goal: 0.9, hint: 'экономика работает почти как до бури' }
  ];
  // ── очистка решений
  function sanitize(p, iso) {
    const o = {}; if (!p || typeof p !== 'object') return o;
    const c = isoIdx(iso);
    for (const L of LEVERS) {
      const v = p[L.k]; if (v == null) continue;
      if (L.kind === 'num') { const x = +v; if (!isFinite(x)) continue; if (L.k === 'exportT' && !(c >= 0 && FACT[c])) continue; o[L.k] = +clamp(x, L.min, L.max).toFixed(3); }
      else if (L.kind === 'iso') {
        if (typeof v !== 'object') continue; const m = {};
        for (const k in v) { if (isoIdx(k) < 0 || k === iso) continue; const x = +v[k]; if (!isFinite(x) || x <= 0) continue; m[k] = +clamp(Math.round(x / L.step) * L.step, L.min, L.max).toFixed(2); }
        if (Object.keys(m).length) o[L.k] = m;
      }
    }
    // приоритеты, если заданы, нормируются на единицу
    const pk = ['prC', 'prW', 'prG', 'prL'].filter(k => o[k] != null);
    if (pk.length) { const full = priorities(Object.assign({}, { prC: 0.25, prW: 0.25, prG: 0.25, prL: 0.25 }, o)); ['prC', 'prW', 'prG', 'prL'].forEach((k, i) => { o[k] = +full[i].toFixed(3); }); }
    return o;
  }
  function isFactory(iso) { const c = isoIdx(iso); return c >= 0 && FACT[c] > 0; }
  function factShare(iso) { const c = isoIdx(iso); return c >= 0 ? FACT[c] : 0; }
  return { MODELV, LEVERS, PHASES, KEYS, setup, init, step, summary, world, sanitize, cal, label, labelShort, isFactory, factShare, priorities, harvest, get N() { return N; }, get ISO() { return ISO; }, get C() { return C; } };
})();
