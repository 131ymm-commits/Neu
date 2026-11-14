#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: проверки оценщиков на игрушечных данных (ожидания записаны до запуска)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_occor as Z  # noqa: E402

bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name)
    if not ok:
        bad.append(name)


# 1. Совпадения: None не совпадает ни с чем; на диагонали False
ans = [[1, None, 3], [1, None, 4], [2, 5, 3]]
ag = Z.agree_matrix(ans)
check('agree_matrix: None не совпадает, диагональ пуста',
      ag[0, 1].tolist() == [True, False, False] and ag[0, 2].tolist() == [False, False, True] and not ag[0, 0].any())

# 2. Два клона (всегда одинаковые ответы) и независимая голова. Правда — 0 на всех задачах.
g = np.random.default_rng(1)
n = 4000
truth = np.zeros(n, int)
clone = np.where(g.random(n) < 0.6, 0, g.integers(1, 20, n))                  # точность 0,6
indep = np.where(g.random(n) < 0.6, 0, g.integers(1, 20, n))
ans = [clone.tolist(), clone.tolist(), indep.tolist()]
corr = np.array([[a == 0 for a in x] for x in ans])
ag = Z.agree_matrix(ans)
fit = np.arange(n)
S = Z.nb_scores(ag, corr, [0, 1, 2], fit)
# у клона 0: совпадение с клоном 1 всегда (p1 = p0 ≈ 1) → вклад ≈ 0; совпадение с независимой — сильный довод
contrib_clone = np.log(((ag[0, 1][corr[0]].sum() + 1) / (corr[0].sum() + 2)) / ((ag[0, 1][~corr[0]].sum() + 1) / ((~corr[0]).sum() + 2)))
check('NB: голос клона почти ничего не весит (|log LR| < 0,01)', abs(contrib_clone) < 0.01)
j_ind_agree = np.nonzero(ag[0, 2] & corr[0])[0][0]
j_ind_dis = np.nonzero(~ag[0, 2] & ~corr[0])[0][0]
check('NB: совпадение с независимой головой поднимает оценку', S[0][j_ind_agree] > S[0][j_ind_dis] + 2)
A = Z.agree_scores(ag, [0, 1, 2])
check('AGREE: клон получает 0,5 только за клона', A[0][j_ind_dis] == 0.5)

# 3. NB-IND: оценка зависит только от точностей и общей s̄ (у двух голов с равной точностью вклады равны)
S2, sbar = Z.nb_ind_scores(ag, corr, [0, 1, 2], fit)
check('NB-IND: s̄ в (0, 1)', 0 < sbar < 1)
both_agree = np.nonzero(ag[2, 0] & ag[2, 1])[0]
check('NB-IND: независимая голова при согласии обоих клонов получает двойной вклад (клоны не распознаны)',
      len(both_agree) > 0 and S2[2][both_agree[0]] > 0)

# 4. FAM-AGREE: клоны — одно семейство; своё семейство не голосует
fam = ['m', 'm', 'x']
F = Z.fam_scores(ag, fam, [0, 1, 2])
check('FAM: у клона голос только семейства x', np.allclose(F[0], ag[0, 2].astype(float)))
check('FAM: у независимой — один голос семейства m (доля его членов)', np.allclose(F[2], (ag[2, 0].astype(float) + ag[2, 1]) / 2))

# 5. Выбор при общих ошибках клонов вне диапазона: 3 клона и 2 независимые; NB-AGREE должен дать ИОИ не хуже AGREE
g = np.random.default_rng(2)
n = 6000
rid = np.arange(n) < 3000
truth = np.zeros(n, int)
base = np.where(g.random(n) < 0.55, 0, g.integers(1, 30, n))
heads = []
for k in range(3):                                                             # клоны: 90 % ответов общие
    own = np.where(g.random(n) < 0.55, 0, g.integers(1, 30, n))
    heads.append(np.where(g.random(n) < 0.9, base, own))
for k in range(2):
    heads.append(np.where(g.random(n) < 0.6, 0, g.integers(1, 30, n)))
ans = [h.tolist() for h in heads]
corr = np.array([[a == 0 for a in x] for x in ans])
ag = Z.agree_matrix(ans)
logp = np.zeros((5, n))
fam = ['c', 'c', 'c', 'u', 'v']
fit, cols = np.nonzero(rid)[0], np.nonzero(~rid)[0]
r = Z.crowd_ioi(ag, corr, logp, fam, list(range(5)), fit, cols)
print('   ИОИ:', {e: round(v['ioi'], 4) for e, v in r.items()})
check('выбор: NB-AGREE не хуже AGREE при клонах', r['NB-AGREE']['ioi'] <= r['AGREE']['ioi'] + 1e-9)
check('выбор: ничьи считаются (доля в [0, 1])', all(0 <= v['tie_frac'] <= 1 for v in r.values()))

# 6. Доли одинаковых неверных ответов
sw = Z.same_wrong_rates(ans, corr, cols, [0, 1, 3])
check('same_wrong: клоны делят больше неверных ответов, чем клон с независимой', sw[(0, 1)][0] > 0.7 and sw[(0, 3)][0] < 0.2)

print('провалов:', bad)
sys.exit(1 if bad else 0)
