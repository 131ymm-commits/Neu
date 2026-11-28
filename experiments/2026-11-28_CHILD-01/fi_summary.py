"""CHILD-01: сводка кривых функциональной информации из fi_curves.json → fi_summary.json (для текстов и отчёта).
Биты = −log2 доли случайных программ (порождение глубины до 6) с числом верных ответов не меньше уровня; область — 201 вход.
«Бит за полностью пройденный экзамен из 16 тестов» = −log2 E[T^16] (тесты с возвращением, среднее по наборам тестов). Оценка даётся только там,
где в выборке не меньше десяти точных решений; иначе — None (верх кривой не достигнут, оценку определяли бы единичные программы). Для отдельного набора тестов бит не меньше (неравенство Йенсена).
  python3 fi_summary.py"""
import json, math, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); j = json.load(open(os.path.join(H, 'fi_curves.json'))); M = 1_500_000
out = dict(note='сводка fi_curves.json; мера — случайное порождение программ глубины до 6; 201 вход', M=M, tasks={})
for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'):
    lf = j['direct'][t + '_D6']['logF']; mx = j['direct'][t + '_D6']['max_level']; lf4 = j['direct'][t + '_D4']['logF']
    tail = [0 if x is None else 2 ** x for x in lf] + [0]; pk = np.array([tail[k] - tail[k + 1] for k in range(202)]); cnt = np.round(pk * M).astype(int)
    lv = np.arange(202) / 201; terms = pk * lv ** 16; e16 = float(terms.sum())
    few = float(terms[cnt <= 5].sum() / e16)                                  # доля оценки, которую дают уровни с пятью программами и меньше
    reliable = lf[201] is not None and cnt[201] >= 10                         # оценка — только если точных решений в выборке не меньше десяти
    ci = None
    if reliable:                                                              # интервал: пуассоновский разброс чисел программ по уровням
        r = np.random.default_rng(0); bs = []
        for _ in range(4000):
            c = r.poisson(cnt); bs.append(math.log2((c / M * lv ** 16).sum()) - math.log2(max(c[201], 1) / M))      # разность «бит задачи − бит экзамена»
        ci = [round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
    out['tasks'][t] = dict(programs_at_10pct=int(round(tail[20] * M)), programs_by_level={str(k): int(round(tail[k] * M)) for k in (100, 105, 110, 114, 115, 116, 117, 118, 120, 150)},
        bits_10pct=round(-lf[20], 2), bits_50pct=None if lf[100] is None else round(-lf[100], 2), programs_at_50pct=int(round(tail[100] * M)),
        programs_at_75pct=int(round(tail[150] * M)), max_level_seen=mx, max_share_seen=round(mx / 201, 2),
        solved_direct_bits=None if lf[201] is None else round(-lf[201], 2), solved_programs=int(cnt[201]),
        solved_upper_bound_bits=round(-j['bound'][t]['D6'], 2), solved_lower_bound_bits=round(-(lf[201] if lf[201] is not None else math.log2(3 / M)), 2),
        exam16_bits=round(-math.log2(e16), 2) if reliable else None, exam16_share_from_rare_levels=round(few, 2),
        task_minus_exam16_bits=None if not reliable else round(-lf[201] + math.log2(e16), 2), task_minus_exam16_ci95=ci,
        bits_10pct_depth4=round(-lf4[20], 2), solved_direct_bits_depth4=None if lf4[201] is None else round(-lf4[201], 2),
        split_solved_bits=[None if v[201] is None else round(-v[201], 1) for v in j['split'][t + '_D6']])
out['constants'] = dict(samples=M, inputs=201, depth=6, upper_bound_zero_hits_bits=round(-math.log2(3 / M), 2), bits_per_input_point=round(math.log2(201), 2))
json.dump(out, open(os.path.join(H, 'fi_summary.json'), 'w'), ensure_ascii=False, indent=1)
for t, d in out['tasks'].items(): print(t, {k: d[k] for k in ('bits_10pct', 'bits_50pct', 'programs_at_50pct', 'programs_at_75pct', 'solved_direct_bits', 'solved_programs', 'exam16_bits', 'exam16_share_from_rare_levels', 'task_minus_exam16_bits', 'task_minus_exam16_ci95')})
