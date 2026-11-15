#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01: проверки кода (ожидания записаны до запуска). python3 test_ocint.py"""
import json
import os
import sys
import tempfile

import numpy as np
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocint as O  # noqa: E402

S, A = O.S, O.A
bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name, flush=True)
    if not ok:
        bad.append(name)


# 1. Мир: размеры, режим, состав толпы
par = O.world_params(0, O.META_PILOT)
g = np.random.default_rng(1)
st, idi, ood = O.draw(par, g)
check('выборка мира: 9 голов, 1000 ID и 1200 OOD, части кросс-подгонки только у ID',
      st['corr'].shape == (9, 2200) and len(idi) == 1000 and len(ood) == 1200 and (st['fold_of'][ood] == -1).all()
      and sorted(set(st['fold_of'][idi])) == [0, 1, 2, 3, 4])
big, _, _ = O.draw(par, np.random.default_rng(2), n_id=20000, n_ood=10)
acc = big['corr'][:, :20000].mean(1)
check('точность голов на ID — Φ(mu) (большая выборка, допуск 0,015)', np.abs(acc - norm.cdf(par['mu_id'])).max() < 0.015)
check('у неверного ответа нет совпадения с правдой; согласие головы с собой не считается',
      all((st['ag'][h, h] == False).all() for h in range(9)))      # noqa: E712
pars = [O.world_params(k, O.META_TEST) for k in range(10)]
best = [float(norm.cdf(p['mu_id'].max())) for p in pars]
check('тяжёлый режим: лучшая голова на ID верна в 0,40–0,56 задач во всех десяти мирах теста', min(best) >= 0.40 and max(best) <= 0.565)
check('миры теста и пилота разные', not np.allclose(O.world_params(0, O.META_TEST)['mu_id'], O.world_params(0, O.META_PILOT)['mu_id']))

# 2. Пять статистик — те же формулы, что зарегистрированный analyze_ocshift.core
pt = S.core(st, idi, ood)
s5 = O.stats5(st, idi, ood)
ref = np.array([pt['wc CONF'], pt['ioi CONF'] - pt['ioi LR-AGREE'], pt['ioi ONE-BEST'] - pt['ioi CONF'],
                pt['ioi POST-IN CONF'] - pt['ioi CONF'], pt['ioi POST-IN CONF'] - pt['ioi ONE-BEST']])
check('stats5 совпадает с analyze_ocshift.core на полной выборке (1e-12)', np.abs(s5 - ref).max() < 1e-12)
fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
pt2, s52 = S.core(st, fit, cols), O.stats5(st, fit, cols)
ref2 = np.array([pt2['wc CONF'], pt2['ioi CONF'] - pt2['ioi LR-AGREE'], pt2['ioi ONE-BEST'] - pt2['ioi CONF'],
                 pt2['ioi POST-IN CONF'] - pt2['ioi CONF'], pt2['ioi POST-IN CONF'] - pt2['ioi ONE-BEST']])
check('stats5 совпадает с core и на выборке с возвращением (копии задач)', np.abs(s52 - ref2).max() < 1e-12)
h_ = O.half(g, idi)
check('половинная выборка: n // 2 разных задач, без копий', len(h_) == 500 and len(set(h_.tolist())) == 500 and set(h_.tolist()) <= set(idi.tolist()))
check('в мире отбор CONF завышает заявку на ID (wc < 0) — модель воспроизводит явление', s5[0] < 0)

# 3. Способы построить интервал
gz = np.random.default_rng(3)
rb = gz.normal(-0.06, 0.01, 4000)          # повторы с возвращением смещены на −0,01 от точки −0,05
rh = gz.normal(-0.06, 0.012, 4000)
iv = O.methods(-0.05, rb, rh, 0.05)
z = float(norm.ppf(0.95))
pq = np.quantile(rb, (0.05, 0.95))
check('M1 — квантили повторов; M3 — обратный: 2·точка − квантили', np.allclose(iv[0], pq) and np.allclose(iv[2], [-0.1 - pq[1], -0.1 - pq[0]]))
check('M4 и M6 — точка ± z·ст. отклонение своих повторов',
      np.allclose(iv[3], [-0.05 - z * rb.std(ddof=1), -0.05 + z * rb.std(ddof=1)]) and np.allclose(iv[5], [-0.05 - z * rh.std(ddof=1), -0.05 + z * rh.std(ddof=1)]))
check('M5 и M7 — с центром в точке и не уже M4 и M6 больше чем на 15 % (огибающая)',
      all(abs(iv[k].mean() + 0.05) < 1e-12 for k in (3, 4, 5, 6)) and iv[4, 1] - iv[4, 0] > 0.85 * (iv[3, 1] - iv[3, 0])
      and iv[6, 1] - iv[6, 0] > 0.85 * (iv[5, 1] - iv[5, 0]))
check('при сдвиге в одну ст. ошибку процентильный интервал (90 %) уезжает от точки: точка у его края',
      abs(iv[0].mean() + 0.06) < 0.002 and iv[0][1] < -0.05 + 0.007)

# 4. Границы Клоппера — Пирсона и правила
check('Клоппер — Пирсон: x = 0 → нижняя 0; x = n → верхняя 1; 90 из 100 — нижняя 0,0025 около 0,79',
      O.cp(0, 50, 0.0025, 'lo') == 0.0 and O.cp(50, 50, 0.0025, 'hi') == 1.0 and 0.77 < O.cp(90, 100, 0.0025, 'lo') < 0.81)


def fake(cov_one, cov_mean, width=None):
    st_ = O.STATS
    c = {'one_env': {m: {s: dict(covered=int(round(cov_one[mi] * 1000)), n=1000, coverage=cov_one[mi], width_in_sd=(width or [3.3] * 7)[mi]) for s in st_}
                     for mi, m in enumerate(O.METHODS)},
         'mean_of_worlds': {m: {s: dict(covered=int(round(cov_mean[mi] * 100)), n=100, coverage=cov_mean[mi], width_in_sd=3.3) for s in st_}
                            for mi, m in enumerate(O.METHODS)}}
    return {'coverage': {'0.9': c}}


r = O.rules_worlds(fake([0.6, 0.5, 0.7, 0.9, 0.92, 0.90, 0.93], [0.10, 0.05, 0.3, 0.9, 0.92, 0.9, 0.93], [3, 3, 3, 3.29, 3.5, 3.4, 3.6]))
check('Б1: покрытие 0,10 из 100 → «подтверждено»; Б2: 0,93 из 1000 → «подтверждено»; выбор — самый узкий годный (M4)',
      r['B1']['verdict'] == 'подтверждено' and r['B2']['verdict'] == 'подтверждено' and r['choice']['chosen'] == O.METHODS[3])
r = O.rules_worlds(fake([0.6, 0.5, 0.7, 0.85, 0.86, 0.78, 0.80], [0.95, 0.9, 0.9, 0.8, 0.8, 0.7, 0.7]))
# ожидание исправлено после первого запуска: при 90 из 100 нижняя граница 0,79 (не выше 0,8), при 820 из 1000 верхняя 0,86 (не ниже 0,85) — моя арифметика в уме
check('Б1: покрытие 0,95 из 100 → «опровергнуто»; Б2: 0,80 из 1000 → «опровергнуто»; годных нет — выбор пуст',
      r['B1']['verdict'] == 'опровергнуто' and r['B2']['verdict'] == 'опровергнуто' and r['choice']['chosen'] is None)
r = O.rules_worlds(fake([0.6, 0.5, 0.7, 0.9, 0.9, 0.9, 0.9], [0.6, 0.5, 0.7, 0.9, 0.9, 0.9, 0.9], [3, 3, 3, 3.3, 3.3, 3.3, 3.3]))
check('Б1: 0,60 → «не решено»; при равной ширине годных выбор — M7', r['B1']['verdict'] == 'не решено' and r['choice']['chosen'] == O.METHODS[6])

lf = O.limit_fit({'0.25': -0.05 - 0.02 * 4, '0.5': -0.05 - 0.02 * 2, '0.75': -0.05 - 0.02 / 0.75}, -0.07)
check('предел по закону a + b·(n/m): для точной кривой a = −0,05, b = −0,02, доля в пределе 0,05 / 0,07',
      abs(lf['limit'] + 0.05) < 1e-12 and abs(lf['slope'] + 0.02) < 1e-12 and abs(lf['share_left'] - 0.05 / 0.07) < 1e-12)

# совет 62: правда не попадает в интервалы; ветвь по границам Клоппера — Пирсона; «не различимы»
import inspect  # noqa: E402
import re  # noqa: E402
src = inspect.getsource(O.worlds)
calls = re.findall(r'methods\(([^)]*)\)', src)
check('methods() не получает правду: в подписи нет θ, в вызовах из worlds нет th и THM',
      list(inspect.signature(O.methods).parameters) == ['point', 'rb', 'rh', 'alpha'] and len(calls) == 2
      and all('th' not in c.replace('alpha', '') and 'THM' not in c for c in calls))
fk = fake([0.6, 0.5, 0.7, 0.92, 0.93, 0.95, 0.96], [0.1, 0.05, 0.3, 0.88, 0.9, 0.95, 0.97], [3, 3, 3, 3.3, 3.4, 3.5, 3.6])
fk['coverage']['0.9']['mean_of_worlds'] = {m: {s_: dict(covered=int(round(v * 60)), n=60, coverage=v, width_in_sd=3.3) for s_ in O.STATS}
                                            for m, v in zip(O.METHODS, [0.1, 0.05, 0.3, 0.88, 0.9, 0.95, 0.97])}
fk['coverage']['0.9']['one_env'] = {m: {s_: dict(covered=int(round(v * 600)), n=600, coverage=v, width_in_sd=wd) for s_ in O.STATS}
                                     for m, v, wd in zip(O.METHODS, [0.6, 0.5, 0.7, 0.88, 0.93, 0.95, 0.96], [3, 3, 3, 3.3, 3.4, 3.5, 3.6])}
# покрытие M4 в одной среде 0,88: основное правило его пропускает (0,88 ≥ 0,88), а нижняя граница КП 0,838 — нет (счёт ocint.cp;
# первая версия случая с 0,92 была посчитана в уме и неверна: там граница 0,884)
gw = np.random.default_rng(9)
base = gw.normal(3.3, 0.2, 600)
fk['width_avg_0.9'] = np.column_stack([base] * 3 + [base, base + 0.1 + gw.normal(0, 0.01, 600), base + 0.2, base + 0.3]).tolist()
rc = O.rules_worlds(fk)['choice']
check('выбор: основное правило — M4 (самый узкий годный); ветвь КП: у M4 нижняя граница в одной среде не выше 0,85 → выбирает M5; «выбор неустойчив»; M4 и M5 различимы (разность 0,1 при ст. ош. 0,0004)',
      rc['chosen'] == O.METHODS[3] and rc['chosen_cp'] == O.METHODS[4] and rc['stability'] == 'выбор неустойчив к ошибке Монте-Карло'
      and rc['nearest']['other'] == O.METHODS[4] and not rc['nearest']['indistinguishable'])
fk['width_avg_0.9'] = np.column_stack([base] * 4 + [base + gw.normal(0, 0.5, 600)] + [base] * 2).tolist()
check('«не различимы»: ширины M4 и M5 по опытам почти равны (разность меньше 2 ст. ош.)', O.rules_worlds(fk)['choice']['nearest']['indistinguishable'])

# 5. Сквозной прогон: миры (крошечные числа) и настоящие среды на заглушке
with tempfile.TemporaryDirectory() as tmp:
    w = O.worlds(os.path.join(tmp, 'w.json'), meta=O.META_PILOT + 1, n_worlds=2, n_exp=3, n_truth=6, B=8, workers=1)
    check('миры: файл хода счёта по мирам записан', json.load(open(os.path.join(tmp, 'w.json.progress.json')))['done'][-1]['world'] == 1)
    qw = O.quarters_worlds(os.path.join(tmp, 'q.json'), meta=O.META_PILOT + 2, worlds_idx=(0,), n_samples=2, B=4, n_truth=4, workers=1)
    check('четверти в мирах: сквозной прогон даёт отношения для всех статистик REAL', set(qw['by_world']['0']) == set(O.REAL)
          and all(np.isfinite(v['ratio_quarter_half']) for v in qw['by_world']['0'].values()))
    check('миры: сквозной прогон даёт покрытия всех способов и статистик при двух номиналах и правила',
          set(w['coverage']) == {'0.9', '0.98'} and all(len(w['coverage']['0.9'][k]) == 7 for k in ('one_env', 'mean_of_worlds'))
          and set(w['rules']) == {'B1', 'B2', 'choice'} and w['coverage']['0.9']['one_env'][O.METHODS[0]][O.STATS[0]]['n'] == 6)
    sys.path.insert(0, os.path.join(O.EXP, '2026-11-15_OCSHIFT-01'))
    import dry_ocshift as D  # noqa: E402
    d = D.build('one', 7_640_001)
    d['envs'] = [e for e in d['envs'] if e['name'] in ('check_ocrep_pilot', 'X4_p0', 'X4_p1')]
    for h in d['heads']:
        h['cols'] = {k: v for k, v in h['cols'].items() if k in ('check_ocrep_pilot', 'X4_p0', 'X4_p1')}
    os.makedirs(os.path.join(tmp, 'stub'))
    json.dump(d, open(os.path.join(tmp, 'stub', 'answers.json'), 'w'))
    rr = O.real(os.path.join(tmp, 'r.json'), [f"new:{os.path.join(tmp, 'stub')}"], B_boot=8, B_half=8, B_curve=4, B_q=4, workers=1)
    an = json.load(open(os.path.join(O.EXP, '2026-11-15_OCSHIFT-01', '..', '..', 'gha_out', 'ocshift_chain', 'dry', 'one_analysis.json'), encoding='utf-8'))
    same = all(abs(rr['envs'][n]['stats']['R2 wc CONF']['point'] - an['R2']['by_env'][n]) < 1e-12 for n in ('X4_p0', 'X4_p1'))
    check('настоящие среды: сквозной прогон на заглушке; точка R2 по среде совпадает с зарегистрированным анализом OCSHIFT-01 (те же зёрна)',
          same and set(rr['envs']) == {'X4_p0', 'X4_p1'} and 'verdict' in rr['rule_A'] and rr['robustness'][0]['group'] == 'среднее по средам OCSHIFT-01'
          and set(rr['envs']['X4_p0']['stats']['R2 wc CONF']['running']) == {'boot', 'half'})
print('провалов:', bad)
sys.exit(1 if bad else 0)
