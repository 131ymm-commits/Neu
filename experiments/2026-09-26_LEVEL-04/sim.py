# LEVEL-04, фаза 3: отбор и дрейф-контроль in silico по таблице ландшафта (решение совета, ред. 3; поправка 1).
# landscape: {генотип: [{'ok': 0/1, 'calls': int}, ...] по цепочкам и повторам}; цепочки — ключ 'chain'.
import json, random, math, statistics as st
from phase0 import GENO, name
GENES = dict(s=(10, 40, 200), v=(0, 1), r=(1, 2))
LAMS = [0.25] * 5 + [0.0] * 5  # поколения 0–4 с ценой, 5–9 без
def mutate(g, rng):
    k = rng.choice(list(GENES)); opts = [x for x in GENES[k] if x != g[k]]; h = dict(g); h[k] = rng.choice(opts); return h
def run(land, C, rng, select=True):
    names = list(land); chains = sorted({c['chain'] for v in land.values() for c in v})
    boot = [rng.choice(chains) for _ in chains]  # бутстреп по цепочкам
    p, cost = {}, {}
    for g, cells in land.items():
        cs = [c for b in boot for c in cells if c['chain'] == b]
        k, n = sum(c['ok'] for c in cs), len(cs)
        p[g] = rng.betavariate(1 + k, 1 + n - k) if n else None; cost[g] = st.mean(c['calls'] for c in cells)
    pop = [rng.choice(GENO) for _ in range(8)]; hist = []
    for gen, lam in enumerate(LAMS):
        fit = []
        for g in pop:
            nm = name(g); acc = sum(rng.random() < p[nm] for _ in range(2)) / 2 if p[nm] is not None else 0.0
            fit.append((acc - lam * cost[nm] / C, -cost[nm] if lam > 0 else 0, rng.random(), g))
        hist.append(dict(gen=gen, mean_p=st.mean(p[name(g)] or 0 for g in pop), short=sum(g['s'] <= 40 for g in pop), r2=sum(g['r'] == 2 for g in pop)))
        order = sorted(fit, key=lambda t: t[:3], reverse=True) if select else [fit[i] for i in rng.sample(range(8), 8)]
        top = [t[3] for t in order[:4]]; pop = top + [mutate(g, rng) for g in top]
    return hist
def shares(land, C, seeds=50, B=100, seed=0):
    rng = random.Random(seed); res = {'select': [], 'drift': []}
    for b in range(B):
        for arm in res:
            h = [run(land, C, random.Random(rng.random()), select=(arm == 'select')) for _ in range(seeds)]
            res[arm].append(dict(H1=st.mean(x[4]['mean_p'] > x[0]['mean_p'] for x in h), H2=st.mean(x[4]['short'] >= 6 for x in h), H3=st.mean(x[9]['r2'] - x[4]['r2'] >= 2 for x in h)))
    out = {}
    for H, thr, diff in (('H1', 0.8, 0.3), ('H2', None, 0.3), ('H3', None, 0.2)):
        ok = [((thr is None or s[H] >= thr) and s[H] - d[H] >= diff) for s, d in zip(res['select'], res['drift'])]
        out[H] = dict(select=st.mean(s[H] for s in res['select']), drift=st.mean(d[H] for d in res['drift']), share_landscapes_ok=st.mean(ok), signal=st.mean(ok) >= 0.8)
    return out
if __name__ == '__main__':
    import sys
    ph0 = json.load(open('phase0.json')); rng = random.Random(1)
    if sys.argv[1] == 'synthetic':  # проверка кода на синтетическом ландшафте из предсказания фазы 0 (K = 3, по 1 испытанию)
        land = {t['name']: [dict(chain=k, ok=int(rng.random() < t['pred_acc']), calls=t['pred_calls']) for k in range(3)] for t in ph0['table']}
        print(json.dumps(shares(land, ph0['C'], seeds=30, B=40), ensure_ascii=False, indent=1))
