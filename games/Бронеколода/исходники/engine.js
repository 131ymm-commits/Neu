// Бронеколода — движок: правила, карты, колоды, ИИ. Чистые функции над состоянием-JSON.
// Работает в браузере (window.Engine) и в Node (require).
(function (root, factory) {
  const E = factory();
  if (typeof module === 'object' && module.exports) module.exports = E; else root.Engine = E;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const MAX_BOARD = 7, MAX_HAND = 10, MAX_MANA = 10, HERO_HP = 30, POWER_COST = 2;

  // ---------- Ключевые слова ----------
  const KW = {
    taunt: 'Заслон', charge: 'Рывок', rush: 'Прорыв', shield: 'Динамическая защита',
    stealth: 'Маскировка', windfury: 'Автомат заряжания', poison: 'Кумулятивный', cantAttack: 'Не атакует'
  };
  const KW_HELP = {
    taunt: 'Противник должен сначала атаковать отряды с Заслоном.',
    charge: 'Может атаковать в тот же ход, когда введён в бой.',
    rush: 'Может сразу атаковать вражеские отряды, но не штаб.',
    shield: 'Первое попадание не наносит урона, защита при этом срабатывает.',
    stealth: 'Нельзя выбрать целью, пока отряд сам не атакует.',
    windfury: 'Атакует дважды за ход.',
    poison: 'Уничтожает любой отряд, которому нанёс урон.',
    cantAttack: 'Не может атаковать, но отвечает на атаки.',
    battlecry: 'При вводе: срабатывает, когда карта разыграна из руки.',
    deathrattle: 'При уничтожении: срабатывает, когда отряд уничтожен.',
    eot: 'В конце хода: срабатывает в конце каждого вашего хода.',
    spellDmg: 'Ваши приказы наносят больше урона.',
    frozen: 'Обездвижен: пропускает следующую атаку.'
  };

  // ---------- Карты ----------
  // fx/bc/dr/eot — списки эффектов. target — кого выбирает игрок.
  // {N} в тексте приказа — урон, к которому прибавляется усиление от корректировщиков.
  const CARDS = {
    // жетоны
    t_rifle: { name: 'Стрелок', cost: 1, type: 'unit', cls: 'Пехота', cal: '7,62 мм', atk: 1, hp: 1, art: 'inf', token: true, text: '' },
    t_hedgehog: { name: 'Противотанковый ёж', cost: 1, type: 'unit', cls: 'Заграждение', atk: 0, hp: 2, kw: ['taunt', 'cantAttack'], art: 'hedgehog', token: true, text: '<b>Заслон</b>. Не атакует.' },
    t_coin: { name: 'Резервная канистра', cost: 0, type: 'order', cls: 'Приказ', art: 'canister', token: true, fx: [{ do: 'mana', n: 1 }], text: 'Получите 1 топливо в этом ходу.' },

    // общие
    n_moto: { name: 'Мотоциклист-разведчик', cost: 1, type: 'unit', cls: 'Разведка', cal: '7,62 мм', atk: 1, hp: 1, kw: ['charge'], art: 'moto', text: '<b>Рывок</b>' },
    n_t27: { name: 'Танкетка Т-27', cost: 1, type: 'unit', cls: 'Танкетка', cal: '7,62 мм', atk: 1, hp: 1, kw: ['shield'], art: 'tankette', text: '<b>Динамическая защита</b>' },
    n_sapper: { name: 'Сапёр', cost: 1, type: 'unit', cls: 'Пехота', cal: 'заряд ВВ', atk: 1, hp: 1, art: 'inf', target: 'any', bc: [{ do: 'dmg', n: 1, to: 'target' }], text: '<b>При вводе:</b> нанести 1 урон.' },
    n_t26: { name: 'Т-26', cost: 2, type: 'unit', cls: 'Лёгкий танк', cal: '45 мм', atk: 2, hp: 3, art: 'light', text: '' },
    n_ba64: { name: 'Бронеавтомобиль БА-64', cost: 2, type: 'unit', cls: 'Бронеавтомобиль', cal: '7,62 мм', atk: 3, hp: 2, kw: ['rush'], art: 'car', text: '<b>Прорыв</b>' },
    n_ptr: { name: 'Расчёт ПТР', cost: 2, type: 'unit', cls: 'Пехота', cal: '14,5 мм', atk: 1, hp: 3, kw: ['poison'], art: 'atr', text: '<b>Кумулятивный</b>' },
    n_motor: { name: 'Мотопехота', cost: 2, type: 'unit', cls: 'Пехота', cal: '7,62 мм', atk: 2, hp: 1, art: 'inf', dr: [{ do: 'summon', id: 't_rifle', n: 1 }], text: '<b>При уничтожении:</b> вызвать Стрелка 1/1.' },
    n_medic: { name: 'Санитарный тягач', cost: 2, type: 'unit', cls: 'Тягач', cal: 'без вооружения', atk: 2, hp: 2, art: 'truck', target: 'any', bc: [{ do: 'heal', n: 3, to: 'target' }], text: '<b>При вводе:</b> восстановить 3 прочности.' },
    n_bt7: { name: 'БТ-7', cost: 3, type: 'unit', cls: 'Лёгкий танк', cal: '45 мм', atk: 3, hp: 2, kw: ['charge'], art: 'light2', text: '<b>Рывок</b>' },
    n_t34: { name: 'Т-34', cost: 3, type: 'unit', cls: 'Средний танк', cal: '76 мм', atk: 3, hp: 4, art: 'medium', text: '' },
    n_matilda: { name: 'Матильда II', cost: 3, type: 'unit', cls: 'Пехотный танк', cal: '40 мм', atk: 2, hp: 4, kw: ['taunt'], art: 'matilda', text: '<b>Заслон</b>' },
    n_spotter: { name: 'Корректировщик', cost: 3, type: 'unit', cls: 'Пехота', cal: 'рация', atk: 2, hp: 3, spellDmg: 1, art: 'spotter', text: 'Ваши приказы наносят <b>+1 урона</b>.' },
    n_zis3: { name: 'ЗиС-3 в засаде', cost: 3, type: 'unit', cls: 'Орудие', cal: '76 мм', atk: 3, hp: 2, kw: ['stealth'], art: 'atgun', text: '<b>Маскировка</b>' },
    n_pz4: { name: 'Pz.IV', cost: 4, type: 'unit', cls: 'Средний танк', cal: '75 мм', atk: 4, hp: 5, art: 'medium2', text: '' },
    n_sherman: { name: 'Шерман', cost: 4, type: 'unit', cls: 'Средний танк', cal: '75 мм', atk: 3, hp: 5, kw: ['taunt'], art: 'sherman', text: '<b>Заслон</b>' },
    n_su85: { name: 'СУ-85', cost: 4, type: 'unit', cls: 'ПТ-САУ', cal: '85 мм', atk: 3, hp: 3, art: 'td', target: 'any', bc: [{ do: 'dmg', n: 2, to: 'target' }], text: '<b>При вводе:</b> нанести 2 урона.' },
    n_halftrack: { name: 'Бронетранспортёр', cost: 4, type: 'unit', cls: 'Бронетранспортёр', cal: '7,62 мм', atk: 2, hp: 3, art: 'halftrack', bc: [{ do: 'summon', id: 't_rifle', n: 2 }], text: '<b>При вводе:</b> вызвать двух Стрелков 1/1.' },
    n_katyusha: { name: 'Катюша', cost: 5, type: 'unit', cls: 'Реактивная установка', cal: '132 мм', atk: 3, hp: 3, art: 'rocket', bc: [{ do: 'dmg', n: 1, to: 'enemyUnits' }], text: '<b>При вводе:</b> нанести 1 урон всем вражеским отрядам.' },
    n_panther: { name: 'Пантера', cost: 5, type: 'unit', cls: 'Средний танк', cal: '75 мм', atk: 5, hp: 4, kw: ['rush'], art: 'panther', text: '<b>Прорыв</b>' },
    n_kv1: { name: 'КВ-1', cost: 5, type: 'unit', cls: 'Тяжёлый танк', cal: '76 мм', atk: 3, hp: 7, kw: ['taunt'], art: 'kv', text: '<b>Заслон</b>' },
    n_tiger: { name: 'Тигр', cost: 6, type: 'unit', cls: 'Тяжёлый танк', cal: '88 мм', atk: 6, hp: 7, art: 'tiger', text: '' },
    n_is2: { name: 'ИС-2', cost: 6, type: 'unit', cls: 'Тяжёлый танк', cal: '122 мм', atk: 5, hp: 5, art: 'is2', target: 'any', bc: [{ do: 'dmg', n: 3, to: 'target' }], text: '<b>При вводе:</b> нанести 3 урона.' },
    n_kt: { name: 'Королевский тигр', cost: 7, type: 'unit', cls: 'Тяжёлый танк', cal: '88 мм', atk: 6, hp: 8, kw: ['taunt'], art: 'kingtiger', text: '<b>Заслон</b>' },
    n_maus: { name: 'Маус', cost: 8, type: 'unit', cls: 'Сверхтяжёлый танк', cal: '128 мм', atk: 7, hp: 10, kw: ['taunt'], art: 'maus', text: '<b>Заслон</b>' },

    // доктрина А — бронетанковая
    a_ap: { name: 'Бронебойный снаряд', cost: 1, type: 'order', cls: 'Приказ', doc: 'A', art: 'shell', target: 'unit', fx: [{ do: 'dmg', n: 3, to: 'target' }], text: 'Нанести {3} урона отряду.' },
    a_track: { name: 'Выстрел по гусенице', cost: 1, type: 'order', cls: 'Приказ', doc: 'A', art: 'track', target: 'enemyUnit', fx: [{ do: 'dmg', n: 1, to: 'target' }, { do: 'freeze', to: 'target' }], text: 'Нанести {1} урон вражескому отряду и <b>обездвижить</b> его.' },
    a_t34g: { name: 'Гвардейский Т-34', cost: 3, type: 'unit', cls: 'Средний танк', cal: '85 мм', doc: 'A', atk: 3, hp: 2, kw: ['rush', 'shield'], art: 'medium', text: '<b>Прорыв</b>. <b>Динамическая защита</b>' },
    a_wedge: { name: 'Танковый клин', cost: 3, type: 'order', cls: 'Приказ', doc: 'A', art: 'wedge', fx: [{ do: 'buffAll', atk: 1, hp: 1 }], text: 'Ваши отряды получают <b>+1/+1</b>.' },
    a_breach: { name: 'Прорыв обороны', cost: 4, type: 'order', cls: 'Приказ', doc: 'A', art: 'blast', fx: [{ do: 'dmg', n: 2, to: 'enemyUnits' }], text: 'Нанести {2} урона всем вражеским отрядам.' },
    a_ace: { name: 'Танковый ас', cost: 5, type: 'unit', cls: 'Средний танк', cal: '85 мм', doc: 'A', atk: 4, hp: 5, kw: ['windfury'], art: 'ace', text: '<b>Автомат заряжания</b>' },

    // доктрина Б — артиллерийская
    b_barrage: { name: 'Артналёт', cost: 2, type: 'order', cls: 'Приказ', doc: 'B', art: 'barrage', fx: [{ do: 'dmg', n: 1, to: 'enemyUnits' }], text: 'Нанести {1} урон всем вражеским отрядам.' },
    b_recon: { name: 'Аэроразведка', cost: 3, type: 'order', cls: 'Приказ', doc: 'B', art: 'plane', fx: [{ do: 'draw', n: 2 }], text: 'Возьмите 2 карты.' },
    b_m30: { name: 'Гаубица М-30', cost: 3, type: 'unit', cls: 'Орудие', cal: '122 мм', doc: 'B', atk: 2, hp: 3, art: 'howitzer', eot: [{ do: 'dmg', n: 1, to: 'randomEnemy' }], text: '<b>В конце хода:</b> нанести 1 урон случайному врагу.' },
    b_shot: { name: 'Удар гаубицы', cost: 5, type: 'order', cls: 'Приказ', doc: 'B', art: 'impact', target: 'any', fx: [{ do: 'dmg', n: 6, to: 'target' }], text: 'Нанести {6} урона.' },
    b_su152: { name: 'СУ-152 «Зверобой»', cost: 5, type: 'unit', cls: 'САУ', cal: '152 мм', doc: 'B', atk: 4, hp: 3, art: 'su152', target: 'enemyBig', bc: [{ do: 'destroy', to: 'target' }], text: '<b>При вводе:</b> уничтожить вражеский отряд с атакой 5 и больше.' },
    b_wall: { name: 'Огневой вал', cost: 8, type: 'order', cls: 'Приказ', doc: 'B', art: 'barrage', fx: [{ do: 'dmg', n: 4, to: 'enemyUnits' }], text: 'Нанести {4} урона всем вражеским отрядам.' },

    // доктрина В — оборонительная
    c_hedge: { name: 'Противотанковые ежи', cost: 2, type: 'order', cls: 'Приказ', doc: 'C', art: 'hedgehog', fx: [{ do: 'summon', id: 't_hedgehog', n: 2 }], text: 'Вызвать двух Ежей 0/2 с <b>Заслоном</b>.' },
    c_fire: { name: 'Заградительный огонь', cost: 2, type: 'order', cls: 'Приказ', doc: 'C', art: 'impact', target: 'enemyUnit', fx: [{ do: 'dmg', n: 2, to: 'target' }, { do: 'armor', n: 2 }], text: 'Нанести {2} урона вражескому отряду. Получить 2 брони.' },
    c_dot: { name: 'ДОТ', cost: 3, type: 'unit', cls: 'Укрепление', cal: '76 мм', doc: 'C', atk: 3, hp: 6, kw: ['taunt', 'cantAttack'], art: 'bunker', text: '<b>Заслон</b>. Не атакует.' },
    c_arv: { name: 'БРЭМ', cost: 3, type: 'unit', cls: 'Ремонтная машина', cal: 'кран 3 т', doc: 'C', atk: 2, hp: 3, art: 'arv', eot: [{ do: 'heal', n: 2, to: 'friendly' }], text: '<b>В конце хода:</b> восстановить 2 прочности вашим отрядам и штабу.' },
    c_trench: { name: 'Окопы полного профиля', cost: 3, type: 'order', cls: 'Приказ', doc: 'C', art: 'trench', fx: [{ do: 'armor', n: 5 }, { do: 'draw', n: 1 }], text: 'Получить 5 брони. Взять карту.' },
    c_t35: { name: 'Т-35', cost: 6, type: 'unit', cls: 'Тяжёлый танк', cal: '76 + 45 мм', doc: 'C', atk: 4, hp: 6, kw: ['taunt', 'windfury'], art: 't35', text: '<b>Заслон</b>. <b>Автомат заряжания</b>' }
  };
  for (const id in CARDS) CARDS[id].id = id;

  const DOCTRINES = {
    A: {
      name: 'Бронетанковая доктрина', short: 'Бронетанковая', commander: 'Майор Ветров',
      style: 'Быстрый натиск: дешёвые танки, рывки и прорывы, точечные бронебойные выстрелы.',
      power: { name: 'Пулемётная очередь', target: 'any', fx: [{ do: 'dmg', n: 1, to: 'target' }], text: 'Нанести 1 урон.' },
      deck: ['a_ap', 'a_track', 'a_t34g', 'a_wedge', 'a_breach', 'a_ace', 'n_moto', 'n_t27', 'n_t26', 'n_ba64', 'n_bt7', 'n_t34', 'n_pz4', 'n_panther', 'n_is2']
    },
    B: {
      name: 'Артиллерийская доктрина', short: 'Артиллерийская', commander: 'Полковник Громов',
      style: 'Огонь с закрытых позиций: артналёты по площадям, удары по штабу, тяжёлые калибры.',
      power: { name: 'Корректировка огня', fx: [{ do: 'dmg', n: 2, to: 'enemyHero' }], text: 'Нанести 2 урона вражескому штабу.' },
      deck: ['b_barrage', 'b_recon', 'b_m30', 'b_shot', 'b_su152', 'b_wall', 'n_sapper', 'n_ptr', 'n_motor', 'n_spotter', 'n_zis3', 'n_su85', 'n_katyusha', 'n_kv1', 'n_tiger']
    },
    C: {
      name: 'Оборонительная доктрина', short: 'Оборонительная', commander: 'Капитан Осокина',
      style: 'Эшелонированная оборона: заслоны, броня, ремонт в поле и тяжёлые машины к концу боя.',
      power: { name: 'Окопаться', fx: [{ do: 'armor', n: 2 }], text: 'Получить 2 брони.' },
      deck: ['c_hedge', 'c_fire', 'c_dot', 'c_arv', 'c_trench', 'c_t35', 'n_t27', 'n_ptr', 'n_medic', 'n_matilda', 'n_t34', 'n_sherman', 'n_halftrack', 'n_kt', 'n_maus']
    }
  };

  // ---------- Случайность (mulberry32, зерно хранится в состоянии) ----------
  function rnd(s) {
    let t = s.seed = (s.seed + 0x6D2B79F5) | 0;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  function shuffle(s, a) {
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd(s) * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }

  // ---------- Служебное ----------
  const ev = (s, e) => { s.events.push(e); };
  function log(s, p, text) {
    s.log.push({ turn: s.turn, p, text });
    if (s.log.length > 120) s.log.splice(0, s.log.length - 120);
  }
  const who = (s, p) => s.players[p].name;
  const q = name => '«' + name + '»';

  function find(s, uid) {
    for (let p = 0; p < 2; p++) {
      const pl = s.players[p];
      if (pl.hero.uid === uid) return { kind: 'hero', obj: pl.hero, p };
      const m = pl.board.find(u => u.uid === uid);
      if (m) return { kind: 'unit', obj: m, p };
    }
    return null;
  }
  function nameOf(s, uid) {
    const f = find(s, uid);
    if (!f) return '?';
    return f.kind === 'hero' ? 'штаб (' + who(s, f.p).toLowerCase() + ')' : q(CARDS[f.obj.id].name);
  }

  function makeUnit(s, p, id) {
    const d = CARDS[id], kw = d.kw || [];
    return {
      uid: 'u' + (s.nextUid++), id, owner: p, atk: d.atk, hp: d.hp, maxHp: d.hp,
      taunt: kw.includes('taunt'), charge: kw.includes('charge'), rush: kw.includes('rush'),
      shield: kw.includes('shield'), stealth: kw.includes('stealth'), windfury: kw.includes('windfury'),
      poison: kw.includes('poison'), cantAttack: kw.includes('cantAttack'), spellDmg: d.spellDmg || 0,
      sleep: true, attacks: 0, frozenAt: null, dead: false
    };
  }

  function spellPower(s, p) { return s.players[p].board.reduce((a, m) => a + (m.spellDmg || 0), 0); }

  // ---------- Цели ----------
  function validTargets(s, p, spec) {
    const me = s.players[p], op = s.players[1 - p];
    const my = me.board.map(m => m.uid);
    const opVis = op.board.filter(m => !m.stealth);
    const opU = opVis.map(m => m.uid);
    switch (spec) {
      case 'any': return [op.hero.uid, ...opU, me.hero.uid, ...my];
      case 'unit': return [...opU, ...my];
      case 'enemyUnit': return opU;
      case 'friendlyUnit': return my;
      case 'enemy': return [op.hero.uid, ...opU];
      case 'enemyBig': return opVis.filter(m => m.atk >= 5).map(m => m.uid);
      default: return [];
    }
  }

  function resolveTo(s, p, to, ctx) {
    const me = s.players[p], op = s.players[1 - p];
    switch (to) {
      case 'target': return ctx.target ? [ctx.target] : [];
      case 'enemyUnits': return op.board.map(m => m.uid);
      case 'enemyHero': return [op.hero.uid];
      case 'myHero': return [me.hero.uid];
      case 'friendly': return [me.hero.uid, ...me.board.map(m => m.uid)];
      case 'friendlyUnits': return me.board.map(m => m.uid);
      case 'randomEnemy': {
        const pool = [op.hero.uid, ...op.board.filter(m => m.hp > 0 && !m.dead).map(m => m.uid)];
        return [pool[Math.floor(rnd(s) * pool.length)]];
      }
      default: return [];
    }
  }

  // ---------- Урон, лечение, гибель ----------
  function damage(s, uid, n, srcUid) {
    if (n <= 0) return 0;
    const f = find(s, uid);
    if (!f) return 0;
    if (f.kind === 'hero') {
      const h = f.obj, a = Math.min(h.armor, n);
      h.armor -= a; h.hp -= (n - a);
      ev(s, { t: 'dmg', uid, n });
      return n;
    }
    const m = f.obj;
    if (m.shield) { m.shield = false; ev(s, { t: 'shield', uid }); return 0; }
    m.hp -= n;
    ev(s, { t: 'dmg', uid, n });
    const src = srcUid && find(s, srcUid);
    if (src && src.kind === 'unit' && src.obj.poison && m.hp > 0) m.dead = true;
    return n;
  }
  function heal(s, uid, n) {
    const f = find(s, uid);
    if (!f) return 0;
    const o = f.obj, got = Math.max(0, Math.min(n, o.maxHp - o.hp));
    if (got > 0) { o.hp += got; ev(s, { t: 'heal', uid, n: got }); }
    return got;
  }

  function summon(s, p, id, pos) {
    const b = s.players[p].board;
    if (b.length >= MAX_BOARD) return null;
    const m = makeUnit(s, p, id);
    const at = Math.max(0, Math.min(pos == null ? b.length : pos, b.length));
    b.splice(at, 0, m);
    ev(s, { t: 'summon', uid: m.uid, p });
    return m;
  }

  function resolveDeaths(s) {
    for (let guard = 0; guard < 20; guard++) {
      const dead = [];
      for (const p of [s.active, 1 - s.active]) {
        const b = s.players[p].board;
        for (let i = 0; i < b.length; i++) if (b[i].hp <= 0 || b[i].dead) dead.push({ m: b[i], p, i });
      }
      if (!dead.length) break;
      for (const d of dead) {
        const b = s.players[d.p].board;
        b.splice(b.indexOf(d.m), 1);
        ev(s, { t: 'death', uid: d.m.uid, id: d.m.id, p: d.p });
        log(s, d.p, q(CARDS[d.m.id].name) + ' уничтожен');
      }
      for (const d of dead) {
        const def = CARDS[d.m.id];
        if (def.dr) runFx(s, d.p, def.dr, { pos: d.i, spell: false });
      }
    }
    checkWin(s);
  }

  function checkWin(s) {
    if (s.phase === 'over') return;
    const d0 = s.players[0].hero.hp <= 0, d1 = s.players[1].hero.hp <= 0;
    if (d0 || d1) {
      s.phase = 'over';
      s.winner = d0 && d1 ? 'draw' : d0 ? 1 : 0;
      ev(s, { t: 'over', winner: s.winner });
      log(s, null, s.winner === 'draw' ? 'Ничья: оба штаба уничтожены' : 'Штаб уничтожен. Победа: ' + who(s, s.winner).toLowerCase());
    }
  }

  // ---------- Эффекты ----------
  function runFx(s, p, list, ctx) { for (const e of list) applyFx(s, p, e, ctx); }
  function applyFx(s, p, e, ctx) {
    const me = s.players[p];
    switch (e.do) {
      case 'dmg': {
        const n = e.n + (ctx.spell ? spellPower(s, p) : 0);
        for (const uid of resolveTo(s, p, e.to, ctx)) damage(s, uid, n, ctx.source);
        break;
      }
      case 'heal': for (const uid of resolveTo(s, p, e.to, ctx)) heal(s, uid, e.n); break;
      case 'summon': for (let i = 0; i < e.n; i++) summon(s, p, e.id, ctx.pos == null ? null : ctx.pos + i); break;
      case 'draw': for (let i = 0; i < e.n; i++) draw(s, p); break;
      case 'armor': me.hero.armor += e.n; ev(s, { t: 'armor', uid: me.hero.uid, n: e.n }); break;
      case 'mana': me.mana = Math.min(MAX_MANA, me.mana + e.n); break;
      case 'buffAll':
        for (const m of me.board) { m.atk += e.atk; m.hp += e.hp; m.maxHp += e.hp; ev(s, { t: 'buff', uid: m.uid }); }
        break;
      case 'destroy':
        for (const uid of resolveTo(s, p, e.to, ctx)) { const f = find(s, uid); if (f && f.kind === 'unit') { f.obj.dead = true; ev(s, { t: 'destroy', uid }); } }
        break;
      case 'freeze':
        for (const uid of resolveTo(s, p, e.to, ctx)) { const f = find(s, uid); if (f && f.kind === 'unit' && f.obj.hp > 0) { f.obj.frozenAt = s.turn; ev(s, { t: 'freeze', uid }); } }
        break;
    }
  }

  // ---------- Карты в руку ----------
  function draw(s, p) {
    const pl = s.players[p];
    if (!pl.deck.length) {
      pl.fatigue++;
      ev(s, { t: 'fatigue', p, n: pl.fatigue });
      log(s, p, 'Колода пуста: штабу ' + pl.fatigue + ' урона от истощения');
      damage(s, pl.hero.uid, pl.fatigue, null);
      return null;
    }
    const id = pl.deck.pop();
    if (pl.hand.length >= MAX_HAND) {
      ev(s, { t: 'burn', p, id });
      log(s, p, 'Рука полна: ' + q(CARDS[id].name) + ' сгорает');
      return null;
    }
    const c = { uid: 'c' + (s.nextUid++), id };
    pl.hand.push(c);
    ev(s, { t: 'draw', p, uid: c.uid });
    return c;
  }

  // ---------- Партия ----------
  function newGame(o) {
    o = o || {};
    const first = o.first == null ? 0 : o.first;
    const s = {
      v: 1, seed: (o.seed >>> 0) || 1, turn: 0, active: first, first, phase: 'mulligan', winner: null,
      nextUid: 1, events: [], log: [], players: []
    };
    for (let i = 0; i < 2; i++) {
      const d = o.doctrines[i];
      const deck = [];
      for (const id of DOCTRINES[d].deck) deck.push(id, id);
      s.players.push({
        name: (o.names && o.names[i]) || (i === 0 ? 'Вы' : 'Противник'), doctrine: d,
        hero: { uid: 'h' + i, hp: HERO_HP, maxHp: HERO_HP, armor: 0 },
        mana: 0, maxMana: 0, deck: shuffle(s, deck), hand: [], board: [], fatigue: 0, powerUsed: false, mulled: false
      });
    }
    for (let i = 0; i < 2; i++) {
      const n = i === first ? 3 : 4;
      for (let k = 0; k < n; k++) draw(s, i);
    }
    s.events.length = 0;
    return s;
  }

  function mulligan(s, p, idxs) {
    const pl = s.players[p];
    if (s.phase !== 'mulligan' || pl.mulled) return false;
    const sorted = [...new Set(idxs || [])].filter(i => i >= 0 && i < pl.hand.length).sort((a, b) => b - a);
    const back = sorted.map(i => pl.hand.splice(i, 1)[0].id);
    for (let k = 0; k < back.length; k++) draw(s, p);
    for (const id of back) pl.deck.splice(Math.floor(rnd(s) * (pl.deck.length + 1)), 0, id);
    pl.mulled = true;
    if (back.length) log(s, p, 'Заменено карт: ' + back.length);
    if (s.players[0].mulled && s.players[1].mulled) {
      const second = 1 - s.first;
      s.players[second].hand.push({ uid: 'c' + (s.nextUid++), id: 't_coin' });
      s.phase = 'play';
      startTurn(s);
    }
    return true;
  }

  function startTurn(s) {
    const p = s.active, pl = s.players[p];
    s.turn++;
    pl.maxMana = Math.min(MAX_MANA, pl.maxMana + 1);
    pl.mana = pl.maxMana;
    pl.powerUsed = false;
    for (const m of pl.board) { m.sleep = false; m.attacks = 0; }
    ev(s, { t: 'turn', p, turn: s.turn });
    log(s, p, '— ход ' + s.turn + ': ' + who(s, p).toLowerCase() + ' —');
    draw(s, p);
    resolveDeaths(s);
  }

  function endTurn(s) {
    if (s.phase !== 'play') return false;
    const p = s.active, pl = s.players[p];
    for (const m of [...pl.board]) {
      const def = CARDS[m.id];
      if (!def.eot || !pl.board.includes(m) || m.hp <= 0 || m.dead) continue;
      ev(s, { t: 'trigger', uid: m.uid });
      runFx(s, p, def.eot, { source: m.uid, spell: false });
      resolveDeaths(s);
      if (s.phase === 'over') return true;
    }
    for (const m of pl.board) if (m.frozenAt != null && m.frozenAt < s.turn) m.frozenAt = null;
    s.active = 1 - p;
    startTurn(s);
    return true;
  }

  function canPlay(s, p, h) {
    const pl = s.players[p], c = pl.hand[h];
    if (s.phase !== 'play' || s.active !== p || !c) return false;
    const d = CARDS[c.id];
    if (d.cost > pl.mana) return false;
    if (d.type === 'unit' && pl.board.length >= MAX_BOARD) return false;
    if (d.type === 'order' && d.target && !validTargets(s, p, d.target).length) return false;
    if (d.type === 'order' && d.fx.some(e => e.do === 'summon') && pl.board.length >= MAX_BOARD) return false;
    return true;
  }
  // Нужно ли спрашивать цель у игрока при розыгрыше
  function needsTarget(s, p, h) {
    const c = s.players[p].hand[h];
    if (!c) return false;
    const d = CARDS[c.id];
    return !!d.target && validTargets(s, p, d.target).length > 0;
  }

  function playCard(s, p, h, opt) {
    opt = opt || {};
    if (!canPlay(s, p, h)) return false;
    const pl = s.players[p], c = pl.hand[h], d = CARDS[c.id];
    let target = null;
    if (d.target) {
      const vt = validTargets(s, p, d.target);
      if (vt.length) { if (!vt.includes(opt.target)) return false; target = opt.target; }
    }
    pl.mana -= d.cost;
    pl.hand.splice(h, 1);
    ev(s, { t: 'play', p, id: c.id, uid: c.uid, target });
    const tName = target ? ' → ' + nameOf(s, target) : '';
    if (d.type === 'unit') {
      const pos = opt.pos == null ? pl.board.length : opt.pos;
      const m = summon(s, p, c.id, pos);
      log(s, p, who(s, p) + ': ' + q(d.name) + tName);
      if (d.bc) runFx(s, p, d.bc, { target, source: m.uid, pos: pl.board.indexOf(m) + 1, spell: false });
    } else {
      log(s, p, who(s, p) + ': приказ ' + q(d.name) + tName);
      runFx(s, p, d.fx, { target, source: null, spell: true });
    }
    resolveDeaths(s);
    return true;
  }

  function canAttack(s, p, m) {
    return !!m && s.phase === 'play' && s.active === p && m.owner === p && m.atk > 0 && !m.cantAttack &&
      m.frozenAt == null && m.attacks < (m.windfury ? 2 : 1) && (!m.sleep || m.charge || m.rush);
  }
  function attackTargets(s, p, uid) {
    const m = s.players[p].board.find(u => u.uid === uid);
    if (!canAttack(s, p, m)) return [];
    const op = s.players[1 - p];
    const vis = op.board.filter(u => !u.stealth);
    const taunts = vis.filter(u => u.taunt);
    let t = taunts.length ? taunts.map(u => u.uid) : [...vis.map(u => u.uid), op.hero.uid];
    if (m.sleep && !m.charge) t = t.filter(x => x !== op.hero.uid);
    return t;
  }
  function attack(s, p, aUid, tUid) {
    if (!attackTargets(s, p, aUid).includes(tUid)) return false;
    const m = s.players[p].board.find(u => u.uid === aUid);
    const tg = find(s, tUid);
    m.attacks++;
    m.stealth = false;
    ev(s, { t: 'attack', from: aUid, to: tUid });
    log(s, p, q(CARDS[m.id].name) + ' атакует ' + nameOf(s, tUid));
    const back = tg.kind === 'unit' ? tg.obj.atk : 0;
    damage(s, tUid, m.atk, aUid);
    if (back > 0) damage(s, aUid, back, tUid);
    resolveDeaths(s);
    return true;
  }

  function canPower(s, p) {
    const pl = s.players[p];
    if (s.phase !== 'play' || s.active !== p || pl.powerUsed || pl.mana < POWER_COST) return false;
    const pw = DOCTRINES[pl.doctrine].power;
    return !pw.target || validTargets(s, p, pw.target).length > 0;
  }
  function usePower(s, p, target) {
    if (!canPower(s, p)) return false;
    const pl = s.players[p], pw = DOCTRINES[pl.doctrine].power;
    if (pw.target && !validTargets(s, p, pw.target).includes(target)) return false;
    pl.mana -= POWER_COST;
    pl.powerUsed = true;
    ev(s, { t: 'power', p, target: target || null });
    log(s, p, who(s, p) + ': ' + q(pw.name) + (target ? ' → ' + nameOf(s, target) : ''));
    runFx(s, p, pw.fx, { target: target || null, source: null, spell: false });
    resolveDeaths(s);
    return true;
  }

  function cardText(id, sp) {
    const d = CARDS[id];
    return (d.text || '').replace(/\{(\d+)\}/g, (_, n) => sp ? '<em>' + (+n + sp) + '</em>' : n);
  }

  // ---------- ИИ ----------
  function apply(s, a) {
    switch (a.type) {
      case 'play': return playCard(s, a.p, a.h, { target: a.target, pos: a.pos });
      case 'attack': return attack(s, a.p, a.from, a.to);
      case 'power': return usePower(s, a.p, a.target);
      case 'end': return endTurn(s);
    }
    return false;
  }
  function clone(s) {
    return JSON.parse(JSON.stringify(Object.assign({}, s, { events: [], log: [] })));
  }
  function legalActions(s, p) {
    const out = [], pl = s.players[p];
    if (s.phase !== 'play' || s.active !== p) return out;
    for (let h = 0; h < pl.hand.length; h++) {
      if (!canPlay(s, p, h)) continue;
      const d = CARDS[pl.hand[h].id];
      const vt = d.target ? validTargets(s, p, d.target) : [];
      if (vt.length) for (const t of vt) out.push({ type: 'play', p, h, target: t });
      else out.push({ type: 'play', p, h });
    }
    if (canPower(s, p)) {
      const pw = DOCTRINES[pl.doctrine].power;
      if (pw.target) for (const t of validTargets(s, p, pw.target)) out.push({ type: 'power', p, target: t });
      else out.push({ type: 'power', p });
    }
    for (const m of pl.board) for (const t of attackTargets(s, p, m.uid)) out.push({ type: 'attack', p, from: m.uid, to: t });
    return out;
  }
  function unitVal(m) {
    const def = CARDS[m.id];
    let v = 0.5 + m.atk + m.hp * 0.9;
    if (m.taunt) v += 1;
    if (m.shield) v += 1 + m.atk * 0.5;
    if (m.windfury) v += m.atk * 0.6;
    if (m.poison) v += 2.5;
    if (m.stealth) v += 1;
    if (m.spellDmg) v += 1;
    if (def.eot) v += 2;
    if (def.dr) v += 1;
    if (m.cantAttack) v -= m.atk * 0.4;
    if (m.frozenAt != null) v -= m.atk * 0.3;
    return v;
  }
  const heroVal = hp => hp <= 0 ? -1e4 : 6 * Math.sqrt(hp);
  function evaluate(s, p) {
    if (s.phase === 'over') return s.winner === p ? 1e5 : s.winner === 'draw' ? 0 : -1e5;
    const me = s.players[p], op = s.players[1 - p];
    let v = heroVal(me.hero.hp + me.hero.armor) - heroVal(op.hero.hp + op.hero.armor);
    for (const m of me.board) v += unitVal(m);
    for (const m of op.board) v -= unitVal(m) * 1.05;
    v += Math.min(me.hand.length, 9) * 1.2;
    return v;
  }
  function staticVal(id) {
    const d = CARDS[id];
    if (d.type === 'unit') return unitVal(makeUnit({ nextUid: 0 }, 0, id)) - 1.2;
    return 1;
  }
  // Потенциал позиции: оценка + лучшая карта, на которую ещё хватает топлива.
  // Так ИИ не тратит топливо на слабую карту, если на него можно сыграть сильную.
  function potential(s, p) {
    const me = s.players[p];
    let follow = 0;
    if (s.phase === 'play' && s.active === p) {
      for (let k = 0; k < me.hand.length; k++) {
        if (me.hand[k].id !== 't_coin' && canPlay(s, p, k)) follow = Math.max(follow, staticVal(me.hand[k].id));
      }
    }
    return evaluate(s, p) + 0.8 * follow;
  }
  // Один шаг: лучшее действие; null — пора заканчивать ход
  function aiChoose(s, p) {
    const acts = legalActions(s, p);
    if (!acts.length) return null;
    const base = potential(s, p);
    let best = null, bestG = 0.05;
    for (const a of acts) {
      const c = clone(s);
      c.seed = (c.seed ^ 0x9E3779B9) | 0;
      if (!apply(c, a)) continue;
      const g = potential(c, p) - base;
      if (g > bestG) { bestG = g; best = a; }
    }
    return best;
  }
  function aiMulligan(s, p) {
    return s.players[p].hand.map((c, i) => CARDS[c.id].cost > 3 ? i : -1).filter(i => i >= 0);
  }

  return {
    CARDS, DOCTRINES, KW, KW_HELP, MAX_BOARD, MAX_HAND, MAX_MANA, HERO_HP, POWER_COST,
    newGame, mulligan, playCard, attack, usePower, endTurn,
    canPlay, needsTarget, canAttack, attackTargets, canPower, validTargets, spellPower, cardText, find,
    AI: { choose: aiChoose, mulligan: aiMulligan, evaluate, legalActions, apply, clone }
  };
});
