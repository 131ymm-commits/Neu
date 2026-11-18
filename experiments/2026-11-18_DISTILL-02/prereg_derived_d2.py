#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: константы PREREG из кода (для ledger.py audit): места фаз, конец пилота OCDIV-04, число заданий, B, R, z, пороги t, ID
работ литературы. Ничего не придумывается: каждое число — из модуля, файла или выражения ниже.  python3 prereg_derived_d2.py"""
import inspect
import json
import os
import re
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import distill02 as D  # noqa: E402
import distill02_extract as XD  # noqa: E402
import make_jobs_d2 as MJ  # noqa: E402
from scipy.stats import t as student_t  # noqa: E402

X4 = D.C4.X4
lit = open(os.path.join(ROOT, 'docs/prior_art/2026-11-18_DISTILL-02.md'), encoding='utf-8').read()
der = dict(source='prereg_derived_d2.py: константы из distill02.py, distill02_extract.py, make_jobs_d2.py, ocdiv4_extract.py, записки литературы',
           pilot3_end=max(e['place'][1] for e in X4.envs_ocdiv4('pilot3')), start5=XD.START5, start_new5=XD.START_NEW5,
           n_test=XD.PHASES5['test5']['n'], places={ph: [min(e['place'][0] for e in XD.envs_d2(ph)), max(e['place'][1] for e in XD.envs_d2(ph))]
                                                       for ph in XD.PHASES5},
           n_jobs=len(MJ.all_jobs()), n_rep=MJ.REP_N, rep_jobs=MJ.rep_jobs(), B=D.B_TEST, R=D.R_TEST, top_offsets=D.TOP_OFFSETS,
           min_numeric=D.MIN_NUMERIC, share_min=D.SHARE_MIN, z=D.C4.Z, level=D.LEVEL,
           t_crit={n: float(student_t.ppf(1 - D.LEVEL, n - 1)) for n in (3, 4, 8)}, mc_sets=inspect.signature(D.C4.power4).parameters['n'].default,
           arxiv_ids=sorted(set(re.findall(r'\b2\d{3}\.\d{5}\b', lit))),
           n_pilot_ocdiv4=X4.PHASES4['pilot3']['n'], families5={ph: {f: list(x) for f, x in fx.items()} for ph, fx in XD.FAMILIES5.items()},
           ocdiv2_end_L_X9999=max(e['place'][1] for ph in XD.X2.PHASES for e in XD.X2.envs_ocdiv2(ph) if e['name'] == 'L_X9999_p3') - 1,
           quantile=1 - D.LEVEL)
json.dump(der, open(os.path.join(X, 'prereg_derived_d2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(der, ensure_ascii=False, default=str)[:600])
