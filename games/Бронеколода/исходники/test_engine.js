// Проверки правил движка: node test_engine.js
const E = require('./engine.js');
let pass = 0, fail = 0;
function ok(cond, name) { if (cond) pass++; else { fail++; console.log('НЕ ПРОШЛО:', name); } }

// Партия в фазе боя с заданными руками; колоды по 30 карт
function game(o = {}) {
  const s = E.newGame({ doctrines: o.d || ['A', 'B'], seed: o.seed || 7, first: 0 });
  E.mulligan(s, 0, []); E.mulligan(s, 1, []);
  s.events.length = 0;
  return s;
}
function put(s, p, id, extra) {
  const d = E.CARDS[id], kw = d.kw || [];
  const m = { uid: 'u' + (s.nextUid++), id, owner: p, atk: d.atk, hp: d.hp, maxHp: d.hp,
    taunt: kw.includes('taunt'), charge: kw.includes('charge'), rush: kw.includes('rush'), shield: kw.includes('shield'),
    stealth: kw.includes('stealth'), windfury: kw.includes('windfury'), poison: kw.includes('poison'),
    cantAttack: kw.includes('cantAttack'), spellDmg: d.spellDmg || 0, sleep: false, attacks: 0, frozenAt: null, dead: false };
  Object.assign(m, extra || {});
  s.players[p].board.push(m);
  return m;
}
function give(s, p, id) { const c = { uid: 'c' + (s.nextUid++), id }; s.players[p].hand.push(c); return s.players[p].hand.length - 1; }

// колоды и старт
{
  for (const d of ['A', 'B', 'C']) {
    ok(E.DOCTRINES[d].deck.length === 15, 'в колоде ' + d + ' 15 разных карт');
    for (const id of E.DOCTRINES[d].deck) ok(!!E.CARDS[id], 'карта существует ' + id);
  }
  const s = E.newGame({ doctrines: ['A', 'C'], seed: 3, first: 0 });
  ok(s.players[0].hand.length === 3 && s.players[1].hand.length === 4, 'первый берёт 3, второй 4');
  ok(s.players[0].deck.length === 27 && s.players[1].deck.length === 26, 'колоды по 30');
  E.mulligan(s, 0, [0, 1, 2]);
  ok(s.players[0].hand.length === 3 && s.players[0].deck.length === 27, 'замена сохраняет число карт');
  E.mulligan(s, 1, []);
  ok(s.phase === 'play' && s.turn === 1, 'после замены начинается первый ход');
  ok(s.players[1].hand.some(c => c.id === 't_coin'), 'второй получает канистру');
  ok(s.players[0].hand.length === 4 && s.players[0].mana === 1, 'первый ход: +1 карта, 1 топливо');
}

// топливо растёт до 10
{
  const s = game();
  for (let i = 0; i < 24; i++) E.endTurn(s);
  ok(s.players[0].maxMana === 10 && s.players[1].maxMana === 10, 'топливо не больше 10');
}

// Заслон
{
  const s = game();
  const a = put(s, 0, 'n_t26');
  const t = put(s, 1, 'n_matilda');
  put(s, 1, 'n_t34');
  const tg = E.attackTargets(s, 0, a.uid);
  ok(tg.length === 1 && tg[0] === t.uid, 'Заслон закрывает остальных и штаб');
  ok(!E.attack(s, 0, a.uid, 'h1'), 'нельзя бить штаб через Заслон');
  // замаскированный заслон не заставляет
  t.stealth = true;
  ok(E.attackTargets(s, 0, a.uid).includes('h1'), 'замаскированный Заслон не держит');
}

// Рывок, Прорыв, сон
{
  const s = game();
  s.players[0].mana = 10;
  E.playCard(s, 0, give(s, 0, 'n_t26'));
  const t26 = s.players[0].board.at(-1);
  ok(E.attackTargets(s, 0, t26.uid).length === 0, 'новый отряд не атакует');
  E.playCard(s, 0, give(s, 0, 'n_bt7'));
  const bt = s.players[0].board.at(-1);
  ok(E.attackTargets(s, 0, bt.uid).includes('h1'), 'Рывок бьёт штаб сразу');
  E.playCard(s, 0, give(s, 0, 'n_ba64'));
  const ba = s.players[0].board.at(-1);
  ok(!E.attackTargets(s, 0, ba.uid).includes('h1'), 'Прорыв не бьёт штаб в первый ход');
  put(s, 1, 'n_t26');
  ok(E.attackTargets(s, 0, ba.uid).length === 1, 'Прорыв бьёт отряд в первый ход');
}

// Обмен ударами, гибель, урон по штабу
{
  const s = game();
  const a = put(s, 0, 'n_t34'); // 3/4
  const b = put(s, 1, 'n_bt7'); // 3/2
  E.attack(s, 0, a.uid, b.uid);
  ok(a.hp === 1, 'ответный урон');
  ok(!s.players[1].board.includes(b), 'цель уничтожена');
  ok(!E.attack(s, 0, a.uid, 'h1'), 'вторая атака без автомата запрещена');
  const c = put(s, 0, 'n_pz4');
  E.attack(s, 0, c.uid, 'h1');
  ok(s.players[1].hero.hp === 26, 'урон по штабу');
}

// Динамическая защита
{
  const s = game();
  const a = put(s, 0, 'n_t34');
  const t = put(s, 1, 'n_t27');
  E.attack(s, 0, a.uid, t.uid);
  ok(s.players[1].board.includes(t) && !t.shield && t.hp === 1, 'ДЗ поглощает первый удар');
  ok(a.hp === 3, 'отряд с ДЗ отвечает');
}

// Кумулятивный
{
  const s = game();
  const a = put(s, 0, 'n_ptr'); // 1/3
  const t = put(s, 1, 'n_maus');
  E.attack(s, 0, a.uid, t.uid);
  ok(!s.players[1].board.includes(t), 'Кумулятивный уничтожает Маус');
  const s2 = game();
  const big = put(s2, 0, 'n_tiger');
  const ptr = put(s2, 1, 'n_ptr');
  E.attack(s2, 0, big.uid, ptr.uid);
  ok(!s2.players[0].board.includes(big), 'Кумулятивный уничтожает и атакующего');
  const s3 = game();
  const a3 = put(s3, 0, 'n_ptr');
  const t3 = put(s3, 1, 'n_t27');
  E.attack(s3, 0, a3.uid, t3.uid);
  ok(s3.players[1].board.includes(t3), 'ДЗ спасает от кумулятивного');
}

// Автомат заряжания
{
  const s = game();
  const a = put(s, 0, 'a_ace');
  ok(E.attack(s, 0, a.uid, 'h1') && E.attack(s, 0, a.uid, 'h1'), 'две атаки за ход');
  ok(!E.attack(s, 0, a.uid, 'h1'), 'третьей нет');
  ok(s.players[1].hero.hp === 22, 'урон 2×4');
}

// Маскировка
{
  const s = game();
  const z = put(s, 1, 'n_zis3');
  const a = put(s, 0, 'n_t34');
  ok(!E.attackTargets(s, 0, a.uid).includes(z.uid), 'замаскированного нельзя атаковать');
  ok(!E.validTargets(s, 0, 'any').includes(z.uid), 'замаскированного нельзя выбрать приказом');
  ok(E.validTargets(s, 1, 'any').includes(z.uid), 'свой замаскированный доступен');
  s.active = 1; z.sleep = false;
  E.attack(s, 1, z.uid, 'h0');
  ok(!z.stealth, 'атака снимает маскировку');
}

// Обездвиживание и оттаивание
{
  const s = game();
  const t = put(s, 1, 'n_t34');
  s.players[0].mana = 10;
  ok(E.playCard(s, 0, give(s, 0, 'a_track'), { target: t.uid }), 'выстрел по гусенице');
  ok(t.frozenAt != null && t.hp === 3, 'цель обездвижена, 1 урон');
  E.endTurn(s); // ход противника
  ok(E.attackTargets(s, 1, t.uid).length === 0, 'обездвиженный не атакует в свой ход');
  E.endTurn(s); // снова наш
  ok(t.frozenAt == null, 'оттаял в конце своего хода');
  E.endTurn(s);
  ok(E.attackTargets(s, 1, t.uid).length > 0, 'на следующий ход атакует');
}

// Приказы, корректировщик, цели
{
  const s = game();
  s.players[0].mana = 10;
  const t = put(s, 1, 'n_kv1'); // 3/7
  put(s, 0, 'n_spotter');
  E.playCard(s, 0, give(s, 0, 'a_ap'), { target: t.uid });
  ok(t.hp === 3, 'Бронебойный + корректировщик: 4 урона');
  ok(!E.playCard(s, 0, give(s, 0, 'a_ap'), { target: 'h1' }), 'бронебойный не бьёт штаб');
  const s2 = game();
  s2.players[0].mana = 10;
  const h = give(s2, 0, 'a_track');
  ok(!E.canPlay(s2, 0, h), 'приказ без допустимой цели не играется');
}

// При вводе без цели и с целью
{
  const s = game();
  s.players[0].mana = 10;
  ok(!E.playCard(s, 0, give(s, 0, 'n_su85')), 'СУ-85 без выбранной цели не разыгрывается (штабы — допустимые цели)');
  const s2 = game();
  s2.players[0].mana = 10;
  const h = give(s2, 0, 'n_su85');
  ok(E.needsTarget(s2, 0, h), 'СУ-85 спрашивает цель');
  ok(E.playCard(s2, 0, h, { target: 'h1' }) && s2.players[1].hero.hp === 28, 'СУ-85 бьёт штаб на 2');
  const s3 = game();
  s3.players[0].mana = 10;
  const h3 = give(s3, 0, 'b_su152');
  ok(!E.needsTarget(s3, 0, h3) && E.playCard(s3, 0, h3), 'Зверобой без крупной цели играется без эффекта');
  const s4 = game();
  s4.players[0].mana = 10;
  const tiger = put(s4, 1, 'n_tiger');
  E.playCard(s4, 0, give(s4, 0, 'b_su152'), { target: tiger.uid });
  ok(!s4.players[1].board.includes(tiger), 'Зверобой уничтожает Тигра');
}

// Призыв, позиции, предел поля
{
  const s = game();
  s.players[0].mana = 10;
  E.playCard(s, 0, give(s, 0, 'n_t26'));
  E.playCard(s, 0, give(s, 0, 'n_t26'));
  E.playCard(s, 0, give(s, 0, 'n_halftrack'), { pos: 1 });
  const ids = s.players[0].board.map(m => m.id);
  ok(ids.join() === 'n_t26,n_halftrack,t_rifle,t_rifle,n_t26', 'стрелки встают справа от бронетранспортёра');
  s.players[0].mana = 10;
  E.playCard(s, 0, give(s, 0, 'n_t26'));
  E.playCard(s, 0, give(s, 0, 'n_t26'));
  ok(s.players[0].board.length === 7, 'поле заполнено');
  const h = give(s, 0, 'n_moto');
  ok(!E.canPlay(s, 0, h), 'восьмой отряд нельзя');
  const s2 = game();
  s2.players[0].mana = 10;
  for (let i = 0; i < 6; i++) put(s2, 0, 'n_t26');
  E.playCard(s2, 0, give(s2, 0, 'n_halftrack'));
  ok(s2.players[0].board.length === 7, 'лишние стрелки не появляются');
}

// При уничтожении
{
  const s = game();
  const m = put(s, 1, 'n_motor');
  put(s, 1, 'n_t26');
  const a = put(s, 0, 'n_t34');
  E.attack(s, 0, a.uid, m.uid);
  const b = s.players[1].board.map(x => x.id).join();
  ok(b === 't_rifle,n_t26', 'стрелок встаёт на место мотопехоты');
}

// Конец хода: гаубица и БРЭМ
{
  const s = game({ d: ['B', 'C'] });
  put(s, 0, 'b_m30');
  E.endTurn(s);
  ok(s.players[1].hero.hp === 29, 'гаубица бьёт единственную цель — штаб');
  const s2 = game({ d: ['C', 'A'] });
  s2.players[0].hero.hp = 20;
  const t = put(s2, 0, 'n_t34', { hp: 1 });
  put(s2, 0, 'c_arv');
  E.endTurn(s2);
  ok(s2.players[0].hero.hp === 22 && t.hp === 3, 'БРЭМ чинит штаб и отряды');
}

// Броня и умения командиров
{
  const s = game({ d: ['C', 'B'] });
  s.players[0].mana = 2;
  ok(E.usePower(s, 0), 'Окопаться');
  ok(s.players[0].hero.armor === 2 && s.players[0].mana === 0, 'броня +2, топливо −2');
  ok(!E.usePower(s, 0), 'умение раз в ход');
  E.endTurn(s);
  s.players[1].mana = 2;
  E.usePower(s, 1);
  ok(s.players[0].hero.armor === 0 && s.players[0].hero.hp === 30, 'броня поглощает урон');
  const s2 = game({ d: ['A', 'B'] });
  s2.players[0].mana = 2;
  const t = put(s2, 1, 'n_t27');
  ok(E.usePower(s2, 0, t.uid) && !t.shield, 'пулемёт снимает ДЗ');
}

// Канистра
{
  const s = game();
  E.endTurn(s);
  const h = s.players[1].hand.findIndex(c => c.id === 't_coin');
  E.playCard(s, 1, h);
  ok(s.players[1].mana === 2, 'канистра даёт топливо');
}

// Истощение и полная рука
{
  const s = game();
  s.players[0].deck.length = 0;
  E.endTurn(s); E.endTurn(s);
  ok(s.players[0].hero.hp === 29 && s.players[0].fatigue === 1, 'истощение 1');
  E.endTurn(s); E.endTurn(s);
  ok(s.players[0].hero.hp === 27, 'истощение 2');
  const s2 = game();
  while (s2.players[1].hand.length < 10) give(s2, 1, 'n_t26');
  const deckBefore = s2.players[1].deck.length;
  E.endTurn(s2);
  ok(s2.players[1].hand.length === 10 && s2.players[1].deck.length === deckBefore - 1, 'лишняя карта сгорает');
}

// Победа
{
  const s = game();
  s.players[1].hero.hp = 3;
  const a = put(s, 0, 'n_t34');
  E.attack(s, 0, a.uid, 'h1');
  ok(s.phase === 'over' && s.winner === 0, 'штаб уничтожен — победа');
  ok(!E.endTurn(s), 'после победы ходов нет');
}

// Клин и прорыв обороны
{
  const s = game();
  s.players[0].mana = 10;
  const a = put(s, 0, 'n_t26');
  E.playCard(s, 0, give(s, 0, 'a_wedge'));
  ok(a.atk === 3 && a.hp === 4 && a.maxHp === 4, 'клин +1/+1');
  const e1 = put(s, 1, 'n_t26'), e2 = put(s, 1, 'n_t27');
  E.playCard(s, 0, give(s, 0, 'a_breach'));
  ok(e1.hp === 1 && s.players[1].board.includes(e2) && !e2.shield, 'прорыв обороны по всем, ДЗ поглощает');
}

// ИИ делает только допустимые ходы, состояние остаётся JSON
{
  for (let seed = 1; seed <= 6; seed++) {
    const s = E.newGame({ doctrines: ['A', 'B', 'C'][seed % 3] ? [['A', 'B', 'C'][seed % 3], ['A', 'B', 'C'][(seed + 1) % 3]] : ['A', 'B'], seed, first: seed % 2 });
    E.mulligan(s, 0, E.AI.mulligan(s, 0)); E.mulligan(s, 1, E.AI.mulligan(s, 1));
    let steps = 0, bad = 0;
    while (s.phase === 'play' && steps < 2000) {
      const p = s.active;
      const a = E.AI.choose(s, p);
      if (a) { if (!E.AI.apply(s, a)) bad++; } else E.endTurn(s);
      s.events.length = 0;
      steps++;
    }
    ok(s.phase === 'over' && bad === 0, 'партия ИИ против ИИ доходит до конца без ошибок, зерно ' + seed);
    ok(JSON.stringify(JSON.parse(JSON.stringify(s))) === JSON.stringify(s), 'состояние сериализуется');
  }
}

console.log('проверок пройдено:', pass, 'не пройдено:', fail);
process.exit(fail ? 1 : 0);
