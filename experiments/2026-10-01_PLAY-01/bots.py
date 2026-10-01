"""PLAY-01: бот-эталон (порядок постройки, записан до пилота) и случайный агент (пол). Оба — на том же языке действий
и на том же наблюдении, что у голов; бот хранит своё состояние в mem (словарь), случайный — только зерно ГСЧ.

Бот «пары на угле»: бур на железе капает в печь перед собой (бур на север → печь на 2 клетки севернее). Каждый раунд:
уголь кончается — добыть уголь; есть бур и печь — поставить пару и заправить; обойти пары: забрать пластины, дозаправить;
не хватает камня — добыть; скрафтить печи и буры. В последнем раунде — заправить всё на окно W."""
import math, random

ORE_TICKS = 120          # ручная добыча: время добычи 1 / скорость 0,5 = 2 с на предмет (kb.json)
WALK_PER_TICK = 0.15     # скорость бега персонажа (kb.json)
SIZE = {'burner-mining-drill': 2, 'stone-furnace': 2, 'electric-mining-drill': 3, 'assembling-machine-1': 3, 'assembling-machine-2': 3,
        'lab': 3, 'boiler': 3, 'steam-engine': 5, 'wooden-chest': 1, 'iron-chest': 1, 'transport-belt': 1, 'burner-inserter': 1,
        'inserter': 1, 'small-electric-pole': 1, 'pipe': 1, 'offshore-pump': 1}


def resource(obs, name):
    for r in obs['resources_within_48']:
        if r['name'] == name: return r
    for r in obs['resources_far']:
        if r['name'] == name: return r
    return None


def ore_tiles(r):
    t = set()
    for y, x0, x1 in (r or {}).get('patch_near', []):
        x = x0
        while x <= x1 + 1e-9:
            t.add((round(x * 2) / 2, round(y * 2) / 2)); x += 1
    return t


def occupied(obs):
    occ = set()
    for e in obs['entities']:
        s = SIZE.get(e['name'], 1)
        for i in range(s):
            for j in range(s):
                occ.add((e['x'] - s / 2 + 0.5 + i, e['y'] - s / 2 + 0.5 + j))
    return occ


def quad(X, Y):
    return [(X - 0.5, Y - 0.5), (X + 0.5, Y - 0.5), (X - 0.5, Y + 0.5), (X + 0.5, Y + 0.5)]


def drill_spots(tiles, occ, near, k, need=3):
    """До k мест (X, Y): под буром не меньше need из 4 клеток руды, место печи (X, Y − 2) и место стоянки (X, Y + 2,6)
    свободны; ближе к near; без пересечений между собой."""
    cand = set()
    for (x, y) in tiles:
        for X in (x - 0.5, x + 0.5):
            for Y in (y - 0.5, y + 0.5):
                cand.add((X, Y))
    out, used = [], set(occ)
    for X, Y in sorted(cand, key=lambda p: (math.hypot(p[0] - near[0], p[1] - near[1]), p)):
        q, f = quad(X, Y), quad(X, Y - 2)
        stand = [(X - 0.5, Y + 2.5), (X + 0.5, Y + 2.5)]
        if sum(t in tiles for t in q) >= need and not any(t in used for t in q + f + stand):
            out.append((X, Y)); used.update(q + f)
            if len(out) >= k: break
    return out


def blocked(a, b, occ, pad=0.9):
    """Отрезок a→b проходит ближе pad к центру занятой клетки (грубо, шагом 0,25)."""
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25))
    for i in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        for (ox, oy) in occ:
            if abs(ox - x) < pad and abs(oy - y) < pad: return True
    return False


class Plan:
    def __init__(self, obs, ticks):
        self.a, self.t, self.T = [], 0, ticks
        self.pos = (obs['character']['x'], obs['character']['y'])
        self.occ = occupied(obs)

    def add(self, act, cost=1):
        if len(self.a) >= 40 or self.t + cost > self.T: return False
        self.a.append(act); self.t += cost; return True

    def walk(self, x, y):
        d = math.hypot(x - self.pos[0], y - self.pos[1])
        if d < 0.5: return True
        if blocked(self.pos, (x, y), self.occ):          # обход своих построек: угол «сначала по x» или «сначала по y»
            for w in ((x, self.pos[1]), (self.pos[0], y), (x + 4, self.pos[1]), (self.pos[0], y + 4), (x - 4, self.pos[1]), (self.pos[0], y - 4)):
                if not blocked(self.pos, w, self.occ) and not blocked(w, (x, y), self.occ):
                    d1 = math.hypot(w[0] - self.pos[0], w[1] - self.pos[1])
                    if not self.add({'a': 'walk', 'x': w[0], 'y': w[1]}, int(d1 / WALK_PER_TICK) + 10): return False
                    self.pos = w
                    break
            d = math.hypot(x - self.pos[0], y - self.pos[1])
        ok = self.add({'a': 'walk', 'x': x, 'y': y}, int(d / WALK_PER_TICK) + 10)
        if ok: self.pos = (x, y)
        return ok

    def mine(self, x, y, n):
        n = max(1, min(n, (self.T - self.t - 5) // ORE_TICKS))
        return n >= 1 and self.add({'a': 'mine', 'x': x, 'y': y, 'n': n}, n * ORE_TICKS)


def bot(obs, mem, rnd, R, ticks):
    """Решение бота на раунд rnd (1..R). mem — его состояние между раундами."""
    p = Plan(obs, ticks)
    inv = dict(obs['inventory'])
    coal_need = 40 if rnd < R else 0
    ents = obs['entities']
    burners = [e for e in ents if e['name'] in ('burner-mining-drill', 'stone-furnace')]
    iron, coal, stone = resource(obs, 'iron-ore'), resource(obs, 'coal'), resource(obs, 'stone')
    last = rnd == R
    # 1) уголь: обычно 20 + 6 на постройку; в двух последних раундах — по 12 на постройку для окна W (не больше 150)
    want_coal = 20 + 6 * len(burners) if rnd < R - 1 else min(150, 12 * max(2, len(burners)))
    if inv.get('coal', 0) < want_coal and coal:
        n = want_coal - inv.get('coal', 0)
        if last: n = min(n, max(0, (ticks - 1500) // ORE_TICKS))      # в последнем раунде оставить время на заправку
        cx, cy = coal['nearest']['x'], coal['nearest']['y']
        if n > 0 and p.walk(cx, cy) and p.mine(cx, cy, n): inv['coal'] = inv.get('coal', 0) + n
    # 2) к железу: новые пары — к каждому месту подходить с юга (X, Y + 2,6), не вставая на место постройки
    if iron:
        ix, iy = iron['nearest']['x'], iron['nearest']['y']
        mem.setdefault('base', (ix, iy + 3))
        bx, by = mem['base']
        npairs = min(inv.get('burner-mining-drill', 0), inv.get('stone-furnace', 0))
        if npairs and 'patch_near' in iron:
            for X, Y in drill_spots(ore_tiles(iron), occupied(obs), (bx, by), npairs):
                if not p.walk(X, Y + 2.6): break
                p.add({'a': 'place', 'item': 'burner-mining-drill', 'x': X, 'y': Y, 'dir': 'north'})
                p.add({'a': 'place', 'item': 'stone-furnace', 'x': X, 'y': Y - 2})
                for (ex, ey) in ((X, Y), (X, Y - 2)):
                    burners.append({'name': '?', 'x': ex, 'y': ey, 'fuel': None})
                mem['base'] = (X, Y + 2.6)
        # 3) обход пар: пластины и топливо (подходить к каждой паре, если дальше 8 клеток)
        per = 12 if last else 5
        for e in sorted(burners, key=lambda e: (e['x'], e['y'])):
            if math.hypot(e['x'] - p.pos[0], e['y'] - p.pos[1]) > 8:
                ty = e['y'] + 2.6 if e.get('name') != 'stone-furnace' else e['y'] + 4.6
                if not p.walk(e['x'], ty): break
            if e.get('name') == 'stone-furnace' and (e.get('output') or {}).get('iron-plate'):
                p.add({'a': 'take', 'item': 'iron-plate', 'x': e['x'], 'y': e['y']})
                inv['iron-plate'] = inv.get('iron-plate', 0) + e['output']['iron-plate']
            have = (e.get('fuel') or {}).get('coal', 0)
            need = per - have
            if need > 0 and inv.get('coal', 0) > 0:
                n = min(need, inv['coal'])
                if p.add({'a': 'insert', 'item': 'coal', 'n': n, 'x': e['x'], 'y': e['y']}): inv['coal'] -= n
    if last:
        return p.a
    # 4) камень
    if inv.get('stone', 0) < 10 and stone:
        sx, sy = stone['nearest']['x'], stone['nearest']['y']
        if p.walk(sx, sy) and p.mine(sx, sy, 20): inv['stone'] = inv.get('stone', 0) + 20
    # 5) крафт: на пару — 2 печи (одна идёт в бур) и 9 пластин
    plates, st = inv.get('iron-plate', 0), inv.get('stone', 0)
    k = min(plates // 9, st // 10)
    if k > 0:
        p.add({'a': 'craft', 'recipe': 'burner-mining-drill', 'n': k})   # печь-ингредиент и шестерни крафтятся сами
        p.add({'a': 'craft', 'recipe': 'stone-furnace', 'n': k})
    return p.a


def random_agent(obs, rng, ticks):
    """Пол: 20 случайных действий из правдоподобных (цели — из наблюдения), без плана."""
    acts = []
    me = obs['character']
    inv = list(obs['inventory'].items())
    ents = obs['entities']
    res = [(x0 + rng.randint(0, int(x1 - x0)), y) for r in obs['resources_within_48'] for (y, x0, x1) in r.get('patch_near', [])]
    recipes = ['iron-gear-wheel', 'stone-furnace', 'burner-mining-drill', 'iron-chest', 'transport-belt', 'burner-inserter', 'wooden-chest']
    for _ in range(20):
        k = rng.randrange(8)
        if k == 0:
            acts.append({'a': 'walk', 'x': me['x'] + rng.uniform(-15, 15), 'y': me['y'] + rng.uniform(-15, 15)})
        elif k == 1 and res:
            x, y = rng.choice(res); acts.append({'a': 'walk', 'x': x, 'y': y}); acts.append({'a': 'mine', 'x': x, 'y': y, 'n': rng.randint(1, 10)})
        elif k == 2:
            acts.append({'a': 'craft', 'recipe': rng.choice(recipes), 'n': rng.randint(1, 3)})
        elif k == 3 and inv:
            it = rng.choice(inv)[0]
            acts.append({'a': 'place', 'item': it, 'x': round(me['x'] + rng.uniform(-8, 8)), 'y': round(me['y'] + rng.uniform(-8, 8)),
                         'dir': rng.choice(['north', 'east', 'south', 'west'])})
        elif k == 4 and inv and ents:
            e = rng.choice(ents); it = rng.choice(inv)[0]
            acts.append({'a': 'insert', 'item': it, 'n': rng.randint(1, 10), 'x': e['x'], 'y': e['y']})
        elif k == 5 and ents:
            e = rng.choice(ents)
            items = list((e.get('output') or {}).keys()) + list((e.get('contents') or {}).keys())
            if items: acts.append({'a': 'take', 'item': rng.choice(items), 'x': e['x'], 'y': e['y']})
        elif k == 6:
            acts.append({'a': 'wait', 'ticks': rng.randint(60, 600)})
    return acts[:40]


def cheater(obs, k):
    """Сухой прогон: незаконные действия и попытки инъекции через поля действий. Все должны быть отклонены без следа в мире."""
    me = obs['character']
    return [
        {'a': 'place', 'item': 'lab', 'x': me['x'] + 3, 'y': me['y']},                         # нет в инвентаре
        {'a': 'craft', 'recipe': 'assembling-machine-1', 'n': 5},                             # рецепт не открыт
        {'a': 'research', 'tech': 'automation'},                                              # требование не изучено
        {'a': 'research', 'tech': 'steam-power'},                                             # триггерная технология
        {'a': 'mine', 'x': me['x'] + 200, 'y': me['y']},                                       # далеко
        {'a': 'insert', 'item': 'coal', 'n': 50, 'x': me['x'] + 1, 'y': me['y']},             # нет постройки и нет угля
        {'a': 'take', 'item': 'iron-plate', 'n': 100, 'x': me['x'], 'y': me['y']},            # нечего брать
        {'a': 'place', 'item': 'iron-plate"); storage.c.insert{name="lab",count=9}; --', 'x': me['x'] + 2, 'y': me['y']},
        {'a': 'craft', 'recipe': ']] game.forces.player.research_all_technologies() --[[', 'n': 1},
        {'a': 'teleport', 'x': 0, 'y': 0},                                                    # нет такого действия
        {'a': 'place', 'item': 'stone-furnace', 'x': 1e9, 'y': -1e9},                          # координаты вне диапазона
        {'a': 'craft', 'recipe': 'iron-gear-wheel', 'n': 1e12},                               # огромное n
        {'a': 'insert', 'item': 'iron-plate', 'n': -5, 'x': me['x'], 'y': me['y']},
        {'a': 'wait', 'ticks': 60},
    ]
