# LEVEL-04, фаза 0 (решение совета, ред. 3): вызовы на цепочку для 12 генотипов, выбор K, предсказание формулы при ε на шаг.
import json, math, itertools, random
L, EPS, LAM = 200, 0.006, 0.25
GENO = [dict(s=s, v=v, r=r) for s in (10, 40, 200) for v in (0, 1) for r in (1, 2)]
def name(g): return f"s{g['s']}{'v' if g['v'] else ''}{'r2' if g['r'] == 2 else ''}"
def calls(g):
    n = math.ceil(L / g['s']); per = 3 if g['r'] == 2 else 1  # r=2: два звена + третье при расхождении
    return dict(links=n, min=n * g['r'], max=n * per + (n - 1) * per * g['v'])  # v: не больше одного пересчёта предыдущего звена
def simulate(g, eps=EPS, trials=20000, seed=0):
    """Модель: ошибка звена = хотя бы одна ошибка на его шагах; дублирование ловит расхождение; проверка ловит ошибку только на последнем шаге звена."""
    rng = random.Random(seed); ok = cost = 0
    for _ in range(trials):
        good, c = True, 0; n = math.ceil(L / g['s'])
        for k in range(n):
            m = min(g['s'], L - k * g['s'])
            def link():
                errs = [rng.random() < eps for _ in range(m)]; return any(errs), errs[-1] and not any(errs[:-1])
            if g['r'] == 1:
                bad, lastonly = link(); c += 1
            else:
                (b1, l1), (b2, l2) = link(), link(); c += 2
                if b1 or b2: (b3, l3) = link(); c += 1; bad, lastonly = (b3 and (b1 or b2)), l3  # большинство: верно, если хотя бы два верных
                else: bad, lastonly = False, False
            if g['v'] and k < n - 1 and bad and lastonly:  # следующее звено замечает ошибку последнего шага и просит пересчёт
                c += 1; bad = any(rng.random() < eps for _ in range(m))
            good = good and not bad
        ok += good; cost += c
    return ok / trials, cost / trials
if __name__ == '__main__':
    tab = []
    for g in GENO:
        cc = calls(g); acc, mean_c = simulate(g); tab.append(dict(name=name(g), **g, **cc, pred_acc=round(acc, 3), pred_calls=round(mean_c, 1)))
    C = max(t['max'] for t in tab)
    for t in tab: t['fitness_pred'] = round(t['pred_acc'] - LAM * t['pred_calls'] / C, 3)
    for K in (4, 3, 2):
        worst = sum(t['max'] for t in tab) * K + 2 * K * 1  # плюс повтор двух генотипов s=200 (по 1 вызову на цепочку)
        if worst <= 1000: break
    json.dump(dict(L=L, eps=EPS, lam=LAM, C=C, K=K, worst_phase2=worst, table=tab), open('phase0.json', 'w'), ensure_ascii=False, indent=1)
    for t in sorted(tab, key=lambda t: -t['fitness_pred']): print(f"{t['name']:8s} звеньев {t['links']:3d} вызовы {t['min']:3d}…{t['max']:3d}  ожид. точность {t['pred_acc']:.3f} ожид. вызовы {t['pred_calls']:6.1f}  приспособленность {t['fitness_pred']:+.3f}")
    print('C =', C, '; K =', K, '; худший расход фазы 2 =', worst)
