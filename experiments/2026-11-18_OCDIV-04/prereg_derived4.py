#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: константы PREREG из кода (для ledger.py audit): места фаз, зёрна, z, квантиль, число наборов Монте-Карло, предел шага
workflow, ID работ литературы. Ничего не придумывается: каждое число берётся из модуля, файла или выражения ниже.
  python3 prereg_derived4.py    пишет prereg_derived4.json рядом со скриптом"""
import inspect
import json
import os
import re
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import ocdiv4 as C  # noqa: E402
import make_jobs4 as MJ  # noqa: E402

X4, X2 = C.X4, C.X4.X2
places = {ph: [min(e['place'][0] for e in X4.envs_ocdiv4(ph)), max(e['place'][1] for e in X4.envs_ocdiv4(ph)) - 1] for ph in X4.PHASES4}
old = {ph: [min(e['place'][0] for e in X2.envs_ocdiv2(ph)), max(e['place'][1] for e in X2.envs_ocdiv2(ph)) - 1] for ph in X2.PHASES}
wf = open(os.path.join(ROOT, '.github/workflows/neu-par.yml'), encoding='utf-8').read()
lit = open(os.path.join(ROOT, 'docs/prior_art/2026-11-18_OCDIV-04.md'), encoding='utf-8').read()
der = dict(source='prereg_derived4.py: константы из ocdiv4.py, ocdiv4_extract.py, ocdiv2_extract.py, make_jobs4.py, neu-par.yml, записки литературы',
           places_new=places, places_old=old, n_test=X4.PHASES4['test3']['n'], n_pilot=X4.PHASES4['pilot3']['n'],
           seeds=dict(cv=C.SEED_CV4, test=C.SEED_TEST, pilot=C.SEED_PILOT, power=C.SEED_POWER4, rep=C.SEED_REP4),
           z=C.Z, quantile=1 - C.LEVEL, mc_sets=inspect.signature(C.power4).parameters['n'].default,
           workflow_timeouts_min=[int(x) for x in re.findall(r'timeout-minutes:\s*(\d+)', wf)],
           rep_jobs=MJ.rep_jobs(), arxiv_ids=sorted(set(re.findall(r'\b2\d{3}\.\d{5}\b|\b2006\.\d{5}\b', lit))))
json.dump(der, open(os.path.join(X, 'prereg_derived4.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(der, ensure_ascii=False, default=str)[:900])
