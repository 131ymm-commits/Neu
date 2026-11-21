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
           quantile=1 - D.LEVEL, lam=D.LAMBDA, lam_sens=list(D.LAMBDA_SENS), fragile=D.FRAGILE, power_min=D.POWER_MIN,
           seed_test=D.SEED_TEST, n_rules=len(D.RULES), workers=4, det_B=200, det_envs=['T_X19_p3', 'L_X9_p3'],
           n_templates=len(MJ.all_jobs()) + MJ.REP_N + 1, top_k_wrong=D.TOPK_WRONG, max_features=D.MAX_FEATURES,
           new5_carries={e['name']: D.carry_summary([dict(a=p['a'], b=p['b'], sum=p['sum'], ood=int(p['range'] != 'ID')) for p in e['problems']])
                         for e in XD.envs_d2('new5')},
           ref_size_4digit=D.ref_size(2045), log_floor_old=float(__import__('math').log(1e-300)),
           skeptic_assumed_offset=-10 ** 4,                                 # допущение скептика (совет 74): «в B1 нет смещения −10 000»
           new5_max_lost_offset={e['name']: -10 ** max(j for p in e['problems'] for j, _ in D.carry_info(p['a'], p['b'])) for e in XD.envs_d2('new5')},
           errors_refs=sorted(int(x) for x in re.findall(r'^## №(\d+) \([^)]*\) DISTILL-02', open(os.path.join(ROOT, 'journal/ERRORS.md'),
                                                                                                   encoding='utf-8').read(), re.M)))
dry = os.path.join(ROOT, 'gha_out/distill02_dry')                  # сухой прогон (совет 74, п. 10): числа — из его вывода
if os.path.exists(os.path.join(dry, 'dry_summary.txt')):
    txt = open(os.path.join(dry, 'dry_summary.txt'), encoding='utf-8').read()
    mem = [int(x) for x in open(os.path.join(dry, 'mem_used_mb.txt')).read().split() if x.strip().isdigit()]
    tm = open(os.path.join(dry, 'time_main.txt'), encoding='utf-8', errors='replace').read()
    nums = lambda pat: [float(x) for x in re.findall(pat, txt)]   # noqa: E731
    der['dry'] = dict(main_s=nums(r'основной прогон, с: (\d+)')[0], analysis_s=nums(r'по выводу анализа, с: ([\d.]+)')[0],
                      resume_s=nums(r'продолжение с готовых сред, с: (\d+)')[0], det_s=nums(r'повтор на детерминизм \(2 × 2 среды, B = 200\), с: (\d+)')[0],
                      resume_same='вывод тот же, кроме времени: True' in txt, det_same='побайтно одинаково: True' in txt,
                      mem_before_mb=mem[0], mem_peak_mb=max(mem), mem_peak_over_mb=max(mem) - mem[0],
                      max_rss_kb=int(re.findall(r'Maximum resident set size \(kbytes\): (\d+)', tm)[0]))   # nproc при OMP_NUM_THREADS=1 печатает 1 — не ядра
    der['dry']['main_min'] = der['dry']['main_s'] / 60
json.dump(der, open(os.path.join(X, 'prereg_derived_d2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(der, ensure_ascii=False, default=str)[:600])
