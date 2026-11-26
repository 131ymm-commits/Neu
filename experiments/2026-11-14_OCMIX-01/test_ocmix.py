#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: проверки оценщиков-смесей на игрушечных данных (ожидания записаны до запуска)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_ocmix as M  # noqa: E402

Z = M.Z
bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name)
    if not ok:
        bad.append(name)


# 1. VETO: неподдержанный ответ сдвигается на −1000; ответ без числа не поддержан никогда
ans = [[5, 7, None], [5, 8, None], [6, 9, 3]]
ag = M.agree_matrix(ans)
logp = np.array([[-1.0, -0.5, -50.0], [-2.0, -0.4, -50.0], [-3.0, -0.3, -0.2]])
V = M.veto_scores(ag, logp, [0, 1, 2])
check('VETO: поддержанный ответ сохраняет logp', V[0][0] == -1.0 and V[1][0] == -2.0)
check('VETO: неподдержанный — logp − 1000', V[0][1] == -1000.5 and V[2][2] == -1000.2)
check('VETO: ответ без числа не поддержан', V[0][2] == -1050.0 and V[1][2] == -1050.0)

# 2. VETO выбирает поддержанный ответ, CONF — уверенный одиночный
g = np.random.default_rng(5)
n = 3000
truth = np.zeros(n, int)
heads, lps = [], []
for k in range(5):
    ok = g.random(n) < 0.6
    a = np.where(ok, 0, g.integers(1, 1000, n))                                # неверные ответы почти не совпадают
    lp = np.where(ok, -0.3 - 0.5 * g.random(n), -1.5 - 2.0 * g.random(n))
    lone = (~ok) & (g.random(n) < 0.3)                                         # часть неверных — уверенные одиночные
    lp = np.where(lone, -0.05 * g.random(n), lp)
    heads.append(a.tolist()); lps.append(lp)
corr = np.array([[x == 0 for x in h] for h in heads])
ag = M.agree_matrix(heads)
logp = np.array(lps)
rid = np.arange(n) < 1500
fit, cols = np.nonzero(rid)[0], np.nonzero(~rid)[0]
r = M.crowd(ag, corr, logp, list(range(5)), fit, cols, auroc=True)
print('   ИОИ:', {e: round(v['ioi'], 4) for e, v in r.items()}, '| верхушка:', {e: round(v['top10_sel']['deception'], 4) for e, v in r.items()})
check('VETO лучше CONF, когда уверенные одиночные ответы неверны', r['VETO']['ioi'] < r['CONF']['ioi'])
check('VETO: доля поддержанных выбранных ответов в [0, 1] и выше половины', 0.5 < r['VETO']['selected_supported'] <= 1)

# 3. Калибровка VETO монотонна: откалиброванная вероятность неподдержанного не выше, чем у поддержанного
cal = Z.T.calibrate(M.veto_scores(ag, logp, list(range(5))), corr, fit, cols)
sup = M.supported(ag, list(range(5)))[:, cols]
# (первая редакция сравнивала головы между собой и упала: калибровка — по каждой голове отдельно, монотонность — внутри головы)
check('VETO: у каждой головы неподдержанный не выше любого её поддержанного после калибровки',
      all(cal[k][~sup[k]].max() <= cal[k][sup[k]].min() + 1e-12 for k in range(5) if (~sup[k]).any() and sup[k].any()))

# 4. MIX-LR: форма, защита от одного класса, счётчик
S = M.mixlr_scores(ag, corr, logp, list(range(5)), fit)
check('MIX-LR: оценки на всех задачах конечны', S.shape == (5, n) and np.isfinite(S).all())
corr1 = corr.copy(); corr1[0][fit] = True                                       # у головы 0 в fit только верные
S1 = M.mixlr_scores(ag, corr1, logp, list(range(5)), fit)
r1 = M.crowd(ag, corr1, logp, list(range(5)), fit, cols, evals=('LR-AGREE', 'MIX-LR'))
check('MIX-LR: один класс → константа, lr_one_class = 1', np.all(S1[0] == 0) and r1['MIX-LR']['lr_one_class'] == 1 and r1['LR-AGREE']['lr_one_class'] == 1)

# 5. AGREE, LR-AGREE и CONF считаются тем же кодом OCCOR-01
ro = Z.crowd_ioi(ag, corr, logp, None, list(range(5)), fit, cols, evals=('AGREE', 'LR-AGREE', 'CONF'), top10=True, auroc=False,
                 S={'AGREE': Z.agree_scores(ag, list(range(5))), 'LR-AGREE': Z.lr_scores(ag, corr, list(range(5)), fit), 'CONF': logp})
check('AGREE, LR-AGREE, CONF совпадают с кодом OCCOR-01', all(abs(ro[e]['ioi'] - r[e]['ioi']) < 1e-12 and
                                                             abs(ro[e]['top10_sel']['deception'] - r[e]['top10_sel']['deception']) < 1e-12
                                                             for e in ('AGREE', 'LR-AGREE', 'CONF')))

print('провалов:', bad)
sys.exit(1 if bad else 0)
