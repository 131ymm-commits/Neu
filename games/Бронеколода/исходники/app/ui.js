// Бронеколода — интерфейс: отрисовка стола, ввод, анимации, звук, ход ИИ.
(() => {
  'use strict';
  const E = window.Engine, A = window.Art;
  const ME = 0, OP = 1;
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const T = ms => reduce ? Math.min(ms, 80) : ms;
  const sleep = ms => new Promise(r => setTimeout(r, T(ms)));
  const canHover = window.matchMedia && matchMedia('(hover: hover) and (pointer: fine)').matches;

  let S = null;
  const U = {
    screen: 'start', doctrine: 'A', sel: null, pending: null, busy: false, mull: new Set(),
    sound: true, ai: false, seen: new Set(), seenHand: new Set(), seenBacks: 0, pointer: null,
    record: { w: 0, l: 0 }, hintMsg: '', hintWarn: false
  };

  // ---------- хранилище (только удобства одного зрителя) ----------
  const store = {
    get(k, d) { try { const v = localStorage.getItem('bronekoloda.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('bronekoloda.' + k, JSON.stringify(v)); } catch (e) { /* без хранилища */ } }
  };

  // ---------- звук ----------
  const Snd = (() => {
    let ctx = null;
    function ac() {
      if (!U.sound) return null;
      try { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === 'suspended') ctx.resume(); } catch (e) { ctx = null; }
      return ctx;
    }
    function noise(dur, freq, gain, q) {
      const c = ac(); if (!c) return;
      const len = Math.floor(c.sampleRate * dur), buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.2);
      const src = c.createBufferSource(); src.buffer = buf;
      const fl = c.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.value = freq; fl.Q.value = q || 0.7;
      const g = c.createGain(); g.gain.value = gain * 0.5;
      src.connect(fl); fl.connect(g); g.connect(c.destination); src.start();
    }
    function tone(f, dur, type, gain, f2) {
      const c = ac(); if (!c) return;
      const o = c.createOscillator(), g = c.createGain(); o.type = type; o.frequency.setValueAtTime(f, c.currentTime);
      if (f2) o.frequency.exponentialRampToValueAtTime(f2, c.currentTime + dur);
      g.gain.setValueAtTime(gain * 0.5, c.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + dur);
      o.connect(g); g.connect(c.destination); o.start(); o.stop(c.currentTime + dur + 0.02);
    }
    return {
      shot() { noise(0.45, 700, 0.9); tone(90, 0.3, 'sine', 0.7, 40); },
      mg() { for (let i = 0; i < 4; i++) setTimeout(() => noise(0.06, 2400, 0.35), i * 70); },
      hit() { noise(0.18, 1600, 0.4); },
      boom() { noise(0.9, 380, 1); tone(60, 0.5, 'sine', 0.6, 30); },
      play() { tone(180, 0.12, 'triangle', 0.25, 120); noise(0.12, 500, 0.2); },
      click() { tone(720, 0.04, 'square', 0.05); },
      turn() { tone(392, 0.14, 'triangle', 0.22); setTimeout(() => tone(587, 0.22, 'triangle', 0.22), 130); },
      heal() { tone(520, 0.18, 'sine', 0.18, 780); },
      clang() { tone(900, 0.12, 'square', 0.08, 500); noise(0.1, 3000, 0.2); },
      win() { [392, 494, 587, 784].forEach((f, i) => setTimeout(() => tone(f, 0.3, 'triangle', 0.22), i * 140)); },
      lose() { [392, 330, 262].forEach((f, i) => setTimeout(() => tone(f, 0.4, 'triangle', 0.2), i * 200)); }
    };
  })();

  // ---------- карта местности на холсте ----------
  function drawMap() {
    const cv = $('map'), field = $('field');
    const r = field.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = r.width, H = r.height;
    // рельеф: холмы-гауссианы с фиксированным зерном партии
    let seed = (S ? S.seed : 7) ^ 0x51ED;
    const rr = () => { seed = (seed * 1664525 + 1013904223) | 0; return ((seed >>> 0) % 10000) / 10000; };
    const hills = [];
    for (let i = 0; i < 9; i++) hills.push({ x: rr() * W, y: rr() * H, s: (0.12 + rr() * 0.22) * Math.max(W, H), a: (rr() < 0.25 ? -0.6 : 1) * (0.5 + rr()) });
    const step = 7, nx = Math.ceil(W / step) + 1, ny = Math.ceil(H / step) + 1;
    const F = new Float32Array(nx * ny);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const x = i * step, y = j * step;
      let v = 0.08 * Math.sin(x / 90 + y / 140) + 0.05 * Math.cos(x / 50 - y / 70);
      for (const h of hills) { const dx = x - h.x, dy = y - h.y; v += h.a * Math.exp(-(dx * dx + dy * dy) / (2 * h.s * h.s)); }
      F[j * nx + i] = v;
    }
    g.clearRect(0, 0, W, H);
    // километровая сетка
    const km = Math.max(56, Math.min(96, W / 12));
    g.strokeStyle = 'rgba(236,229,207,0.10)'; g.lineWidth = 1;
    g.beginPath();
    for (let x = km / 2; x < W; x += km) { g.moveTo(Math.round(x) + .5, 0); g.lineTo(Math.round(x) + .5, H); }
    for (let y = km / 2; y < H; y += km) { g.moveTo(0, Math.round(y) + .5); g.lineTo(W, Math.round(y) + .5); }
    g.stroke();
    // горизонтали (марширующие квадраты)
    const lerp = (a, b, L) => (L - a) / (b - a);
    for (let k = -4; k <= 16; k++) {
      const L = k * 0.11;
      g.strokeStyle = k % 5 === 0 ? 'rgba(35,30,12,0.42)' : 'rgba(35,30,12,0.22)';
      g.lineWidth = k % 5 === 0 ? 1.4 : 0.9;
      g.beginPath();
      for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
        const a = F[j * nx + i], b = F[j * nx + i + 1], c = F[(j + 1) * nx + i + 1], d = F[(j + 1) * nx + i];
        const idx = (a > L ? 8 : 0) | (b > L ? 4 : 0) | (c > L ? 2 : 0) | (d > L ? 1 : 0);
        if (idx === 0 || idx === 15) continue;
        const x = i * step, y = j * step;
        const T_ = [x + step * lerp(a, b, L), y], R = [x + step, y + step * lerp(b, c, L)], B = [x + step * lerp(d, c, L), y + step], Lf = [x, y + step * lerp(a, d, L)];
        const seg = (p, q) => { g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); };
        switch (idx) {
          case 1: case 14: seg(Lf, B); break;
          case 2: case 13: seg(B, R); break;
          case 3: case 12: seg(Lf, R); break;
          case 4: case 11: seg(T_, R); break;
          case 5: seg(Lf, T_); seg(B, R); break;
          case 6: case 9: seg(T_, B); break;
          case 7: case 8: seg(Lf, T_); break;
          case 10: seg(Lf, B); seg(T_, R); break;
        }
      }
      g.stroke();
    }
    // подписи сетки и масштаба
    g.fillStyle = 'rgba(236,229,207,0.38)';
    g.font = '500 10px "IBM Plex Mono", monospace';
    let n = 37;
    for (let x = km / 2; x < W; x += km) g.fillText(String(n++).padStart(2, '0'), x + 3, 12);
    n = 64;
    for (let y = km / 2; y < H; y += km) g.fillText(String(n--), 3, y - 3);
    g.textAlign = 'right';
    g.fillText('М 1:50 000', W - 8, H - 7);
  }
  let mapTimer = 0;
  function scheduleMap() { clearTimeout(mapTimer); mapTimer = setTimeout(drawMap, 120); }

  // ---------- разметка ----------
  const UNIT_VB = '8 18 104 56';
  const POWER_ICON = {
    A: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="6.5" fill="none" stroke="#f1e8cc" stroke-width="2.2"/><path d="M12 1.5v7M12 15.5v7M1.5 12h7M15.5 12h7" stroke="#f1e8cc" stroke-width="2.2"/></svg>',
    B: '<svg viewBox="0 0 24 24"><path d="M2.5 14.5l15-8.5 2 3.2-15 8.5z"/><circle cx="7" cy="18" r="3.6"/><path d="M17 4.6l3.6-2 1.6 2.8-3.6 2z"/></svg>',
    C: '<svg viewBox="0 0 24 24"><path d="M11 1h2v12h-2z"/><path d="M6.5 12.5h11l-1.2 6.2C15.8 21 14.2 23 12 23s-3.8-2-4.3-4.3z"/><rect x="8.5" y="0.5" width="7" height="2.6" rx="1"/></svg>'
  };

  function cardHTML(id, o) {
    o = o || {};
    const d = E.CARDS[id], doc = d.doc || 'N';
    const atk = o.atk == null ? d.atk : o.atk, hp = o.hp == null ? d.hp : o.hp;
    const atkCls = atk > d.atk ? ' up' : '', hpCls = hp > d.hp ? ' up' : (o.maxHp != null && hp < o.maxHp ? ' down' : '');
    return `<div class="card doc-${doc} ${d.type === 'unit' ? 'unit-card' : 'order'} ${o.cls || ''}" ${o.attrs || ''}>` +
      `<div class="c-art">${A.svg(d.art)}</div>` +
      `<div class="c-cost"><span>${d.cost}</span></div>` +
      (d.type === 'order' ? '<div class="c-stamp">ПРИКАЗ</div>' : '') +
      `<div class="c-name">${esc(d.name)}</div>` +
      `<div class="c-cls">${esc(d.cls)}${d.cal ? ' · ' + esc(d.cal) : ''}</div>` +
      `<div class="c-text">${E.cardText(id, o.sp || 0)}</div>` +
      (d.type === 'unit' ? `<div class="c-atk${atkCls}">${atk}</div><div class="c-hp${hpCls}">${hp}</div>` : '') +
      `</div>`;
  }

  function unitHTML(m, side, targets) {
    const d = E.CARDS[m.id];
    const ready = side === 'me' && S.active === ME && !U.busy && E.attackTargets(S, ME, m.uid).length > 0;
    const cls = ['unit', side, 'doc-' + (d.doc || 'N'),
      m.taunt && 'taunt', m.shield && 'shield', m.stealth && 'stealth', m.frozenAt != null && 'frozen',
      ready && 'ready', U.sel && U.sel.k === 'unit' && U.sel.uid === m.uid && 'selected',
      targets.includes(m.uid) && 'is-target', !U.seen.has(m.uid) && 'enter'].filter(Boolean).join(' ');
    const badges = [];
    if (m.windfury) badges.push('<i title="Автомат заряжания">×2</i>');
    if (m.poison) badges.push('<i title="Кумулятивный">К</i>');
    if (m.spellDmg) badges.push(`<i title="Приказы +${m.spellDmg} урона">+${m.spellDmg}</i>`);
    if (d.eot) badges.push(`<i title="В конце хода">${A.ICONS.gear}</i>`);
    if (d.dr) badges.push(`<i title="При уничтожении">${A.ICONS.cross}</i>`);
    if (m.cantAttack) badges.push('<i title="Не атакует">—</i>');
    const sleep = side === 'me' && m.sleep && !m.charge && !m.rush && !m.cantAttack && S.active === ME;
    const atkCls = m.atk > d.atk ? ' up' : '', hpCls = m.hp < m.maxHp ? ' down' : (m.hp > d.hp ? ' up' : '');
    return `<div class="${cls}" data-uid="${m.uid}" data-side="${side}" role="button" tabindex="0" aria-label="${esc(d.name)}, атака ${m.atk}, прочность ${m.hp}">` +
      `<div class="u-stripe"></div><div class="u-art">${A.svg(d.art, UNIT_VB)}</div>` +
      (m.stealth ? '<div class="u-veil"></div>' : '') +
      `<div class="u-badges">${badges.join('')}</div>` +
      (sleep ? '<div class="u-sleep">zZ</div>' : '') +
      (m.frozenAt != null ? '<div class="u-frz">обездвижен</div>' : '') +
      `<div class="u-atk${atkCls}">${m.atk}</div><div class="u-hp${hpCls}">${m.hp}</div><i class="ret"></i></div>`;
  }

  function hqHTML(p, targets) {
    const pl = S.players[p], doc = E.DOCTRINES[pl.doctrine], side = p === ME ? 'Me' : 'Op';
    const pw = doc.power;
    const myTurn = S.active === ME && S.phase === 'play' && !U.busy;
    const canPw = p === ME && myTurn && E.canPower(S, ME);
    const pwCls = ['power', 'doc-' + pl.doctrine, p === OP && 'power-op', pl.powerUsed && 'used', canPw && 'ready', U.sel && U.sel.k === 'power' && p === ME && 'selected'].filter(Boolean).join(' ');
    let pips = '';
    for (let i = 0; i < 10; i++) pips += `<i class="${i < pl.mana ? 'on' : i < pl.maxMana ? 'spent' : ''}"></i>`;
    const hurt = pl.hero.hp < pl.hero.maxHp ? ' hurt' : '';
    return `<div class="fuel" title="Топливо: ${pl.mana} из ${pl.maxMana}"><div class="fuel-num">${pl.mana}<small>/${pl.maxMana}</small></div><div class="fuel-pips">${pips}</div><div class="fuel-lbl">топливо</div></div>` +
      `<button type="button" class="hq doc-${pl.doctrine}${targets.includes(pl.hero.uid) ? ' is-target' : ''}" data-uid="${pl.hero.uid}" data-side="${p === ME ? 'me' : 'op'}" aria-label="Штаб: ${esc(doc.commander)}, прочность ${pl.hero.hp}${pl.hero.armor ? ', броня ' + pl.hero.armor : ''}">` +
      `${A.emblem(pl.doctrine)}<div class="hq-name">${esc(doc.commander.split(' ').pop())}</div>` +
      `<div class="hq-hp${hurt}">${pl.hero.hp}</div>${pl.hero.armor ? `<div class="hq-armor">${pl.hero.armor}</div>` : ''}<i class="ret"></i></button>` +
      `<button type="button" class="${pwCls}" id="power${side}" aria-label="Приказ командира: ${esc(pw.name)}. ${esc(pw.text)} Стоимость 2."${p === ME ? '' : ' tabindex="-1"'}>${POWER_ICON[pl.doctrine]}<span class="power-cost">${E.POWER_COST}</span></button>` +
      `<div class="deckchip" title="Карт в колоде">${A.ICONS.deck}${pl.deck.length}<span>колода</span></div>`;
  }

  // ---------- выбор и цели ----------
  function selDef() { if (!U.sel || U.sel.k !== 'hand') return null; const c = S.players[ME].hand[U.sel.h]; return c ? E.CARDS[c.id] : null; }
  function currentTargets() {
    if (!S || S.phase !== 'play' || S.active !== ME || U.busy || !U.sel) return [];
    if (U.sel.k === 'unit') return E.attackTargets(S, ME, U.sel.uid);
    if (U.sel.k === 'power') { const pw = E.DOCTRINES[S.players[ME].doctrine].power; return pw.target ? E.validTargets(S, ME, pw.target) : []; }
    const d = selDef();
    if (!d) return [];
    if (d.type === 'unit') return U.pending ? E.validTargets(S, ME, d.target) : [];
    return d.target ? E.validTargets(S, ME, d.target) : [];
  }
  function arrowSource() {
    if (!U.sel) return null;
    if (U.sel.k === 'unit') return document.querySelector(`[data-uid="${U.sel.uid}"]`);
    if (U.sel.k === 'power') return $('powerMe');
    const d = selDef();
    if (!d) return null;
    if (d.type === 'unit') return U.pending ? $('laneMe').querySelector('.ghost') : null;
    return d.target ? $('handMe').querySelector('.card.selected') : null;
  }

  // подсказки выводятся в плашку на переднем крае
  function hint(msg, warn) {
    U.hintMsg = msg || ''; U.hintWarn = !!warn;
    const f = $('frontInfo');
    const base = !S || S.phase !== 'play' ? 'Подготовка' : S.active === ME ? 'Ваш ход' : 'Ход противника';
    f.textContent = U.hintMsg || base;
    f.classList.toggle('warn', U.hintWarn);
    f.classList.toggle('tip', !!U.hintMsg && !U.hintWarn && U.hintMsg !== base);
    clearTimeout(hint.t);
    if (warn) hint.t = setTimeout(() => { if (U.hintWarn) hint(defaultHint()); }, 2200);
  }
  function defaultHint() {
    if (!S || S.phase !== 'play') return '';
    if (S.active !== ME) return 'Ход противника';
    if (U.pending) return 'Выберите цель: ' + stripTags(selDef().text);
    if (U.sel) {
      if (U.sel.k === 'unit') return 'Выберите цель атаки';
      if (U.sel.k === 'power') return 'Выберите цель приказа командира';
      const d = selDef();
      if (d.type === 'unit') return 'Нажмите на свою линию, чтобы ввести отряд';
      return d.target ? 'Выберите цель приказа' : 'Нажмите на поле или ещё раз на карту, чтобы отдать приказ';
    }
    return '';
  }
  const stripTags = s => String(s || '').replace(/<[^>]+>/g, '').replace(/\{(\d+)\}/g, '$1');

  // ---------- отрисовка ----------
  function render() {
    if (!S) return;
    const targets = currentTargets();
    const me = S.players[ME], op = S.players[OP];
    const myTurn = S.phase === 'play' && S.active === ME;

    $('barInfo').innerHTML = `Ход ${Math.max(1, S.turn)}<span class="bar-docs"> · ${esc(E.DOCTRINES[me.doctrine].short)} против ${esc(E.DOCTRINES[op.doctrine].short.toLowerCase())}</span>`;

    // рука противника
    let backs = '';
    for (let i = 0; i < op.hand.length; i++) backs += `<div class="back${i >= U.seenBacks ? ' enter' : ''}"></div>`;
    $('handOp').innerHTML = backs;
    U.seenBacks = op.hand.length;

    $('hqOp').innerHTML = hqHTML(OP, targets);
    $('hqMe').innerHTML = hqHTML(ME, targets);

    $('laneOp').innerHTML = op.board.map(m => unitHTML(m, 'op', targets)).join('');
    let mine = me.board.map(m => unitHTML(m, 'me', targets));
    if (U.pending) {
      const d = selDef();
      mine.splice(U.pending.pos, 0, `<div class="unit me ghost doc-${d.doc || 'N'}"><div class="u-stripe"></div><div class="u-art">${A.svg(d.art, UNIT_VB)}</div><div class="u-atk">${d.atk}</div><div class="u-hp">${d.hp}</div></div>`);
    }
    $('laneMe').innerHTML = mine.join('');
    const placing = myTurn && !U.busy && U.sel && U.sel.k === 'hand' && !U.pending && selDef() && selDef().type === 'unit';
    $('laneMe').classList.toggle('placing', !!placing);
    for (const m of me.board) U.seen.add(m.uid);
    for (const m of op.board) U.seen.add(m.uid);

    // рука игрока
    const sp = E.spellPower(S, ME);
    const n = me.hand.length;
    const html = me.hand.map((c, h) => {
      const playable = myTurn && !U.busy && E.canPlay(S, ME, h);
      const sel = U.sel && U.sel.k === 'hand' && U.sel.h === h;
      const mid = (n - 1) / 2, off = h - mid;
      const style = `--rot:${(off * Math.min(4, 26 / Math.max(n, 1))).toFixed(2)}deg;--ty:${((off * off - mid * mid) * 1.2 - 2).toFixed(1)}px;z-index:${h + 1}`;
      const cls = [playable && 'playable', sel && 'selected', sel && U.pending && 'pending', !U.seenHand.has(c.uid) && 'enter'].filter(Boolean).join(' ');
      return cardHTML(c.id, { sp, cls, attrs: `data-h="${h}" style="${style}" role="button" tabindex="0" aria-label="${esc(E.CARDS[c.id].name)}, стоимость ${E.CARDS[c.id].cost}"` });
    }).join('');
    $('handMe').innerHTML = html;
    for (const c of me.hand) U.seenHand.add(c.uid);
    layoutHand();

    const end = $('btnEnd');
    end.disabled = !myTurn || U.busy;
    end.textContent = myTurn ? 'Конец хода' : 'Ход противника';
    end.classList.toggle('done', myTurn && !U.busy && E.AI.legalActions(S, ME).length === 0);

    if (!U.hintWarn) hint(defaultHint());
    else hint(U.hintMsg, true);
    updateArrow();
    renderLog();
  }

  function layoutHand() {
    const box = $('handMe'), cards = box.querySelectorAll('.card');
    if (!cards.length) return;
    const W = box.clientWidth, cw = cards[0].offsetWidth, n = cards.length;
    const need = n * cw, ov = need > W - 8 ? (need - (W - 8)) / (n - 1) : -4;
    box.style.setProperty('--ov', Math.max(-6, ov) + 'px');
  }

  // ---------- стрелка прицела ----------
  function updateArrow() {
    const svg = $('arrow');
    const src = arrowSource();
    if (!src || !U.pointer || U.busy) { svg.hidden = true; return; }
    const r = src.getBoundingClientRect();
    const x1 = r.left + r.width / 2, y1 = r.top + r.height / 2, x2 = U.pointer.x, y2 = U.pointer.y;
    const mx = (x1 + x2) / 2, my = Math.min(y1, y2) - Math.abs(x2 - x1) * 0.15 - 30;
    $('arrowPath').setAttribute('d', `M${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`);
    $('arrowEnd').setAttribute('cx', x2); $('arrowEnd').setAttribute('cy', y2);
    const over = document.elementFromPoint(x2, y2);
    const t = over && over.closest('[data-uid]');
    const hot = !!(t && currentTargets().includes(t.dataset.uid));
    svg.classList.toggle('hot', hot);
    document.querySelectorAll('.is-target.hot').forEach(e => e.classList.remove('hot'));
    if (hot) t.classList.add('hot');
    svg.hidden = false;
  }

  // ---------- эффекты ----------
  function centerOf(uid, before) {
    const el = document.querySelector(`[data-uid="${uid}"]`);
    const r = el ? el.getBoundingClientRect() : before && before[uid];
    return r ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : null;
  }
  function spawn(cls, pt, text, style) {
    if (!pt) return;
    const d = document.createElement('div');
    d.className = cls; d.style.left = pt.x + 'px'; d.style.top = pt.y + 'px';
    if (style) Object.assign(d.style, style);
    if (text != null) d.textContent = text;
    $('fx').appendChild(d);
    setTimeout(() => d.remove(), T(1400));
  }
  function boom(pt) {
    if (!pt) return;
    spawn('boom', pt);
    if (!reduce) for (let i = 0; i < 6; i++) {
      const a = Math.random() * Math.PI * 2, r = 30 + Math.random() * 40;
      spawn('smoke', pt, null, { '--dx': Math.cos(a) * r + 'px', '--dy': Math.sin(a) * r - 20 + 'px' });
    }
  }
  function rectsAll() {
    const out = {};
    document.querySelectorAll('[data-uid]').forEach(el => { out[el.dataset.uid] = el.getBoundingClientRect(); });
    return out;
  }
  function shake() { if (reduce) return; const t = $('table'); t.classList.remove('shake'); void t.offsetWidth; t.classList.add('shake'); }

  // эффекты, видимые сразу (элементы ещё на месте)
  function fxNow(evs, deferred) {
    for (const e of evs) {
      const known = e.uid && document.querySelector(`[data-uid="${e.uid}"]`);
      if (!known && ['dmg', 'heal', 'shield', 'freeze', 'destroy', 'armor'].includes(e.t)) { deferred.push(e); continue; }
      switch (e.t) {
        case 'dmg': spawn('pop dmg', centerOf(e.uid), '−' + e.n); spawn('flash', centerOf(e.uid)); if (e.uid[0] === 'h' && e.n >= 5) shake(); break;
        case 'heal': spawn('pop heal', centerOf(e.uid), '+' + e.n); break;
        case 'armor': spawn('pop armor', centerOf(e.uid), '+' + e.n + ' брони'); break;
        case 'shield': spawn('ring', centerOf(e.uid)); spawn('pop info', centerOf(e.uid), 'защита сработала'); Snd.clang(); break;
        case 'freeze': spawn('pop info', centerOf(e.uid), 'обездвижен'); break;
        case 'destroy': spawn('pop info', centerOf(e.uid), 'уничтожен'); break;
      }
    }
  }
  async function fxAfter(evs, before, deferred) {
    let deaths = 0, dmg = false;
    for (const e of deferred) fxNow([e], []);
    for (const e of evs) {
      switch (e.t) {
        case 'death': deaths++; boom(centerOf(e.uid, before)); break;
        case 'dmg': dmg = true; break;
        case 'heal': Snd.heal(); break;
        case 'trigger': { const el = document.querySelector(`[data-uid="${e.uid}"]`); if (el) el.classList.add('pulse'); break; }
        case 'fatigue': spawn('pop info', centerOf(S.players[e.p].hero.uid), 'истощение −' + e.n); break;
        case 'burn': if (e.p === ME) hint('Рука полна: «' + E.CARDS[e.id].name + '» сгорает', true); break;
        case 'turn':
          if (e.p === ME && S.phase === 'play') { await sleep(150); showBanner('Ваш ход', 'ход ' + e.turn); Snd.turn(); }
          break;
      }
    }
    if (deaths) { Snd.boom(); await sleep(420); }
    else if (dmg) { Snd.hit(); }
  }
  function showBanner(text, small) {
    const b = $('banner');
    b.innerHTML = esc(text) + (small ? `<small>${esc(small)}</small>` : '');
    b.hidden = false; b.style.animation = 'none'; void b.offsetWidth; b.style.animation = '';
    clearTimeout(showBanner.t); showBanner.t = setTimeout(() => { b.hidden = true; }, T(1300));
  }
  async function reveal(html, label, ms) {
    const r = $('reveal');
    r.innerHTML = `<div class="reveal-lbl">${esc(label)}</div>${html}`;
    r.hidden = false; r.style.animation = 'none'; void r.offsetWidth; r.style.animation = '';
    await sleep(ms || 1150);
    r.hidden = true;
  }
  async function lunge(fromUid, toUid) {
    const a = document.querySelector(`[data-uid="${fromUid}"]`), b = document.querySelector(`[data-uid="${toUid}"]`);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const dx = (rb.left + rb.width / 2 - ra.left - ra.width / 2) * 0.78, dy = (rb.top + rb.height / 2 - ra.top - ra.height / 2) * 0.78;
    a.style.zIndex = 20;
    if (a.animate && !reduce) {
      const an = a.animate([{ transform: 'translate(0,0)' }, { transform: `translate(${dx}px,${dy}px) scale(1.08)`, offset: 0.5 }, { transform: 'translate(0,0)' }], { duration: 460, easing: 'cubic-bezier(.55,0,.35,1)' });
      await sleep(230);
      Snd.shot();
      return an.finished.catch(() => {});
    }
    Snd.shot();
  }

  // ---------- действия ----------
  async function act(a) {
    if (!S || S.phase !== 'play') return;
    const g = S;
    U.busy = true;
    const wasSel = U.sel;
    U.sel = null; U.pending = null;
    $('arrow').hidden = true;
    let tail = null;
    try {
      if (a.p === OP && a.type === 'play') {
        const c = S.players[OP].hand[a.h];
        render();
        if (c) await reveal(cardHTML(c.id, { sp: E.spellPower(S, OP) }), 'Противник разыгрывает', 1150);
      } else if (a.p === OP && a.type === 'power') {
        render();
        const pw = E.DOCTRINES[S.players[OP].doctrine].power;
        spawn('pop info', centerOf('powerOp') || centerOf(S.players[OP].hero.uid), pw.name);
        await sleep(500);
      } else render();
      if (g !== S) return;
      if (a.type === 'attack') tail = lunge(a.from, a.to);
      if (a.type === 'play') Snd.play();
      if (a.type === 'power') { const d = S.players[a.p].doctrine; if (d === 'A') Snd.mg(); else if (d === 'B') Snd.shot(); else Snd.clang(); }
      const before = rectsAll();
      const ok = E.AI.apply(S, a);
      if (!ok) { console.warn('действие отклонено', a); U.sel = a.p === ME ? wasSel : null; }
      const evs = S.events.splice(0);
      const deferred = [];
      fxNow(evs, deferred);
      if (tail) await tail;
      else if (evs.some(e => e.t === 'death')) await sleep(260);
      if (g !== S) return;
      render();
      await fxAfter(evs, before, deferred);
      if (S.phase === 'play' && S.active === ME && a.type === 'end') await sleep(250);
    } finally {
      if (g === S) {
        U.busy = false;
        render();
        if (S.phase === 'over') finish();
        else if (S.active === OP) aiTurn();
      }
    }
  }

  async function aiTurn() {
    if (U.ai || !S || S.phase !== 'play' || S.active !== OP) return;
    U.ai = true;
    const g = S;
    try {
      await sleep(650);
      let guard = 0;
      while (g === S && S.phase === 'play' && S.active === OP && guard++ < 60) {
        while (U.busy) await sleep(60);
        if (g !== S || U.screen !== 'game') break;
        const a = E.AI.choose(S, OP);
        if (!a) break;
        U.ai = 'acting';
        await act(Object.assign({}, a, { _ai: true }));
        U.ai = true;
        await sleep(380);
      }
      if (g === S && S.phase === 'play' && S.active === OP && U.screen === 'game') { U.ai = 'acting'; await act({ type: 'end', p: OP }); }
    } finally { if (g === S) U.ai = false; }
  }

  // ---------- ввод игрока ----------
  function cancel(quiet) {
    if (!U.sel && !U.pending) return;
    U.sel = null; U.pending = null;
    if (!quiet) Snd.click();
    render();
  }
  function clickHand(h) {
    const pl = S.players[ME], c = pl.hand[h];
    if (!c) return;
    const d = E.CARDS[c.id];
    if (U.pending) { U.pending = null; }
    if (U.sel && U.sel.k === 'hand' && U.sel.h === h) {
      if (d.type === 'order' && !d.target) return act({ type: 'play', p: ME, h });
      return cancel();
    }
    if (!E.canPlay(S, ME, h)) {
      const el = $('handMe').querySelector(`[data-h="${h}"]`);
      if (el) { el.classList.remove('nope'); void el.offsetWidth; el.classList.add('nope'); }
      let why = 'Сейчас эту карту не разыграть';
      if (d.cost > pl.mana) why = `Не хватает топлива: нужно ${d.cost}, есть ${pl.mana}`;
      else if ((d.type === 'unit' || (d.fx || []).some(e => e.do === 'summon')) && pl.board.length >= E.MAX_BOARD) why = 'На линии не больше 7 отрядов';
      else if (d.target) why = 'Нет подходящей цели для приказа';
      U.sel = null; render();
      return hint(why, true);
    }
    U.sel = { k: 'hand', h };
    Snd.click();
    render();
  }
  function place(pos) {
    const h = U.sel.h;
    if (E.needsTarget(S, ME, h)) { U.pending = { h, pos }; Snd.click(); render(); return; }
    act({ type: 'play', p: ME, h, pos });
  }
  function clickUnit(uid) {
    const m = S.players[ME].board.find(u => u.uid === uid);
    if (!m) return;
    if (U.sel && U.sel.k === 'unit' && U.sel.uid === uid) return cancel();
    if (E.canAttack(S, ME, m) && E.attackTargets(S, ME, uid).length) { U.sel = { k: 'unit', uid }; Snd.click(); render(); return; }
    let why = 'Этот отряд сейчас не может атаковать';
    if (m.cantAttack || m.atk <= 0) why = 'Этот отряд не атакует';
    else if (m.frozenAt != null) why = 'Обездвижен: пропускает атаку';
    else if (m.attacks >= (m.windfury ? 2 : 1)) why = 'Уже атаковал в этом ходу';
    else if (m.sleep && !m.charge && !m.rush) why = 'Только что введён: атакует со следующего хода';
    else if (m.sleep && m.rush) why = 'Прорыв: в первый ход можно атаковать только отряды';
    U.sel = null; render();
    hint(why, true);
  }
  function clickPower() {
    const pl = S.players[ME];
    if (!E.canPower(S, ME)) {
      return hint(pl.powerUsed ? 'Приказ командира — один раз за ход' : `Нужно ${E.POWER_COST} топлива`, true);
    }
    const pw = E.DOCTRINES[pl.doctrine].power;
    if (U.sel && U.sel.k === 'power') return cancel();
    if (pw.target) { U.sel = { k: 'power' }; U.pending = null; Snd.click(); render(); return; }
    act({ type: 'power', p: ME });
  }
  function commit(uid) {
    if (U.sel.k === 'unit') return act({ type: 'attack', p: ME, from: U.sel.uid, to: uid });
    if (U.sel.k === 'power') return act({ type: 'power', p: ME, target: uid });
    if (U.pending) return act({ type: 'play', p: ME, h: U.pending.h, pos: U.pending.pos, target: uid });
    return act({ type: 'play', p: ME, h: U.sel.h, target: uid });
  }
  function posFromX(x) {
    let i = 0;
    $('laneMe').querySelectorAll('.unit:not(.ghost)').forEach(u => { const r = u.getBoundingClientRect(); if (x > r.left + r.width / 2) i++; });
    return i;
  }

  function onTableClick(ev) {
    if (U.longPress) { U.longPress = false; return; }
    if (!S || U.screen !== 'game' || S.phase !== 'play') return;
    if (ev.target.closest('#btnEnd')) return;
    if (U.busy || S.active !== ME) { if (ev.target.closest('[data-h],[data-uid],#powerMe')) hint('Дождитесь своего хода', true); return; }
    const tEl = ev.target.closest('[data-uid]');
    const targets = currentTargets();
    if (tEl && targets.includes(tEl.dataset.uid)) return commit(tEl.dataset.uid);
    const hEl = ev.target.closest('[data-h]');
    if (hEl) return clickHand(+hEl.dataset.h);
    if (ev.target.closest('#powerMe')) return clickPower();
    const d = selDef();
    if (d && !U.pending && ev.target.closest('#laneMe')) {
      if (d.type === 'unit') return place(posFromX(ev.clientX));
    }
    if (d && !U.pending && d.type === 'order' && !d.target && ev.target.closest('#field')) return act({ type: 'play', p: ME, h: U.sel.h });
    if (tEl && tEl.dataset.side === 'me' && tEl.classList.contains('unit') && !tEl.classList.contains('ghost')) return clickUnit(tEl.dataset.uid);
    if (U.sel || U.pending) {
      cancel();
      if (tEl && targets.length) hint('Эта цель недоступна', true);
    }
  }

  // ---------- подсказка-карточка ----------
  function previewFor(el) {
    if (!S) return null;
    if (el.dataset.h != null) {
      const c = S.players[ME].hand[+el.dataset.h];
      return c ? { id: c.id, sp: E.spellPower(S, ME) } : null;
    }
    const uid = el.dataset.uid;
    if (!uid) return null;
    if (uid[0] === 'h') return { hero: +uid.slice(1) };
    const f = E.find(S, uid);
    return f && f.kind === 'unit' ? { id: f.obj.id, unit: f.obj } : null;
  }
  function showPreview(info, center) {
    const pv = $('preview');
    if (!info) { pv.hidden = true; return; }
    let html = '', kws = [];
    if (info.hero != null) {
      const pl = S.players[info.hero], doc = E.DOCTRINES[pl.doctrine];
      html = `<div class="kw-list"><div><b>${esc(doc.commander)}</b><br>${esc(doc.name)}. Прочность штаба ${pl.hero.hp} из ${pl.hero.maxHp}${pl.hero.armor ? ', броня ' + pl.hero.armor : ''}. В колоде ${pl.deck.length}, в руке ${pl.hand.length}.</div><div><b>${esc(doc.power.name)}</b> — 2 топлива: ${esc(doc.power.text)}</div></div>`;
    } else {
      const d = E.CARDS[info.id], m = info.unit;
      html = cardHTML(info.id, m ? { atk: m.atk, hp: m.hp, maxHp: m.maxHp } : { sp: info.sp });
      for (const k of (d.kw || [])) if (E.KW_HELP[k] && k !== 'cantAttack') kws.push([E.KW[k], E.KW_HELP[k]]);
      if (m && m.shield === false && (d.kw || []).includes('shield')) kws = kws.filter(x => x[0] !== E.KW.shield);
      if (m && !m.stealth && (d.kw || []).includes('stealth')) kws = kws.filter(x => x[0] !== E.KW.stealth);
      if (d.bc) kws.push(['При вводе', E.KW_HELP.battlecry.split(': ')[1]]);
      if (d.dr) kws.push(['При уничтожении', E.KW_HELP.deathrattle.split(': ')[1]]);
      if (d.eot) kws.push(['В конце хода', E.KW_HELP.eot.split(': ')[1]]);
      if (m && m.frozenAt != null) kws.push(['Обездвижен', 'Пропускает следующую атаку.']);
      if (m && m.sleep && !m.charge && !m.rush && !m.cantAttack && m.owner === ME) kws.push(['На марше', 'Введён в этом ходу и атакует со следующего.']);
      html += kws.length ? `<div class="kw-list">${kws.map(([a, b]) => `<div><b>${esc(a)}.</b> ${esc(b)}</div>`).join('')}</div>` : '';
    }
    pv.innerHTML = html;
    pv.classList.toggle('center', !!center);
    pv.hidden = false;
  }

  // ---------- экраны ----------
  function show(id) {
    for (const o of ['ovStart', 'ovMull', 'ovEnd', 'ovMenu']) $(o).hidden = o !== id;
  }
  function renderRecord() {
    const t = U.record.w + U.record.l;
    const txt = t ? `Побед <b>${U.record.w}</b> · поражений <b>${U.record.l}</b>` : 'Первый бой';
    $('record').innerHTML = txt; $('record2').innerHTML = txt;
  }
  function renderStart() {
    U.screen = 'start';
    const sig = { A: ['a_ap', 'a_t34g', 'a_ace', 'a_breach'], B: ['b_barrage', 'b_m30', 'b_su152', 'b_shot'], C: ['c_hedge', 'c_dot', 'c_arv', 'c_t35'] };
    $('docs').innerHTML = ['A', 'B', 'C'].map(k => {
      const d = E.DOCTRINES[k];
      return `<button type="button" class="doc doc-${k}" data-doc="${k}" aria-pressed="${U.doctrine === k}">` +
        `<span class="hq doc-${k}">${A.emblem(k)}</span><h3>${esc(d.name)}</h3><div class="who">${esc(d.commander)}</div>` +
        `<p>${esc(d.style)}</p><p class="pw"><b>${esc(d.power.name)}</b> · 2 топлива: ${esc(d.power.text)}</p>` +
        `<div class="sig">${sig[k].map(id => `<span>${esc(E.CARDS[id].name)}</span>`).join('')}</div></button>`;
    }).join('');
    const rules = [
      ['Цель', 'довести прочность вражеского штаба с 30 до нуля.'],
      ['Топливо', 'каждый ход запас растёт на 1, до 10, и пополняется полностью. Цена карты — в канистре в левом углу.'],
      ['Отряды', 'вводятся на вашу линию (до 7) и атакуют со следующего хода. Атака по отряду — обмен ударами: оба получают урон, равный атаке другого.'],
      ['Приказы', 'разовые действия: удары, ремонт, усиление.'],
      ['Приказ командира', 'у каждой доктрины своё умение за 2 топлива, раз в ход.'],
      ['Управление', 'нажмите карту, затем свою линию или цель. Нажмите свой готовый отряд (зелёная рамка), затем цель. Наведите курсор или удерживайте палец на карте — откроется описание.'],
      ...['taunt', 'charge', 'rush', 'shield', 'stealth', 'windfury', 'poison'].map(k => [E.KW[k], E.KW_HELP[k]]),
      ['Обездвижен', E.KW_HELP.frozen.split(': ')[1]],
      ['Истощение', 'если колода кончилась, каждый набор карты наносит штабу растущий урон.']
    ];
    $('rulesList').innerHTML = rules.map(([a, b]) => `<li><b>${esc(a)}:</b> ${esc(b)}</li>`).join('');
    renderRecord();
    show('ovStart');
  }

  function newGame() {
    const others = ['A', 'B', 'C'].filter(d => d !== U.doctrine);
    const opDoc = others[Math.floor(Math.random() * others.length)];
    const first = Math.random() < 0.5 ? 0 : 1;
    S = E.newGame({ doctrines: [U.doctrine, opDoc], seed: (Math.random() * 2 ** 31) | 0, first, names: ['Вы', 'Противник'] });
    E.mulligan(S, OP, E.AI.mulligan(S, OP));
    S.events.length = 0;
    U.sel = null; U.pending = null; U.busy = false; U.ai = false; U.mull = new Set();
    U.seen = new Set(); U.seenHand = new Set(S.players[ME].hand.map(c => c.uid)); U.seenBacks = S.players[OP].hand.length;
    U.screen = 'mull';
    renderMull();
    render();
    scheduleMap();
  }
  function renderMull() {
    $('mullWho').textContent = S.first === ME ? 'Вы ходите первым' : 'Вы ходите вторым и получите «Резервную канистру»';
    $('mullCards').innerHTML = S.players[ME].hand.map((c, i) => cardHTML(c.id, { cls: U.mull.has(i) ? 'out' : '', attrs: `data-m="${i}" role="button" tabindex="0" aria-pressed="${U.mull.has(i)}"` })).join('');
    $('btnMull').textContent = U.mull.size ? `Заменить: ${U.mull.size}` : 'Оставить все';
    show('ovMull');
  }
  function confirmMull() {
    E.mulligan(S, ME, [...U.mull]);
    S.events.length = 0;
    U.seenHand = new Set();
    U.screen = 'game';
    show(null);
    render();
    scheduleMap();
    if (S.active === ME) { showBanner('Ваш ход', 'ход ' + S.turn); Snd.turn(); }
    else aiTurn();
  }
  function finish() {
    if (U.screen === 'end') return;
    U.screen = 'end';
    const w = S.winner;
    if (w === ME) U.record.w++; else if (w === OP) U.record.l++;
    store.set('record', U.record);
    const me = S.players[ME], op = S.players[OP];
    $('endEyebrow').textContent = w === ME ? 'Штаб противника уничтожен' : w === OP ? 'Ваш штаб уничтожен' : 'Оба штаба уничтожены';
    const t = $('endTitle');
    t.textContent = w === ME ? 'Победа' : w === OP ? 'Поражение' : 'Ничья';
    t.classList.toggle('lose', w === OP);
    $('endStats').innerHTML = `<div><b>${S.turn}</b>ходов</div><div><b>${Math.max(0, me.hero.hp)}</b>ваш штаб</div><div><b>${Math.max(0, op.hero.hp)}</b>штаб противника</div>`;
    renderRecord();
    setTimeout(() => { if (U.screen === 'end') { show('ovEnd'); w === ME ? Snd.win() : Snd.lose(); } }, T(900));
  }

  // ---------- журнал ----------
  function renderLog() {
    if ($('logPanel').hidden || !S) return;
    $('log').innerHTML = S.log.map(l => `<p class="${l.text.startsWith('—') ? 'sep' : l.p === 0 ? 'p0' : l.p === 1 ? 'p1' : ''}">${esc(l.text)}</p>`).join('');
    $('log').scrollTop = $('log').scrollHeight;
  }

  // ---------- привязка событий ----------
  function bind() {
    const app = $('app');
    $('table').addEventListener('click', onTableClick);
    $('btnEnd').addEventListener('click', () => {
      if (!S || S.phase !== 'play' || S.active !== ME || U.busy) return;
      U.sel = null; U.pending = null;
      act({ type: 'end', p: ME });
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') { if (!$('logPanel').hidden) { $('logPanel').hidden = true; return; } cancel(); }
      if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('[data-h],[data-uid].unit,[data-m],.doc')) { e.preventDefault(); e.target.click(); }
    });
    app.addEventListener('contextmenu', e => { if (U.sel || U.pending) { e.preventDefault(); cancel(); } });
    window.addEventListener('pointermove', e => {
      U.pointer = { x: e.clientX, y: e.clientY };
      if (!$('arrow').hidden || arrowSource()) { if (!updateArrow.raf) updateArrow.raf = requestAnimationFrame(() => { updateArrow.raf = 0; updateArrow(); }); }
    }, { passive: true });
    window.addEventListener('pointerdown', e => { U.pointer = { x: e.clientX, y: e.clientY }; }, { passive: true });

    // подсказка-карточка: наведение мышью и долгое нажатие пальцем
    let hoverT = 0, pressT = 0, hoverEl = null;
    const previewTarget = t => t.closest && t.closest('.hand-me [data-h], .lane [data-uid], .hq[data-uid]');
    if (canHover) {
      app.addEventListener('mouseover', e => {
        const el = previewTarget(e.target);
        if (el === hoverEl) return;
        hoverEl = el; clearTimeout(hoverT);
        if (!el) { showPreview(null); return; }
        hoverT = setTimeout(() => { if (hoverEl === el && el.isConnected) showPreview(previewFor(el)); }, 280);
      });
      app.addEventListener('mouseleave', () => { hoverEl = null; showPreview(null); });
    }
    app.addEventListener('pointerdown', e => {
      if (e.pointerType === 'mouse') return;
      const el = previewTarget(e.target);
      if (!el) return;
      clearTimeout(pressT);
      pressT = setTimeout(() => { U.longPress = true; showPreview(previewFor(el), true); }, 420);
    });
    const endPress = () => { clearTimeout(pressT); if (U.longPress) { showPreview(null); setTimeout(() => { U.longPress = false; }, 350); } };
    app.addEventListener('pointerup', endPress);
    app.addEventListener('pointercancel', endPress);
    app.addEventListener('pointermove', e => { if (e.pointerType !== 'mouse' && Math.abs(e.movementX) + Math.abs(e.movementY) > 6) clearTimeout(pressT); });

    // экраны
    $('docs').addEventListener('click', e => {
      const b = e.target.closest('[data-doc]'); if (!b) return;
      U.doctrine = b.dataset.doc; store.set('doctrine', U.doctrine); Snd.click();
      $('docs').querySelectorAll('[data-doc]').forEach(x => x.setAttribute('aria-pressed', x.dataset.doc === U.doctrine));
    });
    $('docs').addEventListener('dblclick', e => { if (e.target.closest('[data-doc]')) newGame(); });
    $('btnStart').addEventListener('click', () => { Snd.click(); newGame(); });
    $('mullCards').addEventListener('click', e => {
      const c = e.target.closest('[data-m]'); if (!c) return;
      const i = +c.dataset.m; U.mull.has(i) ? U.mull.delete(i) : U.mull.add(i); Snd.click(); renderMull();
    });
    $('btnMull').addEventListener('click', confirmMull);
    $('btnAgain').addEventListener('click', () => { Snd.click(); newGame(); });
    $('btnToMenu').addEventListener('click', () => { Snd.click(); S = null; renderStart(); });
    $('btnMenu').addEventListener('click', () => {
      if (U.screen === 'game' && S && S.phase === 'play') { show('ovMenu'); U.screen = 'menu'; }
      else if (U.screen !== 'start') { S = null; renderStart(); }
    });
    $('btnResume').addEventListener('click', () => { U.screen = 'game'; show(null); if (S && S.active === OP) aiTurn(); });
    $('btnSurrender').addEventListener('click', () => {
      if (S && S.phase === 'play') { U.record.l++; store.set('record', U.record); }
      S = null; renderStart();
    });
    $('btnLog').addEventListener('click', () => { $('logPanel').hidden = !$('logPanel').hidden; renderLog(); });
    $('btnLogClose').addEventListener('click', () => { $('logPanel').hidden = true; });
    $('btnSound').addEventListener('click', () => {
      U.sound = !U.sound; store.set('sound', U.sound);
      $('btnSound').setAttribute('aria-pressed', U.sound); if (U.sound) Snd.click();
    });
    window.addEventListener('resize', () => { scheduleMap(); layoutHand(); updateArrow(); });
    if (window.ResizeObserver) new ResizeObserver(scheduleMap).observe($('field'));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleMap);
  }

  // ---------- запуск и горячая замена ----------
  function start(data) {
    U.record = store.get('record', { w: 0, l: 0 });
    U.sound = store.get('sound', true);
    U.doctrine = store.get('doctrine', 'A');
    if (!E.DOCTRINES[U.doctrine]) U.doctrine = 'A';
    $('btnSound').setAttribute('aria-pressed', U.sound);
    bind();
    if (data && data.S && data.S.v === 1) {
      S = data.S; U.doctrine = data.doctrine || U.doctrine;
      U.seen = new Set([...S.players[0].board, ...S.players[1].board].map(m => m.uid));
      U.seenHand = new Set(S.players[ME].hand.map(c => c.uid)); U.seenBacks = S.players[OP].hand.length;
      if (S.phase === 'mulligan') { U.mull = new Set(data.mull || []); U.screen = 'mull'; renderMull(); render(); }
      else if (S.phase === 'over') { render(); U.screen = 'game'; finish(); }
      else { U.screen = 'game'; show(null); render(); if (S.active === OP) aiTurn(); }
      renderStart.done = true;
      scheduleMap();
      return;
    }
    renderStart();
    // фон под стартовым экраном: пример расстановки
    S = E.newGame({ doctrines: [U.doctrine, 'C'], seed: 11, first: 0 });
    E.mulligan(S, 0, []); E.mulligan(S, 1, []);
    for (const id of ['n_t34', 'n_pz4']) S.players[0].board.push(mk(id, 0));
    for (const id of ['n_matilda', 'c_dot', 'n_t26']) S.players[1].board.push(mk(id, 1));
    S.events.length = 0;
    render(); scheduleMap();
    S = null;
  }
  function mk(id, p) {
    const d = E.CARDS[id], kw = d.kw || [];
    return { uid: 'demo' + id + p, id, owner: p, atk: d.atk, hp: d.hp, maxHp: d.hp, taunt: kw.includes('taunt'), charge: false, rush: false, shield: kw.includes('shield'), stealth: false, windfury: false, poison: false, cantAttack: kw.includes('cantAttack'), spellDmg: 0, sleep: false, attacks: 0, frozenAt: null, dead: false };
  }

  const hot = window.claude && window.claude.hot;
  if (hot && hot.snapshot) {
    try { hot.snapshot(() => ({ S: S ? JSON.parse(JSON.stringify(Object.assign({}, S, { events: [] }))) : null, doctrine: U.doctrine, mull: [...U.mull] })); } catch (e) { /* без горячей замены */ }
  }
  if (hot && hot.ready) hot.ready(start); else start((hot && hot.data) || {});
})();
