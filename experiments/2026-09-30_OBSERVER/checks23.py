# Проверки, назначенные советом 23 (п. 4): утечка эталонов в цель; AUROC P(REJECT) у ex против частоты, перестановочный тест, выбрасывание по одному.
import json, os, sys, itertools, random
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from observer import load, label, seq_base, K_EX
from analyze import out, pv, clean, C, Y, P
res = {}
# 1. утечка: текст ответа автора на цель (или его первые 40 знаков) среди ответов в эталонах
leak = []
for i in C:
    h = P[i]['human'].strip()
    for j in range(max(0, i - K_EX), i):
        e = P[j]['human'].strip()
        if e == h or (len(h) > 20 and (h[:40] in e or e[:40] in h)): leak.append(dict(i=i, j=j, y=Y[i]))
res['leaks'] = leak
def auroc(pos, neg): return sum((p > n) + .5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
def block(I, name):
    rj = [i for i in I if Y[i] == 'REJECT']; nr = [i for i in I if Y[i] != 'REJECT']
    r = {}
    for arm in ('ex', 'solo'):
        s = {i: pv(out[f'{i}|{arm}'])[1] for i in I}
        a = auroc([s[i] for i in rj], [s[i] for i in nr])
        # перестановочный: доля случайных наборов из len(rj) пунктов с AUROC ≥ наблюдаемого (оценка Монте-Карло, 20000)
        allS = [s[i] for i in I]; k = len(rj); rng = random.Random(0); R = 20000
        cnt = tot = 0
        for _ in range(R):
            c = rng.sample(range(len(I)), k)
            cs = set(c); cnt += auroc([allS[x] for x in c], [allS[x] for x in range(len(I)) if x not in cs]) >= a - 1e-12; tot += 1
        r[arm] = dict(auroc=a, p_mc=(cnt + 1) / (tot + 1), n_mc=tot, mean_p_rej_on_rej=sum(s[i] for i in rj) / k, mean_p_rej_on_other=sum(s[i] for i in nr) / len(nr),
                      loo=[auroc([s[x] for x in rj if x != i], [s[x] for x in nr]) for i in rj])
    sq = {i: seq_base(Y, i)[1] for i in I}; r['seq_auroc'] = auroc([sq[i] for i in rj], [sq[i] for i in nr])
    return dict(name=name, n_rej=len(rj), n_other=len(nr), **r)
res['clean'] = block(clean, 'чистые 77')
json.dump(res, open(os.path.join(HERE, 'run', 'checks23.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:2500])
