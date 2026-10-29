# Пост-хок на пилоте (не в зачёт; для оценки линзы 3).
import sys, random, math, collections
sys.path.insert(0, '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses_score02')
import pilot_lib as PL
def coarsen(single, agree):
    """Огрубить уверенности single до долей уровней agree: сортировка по уверенности, корзины по кумулятивным долям;
    равные значения исходной шкалы не разрываются (идут в корзину, где лежит их середина)."""
    levels = collections.Counter(round(c, 4) for c, _ in agree)
    keys = sorted(levels); tot = sum(levels.values())
    cum, edges = 0, []
    for k in keys:
        cum += levels[k]; edges.append(cum / tot)
    vals = sorted(c for c, _ in single); n = len(vals)
    # ранг середины группы равных значений
    pos = {}
    i = 0
    while i < n:
        j = i
        while j < n and vals[j] == vals[i]: j += 1
        pos[vals[i]] = (i + j) / 2 / n
        i = j
    out = []
    for c, o in single:
        q = pos[c]; b = next(k for k, e in enumerate(edges) if q <= e + 1e-12)
        out.append((b, o))
    return out
for m in ('opus', 'haiku'):
    calls = PL.load_calls(f'{PL.SP}/pilot_{m}_out.jsonl')
    J = {t: PL.judg(calls[t], PL.lab[t]) for t in sorted(calls)}
    S = [j for t in J for j in J[t]['single']]; A = [j for t in J for j in J[t]['agree']]
    Sc = coarsen(S, A)
    unan = sum(1 for c, _ in A if c == 1.0) / len(A)
    print(f'{m}: AUC single {PL.auc_pairs(S):.3f}; single, огрублённая до уровней согласия {PL.auc_pairs(Sc):.3f}; agree {PL.auc_pairs(A):.3f}; доля единогласных {unan:.3f}')
    # разложение X2 и X3 по s — доле вызовов (с p ≠ 0,5) на верной стороне, по кандидатам с суждением agree
    g, h, cnt = 0.0, 0.0, 0
    for t in calls:
        ok = [p for p in calls[t].values() if p is not None]
        for i in range(8):
            y = i in PL.lab[t]
            up = sum(p[i] > 0.5 for p in ok); dn = sum(p[i] < 0.5 for p in ok)
            if up == dn: continue
            s = (up if y else dn) / (up + dn)
            cnt += 1
            g += (1 - s) if s > 0.5 else 0.0
            h += s if s < 0.5 else 0.0
    conf_single = sum(c for c, _ in S) / len(S)
    print(f'   E[(1−s)·1(s>½)] = {g/cnt:.4f}; E[s·1(s<½)] = {h/cnt:.4f}; 1 − уверенность single = {1-conf_single:.4f}; '
          f'X2 ≈ (1 − conf) − 2·E[(1−s)1(s>½)] = {1-conf_single-2*g/cnt:+.4f}; X3 ≈ E[(1−s)1(s>½)] − E[s·1(s<½)] = {g/cnt-h/cnt:+.4f}')
    print(f'   X2 опровергается, только если E[(1−s)1(s>½)] > {(1-conf_single)/2:.3f} (в пилоте {g/cnt:.3f}, в {((1-conf_single)/2)/(g/cnt):.1f} раза меньше)')
