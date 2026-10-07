# SELECT-01: генераторы задач со состоянием и отложенными последствиями и их симуляторы (правда от кода).
# Решение совета 26 (docs/council/2026-10-07_NEXT_session26.md): два типа задач — склад (WH) и расписание (SC), анализ раздельный.
# Головы видят только text_rules(task) — правила, прогноз и параметры. Скрытое: зерно шума (noise_seed), из которого берутся
# фактический спрос (WH) и фактические длительности работ (SC). Правда кандидата = simulate(task, plan, noise).
#   python3 sim.py demo   — показать по одной задаче каждого типа и прогнать эвристики
import json, math, random, sys

# ---------------- склад (WH) ----------------
# T дней, 2 товара. Заказ товара i в день t приходит утром дня t+L_i (если t+L_i < T). Партия годна S_i дней с дня прихода
# (в день прихода + S_i − 1 ещё продаётся, вечером дня прихода + S_i − 1 списывается). Продажи — FIFO, сначала старые партии.
# Деньги: старт C0. Заказ оплачивается в день заказа: K (за каждый ненулевой заказ) + c_i·q. Если денег не хватает,
# заказ урезается до доступного (по товарам в порядке 0, 1); при нехватке даже на K заказ отменяется.
# Выручка p_i за проданную единицу приходит вечером. Хранение h_i за единицу на складе вечером (после продаж и списания).
# Склад вмещает CAP единиц всех товаров: излишек при приходе пропадает (оплачен, но не принят).
# Упущенная продажа штрафует g_i за единицу (неустойка). Итог (правда) = деньги в конце дня T−1 − C0. Остатки ничего не стоят.
# Спрос: прогноз mu[t][i] (виден); факт = round(mu·m), m = exp(N(0, σ)) − свой на день и товар (скрыт), σ = 0,3.

def gen_wh(seed, T=30, sigma=0.3):
    r = random.Random(seed)
    items = []
    for i in range(2):
        c = r.randint(4, 12); p = c + r.randint(3, 9)
        items.append(dict(L=r.randint(2, 5), S=r.randint(4, 9), c=c, p=p, h=round(r.uniform(0.2, 1.0), 1), g=r.randint(2, 8)))
    base = [r.randint(15, 40) for _ in range(2)]
    trend = [r.uniform(-0.4, 0.6) for _ in range(2)]
    week = [[1 + r.uniform(-0.35, 0.35) for _ in range(7)] for _ in range(2)]
    promo = sorted(r.sample(range(8, T - 3), 2))
    mu = []
    for t in range(T):
        row = []
        for i in range(2):
            v = base[i] * week[i][t % 7] * (1 + trend[i] * t / T) * (2.2 if t in promo and i == (promo.index(t) % 2) else 1)
            row.append(max(1, round(v)))
        mu.append(row)
    cap = round(sum(base) * 4)
    c0 = round(sum(base[i] * items[i]['c'] for i in range(2)) * 6)
    k = r.randint(15, 60)
    init = [round(base[i] * 1.5) for i in range(2)]   # начальный запас, возраст 0 в день 0
    return dict(type='WH', seed=seed, T=T, items=items, mu=mu, cap=cap, C0=c0, K=k, init=init, sigma=sigma)

def noise_wh(task, nseed):
    r = random.Random(nseed)
    return [[max(0, round(task['mu'][t][i] * math.exp(r.gauss(0, task['sigma'])))) for i in range(2)] for t in range(task['T'])]

def parse_wh(task, plan):
    # план: {"orders": [[q0, q1], ...] длины T}; всё недопустимое — 0, лишние дни отбрасываются, недостающие — 0
    T = task['T']; out = [[0, 0] for _ in range(T)]
    try:
        o = plan.get('orders') if isinstance(plan, dict) else plan
        for t in range(min(T, len(o))):
            for i in range(2):
                try: q = int(o[t][i])
                except Exception: q = 0
                out[t][i] = max(0, min(q, 10 ** 6))
    except Exception:
        pass
    return out

def simulate_wh(task, plan, demand, trace=False):
    T, it = task['T'], task['items']; orders = parse_wh(task, plan)
    cash = task['C0']; lots = [[[task['init'][i], 0]] for i in range(2)]  # партии [кол-во, день прихода]
    pipe = {}  # день прихода -> [q0, q1]
    log = []
    for t in range(T):
        # утро: приход
        arr = pipe.pop(t, [0, 0])
        for i in range(2):
            if arr[i]:
                room = task['cap'] - sum(q for j in range(2) for q, _ in lots[j])
                lots[i].append([min(arr[i], max(0, room)), t])
        # заказ (оплата сейчас)
        q = list(orders[t])
        if any(q):
            if cash < task['K']: q = [0, 0]
            else:
                cash -= task['K']
                for i in range(2):
                    q[i] = min(q[i], int(cash // it[i]['c'])); cash -= q[i] * it[i]['c']
                for i in range(2):
                    if t + it[i]['L'] < T and q[i]: pipe.setdefault(t + it[i]['L'], [0, 0])[i] += q[i]
        # продажи
        sold, lost = [0, 0], [0, 0]
        for i in range(2):
            d = demand[t][i]
            for lot in lots[i]:
                s = min(lot[0], d); lot[0] -= s; d -= s; sold[i] += s
            lost[i] = d
            cash += sold[i] * it[i]['p'] - lost[i] * it[i]['g']
        # вечер: списание и хранение
        for i in range(2):
            lots[i] = [l for l in lots[i] if l[0] > 0 and t < l[1] + it[i]['S'] - 1]
            cash -= sum(l[0] for l in lots[i]) * it[i]['h']
        if trace: log.append(dict(t=t, cash=round(cash, 1), sold=sold, lost=lost, stock=[sum(l[0] for l in lots[i]) for i in range(2)]))
    res = round(cash - task['C0'], 2)
    return (res, log) if trace else res

def rules_wh(task):
    it = task['items']; T = task['T']
    s = [f'Задача «склад». {T} дней (день 0 … день {T - 1}), два товара: 0 и 1.',
         'Каждый день ты можешь заказать любое целое количество каждого товара. Порядок событий в день t:',
         f'1) утро — приходят заказы, сделанные в день t − L (L у каждого товара свой); склад вмещает {task["cap"]} единиц всех товаров вместе, излишек при приходе пропадает (уже оплачен);',
         f'2) заказ — оплачивается сразу: {task["K"]} за каждый день, в который заказано хоть что-то, плюс цена единицы × количество; если денег не хватает, заказ урезается до доступного (сначала товар 0, потом 1), а если не хватает даже на {task["K"]}, заказ этого дня отменяется. Заказ, который пришёл бы после дня {T - 1}, оплачивается, но не приходит;',
         '3) продажи — продаётся min(запас, спрос), сначала самые старые партии; выручка = цена продажи × проданное; за каждую непроданную из-за нехватки единицу спроса — неустойка;',
         '4) вечер — партия, пришедшая в день a, списывается вечером дня a + S − 1 (продаётся S дней, включая день прихода); за каждую единицу, оставшуюся на складе вечером, платится хранение.',
         f'Старт: деньги {task["C0"]}; запас товара 0 — {task["init"][0]}, товара 1 — {task["init"][1]} (пришли в день 0). Остатки в конце ничего не стоят.',
         'Итог задачи — прибыль: деньги в конце дня ' + f'{T - 1} минус стартовые {task["C0"]}. Больше — лучше.',
         'Параметры товаров:']
    for i in range(2):
        s.append(f'  товар {i}: срок поставки L = {it[i]["L"]} дн., годность S = {it[i]["S"]} дн., закупка {it[i]["c"]}, продажа {it[i]["p"]}, хранение {it[i]["h"]} за ед. в день, неустойка {it[i]["g"]} за ед. нехватки.')
    s.append(f'Прогноз спроса по дням [товар 0, товар 1]. Фактический спрос случаен: прогноз × множитель, множитель ≈ exp(N(0; {task["sigma"]})) — свой на каждый день и товар, независимо; в среднем на ~30 % выше или ниже прогноза, иногда сильнее.')
    s.append('mu = ' + json.dumps(task['mu']))
    s.append(f'План — JSON {{"orders": [[q0, q1], …]}}: ровно {T} пар, пара t — заказ в день t.')
    return '\n'.join(s)

# ---------------- расписание (SC) ----------------
# 2 станка, J работ. У работы: семейство f (0..2), номинальная длительность d, момент готовности rel, срок due, вес w.
# План — для каждого станка упорядоченный список: номера работ и "M" (обслуживание). Станок берёт элементы по порядку:
# работа начинается в max(станок свободен, rel) + переналадка SU, если семейство отличается от предыдущей работы станка
# (у первой работы станка переналадки нет). Фактическая длительность = d × износ × шум; износ = 1 + 0,08 × (число работ,
# выполненных станком после последнего обслуживания). Обслуживание "M" занимает MT и сбрасывает износ.
# Шум — exp(N(0; 0,2)), свой у каждой работы, скрыт (одинаков на любом станке). Итог (правда) = −Σ w·max(0, конец − due). Больше — лучше.
# Недопустимый план чинится детерминированно: повторы работ выбрасываются (остаётся первое вхождение по станку 0, потом 1),
# пропущенные работы дописываются в конец станка 0 по возрастанию номера; неизвестные элементы игнорируются.

def gen_sc(seed, J=20, sigma=0.2, wear=0.08, v=1):
    r = random.Random(seed)
    jobs = []
    for j in range(J):
        d = r.randint(3, 15); rel = r.randint(0, 40)
        jobs.append(dict(f=r.randint(0, 2), d=d, rel=rel, due=rel + d + r.randint(5, 45), w=r.randint(1, 5)))
    return dict(type='SC', seed=seed, J=J, jobs=jobs, SU=r.randint(3, 7), MT=r.randint(5, 10), wear=wear, sigma=sigma, v=v)

def noise_sc(task, nseed):
    r = random.Random(nseed)
    return [math.exp(r.gauss(0, task['sigma'])) for _ in range(task['J'])]

def parse_sc(task, plan):
    J = task['J']; seen = set(); m = [[], []]
    try:
        mm = plan.get('machines') if isinstance(plan, dict) else plan
        for k in range(2):
            for x in (mm[k] if k < len(mm) else []):
                if x == 'M' or x == 'm': m[k].append('M'); continue
                try: j = int(x)
                except Exception: continue
                if 0 <= j < J and j not in seen: seen.add(j); m[k].append(j)
    except Exception:
        pass
    m[0] += [j for j in range(J) if j not in seen]
    return m

def simulate_sc(task, plan, mult, trace=False):
    m = parse_sc(task, plan); jobs = task['jobs']; tot = 0.0; log = []
    for k in range(2):
        t, fam, wear = 0.0, None, 0
        for x in m[k]:
            if x == 'M': t += task['MT']; wear = 0; continue
            jb = jobs[x]; st = max(t, jb['rel']) + (task['SU'] if fam is not None and fam != jb['f'] else 0)
            t = st + jb['d'] * (1 + task['wear'] * wear) * mult[x]; wear += 1; fam = jb['f']
            tard = max(0.0, t - jb['due']); tot += jb['w'] * tard
            if trace: log.append(dict(machine=k, job=x, start=round(st, 2), end=round(t, 2), tard=round(tard, 2)))
    res = round(-tot, 2)
    return (res, log) if trace else res

def rules_sc(task):
    s = [f'Задача «расписание». Два станка (0 и 1), {task["J"]} работ (0 … {task["J"] - 1}). Каждую работу надо выполнить ровно один раз на любом станке.',
         'План — для каждого станка упорядоченный список: номера работ и "M" (обслуживание). Станок выполняет элементы строго по порядку, без простоя сверх необходимого:',
         f'— работа начинается не раньше своей готовности rel и не раньше, чем станок освободился; если семейство работы отличается от семейства предыдущей работы на этом станке, сначала переналадка {task["SU"]} ед. времени (у первой работы станка переналадки нет; обслуживание семейство не сбрасывает);',
         f'— фактическая длительность = номинальная d × износ × случайный множитель; износ = 1 + {task["wear"]} × (число работ, выполненных этим станком после последнего обслуживания или с начала); случайный множитель ≈ exp(N(0; {task["sigma"]})), свой у каждой работы, заранее неизвестен;',
         f'— обслуживание "M" занимает {task["MT"]} ед. времени и сбрасывает износ.',
         'Опоздание работы = max(0, момент окончания − срок due). Итог задачи = −(сумма вес × опоздание) по всем работам. Больше — лучше (0 — никто не опоздал).',
         'Если в плане работа повторена, лишние вхождения выбрасываются; пропущенные работы дописываются в конец станка 0 по возрастанию номера.',
         'Работы: номер: семейство f, номинал d, готовность rel, срок due, вес w']
    for j, jb in enumerate(task['jobs']):
        s.append(f'  {j}: f={jb["f"]} d={jb["d"]} rel={jb["rel"]} due={jb["due"]} w={jb["w"]}')
    s.append('План — JSON {"machines": [[…станок 0…], […станок 1…]]}, например [[3, 0, "M", 7], [1, 2]].')
    return '\n'.join(s)

# SC v2 (07.10, после пилота v1: медиана регрета A0 = 0,01 < 0,2 — допуск не пройден; меняются только параметры генератора)
GEN = dict(WH=gen_wh, SC=lambda s: gen_sc(s, J=30, sigma=0.4, wear=0.12, v=2)); NOISE = dict(WH=noise_wh, SC=noise_sc); SIM = dict(WH=simulate_wh, SC=simulate_sc); RULES = dict(WH=rules_wh, SC=rules_sc)

# ---------------- эвристики (для проверки разброса, не головы) ----------------
def heur_wh(task, kind, r):
    T, it, mu = task['T'], task['items'], task['mu']; o = [[0, 0] for _ in range(T)]
    if kind == 'zero': return {'orders': o}
    for t in range(T):
        for i in range(2):
            L, S = it[i]['L'], it[i]['S']
            if kind == 'cover':     # каждый день заказать прогноз дня прихода × коэффициент
                a = t + L
                if a < T: o[t][i] = round(mu[a][i] * r.uniform(0.8, 1.4))
            elif kind == 'batch':   # раз в b дней заказать на b дней вперёд
                b = max(1, min(S, 3))
                if t % b == 0 and t + L < T: o[t][i] = round(sum(mu[a][i] for a in range(t + L, min(T, t + L + b))) * r.uniform(0.8, 1.3))
    return {'orders': o}

def heur_sc(task, kind, r):
    J, jobs = task['J'], task['jobs']
    if kind == 'edd': order = sorted(range(J), key=lambda j: (jobs[j]['due'], j))
    elif kind == 'wspt': order = sorted(range(J), key=lambda j: (jobs[j]['d'] / jobs[j]['w'], j))
    elif kind == 'fam': order = sorted(range(J), key=lambda j: (jobs[j]['f'], jobs[j]['due']))
    else: order = list(range(J)); r.shuffle(order)
    m = [[], []]; load = [0, 0]
    for j in order:
        k = 0 if load[0] <= load[1] else 1; m[k].append(j); load[k] += jobs[j]['d']
    if kind != 'rand':
        for k in range(2):
            if len(m[k]) > 6: m[k].insert(len(m[k]) // 2, 'M')
    return {'machines': m}

if __name__ == '__main__' and sys.argv[1:2] == ['demo']:
    r = random.Random(0)
    for typ in ('WH', 'SC'):
        task = GEN[typ](101); print(RULES[typ](task)[:1500], '\n…')
        nz = NOISE[typ](task, 9001)
        kinds = ['zero', 'cover', 'cover', 'batch', 'batch'] if typ == 'WH' else ['edd', 'wspt', 'fam', 'rand', 'rand']
        H = heur_wh if typ == 'WH' else heur_sc
        print(typ, [(k, SIM[typ](task, H(task, k, r), nz)) for k in kinds])

# ---------------- правда ----------------
# Правда кандидата — среднее итога по R скрытым реализациям шума (ожидаемый исход плана); зёрна шума — из секретной соли.
import hashlib
def noise_seeds(salt, task_seed, R=1000):
    return [int(hashlib.sha256(f'{salt}|{task_seed}|{r}'.encode()).hexdigest()[:12], 16) for r in range(R)]

def truth(task, plan, salt, R=1000):
    typ = task['type']; vals = [SIM[typ](task, plan, NOISE[typ](task, s)) for s in noise_seeds(salt, task['seed'], R)]
    return round(sum(vals) / len(vals), 2)
