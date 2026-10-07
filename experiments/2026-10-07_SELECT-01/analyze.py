# SELECT-01: анализ. Нормированный регрет r = (оракул − выбранный) / (оракул − среднее пула); E (случайный выбор) ≡ 1 в ожидании.
#   python3 analyze.py <WH|SC> <evals/stage.jsonl ...> [--eps X] [--out json]
# Правила (совет 26, DESIGN.md): A0 = argmax заявки; голосование — простое большинство (plurality); ничьи — по сиду (sha256 задачи и руки),
# не по индексу; D/D_N: отказ (choice = −1) → у D засчитывается выбор A0; у D_N большинство среди неотказавшихся, все отказались → A0.
# Голос недействителен (сбой головы после одного автоматического перезапуска, номер вне 0..k−1) → исключается из подсчёта;
# все голоса руки недействительны → r = 1 (у D/D_N: все недействительны или отказ → A0). Дубли (задача, рука, i) — берётся последняя запись.
# Одиночные руки A, C, D — вызов i = 0 рук B_zayavka, C_N, D_N. Ничьи — по sha256(задача|кандидат), без руки (линза 2, Н4).
# ε (порог разброса пула) зашит по типу: EPS. Токены одиночных рук — вызова i = 0.
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

EPS = dict(WH=150.0, SC=15.0)
FAMILY = ('C_N', 'D_N'); SINGLE = (('A', 'B_zayavka'), ('C', 'C_N'), ('D', 'D_N'))

def tost(d, margin=0.1):
    # эквивалентность: оба односторонних перестановочных теста против ±margin
    pu, _ = perm_p([x - margin for x in d]); pl, _ = perm_p([-x - margin for x in d]); return pu, pl

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('typ'); ap.add_argument('evals', nargs='+'); ap.add_argument('--out')
    a = ap.parse_args(); eps = EPS[a.typ]
    rec = {}
    for f in a.evals:
        for line in open(f):
            e = json.loads(line)
            if e['task'].startswith(a.typ + '_'): rec[(e['task'], e['arm'], int(e['i']))] = e   # последняя запись
    for (t, x, i), e in list(rec.items()):
        for one, many in SINGLE:
            if x == many and i == 0: rec[(t, one, 0)] = e
    votes = collections.defaultdict(list); toks = collections.defaultdict(collections.Counter)
    for (t, x, i), e in sorted(rec.items()):
        votes[(t, x)].append(e.get('choice')); toks[(t, x)].update(dict(inp=e.get('inp', 0), out=e.get('out', 0), calls=1))
    tasks = sorted({t for t, _ in votes}); arms = sorted({x for _, x in votes})
    R = collections.defaultdict(dict); excl = []; invalid = collections.Counter()
    sec = dict(spearman=[], goodhart={k: [] for k in (1, 2, 4, 8)}, doubt_auroc=[], refusals=collections.Counter(), a_eq_a0=[])
    for t in tasks:
        pool = json.load(open(f'{D}/pools/{t}.json')); tr = json.load(open(f'{SEC}/truth/{t}.json')); k = len(pool)
        orc, mean = max(tr), st.mean(tr)
        if orc - mean <= eps: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean) if i is not None else 1.0
        i0 = a0(pool, t); R[t]['A0'] = reg(i0); R[t]['E'] = 1.0
        for arm in arms:
            v = votes[(t, arm)]
            ok = [x for x in v if isinstance(x, int) and 0 <= x < k]; invalid[arm] += sum(1 for x in v if not (isinstance(x, int) and (0 <= x < k or x == -1)))
            if arm in ('D', 'D_N'):
                sec['refusals'][arm] += sum(1 for x in v if x == -1)
                ch = plurality(ok, t) if ok else i0
            else:
                ch = plurality(ok, t) if ok else None
            R[t][arm] = reg(ch)
            if arm == 'A': sec['a_eq_a0'].append(ch == i0)
        cl = [c['claim'] for c in pool]; sec['spearman'].append(spearman(cl, tr))
        sec['doubt_auroc'].append(auroc([c['doubt'] for c in pool], [x < mean for x in tr]))
        for kk in (1, 2, 4, 8):   # заявка − правда у argmax заявки по всем подвыборкам размера kk (ничьи по сиду)
            gs = []
            for S in itertools.combinations(range(k), kk):
                m = max(cl[i] for i in S); j = tiebreak([i for i in S if cl[i] == m], f'{t}|A0'); gs.append(cl[j] - tr[j])
            sec['goodhart'][kk].append(st.mean(gs))
    n = len(R); out = dict(type=a.typ, eps=eps, n_tasks=n, excluded=excl, invalid_votes=dict(invalid), mean_regret={}, tokens={}, budget={}, tests={}, secondary={})
    for arm in ['E', 'A0'] + arms:
        xs = [R[t][arm] for t in R if arm in R[t]]
        if xs: out['mean_regret'][arm] = dict(mean=round(st.mean(xs), 3), median=round(st.median(xs), 3), n=len(xs))
    for arm in arms:
        c = collections.Counter()
        for t in R: c.update(toks[(t, arm)])
        out['tokens'][arm] = {kk: round(v / max(1, n)) for kk, v in c.items()}
    fam = [x for x in FAMILY if x in arms]
    if 'B_blind' in arms and fam:
        tb = out['tokens']['B_blind']; tot = lambda q: q.get('inp', 0) + q.get('out', 0)
        out['budget'] = {x: dict(total_ok=tot(tb) >= tot(out['tokens'][x]), out_ok=tb.get('out', 0) >= out['tokens'][x].get('out', 0)) for x in fam}
        out['budget']['equal'] = all(v['total_ok'] and v['out_ok'] for v in out['budget'].values())
        ps = []
        for x in fam:
            d = [R[t][x] - R[t]['B_blind'] for t in R]; p, how = perm_p(d); ps.append((p, x))
            d0 = [R[t][x] - R[t]['A0'] for t in R]; p0, _ = perm_p(d0)
            out['tests'][x] = dict(vs_B_blind=dict(mean_diff=round(st.mean(d), 3), ci95=[round(v, 3) for v in boot_ci(d)], p=p, method=how),
                                   vs_A0=dict(mean_diff=round(st.mean(d0), 3), ci95=[round(v, 3) for v in boot_ci(d0)], p=p0))
        ps.sort(); m = len(ps)   # Холм; p не округляются
        for j, (p, x) in enumerate(ps):
            ok = all(pp <= .05 / (m - jj) for jj, (pp, _) in enumerate(ps[:j + 1]))
            out['tests'][x]['holm_reject'] = ok
            out['tests'][x]['counts'] = bool(ok and out['tests'][x]['vs_A0']['p'] <= .05 and out['budget']['equal'])
    if 'A' in arms and 'B_zayavka' in arms:
        d = [R[t]['A'] - R[t]['B_zayavka'] for t in R]; out['tests']['A_vs_B_zayavka'] = dict(mean_diff=round(st.mean(d), 3), p=perm_p(d)[0])
    if 'A' in arms:
        d = [R[t]['A'] - R[t]['A0'] for t in R]; pu, pl = tost(d)
        out['tests']['A_vs_A0_TOST'] = dict(mean_diff=round(st.mean(d), 3), margin=0.1, p_upper=pu, p_lower=pl,
                                            agree_share=round(st.mean(sec['a_eq_a0']), 3), equivalent=bool(pu <= .05 and pl <= .05 and st.mean(sec['a_eq_a0']) >= 0.7))
    sm = lambda v: round(st.mean([x for x in v if x == x]), 3) if [x for x in v if x == x] else None
    out['secondary'] = dict(spearman_claim_truth=sm(sec['spearman']), doubt_auroc=sm(sec['doubt_auroc']),
                            goodhart_gap_by_k={kk: sm(v) for kk, v in sec['goodhart'].items()}, refusals=dict(sec['refusals']))
    out['per_task'] = {t: {k_: round(v, 3) for k_, v in R[t].items()} for t in R}
    print(json.dumps({k_: v for k_, v in out.items() if k_ != 'per_task'}, ensure_ascii=False, indent=1))
    if a.out: json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
