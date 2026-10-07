# SELECT-01: анализ. Нормированный регрет r = (оракул − выбранный) / (оракул − среднее пула); E (случайный выбор) ≡ 1 в ожидании.
#   python3 analyze.py <WH|SC> <evals/stage.jsonl ...> [--eps X] [--out json]
# Правила (совет 26, DESIGN.md): A0 = argmax заявки; голосование — простое большинство (plurality); ничьи — по сиду (sha256 задачи и руки),
# не по индексу; D/D_N: отказ (choice = −1) → у D засчитывается выбор A0; у D_N большинство среди неотказавшихся, все отказались → A0.
# Недопустимый номер или сбой головы (после одного перезапуска) → ожидание случайного выбора (r = 1).
# Тест: парный перестановочный (смена знаков) по задачам, статистика — среднее разностей регрета, односторонний;
# полный перебор при n ≤ 20, иначе Монте-Карло 200 000 (зерно 0). Холм на семействе {C_N − B_blind, D_N − B_blind}.
import argparse, collections, glob, hashlib, itertools, json, os, random, statistics as st, sys
D = os.environ.get('SELECT_ROOT', os.path.dirname(os.path.abspath(__file__))); SEC = os.environ.get('SELECT_SECRET', '/root/select_secret')

def tiebreak(cands, key):
    return sorted(cands, key=lambda c: hashlib.sha256(f'{key}|{c}'.encode()).hexdigest())[0]

def plurality(votes, key):
    c = collections.Counter(votes); m = max(c.values()); return tiebreak([v for v in c if c[v] == m], key)

def a0(pool, t):
    m = max(c['claim'] for c in pool); return tiebreak([i for i, c in enumerate(pool) if c['claim'] == m], f'{t}|A0')

def perm_p(diffs, seed=0, mc=200000):
    # H1: среднее разностей < 0 (рука лучше: регрет меньше). p = доля перестановок со средним ≤ наблюдаемого.
    n = len(diffs); obs = sum(diffs) / n
    if n <= 20:
        tot = le = 0
        for s in itertools.product((1, -1), repeat=n):
            tot += 1; le += sum(a * b for a, b in zip(s, diffs)) / n <= obs + 1e-12
        return le / tot, 'полный перебор'
    r = random.Random(seed); le = sum(sum(d if r.random() < .5 else -d for d in diffs) / n <= obs + 1e-12 for _ in range(mc))
    return (le + 1) / (mc + 1), f'Монте-Карло {mc}'

def boot_ci(diffs, seed=0, B=20000):
    r = random.Random(seed); n = len(diffs); ms = sorted(sum(r.choice(diffs) for _ in range(n)) / n for _ in range(B))
    return ms[int(.025 * B)], ms[int(.975 * B)]

def spearman(x, y):
    rk = lambda v: [sorted(v).index(a) + (v.count(a) - 1) / 2 for a in v]
    a, b = rk(x), rk(y); ma, mb = st.mean(a), st.mean(b)
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b)); den = (sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b)) ** .5
    return num / den if den else float('nan')

def auroc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]; neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg: return float('nan')
    return sum((p > q) + .5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('typ'); ap.add_argument('evals', nargs='+'); ap.add_argument('--eps', type=float, default=0.0); ap.add_argument('--out')
    a = ap.parse_args()
    votes = collections.defaultdict(list); toks = collections.defaultdict(lambda: collections.Counter())
    for f in a.evals:
        for line in open(f):
            e = json.loads(line)
            if not e['task'].startswith(a.typ + '_'): continue
            votes[(e['task'], e['arm'])].append(e['choice']); toks[(e['task'], e['arm'])].update(dict(inp=e.get('inp', 0), out=e.get('out', 0), calls=1))
    tasks = sorted({t for t, _ in votes}); arms = sorted({x for _, x in votes})
    R = collections.defaultdict(dict); excl = []; sec = dict(spearman=[], goodhart={k: [] for k in (1, 2, 4, 8)}, doubt_auroc=[], refusals=collections.Counter(), a_eq_a0=[])
    for t in tasks:
        pool = json.load(open(f'{D}/pools/{t}.json')); tr = json.load(open(f'{SEC}/truth/{t}.json')); k = len(pool)
        orc, mean = max(tr), st.mean(tr)
        if orc - mean <= a.eps: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean) if isinstance(i, int) and 0 <= i < k else 1.0
        i0 = a0(pool, t); R[t]['A0'] = reg(i0); R[t]['E'] = 1.0
        for arm in arms:
            v = votes[(t, arm)]
            if arm in ('D', 'D_N'):
                sec['refusals'][arm] += sum(1 for x in v if x == -1)
                vv = [x for x in v if x != -1]; ch = plurality(vv, f'{t}|{arm}') if vv else i0
            else:
                ch = v[0] if len(v) == 1 else plurality(v, f'{t}|{arm}')
            R[t][arm] = reg(ch)
            if arm == 'A': sec['a_eq_a0'].append(ch == i0)
        cl = [c['claim'] for c in pool]; sec['spearman'].append(spearman(cl, tr))
        sec['doubt_auroc'].append(auroc([c['doubt'] for c in pool], [x < mean for x in tr]))
        for kk in (1, 2, 4, 8):   # проклятие победителя: заявка − правда у argmax заявки по всем подвыборкам размера kk
            gs = [cl[max(S, key=lambda i: cl[i])] - tr[max(S, key=lambda i: cl[i])] for S in itertools.combinations(range(k), kk)]
            sec['goodhart'][kk].append(st.mean(gs))
    n = len(R); out = dict(type=a.typ, n_tasks=n, excluded=excl, mean_regret={}, tokens={}, tests={}, secondary={})
    for arm in ['E', 'A0'] + arms:
        xs = [R[t][arm] for t in R if arm in R[t]]
        if xs: out['mean_regret'][arm] = dict(mean=round(st.mean(xs), 3), median=round(st.median(xs), 3), n=len(xs))
    for arm in arms:
        c = collections.Counter()
        for t in R: c.update(toks[(t, arm)])
        out['tokens'][arm] = {kk: round(v / max(1, n)) for kk, v in c.items()}
    fam = [x for x in ('C_N', 'D_N') if x in arms]
    if 'B_blind' in arms and fam:
        ps = []
        for x in fam:
            d = [R[t][x] - R[t]['B_blind'] for t in R]; p, how = perm_p(d); ps.append((p, x))
            d0 = [R[t][x] - R[t]['A0'] for t in R]; p0, _ = perm_p(d0)
            out['tests'][x] = dict(vs_B_blind=dict(mean_diff=round(st.mean(d), 3), ci95=[round(v, 3) for v in boot_ci(d)], p=round(p, 4), method=how),
                                   vs_A0=dict(mean_diff=round(st.mean(d0), 3), ci95=[round(v, 3) for v in boot_ci(d0)], p=round(p0, 4)))
        ps.sort(); m = len(ps)   # Холм
        for j, (p, x) in enumerate(ps):
            ok = all(pp <= .05 / (m - jj) for jj, (pp, _) in enumerate(ps[:j + 1]))
            out['tests'][x]['holm_reject'] = ok
            out['tests'][x]['counts'] = ok and out['tests'][x]['vs_A0']['p'] <= .05
    if 'A' in arms and 'B_zayavka' in arms:
        d = [R[t]['A'] - R[t]['B_zayavka'] for t in R]; out['tests']['A_vs_B_zayavka'] = dict(mean_diff=round(st.mean(d), 3), p=round(perm_p(d)[0], 4))
    sm = lambda v: round(st.mean([x for x in v if x == x]), 3) if [x for x in v if x == x] else None
    out['secondary'] = dict(spearman_claim_truth=sm(sec['spearman']), doubt_auroc=sm(sec['doubt_auroc']),
                            goodhart_gap_by_k={kk: sm(v) for kk, v in sec['goodhart'].items()}, refusals=dict(sec['refusals']),
                            A_equals_A0=round(st.mean(sec['a_eq_a0']), 3) if sec['a_eq_a0'] else None)
    out['per_task'] = {t: {k_: round(v, 3) for k_, v in R[t].items()} for t in R}
    print(json.dumps({k_: v for k_, v in out.items() if k_ != 'per_task'}, ensure_ascii=False, indent=1))
    if a.out: json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
