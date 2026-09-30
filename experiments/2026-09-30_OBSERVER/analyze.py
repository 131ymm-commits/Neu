# Наблюдатель: подтверждающий анализ (91 пара, новые 17–107) и «чистый» пост-хок (DEVIATIONS №3).
import json, os, sys, random, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from observer import load, label, feats, seq_base, hans, ll, CLS
SYS = ('This session', 'Another Claude session', 'Your response above was stopped', '[Your previous response', 'Continue from where you left off', '[Request interrupted')
can, P = load(); Y = [label(p['human']) for p in P]; X = [feats(p, Y[i - 1] if i else None) for i, p in enumerate(P)]
out = {}
for f in sorted(os.listdir(os.path.join(HERE, 'run'))):
    if f.startswith('out_') and 'debug' not in f and f not in ('out_0_15.json', 'out_15_30.json'): out.update(json.load(open(os.path.join(HERE, 'run', f)))['out'])
def pv(v): s = sum(max(0, v[k]) for k in ('p_accept', 'p_reject', 'p_other')) or 1; return [max(0, v[k]) / s for k in ('p_accept', 'p_reject', 'p_other')]
def brier(p, y): return sum((p[j] - (CLS[j] == y)) ** 2 for j in range(3))
def perm(d, R=20000):
    rng = random.Random(0); m = sum(d) / len(d); c = sum(abs(sum(x if rng.random() < .5 else -x for x in d) / len(d)) >= abs(m) for _ in range(R)); return (c + 1) / (R + 1)
def boot(d, R=5000):
    rng = random.Random(1); b = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(R)); return [b[int(.025 * R)], b[int(.975 * R)]]
def run(I, name):
    L = {k: [] for k in ('solo', 'ex', 'seq', 'hans', 'hans4')}; B = {k: [] for k in ('solo', 'ex', 'seq')}; acc = {'solo': 0, 'ex': 0, 'seq': 0}; leaks = 0
    for i in I:
        ps = pv(out[f'{i}|solo']); pe = pv(out[f'{i}|ex']); q = seq_base(Y, i)
        leaks += can in json.dumps(out[f'{i}|solo'], ensure_ascii=False) + json.dumps(out[f'{i}|ex'], ensure_ascii=False)
        for k, p in (('solo', ps), ('ex', pe), ('seq', q), ('hans', hans(X, Y, i)), ('hans4', hans(X, Y, i, use_prev=False))): L[k].append(ll(p, Y[i]))
        for k, p in (('solo', ps), ('ex', pe), ('seq', q)): B[k].append(brier(p, Y[i])); acc[k] += CLS[max(range(3), key=lambda j: p[j])] == Y[i]
    n = len(I); m = {k: sum(v) / n for k, v in L.items()}
    r = dict(name=name, n=n, labels={c: sum(Y[i] == c for i in I) for c in CLS}, logloss=m, brier={k: sum(v) / n for k, v in B.items()}, top1={k: v / n for k, v in acc.items()}, leaks=leaks)
    for a, b in (('ex', 'solo'), ('ex', 'seq'), ('ex', 'hans'), ('solo', 'hans'), ('solo', 'seq')):
        d = [x - y for x, y in zip(L[a], L[b])]; r[f'{a}-{b}'] = dict(mean=sum(d) / n, ci95=boot(d), p_perm=perm(d))
    # REJECT: P(REJECT) у ex выше последовательной базы?
    rj = [i for i in I if Y[i] == 'REJECT']; r['reject'] = [dict(i=i, ex=pv(out[f'{i}|ex'])[1], solo=pv(out[f'{i}|solo'])[1], seq=seq_base(Y, i)[1]) for i in rj]
    return r
C = list(range(17, 108)); clean = [i for i in C if not P[i]['human'].lstrip().startswith(SYS) and i != 80]
res = dict(primary=run(C, 'подтверждение, 91 пара (как зарегистрировано)'), clean=run(clean, 'чистый пост-хок (DEVIATIONS №3)'), excluded=[i for i in C if i not in clean])
json.dump(res, open(os.path.join(HERE, 'run', 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
for k in ('primary', 'clean'):
    r = res[k]; print(r['name'], 'n', r['n'], r['labels'], 'утечек', r['leaks'])
    print('  логпотеря', {a: round(v, 3) for a, v in r['logloss'].items()}); print('  Брайер', {a: round(v, 3) for a, v in r['brier'].items()}, 'top1', {a: round(v, 2) for a, v in r['top1'].items()})
    for c in ('ex-solo', 'ex-seq', 'ex-hans', 'solo-hans', 'solo-seq'): print('  ', c, round(r[c]['mean'], 3), [round(x, 3) for x in r[c]['ci95']], 'p', round(r[c]['p_perm'], 4))
    print('  REJECT', [(x['i'], round(x['ex'], 2), round(x['solo'], 2), round(x['seq'], 2)) for x in r['reject']])
