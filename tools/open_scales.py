#!/usr/bin/env python3
"""Открытые весы — ядро в сотню строк (19.10.2026, MIT).

Каждый судья (человек или ИИ) сам ставит вероятность события до того, как увидит других. В общий журнал
идёт только отпечаток sha256(вероятность|соль); время печати даёт git-коммит. После исхода судья
раскрывает число, код считает точность каждого (балл Брайера) и свод, где вес судьи — его измеренная
точность на ДРУГИХ вопросах. «Не знаю» (?) — допустимый ответ: он не штрафуется, но и не голосует.

  python3 tools/open_scales.py seal    ЖУРНАЛ СУДЬЯ ВОПРОС P     # P — число от 0 до 1 или ?
  python3 tools/open_scales.py reveal  ЖУРНАЛ СУДЬЯ ВОПРОС P СОЛЬ
  python3 tools/open_scales.py outcome ЖУРНАЛ ВОПРОС 0|1
  python3 tools/open_scales.py score   ЖУРНАЛ
  python3 tools/open_scales.py demo                              # синтетика: копии против разных судей
Журнал — файл JSON Lines; каждое действие коммитится, история git — нотариус порядка."""
import hashlib, json, math, random, secrets, sys
from collections import defaultdict

def stamp(p, salt): return hashlib.sha256(f'{p}|{salt}'.encode()).hexdigest()
def logit(p): p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))
def sigm(x): return 1 / (1 + math.exp(-x))
def append(path, rec):
    with open(path, 'a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')

def load(path):
    seals, probs, outcomes = {}, {}, {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line); key = (r.get('judge'), r['q'])
        if r['type'] == 'seal' and key not in seals: seals[key] = r['hash']          # первая печать — окончательная
        elif r['type'] == 'reveal' and key in seals and stamp(r['p'], r['salt']) == seals[key] and r['q'] not in outcomes:
            probs[key] = None if r['p'] == '?' else float(r['p'])                    # раскрыто до исхода и совпало с печатью
        elif r['type'] == 'outcome': outcomes.setdefault(r['q'], int(r['y']))
    return probs, outcomes

def brier(pairs): return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None

def score(probs, outcomes):
    """Брайер судей и сводов. Вес судьи на вопросе q — его навык 1 − Брайер/0,25 на остальных вопросах (не меньше 0)."""
    by_judge = defaultdict(dict)
    for (j, q), p in probs.items():
        if q in outcomes: by_judge[j][q] = p
    res = {}
    for j, d in by_judge.items():
        pairs = [(p, outcomes[q]) for q, p in d.items() if p is not None]
        res[j] = dict(brier=brier(pairs), answered=len(pairs), unsure=sum(p is None for p in d.values()))
    qs = sorted({q for d in by_judge.values() for q in d})
    sse = {j: sum((p - outcomes[q]) ** 2 for q, p in d.items() if p is not None) for j, d in by_judge.items()}
    equal, weighted = [], []
    for q in qs:
        votes = {j: d[q] for j, d in by_judge.items() if d.get(q) is not None}
        if not votes: continue
        equal.append((sum(votes.values()) / len(votes), outcomes[q]))
        w = {}
        for j in votes:                                   # Брайер судьи без вопроса q: сумма минус свой член
            n_other = res[j]['answered'] - 1
            w[j] = max(0.0, 1 - (sse[j] - (votes[j] - outcomes[q]) ** 2) / n_other / 0.25) if n_other else 0.0
        if sum(w.values()) == 0: w = {j: 1.0 for j in votes}
        x = sum(w[j] * logit(votes[j]) for j in votes) / sum(w.values())
        weighted.append((sigm(x), outcomes[q]))
    res['= свод на равных'] = dict(brier=brier(equal), answered=len(equal), unsure=0)
    res['= свод с весами по точности'] = dict(brier=brier(weighted), answered=len(weighted), unsure=0)
    return res

def show(res):
    print(f'{"судья":32} {"Брайер":>7} {"ответов":>8} {"не знаю":>8}')
    for j, r in sorted(res.items(), key=lambda kv: (kv[0].startswith('='), kv[1]['brier'] or 9)):
        print(f'{j:32} {r["brier"]:7.3f} {r["answered"]:8d} {r["unsure"]:8d}')

def demo(n=2000, seed=2026):
    """Синтетический мир: у события есть скрытая «правда» t, исход — монетка с вероятностью sigm(t).
    Судья видит t с шумом. У копий шум общий (ошибаются вместе), у независимых — свой.
    Печатает Брайер лучшего судьи и двух сводов в четырёх составах коллектива."""
    rng = random.Random(seed); world = []
    for i in range(n):
        t = rng.uniform(-3, 3); world.append((f'Q{i}', t, int(rng.random() < sigm(t)), rng.gauss(0, 1.0)))
    def jury(kinds):
        probs = {}
        for q, t, y, shared in world:
            for j, (kind, s) in enumerate(kinds):
                noise = shared * s if kind == 'копия' else rng.gauss(0, s)
                probs[(f'{kind}{j}', q)] = sigm(t + noise)
        return probs
    outcomes = {q: y for q, t, y, s in world}
    cases = [('один сильный судья', [('копия', 1.0)]),
             ('сильный + 4 его копии', [('копия', 1.0)] * 5),
             ('5 независимых, таких же сильных', [('свой', 1.0)] * 5),
             ('сильный + 4 слабых независимых', [('свой', 1.0)] + [('свой', 3.0)] * 4)]
    print(f'{"состав коллектива":36} {"лучший":>7} {"на равных":>10} {"с весами":>9}')
    for name, kinds in cases:
        r = score(jury(kinds), outcomes)
        best = min(v['brier'] for k, v in r.items() if not k.startswith('='))
        print(f'{name:36} {best:7.3f} {r["= свод на равных"]["brier"]:10.3f} {r["= свод с весами по точности"]["brier"]:9.3f}')
    print('Брайер: меньше — лучше; монетка 0,25.')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'demo': demo()
    elif a[0] == 'seal':
        salt = secrets.token_hex(8); append(a[1], dict(type='seal', judge=a[2], q=a[3], hash=stamp(a[4], salt)))
        print(f'печать записана; соль храните у себя до раскрытия: {salt}')
    elif a[0] == 'reveal': append(a[1], dict(type='reveal', judge=a[2], q=a[3], p=a[4], salt=a[5]))
    elif a[0] == 'outcome': append(a[1], dict(type='outcome', q=a[2], y=int(a[3])))
    elif a[0] == 'score': show(score(*load(a[1])))
    else: sys.exit(__doc__)
