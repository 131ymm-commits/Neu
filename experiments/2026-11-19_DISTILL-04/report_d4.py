#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: отчёт из вывода анализа (gha_out/distill04_sum_test/test.json) — все числа подставляются из json (ERRORS № 200, 226);
чтения — по таблицам PREREG §5 (регистрация c659755b). Пишет REPORT-DISTILL-04.md и report_view_d4.json (выборка для ledger.py audit).
  python3 report_d4.py [--council docs/council/….json]"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'gha_out', 'distill04_sum_test_b')          # повтор после сбоя (DEVIATIONS.md, отступление 1)
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}
OLMO = 'OLMo-2-0425-1B-Instruct'


def r(x, n=4, sign=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return '—'
    s = f'{x:+.{n}f}' if sign else f'{x:.{n}f}'
    return s.replace('-', '−').replace('.', ',')


def main(a):
    T = json.load(open(os.path.join(OUT, 'test.json'), encoding='utf-8'))
    E = json.load(open(os.path.join(HERE, 'expect_d4.json'), encoding='utf-8'))
    P2 = json.load(open(os.path.join(ROOT, 'gha_out/distill04_pilot2/pilot.json'), encoding='utf-8'))
    rep = json.load(open(os.path.join(OUT, 'rep.json'), encoding='utf-8'))
    det = open(os.path.join(OUT, 'det.txt'), encoding='utf-8').read().strip()
    R, AB, envs = T['rules'], T['ab'], T['envs']
    names = sorted(envs)
    L = []
    w = L.append
    p1 = R['П1-Т']
    w('# DISTILL-04 «ПРОЧИЕ» — отчёт')
    w('')
    w('PREREG — регистрация c659755b (`PREREG-DISTILL-04.md`). Числа ниже подставляет `report_d4.py` из `gha_out/distill04_sum_test/test.json`.')
    w('')
    w('## 1. Итог')
    w('')
    w('| правило | мера | статус | среднее 8 сред | интервал M4 (0,0025) | t по средам (порог) | вердикт |')
    w('|---|---|---|---|---|---|---|')
    for rule in ('П1-Т', 'П1МТ-Т', 'П2-Т'):
        e = R[rule]
        ci = e.get('ci') or [None, None]
        w(f"| {rule} | {e['measure']} | {'решающее' if e['active'] else 'описательно'} | {r(e['delta'], 4, True)} | [{r(ci[0], 4, True)}; {r(ci[1], 4, True)}] | "
          f"{r(e['t_envs']['t'], 2, True)} ({r(e['t_envs']['crit'], 4)}) | {e['verdict_final']} |")
    for rule, v in AB['verdicts'].items():
        w(f"| {rule} | D ({'программа' if v['kind'] == 'prog' else 'форма'}) | решающее | D {r(v.get('D'), 4, True)} | точное p {r(v.get('p'), 6)}; ранг {v.get('rank', '—')} из {v.get('n_perm', '—')}; k = {v.get('k')} | — | {v['verdict']} |")
    w('')
    # чтение П1-Т (PREREG §5)
    v1 = p1['verdict_rule']
    read = {'меньше': 'на новых средах таблица частот того же размера описывает ответы голов лучше механизма из каталога. В «прочих» есть повторяющиеся '
                      'смещения, которые 10 операторов каталога не берут. Это говорит о каталоге, а не о том, что механизма нет вообще.',
            'больше': 'на средах другого устройства (test6: переход через x500) механизм из каталога описывает ответы голов лучше таблицы частот того же '
                      'размера. Это не «механизм лучше частот вообще».',
            'не решено': '«М и Т не различены; решающая мощность 0,0069 — по модели с параметрами new5; на устройстве test6 мощность не измерена; '
                         'это не довод за равенство; 0 бит».'}
    w(f"**Чтение П1-Т (PREREG §5):** {read.get(v1, 'только по части А — в среднем этих 8 сред; на новые среды не переносится.')}")
    w('')
    signs = p1.get('signs', {})
    w(f"- Знак по средам (интервал среды при 0,0025 / 8): больше нуля — {len(signs.get('pos', []))}, меньше — {len(signs.get('neg', []))}, "
      f"накрывает ноль — {len(signs.get('zero', []))}." + (f" Пометка: {p1['mark']}." if p1.get('mark') else ''))
    sym = T['descriptive'].get('m_M_sym', {})
    w(f"- Симметричная версия нормировки (описательно): среднее m_M_sym {r(sym.get('delta'), 4, True)}, вердикт тем же правилом — «{sym.get('verdict_rule')}». "
      f"Нормировка (PREREG §4, ветвь «мала»): направление влияния недостачи не проверялось, величина не больше 1,4e-4 · ε.")
    m5 = np.mean([v['point']['m_M'] for v in P2['sets']['test5_thousands']['envs'].values()])
    w(f"- m_M на test6 минус m_M на test5 (пилот 2, устройство построения; описательно): {r(p1['delta'] - m5, 4, True)}.")
    w('')
    w('## 2. Среды test6 (точки; наты на числовой ответ)')
    w('')
    w('| среда | голов | m_M | m_Mo («прочие») | top3 | m_MT | m_T30 | m_M_sym |')
    w('|---|---|---|---|---|---|---|---|')
    for n in names:
        q = envs[n]['point']
        w(f"| {n} | {len(envs[n]['heads'])} | {r(q['m_M'], 4, True)} | {r(q['m_Mo'], 4, True)} | {r(q['top3'], 4, True)} | {r(q['m_MT'], 4, True)} | "
          f"{r(q['m_T30'], 4, True)} | {r(q['m_M_sym'], 4, True)} |")
    w('')
    # по головам и токенизатор
    ph = {h: {k: float(np.mean([envs[n]['per_head'][h][k] for n in names if h in envs[n]['per_head']])) for k in ('m_M', 'm_Mo', 'top3', 'm_MT')}
          for h in SHORT}
    w('**По головам** (среднее по 8 средам; описательно):')
    w('')
    w('| голова | m_M | m_Mo | top3 | m_MT |')
    w('|---|---|---|---|---|')
    for h, s in SHORT.items():
        w(f"| {s} | {r(ph[h]['m_M'], 4, True)} | {r(ph[h]['m_Mo'], 4, True)} | {r(ph[h]['top3'], 4, True)} | {r(ph[h]['m_MT'], 4, True)} |")
    six = [h for h in SHORT if h != OLMO]
    tok = {k: dict(olmo=ph[OLMO][k], lo=min(ph[h][k] for h in six), hi=max(ph[h][k] for h in six)) for k in ('m_M', 'm_Mo', 'top3')}
    w('')
    w('- **Токенизатор как ковариата** (одна голова, проверки нет, о причине вывода нет): у OLMo (числа группами по три цифры) ' +
      '; '.join(f"{k} {r(t['olmo'], 4, True)} при размахе шести других [{r(t['lo'], 4, True)}; {r(t['hi'], 4, True)}]" for k, t in tok.items()) + '.')
    w('')
    # A-на-B
    res = AB['result']
    w('## 3. Повтор A-на-B на новых ответах (код DISTILL-03 без изменений)')
    w('')
    for kind, nm in (('prog', 'программа'), ('shape', 'форма')):
        x = res.get(kind) or {}
        sl = AB['slices'][kind]['mean']
        line = []
        if sl['mean'] > 0 and sl['median'] > 0 and sl['drop_worst'] > 0:
            line.append('срезы согласны')
        if sl['mean'] > 0 and sl['median'] <= 0:
            line.append('преимущество своей держится на немногих далёких чужих; против типичной чужой его нет')
        if sl['mean'] > 0 and sl['drop_worst'] <= 0:
            line.append('преимущество своей даёт одна худшая чужая')
        nn = x.get('nearest_other', {})
        wo = (x.get('without') or {}).get(OLMO, {})
        w(f"- **{nm}**: D {r(x.get('D'), 4, True)}, точное p {r(x.get('p'), 6)}, ранг {x.get('rank')} из {x.get('n_perm')}, различных D_π {x.get('n_distinct')}; "
          f"своя первая в столбце у {x.get('own_first')} голов из {x.get('k')}; своя лучше любой чужой у {nn.get('heads_own_best')} голов, средний зазор "
          f"{r(nn.get('mean'), 4, True)}; без OLMo — D {r(wo.get('D'), 4, True)}, p {r(wo.get('p'), 6)}.")
        w(f"  - срезы (среднее по головам): своя − среднее чужих {r(sl['mean'], 4, True)}, − медиана чужих {r(sl['median'], 4, True)}, "
          f"− без худшей чужой {r(sl['drop_worst'], 4, True)} → {'; '.join(line) if line else 'D ≤ 0'}.")
    va = {k_: v['verdict'] for k_, v in AB['verdicts'].items()}
    ab_read = {('да', 'да'): 'повтор специфичности на независимых ответах и новых средах — для программы и для формы.',
               ('да', 'нет'): 'повтор для программы целиком; на новых средах test6 своя форма не показана (мощность формы ≈ 0,58: «нет» не доказывает, что форма общая).',
               ('да', 'непроверяемо'): 'повтор для программы целиком; на новых средах test6 своя форма не показана (мощность формы ≈ 0,58: «нет» не доказывает, что форма общая).'}
    w(f"**Чтение повтора A-на-B (PREREG §5, правило «П и Ф»):** " + ab_read.get((va['АБ-П-Т6'], va['АБ-Ф-Т6']),
      'на новых средах test6 (переход через x500) специфичность программы не повторилась; «установлено» остаётся только для сред устройства построения.'))
    ig = res.get('input_gain', {})
    w(f"- Вклад входа (своя программа − своя без входа): {r(ig.get('mean'), 4, True)}, больше нуля у {ig.get('n_pos')} голов из {len(res.get('heads_kept') or [])}.")
    dec = res.get('decomposition') or {}
    if dec.get('total'):
        dm = {p: dec[p]['mean'] for p in dec}
        w(f"- Разбивка D программы (описательно; порядок цепочки и оговорка про «уровень» — ERRORS № 225): всё {r(dm.get('total'), 4, True)} = "
          f"форма {r(dm.get('form'), 4, True)} + уровень {r(dm.get('level'), 4, True)} + прочие {r(dm.get('others'), 4, True)}; "
          f"доля «прочих» {r(dm['others'] / dm['total'] if dm.get('total') else None, 4)}.")
    w(f"- Головы: в тесте {len(res.get('heads_kept') or [])}, выкинуты {res.get('heads_dropped')}; сред {len(res.get('envs_kept') or [])}.")
    w('')
    # описательное
    w('## 4. Описательно')
    w('')
    same_w = all(T['weights'][fam][h]['pi'] == P2['weights'][fam][h]['pi'] for fam in T['weights'] for h in T['weights'][fam])
    w(f"- Веса операторов в тесте совпали с пилотом 2 (то же построение и код): {same_w}. Каталог: {', '.join(T['catalog'])}.")
    k = T['op_kinship']['thousands']
    w(f"- Родство весов операторов (построение): родич ближе среднего чужих у {k['n_kin_closer']} голов из {k['n']} — свойство построения, не теста.")
    lt = T['descriptive'].get('length_test6L', {})
    for n, v in lt.items():
        q = v['point']
        w(f"- «Длина» {n} (описательно): m_M {r(q['m_M'], 4, True)}, m_Mo {r(q['m_Mo'], 4, True)}, top3 {r(q['top3'], 4, True)}, m_MT {r(q['m_MT'], 4, True)}.")
    for job, x in rep['jobs'].items():
        cols = {c: v['equal_share'] for e in x['columns'].values() for c, v in e.items() if v['equal_share'] is not None}
        w(f"- Повтор извлечения {job.replace('distill04_rep_', '')} (доля совпавших значений по столбцам): " +
          ', '.join(f"{c} {r(v, 4)}" for c, v in cols.items()) + '.')
    w(f"- Повтор анализа: {det}.")
    w('')
    # калибровка и вес
    oc = {'E1': v1 == 'меньше', 'E1а': v1 == 'меньше', 'E2': AB['verdicts']['АБ-П-Т6']['verdict'] == 'да', 'E3': AB['verdicts']['АБ-Ф-Т6']['verdict'] == 'да',
          'E4': R['П1МТ-Т']['delta'] > 0, 'E5': R['П2-Т']['delta'] > 0}
    w('## 5. Ожидания (PREREG §6) и вес опоры (§11)')
    w('')
    w('| № | ожидание | исход |')
    w('|---|---|---|')
    ex = E['rules']
    vals = {'E1': ex['П1-Т']['expect_e1']['new5_thousands'], 'E1а': ex['П1-Т']['expect_e1']['test5_thousands'], 'E2': ex['АБ-П-Т6']['expect'],
            'E3': ex['АБ-Ф-Т6']['expect'], 'E4': E['descriptive']['П1МТ-Т']['expect'], 'E5': E['descriptive']['П2-Т']['expect']}
    for kk in oc:
        w(f"| {kk} | {r(vals[kk], 4)} | {'да' if oc[kk] else 'нет'} |")
    bits = {'П1-Т': ex['П1-Т']['bits_less'] if v1 == 'меньше' else (ex['П1-Т']['bits_more'] if v1 == 'больше' else 0.0)}
    for rule in ('АБ-П-Т6', 'АБ-Ф-Т6'):
        vv = AB['verdicts'][rule]['verdict']
        bits[rule] = ex[rule]['bits_yes'] if vv == 'да' else (ex[rule]['bits_no'] if vv == 'нет' else 0.0)
    w('')
    w('- Вес опоры: ' + '; '.join(f"{k_} {r(b, 2, True)} бит" for k_, b in bits.items()) + ' (модельный; перенос M4 на 0,0025 для среднего сред не проверен).')
    w('')
    open(os.path.join(HERE, 'REPORT-DISTILL-04.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    view = dict(rules={k_: dict(delta=e['delta'], ci=e.get('ci'), t=e['t_envs']['t'], crit=e['t_envs']['crit'], verdict=e['verdict_final']) for k_, e in R.items()},
                ab={k_: {kk: v.get(kk) for kk in ('D', 'p', 'rank', 'n_perm', 'k', 'n_distinct', 'verdict')} for k_, v in AB['verdicts'].items()},
                slices={kind: AB['slices'][kind]['mean'] for kind in ('prog', 'shape')}, envs={n: envs[n]['point'] for n in names},
                per_head=ph, tok=tok, sym=dict(delta=sym.get('delta'), verdict=sym.get('verdict_rule')), diff_test5=float(p1['delta'] - m5),
                input_gain=dict(mean=ig.get('mean'), n_pos=ig.get('n_pos')), weights_same=same_w, kin=k['n_kin_closer'],
                length={n: v['point'] for n, v in lt.items()}, outcomes=oc, expect=vals, bits=bits,
                ab_desc={kind: dict(nearest=(res.get(kind) or {}).get('nearest_other', {}).get('mean'),
                                    without={kk: ((res.get(kind) or {}).get('without') or {}).get(OLMO, {}).get(kk) for kk in ('D', 'p')})
                         for kind in ('prog', 'shape')},
                decomposition={p_: dec[p_]['mean'] for p_ in dec} if dec else None,
                others_share=(dec['others']['mean'] / dec['total']['mean']) if dec.get('total') else None,
                rep={job: {c: v['equal_share'] for e in x['columns'].values() for c, v in e.items()} for job, x in rep['jobs'].items()},
                errors_refs=[225, 233])
    json.dump(view, open(os.path.join(HERE, 'report_view_d4.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('\n'.join(L[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
