#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: проверки сборки оценщиков и условия R3 (ожидания записаны до запуска)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_ocrep as Q  # noqa: E402
import power_ocrep as P  # noqa: E402

M, Z = Q.M, Q.Z
bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name)
    if not ok:
        bad.append(name)


g = np.random.default_rng(7)
n = 3000
base = np.where(g.random(n) < 0.55, 0, g.integers(1, 30, n))
heads = []
for k in range(3):
    own = np.where(g.random(n) < 0.55, 0, g.integers(1, 30, n))
    heads.append(np.where(g.random(n) < 0.9, base, own).tolist())
for k in range(3):
    heads.append(np.where(g.random(n) < 0.6, 0, g.integers(1, 30, n)).tolist())
corr = np.array([[a == 0 for a in h] for h in heads])
ag = Q.agree_matrix(heads)
logp = np.where(corr, -0.3, -1.5) - g.random((6, n))
fam = ['c', 'c', 'c', 'u', 'v', 'w']
rid = np.arange(n) < 1500
fit, cols = np.nonzero(rid)[0], np.nonzero(~rid)[0]
hi = list(range(6))
r = Q.crowd(ag, corr, logp, fam, hi, fit, cols)
ro = Z.crowd_ioi(ag, corr, logp, fam, hi, fit, cols, evals=('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF'), top10=True)
check('оценщики OCCOR-01 совпадают с analyze_occor.crowd_ioi', all(abs(r[e]['ioi'] - ro[e]['ioi']) < 1e-12 and
                                                                abs(r[e]['top10_sel']['deception'] - ro[e]['top10_sel']['deception']) < 1e-12
                                                                for e in ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF')))
rm = M.crowd(ag, corr, logp, hi, fit, cols)
check('VETO и MIX-LR совпадают с analyze_ocmix.crowd', all(abs(r[e]['ioi'] - rm[e]['ioi']) < 1e-12 for e in ('VETO', 'MIX-LR'))
      and abs(r['VETO']['selected_supported'] - rm['VETO']['selected_supported']) < 1e-12)
S = Q.scores(ag, corr, logp, hi, fit, fam, ('AGREE', 'NB-IND'))
check('scores считает только запрошенные оценщики', set(S) == {'AGREE', 'NB-IND'})
check('условие R3: 0,2 и 0,9 → да; 0,2 и 0,5 → нет; 0,1 и 0,9 → нет; ровно 0,15 → нет',
      P.gate(0.2, 0.9) and not P.gate(0.2, 0.5) and not P.gate(0.1, 0.9) and not P.gate(0.15, 0.9))
Scf = Q.crossfit_scores(ag, corr, logp, fam, hi, fit, cols)
check('кросс-подгонка: все восемь оценщиков, оценки конечны', set(Scf) >= set(Q.EVALS) and all(np.isfinite(Scf[e]).all() for e in Q.EVALS))
print('провалов:', bad)
sys.exit(1 if bad else 0)
