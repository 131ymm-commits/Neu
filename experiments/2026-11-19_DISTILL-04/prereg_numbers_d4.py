#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: числа PREREG — только из json (ERRORS № 200, 226). Правило активности — PREREG-DISTILL-02 §5 п. 1 (сверено по тексту,
ERRORS № 231): правило решающее, если решающая мощность не меньше POWER_MIN и при τ пилота, и при τ из верхней границы (у двустороннего —
«подтверждено» + «опровергнуто», у одностороннего — «подтверждено»); замок — сверка с test_d4.RULES_ACTIVE. Ожидания — 0,95 × решающая
мощность при τ пилота, при τ из верхней границы — рядом (как DISTILL-02 §6); вес — log₂(мощность / α) и log₂((1 − мощность)/(1 − α)).
  python3 prereg_numbers_d4.py [--write]"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import test_d4 as T  # noqa: E402

POWER_MIN = 0.2
LEVEL = 0.0025
P2 = os.path.join(ROOT, 'gha_out/distill04_pilot2/pilot.json')
E3 = os.path.join(ROOT, 'experiments/2026-11-19_DISTILL-03/expect_d3.json')
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}


def r(x, n=4, sign=False):
    s = f'{x:+.{n}f}' if sign else f'{x:.{n}f}'
    return s.replace('-', '−').replace('.', ',')


def main(a):
    p = json.load(open(P2, encoding='utf-8'))
    e3 = json.load(open(E3, encoding='utf-8'))['rules']
    print('## Каталог (правило CATALOG_MIN = 0,01 на построении):', ', '.join(p['catalog']), f"— {len(p['catalog'])} операторов")
    print('## Веса операторов у голов («тысячи», построение)')
    print('| голова | ' + ' | '.join(p['catalog']) + ' | остаток | «прочих» на построении |')
    print('|---|' + '---|' * (len(p['catalog']) + 2))
    for h, w in p['weights']['thousands'].items():
        print(f'| {SHORT[h]} | ' + ' | '.join(r(x, 3) for x in w['pi'][:-1]) + f" | {r(w['pi'][-1], 3)} | {w['n_other']} |")
    s5 = p['sets']['test5_thousands']['envs']
    print('## Пилот: test5 «тысячи» (уже виденные ответы; описательно)')
    print('| среда | m_M (М − Т того же размера) | m_Mo (по «прочим») | top3 | m_MT (М+Т − таблица 30) | m_T30 (М − таблица 30) |')
    print('|---|---|---|---|---|---|')
    for en in sorted(s5):
        q = s5[en]['point']
        print(f"| {en} | {r(q['m_M'], 4, True)} | {r(q['m_Mo'], 4, True)} | {r(q['top3'], 4, True)} | {r(q['m_MT'], 4, True)} | {r(q['m_T30'], 4, True)} |")
    for meas in ('m_M', 'top3', 'm_MT'):
        xs = [s5[en]['point'][meas] for en in s5]
        print(f"- {meas}: среднее по 8 средам {r(sum(xs) / len(xs), 4, True)}; больше нуля в {sum(x > 0 for x in xs)} средах из {len(xs)}")
    pw = p['power']['test5_thousands']
    print('## Мощность для 8 новых сред (модель «новая среда», пилот — test5 «тысячи») и правило активности')
    act, exp = {}, {}
    for rule, (meas, kind, part_b) in T.RULES.items():
        q, qh = pw[meas]['power'], pw[meas]['power_tau_hi']
        dec = q['confirm'] + (q['refute'] if kind == 'two' else 0.0)
        dec_hi = qh['confirm'] + (qh['refute'] if kind == 'two' else 0.0)
        act[rule] = dec >= POWER_MIN and dec_hi >= POWER_MIN
        side = 'refute' if kind == 'two' and q['refute'] > q['confirm'] else 'confirm'
        p_side = q[side]
        exp[rule] = dict(measure=meas, kind=kind, mu=pw[meas]['mu'], tau=pw[meas]['tau'], tau_hi=pw[meas]['tau_hi'], s_test=pw[meas]['s_test'],
                         power=q, power_tau_hi=qh, decisive=dec, decisive_tau_hi=dec_hi, active=act[rule], expect=round(0.95 * dec, 4),
                         expect_tau_hi=round(0.95 * dec_hi, 4), expect_side=side, expect_side_p=round(0.95 * p_side, 4),
                         expect_outcome=('меньше' if side == 'refute' else 'подтверждено/больше'),
                         bits_side=round(math.log2(max(p_side, 1e-12) / LEVEL), 2), bits_dec=round(math.log2(max(dec, 1e-12) / LEVEL), 2),
                         bits_not=round(math.log2((1 - min(dec, 1 - 1e-12)) / (1 - LEVEL)), 2))
        print(f"- {rule} ({meas}, {'двусторонний' if kind == 'two' else 'односторонний'}): μ {r(pw[meas]['mu'], 4, True)}, τ {r(pw[meas]['tau'], 4)} "
              f"(верхняя {r(pw[meas]['tau_hi'], 4)}), s {r(pw[meas]['s_test'], 4)}; при τ пилота «подтверждено/больше» {r(q['confirm'], 4)}, «опровергнуто/меньше» "
              f"{r(q['refute'], 4)}, часть А {r(q['part_a'], 4)}, часть Б {r(q['part_b'], 4)} → решающая {r(dec, 4)}; при τ из верхней границы — "
              f"{r(qh['confirm'], 4)} / {r(qh['refute'], 4)} → решающая {r(dec_hi, 4)} → {'решающее' if act[rule] else 'описательно'}")
        print(f"    ожидание: «{exp[rule]['expect_outcome']}» {r(0.95 * p_side, 4)} (0,95 × {r(p_side, 4)}); решающий вердикт в любую сторону {r(0.95 * dec, 4)} "
              f"(при τ из верхней границы {r(0.95 * dec_hi, 4)}); вес исхода «{exp[rule]['expect_outcome']}» {r(exp[rule]['bits_side'], 2, True)} бит, "
              f"нерешённого {r(exp[rule]['bits_not'], 2, True)} бит")
    print('## Чувствительность к устройству сред (PREREG §6): мощность для 8 сред при параметрах других наборов пилота 2 (описательно; в правило не входит)')
    for name in ('new5_thousands', 'test5_length'):
        for rule, (meas, kind, part_b) in T.RULES.items():
            e = p['power'][name].get(meas)
            if e is None:
                continue
            q = e['power']
            dec = q['confirm'] + (q['refute'] if kind == 'two' else 0.0)
            print(f"- {name} (сред в пилоте {e['n_envs']}; сред теста в счёте {p['power'][name]['m_test']}), {rule}: μ {r(e['mu'], 4, True)}, τ {r(e['tau'], 4)}; "
                  f"«подтверждено/больше» {r(q['confirm'], 4)}, «опровергнуто/меньше» {r(q['refute'], 4)} → решающая {r(dec, 4)}")
    print('## Совет 78, пп. 1–3: П1-Т по двум моделям «новая среда» (test5 — устройство построения; new5 — другое устройство), 8 сред теста')
    D2 = T.D2
    m78 = {}
    for name in ('test5_thousands', 'new5_thousands'):
        s = p['sets'][name]['envs']
        pts = [s[n]['point']['m_M'] for n in sorted(s)]
        sds = [s[n]['sd']['m_M'] for n in sorted(s)]
        e = D2.power_rule(pts, sds, 1.0, 8, True)                       # как pilot_d4.py: модель «новая среда», 8 сред, части А и Б
        em = D2.power_rule([-x for x in pts], sds, 1.0, 8, True)        # зеркальная модель (μ → −μ): мощность исхода «больше»
        q = e['power']
        m78[name] = dict(mu=e['mu'], tau=e['tau'], s=e['s_test'], p_more=q['confirm'], p_less=q['refute'], decisive=q['confirm'] + q['refute'],
                         p_more_mirror=em['power']['confirm'], n_envs=e['n_envs'])
        x = m78[name]
        print(f"- {name} ({x['n_envs']} сред пилота): μ {r(x['mu'], 4, True)}, τ {r(x['tau'], 4)}, s {r(x['s'], 4)}; «больше» {r(x['p_more'], 4)}, "
              f"«меньше» {r(x['p_less'], 4)}, решающая {r(x['decisive'], 4)}; «больше» в зеркальной модели {r(x['p_more_mirror'], 4)}")
    e1 = {k: round(0.95 * m78[k]['p_less'], 4) for k in m78}
    e1_mix = round(0.95 * (m78['test5_thousands']['p_less'] + m78['new5_thousands']['p_less']) / 2, 4)
    bits_less = min(math.log2(max(m78[k]['p_less'], 1e-12) / LEVEL) for k in m78)
    bits_more = min(math.log2(max(m78[k]['p_more_mirror'], 1e-12) / LEVEL) for k in m78)
    bits_dec_new5 = math.log2(m78['new5_thousands']['decisive'] / LEVEL)
    print(f"- E1 «П1-Т „меньше“» двумя строками: по test5 {r(e1['test5_thousands'], 4)}, по new5 {r(e1['new5_thousands'], 4)} — в калибровку идёт "
          f"меньшая ({r(min(e1.values()), 4)}); смесь 0,5/0,5 (суждение, в калибровку не идёт) {r(e1_mix, 4)}")
    print(f"- вес опоры П1-Т (меньший по двум моделям; мощность того исхода, о котором утверждение): «меньше» {r(bits_less, 2, True)} бит, "
          f"«больше» {r(bits_more, 2, True)} бит (зеркальные модели); «не решено» 0 бит. Оценка совета по решающей мощности обеих сторон new5 — "
          f"{r(bits_dec_new5, 2, True)} бит; взят меньший")
    exp['П1-Т'].update(models_78=m78, expect_e1=e1, expect_e1_used=min(e1.values()), expect_e1_mix_judgment=e1_mix,
                       bits_less=round(bits_less, 2), bits_more=round(bits_more, 2), bits_undecided=0.0, bits_council_estimate=round(bits_dec_new5, 2))
    P3 = os.path.join(ROOT, 'gha_out/distill04_pilot3/pilot.json')
    if os.path.exists(P3):
        p3 = json.load(open(P3, encoding='utf-8'))
        print('## Пилот 3 (совет 78, п. 6): прежние меры против пилота 2 и П1-Т пилота в обеих версиях нормировки')
        same = all(p3['sets'][nm]['envs'][en]['point'][k] == p['sets'][nm]['envs'][en]['point'][k] and
                   p3['sets'][nm]['envs'][en]['sd'][k] == p['sets'][nm]['envs'][en]['sd'][k]
                   for nm in p['sets'] for en in p['sets'][nm]['envs'] for k in ('m_M', 'm_Mo', 'top3', 'm_MT', 'm_T30'))
        print(f"- прежние меры (точки и ст. откл. m_M, m_Mo, top3, m_MT, m_T30 во всех средах всех наборов) совпали с пилотом 2 побайтно: {same}; "
              f"каталог тот же: {p3['catalog'] == p['catalog']}")
        for nm in ('test5_thousands', 'new5_thousands'):
            s3 = p3['sets'][nm]['envs']
            a = [s3[en]['point']['m_M'] for en in sorted(s3)]
            b = [s3[en]['point']['m_M_sym'] for en in sorted(s3)]
            print(f"- {nm}: m_M — среднее {r(sum(a) / len(a), 4, True)}, симметричная версия m_M_sym — среднее {r(sum(b) / len(b), 4, True)}; "
                  f"знак совпал в {sum((x > 0) == (y > 0) for x, y in zip(a, b))} средах из {len(a)}; наибольшая |разность| {r(max(abs(x - y) for x, y in zip(a, b)), 6)}")
            pw3 = p3['power'][nm].get('m_M_sym')
            if pw3:
                print(f"  мощность П1-Т в симметричной версии (8 сред теста): «больше» {r(pw3['power']['confirm'], 4)}, «меньше» {r(pw3['power']['refute'], 4)}")
    print('## Направление среднего 8 сред (описательные правила; модель «новая среда»: среднее ~ N(μ, (τ² + s²)/8))')
    from scipy.stats import norm
    desc = {}
    for rule, (meas, kind, part_b) in T.RULES.items():
        if act[rule]:
            continue
        e = pw[meas]
        m = p['power']['test5_thousands']['m_test']
        pr = {t: float(norm.cdf(e['mu'] / math.sqrt((e[t] ** 2 + e['s_test'] ** 2) / m))) for t in ('tau', 'tau_hi')}
        desc[rule] = dict(measure=meas, p_mean_pos=pr['tau'], p_mean_pos_tau_hi=pr['tau_hi'], expect=round(0.95 * pr['tau'], 4), m=m)
        print(f"- {rule} ({meas}): P(среднее > 0) {r(pr['tau'], 4)} при τ пилота, {r(pr['tau_hi'], 4)} при τ из верхней границы → ожидание "
              f"{r(0.95 * pr['tau'], 4)} (0,95 × P)")
    for rule, kind in T.AB_RULES.items():
        src = {'prog': 'АБ-П-Т', 'shape': 'АБ-Ф-Т'}[kind]
        mp = e3[src]['power_min']
        exp[rule] = dict(kind=kind, power_min_d3=mp, active=True, expect=round(0.95 * mp, 4),
                         bits_yes=round(math.log2(mp / LEVEL), 2), bits_no=round(math.log2((1 - mp) / (1 - LEVEL)), 2))
        print(f"- {rule} (повтор DISTILL-03, {kind}): наименьшая мощность DISTILL-03 {r(mp, 3)} (общий шум — от числа сред не зависит) → ожидание «да» {r(0.95 * mp, 4)}; "
              f"вес «да» {r(exp[rule]['bits_yes'], 2, True)} бит, «нет» {r(exp[rule]['bits_no'], 2, True)} бит")
    print('## Другие наборы пилота 2 (уже виденные ответы; описательно): среднее мер по средам')
    for name in ('test5_length', 'new5_thousands', 'new5_length'):
        s = p['sets'][name]['envs']
        print(f"- {name} ({len(s)} сред): " + '; '.join(f"{meas} {r(sum(v['point'][meas] for v in s.values()) / len(s), 4, True)}" for meas in ('m_M', 'top3', 'm_MT')))
    print('## Родство весов операторов (построение; то же построение и код дадут те же веса в тесте)')
    for fam in ('thousands', 'length'):
        k = T.op_kinship(p['weights'][fam])
        print(f"- {fam}: родич ближе среднего чужих у {k['n_kin_closer']} голов из {k['n']}; " +
              '; '.join(f"{SHORT[x['head']]} → {SHORT[x['kin']]} {r(x['tv_kin'], 3)} против {r(x['tv_others'], 3)}" for x in k['pairs']))
    ok = T.RULES_ACTIVE is not None and all(T.RULES_ACTIVE[k] == act[k] for k in act)
    print('## Замок: test_d4.RULES_ACTIVE совпадает с правилом активности —', ok)
    if '--write' in a:
        json.dump(dict(rule='0,95 × решающая мощность пилота 2 (test5) / наименьшая мощность DISTILL-03 для A-на-B', power_min=POWER_MIN, level=LEVEL,
                       pilot='gha_out/distill04_pilot2/pilot.json', rules=exp, descriptive=desc),
                  open(os.path.join(HERE, 'expect_d4.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('записано expect_d4.json')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
