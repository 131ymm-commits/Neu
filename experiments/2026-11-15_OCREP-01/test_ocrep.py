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
import analyze_ocrep_test as R  # noqa: E402
e_ = dict(ci=[-0.05, 0.03], ci_percentile=[-0.03, 0.05],
          tails=dict(halves=[[-0.06, 0.03], [-0.04, 0.03]], halves_percentile=[[-0.035, 0.05], [-0.025, 0.05]]))
pd_ = R.prior_descr(e_, {'a': -0.08, 'b': -0.045, 'c': -0.01})
check('описательно (совет 58): −0,08 — «исключён»; −0,045 — «неустойчиво» (BC нет, процентильный да), половины расходятся; −0,01 — «не исключён»',
      pd_['a'] == dict(effect=-0.08, status='исключён', excluded_bc=True, excluded_percentile=True, excluded_halves=[True, True], halves_agree=True)
      and pd_['b'] == dict(effect=-0.045, status='неустойчиво', excluded_bc=False, excluded_percentile=True, excluded_halves=[False, True],
                           halves_agree=False)
      and pd_['c']['status'] == 'не исключён')
check('конъюнкция (совет 58): оба < 0 → подтверждено; только BC → «не решено (только BC)»; только процентильный → «… (только процентильный)»; '
      'оба > 0 → опровергнуто; оба через 0 → не решено',
      R.verdict_conj([-0.05, -0.01], [-0.06, -0.005]) == 'подтверждено'
      and R.verdict_conj([-0.05, -0.01], [-0.04, 0.01]) == 'не решено (только BC)'
      and R.verdict_conj([-0.01, 0.05], [0.001, 0.06]) == 'не решено (только процентильный)'
      and R.verdict_conj([0.01, 0.05], [0.02, 0.06]) == 'опровергнуто'
      and R.verdict_conj([-0.02, 0.02], [-0.03, 0.03]) == 'не решено')
b_ = np.concatenate([np.linspace(0.0, 1.0, 1001), [-5.0]])
ce_ = R.ci_entry(b_, 0.5, 0.0025)
check('ci_entry: числа повторов за границами BC и процентильного ДИ записаны; при < 5 за границей — метка «граница BC не определена»',
      set(ce_['n_out']) == {'bc', 'percentile'} and all(len(v) == 2 for v in ce_['n_out'].values())
      and ce_['bc_undetermined'] == [ce_['n_out']['bc'][0] < 5, ce_['n_out']['bc'][1] < 5]
      and (('не определена' in ce_['bc_note']) == any(ce_['bc_undetermined'])))
pe_ = R.prior_effects()
check('прежние эффекты: половина наименьшего = max/2 (R1 — от OCMIX-01 R3, R2 — от OCCOR-01 R3)',
      pe_['R1']['половина наименьшего'] == pe_['R1']['OCMIX-01 R3'] / 2 and pe_['R2']['половина наименьшего'] == pe_['R2']['OCCOR-01 R3'] / 2
      and all(v < 0 for d_ in pe_.values() for v in d_.values()))
print('провалов:', bad)
sys.exit(1 if bad else 0)
