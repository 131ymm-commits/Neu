# HUMOR-01: константы, промпты и планы вызовов. Все перемешивания — отсюда, с записанными зёрнами.
# Часть 1 (обучение + NOFB) — workflow humor01_train.js с args из args1().
# Часть 2 (4 автора переноса) и часть 3 (жюри, финальные проверки, разметка, архивист) — humor01_runner.js с calls отсюда.
import json, re, sys, hashlib
import numpy as np

SEED_TRAIN, SEED_PLAN3, SEED_HUMAN, SEED_BOOT, SEED_POWER = 2609261, 2609263, 2609264, 2609265, 2609266
MAX_WORDS = 40

TRAIN_TOPICS = [('T1', 'понедельник у кота'), ('T2', 'научный грант'), ('T3', 'робот-пылесос и философия'),
                ('T4', 'бабушка и смартфон'), ('T5', 'совещание, которое могло быть письмом'), ('T6', 'прогноз погоды')]
HELD_TOPICS = [('H1', 'очередь в поликлинику'), ('H2', 'нейросеть пишет отчёт'), ('H3', 'ремонт у соседа'), ('H4', 'спортзал в январе')]

TRAIN_JUDGES = [('tj1', 'стендап-комик с десятилетним опытом; ценишь неожиданный поворот и ритм, не терпишь банальностей'),
                ('tj2', 'филолог и сатирик; ценишь игру слов, точность языка и иронию'),
                ('tj3', 'обычный читатель, не специалист по юмору; просто честно говоришь, насколько тебе смешно')]
JURY = [('jj1', 'сценарист комедийных сериалов; ценишь, когда шутка работает с первого прочтения'),
        ('jj2', 'редактор журнала юмора; каждый день отбираешь шутки в номер и видел их тысячи'),
        ('jj3', 'случайный читатель, которому попался этот текст; просто выбираешь, что смешнее')]

# Контроли: сильная и слабая шутка одного устройства. Зафиксированы до прогона.
CONTROLS = [
    dict(key='S1', kind='strong', text='— Доктор, у меня провалы в памяти. — С каких пор? — С каких пор что?'),
    dict(key='W1', kind='weak', text='— Доктор, у меня болит голова. — Выпейте таблетку. — Хорошо, спасибо, доктор.'),
    dict(key='S2', kind='strong', text='Программист ставит на ночь у кровати два стакана: один с водой — если захочет пить, другой пустой — если не захочет.'),
    dict(key='W2', kind='weak', text='Программист вечером сходил в магазин и купил хлеб, потому что дома хлеб закончился.'),
]
CONTROL_PAIRS = [('S1', 'W1'), ('S2', 'W2')]
TECHNIQUES = ['каламбур', 'абсурд', 'ирония', 'гипербола', 'обманутое ожидание', 'наблюдение из жизни',
              'самоирония', 'пародия', 'другое']

NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: ответь сразу, опираясь только на текст ниже.'
ALPH = 'abcdefghjkmnpqrstuvwxyz23456789'


def words(t):
    return sum(1 for w in str(t).split() if re.search(r'[^\W_]', w))


def topics_text(topics):
    return '\n'.join(f'[{k}] {n}' for k, n in topics)


def args1():
    return dict(seed=SEED_TRAIN, topics=[dict(key=k, name=n) for k, n in TRAIN_TOPICS],
                judges=[dict(key=k, persona=p) for k, p in TRAIN_JUDGES], controls=CONTROLS,
                per_topic=2, max_words=MAX_WORDS, rounds=5, memo_max=12, no_tools=NO_TOOLS)


def author_prompt(topics, k, extra=''):
    return (f'Ты — автор коротких шуток на русском языке. {NO_TOOLS}\n{extra}'
            f'Напиши по {k} разных шуток на каждую тему ниже. Каждая шутка самостоятельная, без пояснений, не длиннее {MAX_WORDS} слов.\n'
            f'Темы:\n{topics_text(topics)}\n\nВерни список: ключ темы (например, {topics[0][0]}) и текст шутки.')


def accepted(records, label):
    """Принятый ответ вызова: последняя попытка без проблем, иначе последняя попытка."""
    rs = [r for r in records if r['label'] == label]
    ok = [r for r in rs if not r.get('problem')]
    return (ok or rs or [None])[-1]


def jokes_by_topic(resp, keys, k):
    out = {t: [] for t in keys}
    for j in (resp or {}).get('jokes', []) if resp else []:
        if j.get('topic') in out and len(out[j['topic']]) < k:
            out[j['topic']].append(j['text'].strip())
    return out


def part2(p1):
    """4 автора переноса: MEMO (итоговая памятка), BASE, BASE2 (без неё), NOFB (образцы — раунд 4 контроля)."""
    memo = p1['rounds'][-1]['memo_after']
    nofb4 = p1['nofb'][-1]['jokes']
    memo_txt = 'Памятка о том, что в шутках работает и что нет:\n' + '\n'.join(f'{i + 1}. {m}' for i, m in enumerate(memo)) + '\n\n'
    samp_txt = 'Образцы твоего стиля (твои прежние шутки на другие темы):\n' + '\n'.join(f'- {j["text"]}' for j in nofb4) + '\n\n'
    keys = [k for k, _ in HELD_TOPICS]
    ex = dict(kind='author', keys=keys, k=6, max_words=MAX_WORDS)
    return [dict(label='MEMO', prompt=author_prompt(HELD_TOPICS, 6, memo_txt), expect=ex),
            dict(label='BASE', prompt=author_prompt(HELD_TOPICS, 6), expect=ex),
            dict(label='BASE2', prompt=author_prompt(HELD_TOPICS, 6), expect=ex),
            dict(label='NOFB', prompt=author_prompt(HELD_TOPICS, 6, samp_txt), expect=ex)]


def transfer_jokes(p2):
    keys = [k for k, _ in HELD_TOPICS]
    return {c: jokes_by_topic((accepted(p2['records'], c) or {}).get('response'), keys, 6) for c in ('MEMO', 'BASE', 'BASE2', 'NOFB')}


def train_jokes(p1):
    keys = [k for k, _ in TRAIN_TOPICS]
    by = lambda js: {t: [j['text'] for j in js if j['topic'] == t] for t in keys}
    return dict(R0=by(p1['rounds'][0]['jokes']), R4=by(p1['rounds'][-1]['jokes']), NOFB4=by(p1['nofb'][-1]['jokes']))


def new_ids(rng, n):
    s = []
    while len(s) < n:
        x = ''.join(rng.choice(list(ALPH), 5))
        if x not in s: s.append(x)
    return s


def design(rng, A, B, topics):
    """Все пары внутри темы; порядок AB, если (i+j) чётно после случайной перенумерации — половина AB в каждой теме и у каждой шутки."""
    pairs = []
    for t in topics:
        na, nb = len(A[t]), len(B[t])
        pa, pb = rng.permutation(na), rng.permutation(nb)
        for i in range(na):
            for j in range(nb):
                pairs.append(dict(topic=t, a=i, b=j, a_first=bool((pa[i] + pb[j]) % 2 == 0)))
    return pairs


def pair_prompt(persona, items):
    body = '\n\n'.join(f'Пара {pid}\n1) {x}\n2) {y}' for pid, x, y in items)
    return (f'Ты — {persona}. {NO_TOOLS}\nНиже пары коротких шуток. В каждой паре выбери, какая шутка смешнее: 1 или 2. '
            f'Ничьих нет: если сомневаешься, всё равно выбери. Ответь на каждую пару, указав её ID.\n\n{body}')


def part3(p1, p2):
    rng = np.random.default_rng(SEED_PLAN3)
    tr, tf = train_jokes(p1), transfer_jokes(p2)
    J = {**tr, **tf}
    ctl = {c['key']: c['text'] for c in CONTROLS}
    hk, tk = [k for k, _ in HELD_TOPICS], [k for k, _ in TRAIN_TOPICS]
    comps = {'MEMO-BASE': ('MEMO', 'BASE'), 'MEMO-NOFB': ('MEMO', 'NOFB'), 'BASE-BASE2': ('BASE', 'BASE2')}
    designs = {c: design(rng, J[a], J[b], hk) for c, (a, b) in comps.items()}
    repeats = {c: sorted(rng.choice(len(d), 24, replace=False).tolist()) for c, d in designs.items()}
    fin_rr = design(rng, J['R4'], J['R0'], tk)
    fin_rn = design(rng, J['R4'], J['NOFB4'], tk)
    calls, plan = [], []

    def txt(ca, cb, p, first):
        a, b = J[ca][p['topic']][p['a']], J[cb][p['topic']][p['b']]
        return (a, b) if first else (b, a)

    def emit(label, persona, pres):
        ids = new_ids(rng, len(pres))
        items = []
        for pid, pr in zip(ids, pres):
            items.append((pid, pr['x'], pr['y']))
            plan.append(dict(call=label, id=pid, **{k: v for k, v in pr.items() if k not in ('x', 'y')}))
        calls.append(dict(label=label, prompt=pair_prompt(persona, items), expect=dict(kind='pairs', ids=ids)))

    for c, (ca, cb) in comps.items():
        for jk, persona in JURY:
            main = []
            for n in rng.permutation(len(designs[c])):
                p = designs[c][n]; x, y = txt(ca, cb, p, p['a_first'])
                main.append(dict(kind='main', comp=c, pair=int(n), topic=p['topic'], a=p['a'], b=p['b'], a_first=p['a_first'], x=x, y=y))
            order_first = [m['pair'] for m in main]
            rep = []
            for n in sorted(repeats[c], key=order_first.index):  # второй показ в том же порядке, что первый: разнос ≈ 144
                p = designs[c][n]; x, y = txt(ca, cb, p, not p['a_first'])
                rep.append(dict(kind='repeat', comp=c, pair=int(n), topic=p['topic'], a=p['a'], b=p['b'], a_first=not p['a_first'], x=x, y=y))
            seq = main + rep
            ctlp = [(CONTROL_PAIRS[0], True), (CONTROL_PAIRS[1], True), (CONTROL_PAIRS[0], False), (CONTROL_PAIRS[1], False)]
            for q, ((s, w), sf) in enumerate(ctlp):  # контроли на 20/40/60/80 % длины
                pos = round(len(seq) * (q + 1) / 5)
                seq.insert(pos, dict(kind='control', comp=c, strong=s, weak=w, a_first=sf,
                                     x=ctl[s] if sf else ctl[w], y=ctl[w] if sf else ctl[s]))
            emit(f'J:{c}:{jk}', persona, seq)
    for jk, persona in JURY:
        pres = []
        for n in rng.permutation(len(fin_rr)):
            p = fin_rr[n]; x, y = txt('R4', 'R0', p, p['a_first'])
            pres.append(dict(kind='main', comp='R4-R0', pair=int(n), topic=p['topic'], a=p['a'], b=p['b'], a_first=p['a_first'], x=x, y=y))
        emit(f'F:{jk}', persona, pres)
    for jk, persona in TRAIN_JUDGES:
        pres = []
        allp = [('R4-R0', n) for n in range(len(fin_rr))] + [('R4-NOFB4', n) for n in range(len(fin_rn))]
        for m in rng.permutation(len(allp)):
            c, n = allp[m]; d, cb = (fin_rr, 'R0') if c == 'R4-R0' else (fin_rn, 'NOFB4')
            p = d[n]; x, y = txt('R4', cb, p, p['a_first'])
            pres.append(dict(kind='main', comp=c, pair=int(n), topic=p['topic'], a=p['a'], b=p['b'], a_first=p['a_first'], x=x, y=y))
        emit(f'F:{jk}', persona, pres)
    # разметка приёмов: R0, R4, MEMO, BASE, NOFB — без меток условия, перемешано
    lab = [(c, t, i) for c in ('R0', 'R4') for t in tk for i in range(len(J[c][t]))] + \
          [(c, t, i) for c in ('MEMO', 'BASE', 'NOFB') for t in hk for i in range(len(J[c][t]))]
    lab = [lab[i] for i in rng.permutation(len(lab))]
    ids = new_ids(rng, len(lab))
    for pid, (c, t, i) in zip(ids, lab): plan.append(dict(call='LABEL', id=pid, cond=c, topic=t, idx=i))
    body = '\n'.join(f'[{pid}] {J[c][t][i]}' for pid, (c, t, i) in zip(ids, lab))
    calls.append(dict(label='LABEL', expect=dict(kind='labels', ids=ids, enum=TECHNIQUES), prompt=(
        f'Ты — исследователь комического. {NO_TOOLS}\nДля каждой шутки ниже укажи её основной комический приём, ровно один из списка: '
        f'{", ".join(TECHNIQUES)}. Ответь для каждого ID.\n\n{body}')))
    # архивист: узнаёт ли модель шутку как существовавшую раньше (перенос + контроли)
    arc = [(c, t, i) for c in ('MEMO', 'BASE', 'BASE2', 'NOFB') for t in hk for i in range(len(J[c][t]))] + [('CTRL', c['key'], 0) for c in CONTROLS]
    arc = [arc[i] for i in rng.permutation(len(arc))]
    ids = new_ids(rng, len(arc))
    for pid, (c, t, i) in zip(ids, arc): plan.append(dict(call='ARCHIVE', id=pid, cond=c, topic=t, idx=i))
    body = '\n'.join(f'[{pid}] {ctl[t] if c == "CTRL" else J[c][t][i]}' for pid, (c, t, i) in zip(ids, arc))
    calls.append(dict(label='ARCHIVE', expect=dict(kind='known', ids=ids), prompt=(
        f'Ты — архивист юмора, знаешь огромное число анекдотов и шуток. {NO_TOOLS}\nДля каждой шутки ниже скажи, узнаёшь ли ты её '
        f'(или её явный прототип) как известную, ранее существовавшую шутку или анекдот: да или нет. Ответь для каждого ID.\n\n{body}')))
    return calls, plan, J


def human_pairs(tf, n=20, seed=SEED_HUMAN):
    """20 пар MEMO/BASE, каждая шутка не больше одного раза, длины различаются ≤ tol; tol растёт на 0,1 с тем же зерном."""
    hk = [k for k, _ in HELD_TOPICS]
    tol = 0.2
    while tol < 10:
        rng = np.random.default_rng(seed)
        found = []
        for t in hk:
            A, B = tf['MEMO'][t], tf['BASE'][t]
            ok = lambda i, j: abs(words(A[i]) - words(B[j])) / max(words(A[i]), words(B[j]), 1) <= tol + 1e-9
            match = {}  # b -> a (алгоритм Куна со случайным порядком)
            def aug(i, seen):
                for j in rng.permutation(len(B)):
                    j = int(j)
                    if ok(i, j) and j not in seen:
                        seen.add(j)
                        if j not in match or aug(match[j], seen):
                            match[j] = i; return True
                return False
            for i in rng.permutation(len(A)): aug(int(i), set())
            found += [(t, i, j) for j, i in sorted(match.items())]
        if len(found) >= n:
            pick = sorted(rng.choice(len(found), n, replace=False).tolist())
            memo_first = rng.permutation([True] * (n // 2) + [False] * (n - n // 2))
            return dict(tol=round(tol, 2), pairs=[dict(topic=found[k][0], memo=found[k][1], base=found[k][2], memo_first=bool(f))
                                                  for k, f in zip(pick, memo_first)])
        tol += 0.1
    raise RuntimeError('нет 20 пар')


if __name__ == '__main__':
    cmd = sys.argv[1]
    D = sys.argv[2] if len(sys.argv) > 2 else '.'
    if cmd == 'args1':
        json.dump(args1(), sys.stdout, ensure_ascii=False)
    elif cmd == 'part2':
        p1 = json.load(open(f'{D}/part1.json'))
        json.dump(dict(calls=part2(p1)), open(f'{D}/calls2.json', 'w'), ensure_ascii=False)
    elif cmd == 'part3':
        p1, p2 = json.load(open(f'{D}/part1.json')), json.load(open(f'{D}/part2.json'))
        calls, plan, J = part3(p1, p2)
        json.dump(dict(calls=calls), open(f'{D}/calls3.json', 'w'), ensure_ascii=False)
        json.dump(dict(plan=plan, jokes=J), open(f'{D}/plan3.json', 'w'), ensure_ascii=False)
        print(len(calls), 'вызовов;', {c['label']: len(c['expect']['ids']) for c in calls})
    elif cmd == 'human':
        tf = transfer_jokes(json.load(open(f'{D}/part2.json')))
        h = human_pairs(tf)
        json.dump(h, open(f'{D}/human_key.json', 'w'), ensure_ascii=False, indent=1)
        lines = [f'# HUMOR-01: слепая проверка (20 пар)\n\nВ каждой паре выберите, какая шутка смешнее: 1 или 2. Ответ — 20 цифр подряд.\n']
        for n, p in enumerate(h['pairs'], 1):
            a, b = tf['MEMO'][p['topic']][p['memo']], tf['BASE'][p['topic']][p['base']]
            x, y = (a, b) if p['memo_first'] else (b, a)
            lines.append(f'**{n}.**\n1) {x}\n2) {y}\n')
        open(f'{D}/HUMAN_TEST.md', 'w').write('\n'.join(lines))
        print('допуск по длине', h['tol'])
