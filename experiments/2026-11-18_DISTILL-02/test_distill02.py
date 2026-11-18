#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: проверки кода на заглушках (без настоящих ответов голов). Ожидания — из построения миров (ERRORS № 181, 204).
  python3 test_distill02.py        печатает ✓/✗ по каждой проверке и «провалов: N»"""
import json
import math
import os
import sys
import tempfile

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import distill02 as D  # noqa: E402

fails = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + ('' if ok else f'  [{info}]'), flush=True)
    if not ok:
        fails.append(name)


rng = np.random.default_rng(1)

# 0. Замок констант PREREG: RULES_ACTIVE — либо None (до регистрации: анализ теста не идёт), либо ровно правило активности PREREG §5,
# посчитанное по prereg_power_d2.json, и то же, что записано там
RA0 = D.RULES_ACTIVE
if RA0 is None:
    check('константы PREREG: до регистрации RULES_ACTIVE не задан (анализ теста не пойдёт)', True)
else:
    import prereg_power_d2 as PP  # noqa: E402
    pwj = json.load(open(os.path.join(X_DIR, 'prereg_power_d2.json'), encoding='utf-8'))
    act0, _ = PP.active_rules(pwj['rules'])
    check('замок констант: RULES_ACTIVE в distill02.py = правило активности PREREG §5 по prereg_power_d2.json = записанному там',
          RA0 == act0 == pwj['active'] and set(RA0) == set(D.RULES), json.dumps([RA0, pwj['active']], ensure_ascii=False))

# 1. Переносы: тот же узор, что ocdiv4.kappa; ⌊Φ_j⌋ — перенос в разряд j (второй способ правды)
ok_k, ok_phi = True, True
for _ in range(3000):
    a, b = int(rng.integers(100, 10 ** 6)), int(rng.integers(10, 100))
    cj = [j for j, _ in D.carry_info(a, b)]
    kap = D.C4.kappa(a, b)
    ok_k &= cj == [k + 1 for k, v in enumerate(kap) if v]
    for j in range(1, len(str(a + b)) + 1):
        ok_phi &= (math.floor(D.carry_potential(a, b, j) + 1e-12) == 1) == (j in cj)
check('переносы: тот же узор, что ocdiv4.kappa (3000 пар)', ok_k)
check('потенциал Φ_j (Wen и др.): ⌊Φ_j⌋ = перенос в разряд j (3000 пар)', ok_phi)
check('1987 + 45: переносы в 1, 2 (порождены) и 3 (протянут); Φ = 1,2 / 1,32 / 1,032',
      D.carry_info(1987, 45) == [(1, True), (2, True), (3, False)] and abs(D.carry_potential(1987, 45, 3) - 1.032) < 1e-12)

# 2. Разбор смещения
check('смещение → потерянные переносы: −100 → (2,), −110 → (1, 2), −100 без переноса в 2 → прочее, +10 → прочее, 0 → верно',
      D.lost_set(-100, [1, 2, 3]) == (2,) and D.lost_set(-110, [1, 2, 3]) == (1, 2) and D.lost_set(-100, [1, 3]) is None
      and D.lost_set(10, [1]) is None and D.lost_set(0, []) == () and D.lost_set(D.NC + 2, [1]) is None)


# 3. Мир «голова — программа»: задачи как в «тысячах», программа задана, прочие ошибки — смещение +7·10^k
def items_thousands(n, Xs, seed):
    g = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        X = int(g.choice(Xs))
        a, b = int(100 * X + g.integers(0, 100)), int(g.integers(10, 100))
        out.append(dict(a=a, b=b, sum=a + b, ood=int(a + b >= 100 * (X + 1))))
    return out


TRUE = dict(features=['top', 'prop'], w=[-2.5, 2.0, 1.5], w_round=[-2.5, 2.0, 1.5], eps=0.05,
            q={7: 1 / 3, 70: 1 / 3, 700: 1 / 3}, q_rest=0.0)          # «прочие» — +7·10^k, k = 0…2, как в head_answers


def head_answers(items, prog, seed, other=lambda it, g: 7 * 10 ** int(g.integers(0, 3)), none_rate=0.01):
    g = np.random.default_rng(seed)
    out = []
    for it in items:
        if g.random() < none_rate:
            out.append(D.NC)
            continue
        if g.random() < prog['eps']:
            out.append(int(other(it, g)))
            continue
        off = 0
        for r in D.position_features(it['a'], it['b'], it['ood']):
            if g.random() < D.p_drop(prog, r):
                off -= 10 ** r['j']
        out.append(off)
    return np.array(out, np.int64)


build, fresh = items_thousands(4000, [19, 29, 49, 69, 89], 11), items_thousands(3000, [19, 29, 49, 69, 89], 12)
ob, of = head_answers(build, TRUE, 21), head_answers(fresh, TRUE, 22)
prog = D.fit_program(build, ob)
check('программа: признаки «старший перенос» и «протянут» выбраны, коэффициенты около заложенных (±0,35)',
      set(prog['features']) >= {'top', 'prop'} and abs(prog['w'][0] + 2.5) < 0.35
      and all(abs(prog['w'][1 + prog['features'].index(f)] - v) < 0.35 for f, v in (('top', 2.0), ('prop', 1.5))),
      json.dumps({k: prog[k] for k in ('features', 'w', 'eps')}))
check('программа: ε около заложенной доли прочих ошибок 0,05', abs(prog['eps'] - 0.05) < 0.015, str(prog['eps']))
dsum = D.program_dist(prog, fresh[0])
check('распределение программы на задаче суммируется к 1 − ε', abs(sum(dsum.values()) - (1 - prog['eps'])) < 1e-9)
om, box, phi = D.offset_model(build, ob), D.box_fit(build, ob), D.fit_program(build, ob, fixed=D.PHI_BASE)
sc = D.head_scores(prog, om, box, fresh, of, phi=phi)
check('мир «голова — программа»: на свежих задачах программа лучше B0, B1 и Φ-базы по лог-вероятности ответа',
      sc['prog'] > sc['b0'] and sc['prog'] > sc['b1'] and sc['prog'] > sc['phi'], json.dumps({k: sc[k] for k in ('prog', 'b0', 'b1', 'phi', 'box')}))
check('мир «голова — программа»: доля неверных ответов, названных программой в трёх самых вероятных, не меньше, чем у B1',
      sc['hit_prog'] >= sc['hit_b1'], f"{sc['hit_prog']:.3f} против {sc['hit_b1']:.3f}")
expl = (sc['prog'] - sc['b1']) / (sc['box'] - sc['b1']) if sc['box'] > sc['b1'] else float('nan')
check('мир «голова — программа»: доля объяснимого против ящика больше 0,8', expl > 0.8, str(expl))
check('оценщик: AUC P(верно) программы больше 0,5 на свежих задачах', sc['auc_prog'] > 0.5, str(sc['auc_prog']))

# 4. Мир «смещения без связи со входом»: неверный ответ — всегда −100 (и там, где переноса в сотни нет) — B1 лучше программы
ob2 = np.array([0 if g < 0.7 else -100 for g in np.random.default_rng(31).random(len(build))])
of2 = np.array([0 if g < 0.7 else -100 for g in np.random.default_rng(32).random(len(fresh))])
p2, om2 = D.fit_program(build, ob2), D.offset_model(build, ob2)
sc2 = D.head_scores(p2, om2, None, fresh, of2)
check('мир «смещение без связи со входом»: B1 лучше программы (программа не может назвать −100 без переноса в сотни)',
      sc2['b1'] > sc2['prog'], json.dumps({k: sc2[k] for k in ('prog', 'b1')}))

# 5. Совпадение: головы-программы, независимые при данном входе, → отношения около 1; общий «прочий» ответ → K больше
heads = [dict(TRUE, w=[-2.5 + 0.2 * k, 2.0, 1.5], w_round=[-2.5 + 0.2 * k, 2.0, 1.5]) for k in range(5)]
Dm = np.column_stack([head_answers(fresh, h, 40 + k) for k, h in enumerate(heads)])
co = D.coincidence_env(heads, fresh, Dm, 20, np.random.default_rng(5))
check('совпадение: при программах, независимых при данном входе, K и F наблюдённые / из программ — в [0,85; 1,15]',
      0.85 <= co['K_ratio'] <= 1.15 and 0.85 <= co['F_ratio'] <= 1.15, json.dumps(co))
shared = np.random.default_rng(6).random(len(fresh)) < 0.15
Dm2 = Dm.copy()
for k in range(Dm2.shape[1]):
    Dm2[shared & (Dm2[:, k] < D.NC), k] = 70                      # общий для задачи «прочий» ответ сверх программ
co2 = D.coincidence_env(heads, fresh, Dm2, 20, np.random.default_rng(5))
check('совпадение: общий «прочий» ответ сверх программ поднимает K наблюдённое, K из программ не меняется (±0,02), отношение K растёт',
      co2['K_obs'] > co['K_obs'] + 0.05 and abs(co2['K_prog'] - co['K_prog']) < 0.02 and co2['K_ratio'] > co['K_ratio'], json.dumps([co, co2]))
check('AUC: 1 при полном разделении, 0,5 при равных оценках', D.auc([0.1, 0.9, 0.8], [0, 1, 1]) == 1.0 and D.auc([0.5, 0.5], [0, 1]) == 0.5)

# 6. Сухой прогон цепочки: сборка в виде answers.json (как `analyze_ocshift.load_new`), пилот целиком
tmp = tempfile.mkdtemp(prefix='distill02_stub_')


def write_merged(path, env_specs, heads_progs, seed):
    os.makedirs(path, exist_ok=True)
    envs, hs = [], []
    for name, X, n in env_specs:
        its = items_thousands(n, [X], seed + X)
        envs.append(dict(name=name, family='thousands', X=X, p=3, bound=100 * (X + 1), max_new=6,
                         problems=[dict(a=it['a'], b=it['b'], sum=it['sum'], range='ID' if not it['ood'] else 'OOD') for it in its]))
    for k, hp in enumerate(heads_progs):
        cols = {}
        for e in envs:
            its = [dict(a=p['a'], b=p['b'], sum=p['sum'], ood=int(p['range'] != 'ID')) for p in e['problems']]
            offs = head_answers(its, hp, seed + 100 * k + len(e['problems']))
            ans = [None if o >= D.NC else it['sum'] + int(o) for it, o in zip(its, offs)]
            cols[e['name']] = dict(answer=ans, correct=[int(x is not None and x == it['sum']) for x, it in zip(ans, its)],
                                   logp=[float(-1.0 if x == it['sum'] else -3.0) for x, it in zip(ans, its)], n_tok=[4] * len(its))
        hs.append(dict(model=f'stub/head{k}', revision='0' * 40, cols=cols))
    json.dump(dict(envs=envs, heads=hs), open(os.path.join(path, 'answers.json'), 'w'), ensure_ascii=False)


write_merged(os.path.join(tmp, 'fit'), [('T_X19_p3', 19, 600), ('T_X49_p3', 49, 600)], heads[:4], 70)
write_merged(os.path.join(tmp, 'eval'), [('T_X29_p3', 29, 800), ('T_X69_p3', 69, 800)], heads[:4], 90)
out = D.pilot(os.path.join(tmp, 'pilot.json'), {'thousands': (os.path.join(tmp, 'fit'), None), 'T_low': (os.path.join(tmp, 'fit'), ['T_X19_p3'])},
              {'новые X': ('thousands', [os.path.join(tmp, 'eval')], None), 'перенос': ('T_low', [os.path.join(tmp, 'eval')], ['T_X69_p3'])}, R=5)
sm = out['eval']['новые X']['summary']
check('сухой прогон: пилот собирает формулы четырёх голов, Φ-базу и сводку по двум средам проверки; построение по части сред (П4)',
      len(out['formulas']['thousands']) == 4 and len(out['formulas_phi']['thousands']) == 4 and sm['n_cells'] == 8
      and set(out['eval']['новые X']['envs']) == {'T_X29_p3', 'T_X69_p3'} and out['fit_envs']['T_low'] == ['T_X19_p3']
      and set(out['eval']['перенос']['envs']) == {'T_X69_p3'}, json.dumps(sm, default=float)[:300])
check('сухой прогон: в мире «головы — программы» программа лучше B1 в каждой из 8 пар «голова × среда»',
      sm['prog_minus_b1_pos'] == 8 and sm['prog_minus_b1_mean'] > 0, json.dumps(sm, default=float)[:300])
check('сухой прогон: вывод пилота — json без NaN в формулах', all(np.isfinite(v) for f in out['formulas']['thousands'].values() for v in f['w']))

# 7. Смесь λ (совет 74, п. 1): ответ с p = 0 даёт log(λ/|V|); λ = 0 — прежняя обрезка 1e-300
Vt = D.ref_size(2045)
check('смесь: p = 0 → log(λ/|V|) при λ = 1e-3; p = 1 → log(1 − λ + λ/|V|); λ = 0 → обрезка 1e-300; |V| для суммы из 4 цифр = 10^5 − 10^1',
      abs(float(D.mixed_log(0.0, Vt)) - math.log(D.LAMBDA / Vt)) < 1e-12 and abs(float(D.mixed_log(1.0, Vt)) - math.log(1 - D.LAMBDA + D.LAMBDA / Vt)) < 1e-12
      and float(D.mixed_log(0.0, Vt, 0.0)) == math.log(1e-300) and Vt == 10 ** 5 - 10 and D.LAMBDA == 1e-3,
      f'{float(D.mixed_log(0.0, Vt))} {math.log(D.LAMBDA / Vt)}')

# 8. Φ-база: та же «прочая» часть, что у программы (совет 74, п. 11 — скептик); программа = Φ-база → m1_phi = 0
fit_s = D.fit_family(list(D.load_merged(os.path.join(tmp, 'fit')).values()))
h0 = sorted(fit_s)[0]
check('Φ-база и программа: одни ε, частоты «прочих» смещений и остаток (fit_program с fixed=PHI_BASE)',
      all(fit_s[h]['phi']['eps'] == fit_s[h]['prog']['eps'] and fit_s[h]['phi']['q'] == fit_s[h]['prog']['q']
          and fit_s[h]['phi']['q_rest'] == fit_s[h]['prog']['q_rest'] for h in fit_s))
env_s = D.load_merged(os.path.join(tmp, 'eval'))['T_X29_p3']
fit_eq = {h: dict(f, prog=f['phi']) for h, f in fit_s.items()}
rb, rp = D.env_seed(1, 'T_X29_p3', 'проверка')
ea_eq = D.env_arrays(fit_eq, env_s)
em_eq, _ = D.env_measures(ea_eq, 20, rb, rp, 3)
check('программа = Φ-база → m1_phi = 0 точно (точка и все повторы)', em_eq['point']['m1_phi'] == 0.0 and em_eq['sd']['m1_phi'] == 0.0,
      json.dumps(em_eq['point'], default=float)[:200])
PHI_TRUE = dict(features=['phi'], w=[-1.0, 6.0], w_round=[-1.0, 6.0], eps=0.05, q={7: 1 / 3, 70: 1 / 3, 700: 1 / 3}, q_rest=0.0)
b_phi = items_thousands(6000, [19, 29, 49, 69, 89], 61)
f_phi = items_thousands(3000, [19, 29, 49, 69, 89], 62)
o_bp, o_fp = head_answers(b_phi, PHI_TRUE, 63), head_answers(f_phi, PHI_TRUE, 64)
pp, pf = D.fit_program(b_phi, o_bp), D.fit_program(b_phi, o_bp, fixed=D.PHI_BASE)
sc_phi = D.head_scores(pp, D.offset_model(b_phi, o_bp), None, f_phi, o_fp, phi=pf)
check('мир «голова — Φ-база»: на свежих задачах программа (отбор по BIC) не лучше Φ-базы больше чем на 0,01 нат (|m1_phi| < 0,01)',
      abs(sc_phi['prog'] - sc_phi['phi']) < 0.01 and 'phi' in pp['features'], json.dumps({'prog': sc_phi['prog'], 'phi': sc_phi['phi'], 'f': pp['features']}))

# 9. Выборка программ (метод Уокера) — то же распределение, что program_dist и «прочее» по частотам головы
it0 = fresh[5]
prog_q = dict(TRUE, q={7: 0.5, 70: 0.25}, q_rest=0.25)
D9 = np.zeros((1, 1), np.int64)
S9 = D.env_sampler([prog_q], [it0], D9)
off9, car9 = D.draw_many(S9, np.zeros(400_000, np.int64), np.random.default_rng(9))
dist9 = D.program_dist(prog_q, it0)
v9, tot9 = D.other_valid(prog_q, it0, dist9)
want = {y - it0['sum']: p for y, p in dist9.items()}
want.update({dd: prog_q['eps'] * qq / tot9 for dd, qq in v9.items()})
dev = max(abs(np.mean(off9 == o) - p) / math.sqrt(p * (1 - p) / len(off9) + 1e-12) for o, p in want.items())
rest_mass = 1 - sum(want.values())
in_rest = ~np.isin(off9, list(want))
nd9 = len(str(it0['sum']))
check('выборка программ: частоты опоры и «прочих» смещений — в пределах 5 ст. откл. от вероятностей; «остаток» — с его массой, числа из V '
      'вне опоры; метка «потеря переноса» — только у смещений опоры, кроме 0',
      dev < 5 and abs(in_rest.mean() - rest_mass) < 5 * math.sqrt(rest_mass * (1 - rest_mass) / len(off9))
      and np.all((off9[in_rest] + it0['sum'] >= 10 ** max(nd9 - 3, 0)) & (off9[in_rest] + it0['sum'] < 10 ** (nd9 + 1)))
      and not np.isin(off9[in_rest] + it0['sum'], list(dist9)).any()
      and np.array_equal(car9, np.isin(off9, [o for o in want if o != 0 and o + it0['sum'] in dist9])), f'dev={dev:.2f}')
Ddup, _ = D.sample_D(S9, D9, np.zeros(200, np.int64), 1, np.random.default_rng(10))
check('выборка в повторе: у каждой копии строки — своя выборка (200 копий одной задачи дают разные ответы)', len(np.unique(Ddup)) > 1)

# 10. K и его разбивка (совет 74, п. 5): k_parts = прежний k_stat по парам; Kc — прямым счётом по lost_set
Dm3 = np.column_stack([head_answers(fresh, h, 140 + k) for k, h in enumerate(heads[:4])])
Cm3 = np.zeros(Dm3.shape, bool)
for i, itx in enumerate(fresh):
    cp = [j for j, _ in D.carry_info(itx['a'], itx['b'])]
    for k in range(Dm3.shape[1]):
        Cm3[i, k] = bool(D.lost_set(int(Dm3[i, k]), cp)) if 0 != Dm3[i, k] < D.NC else False


def k_slow(Dx, Cx):
    ks, kcs = [], []
    for i, j in __import__('itertools').combinations(range(Dx.shape[1]), 2):
        both = (Dx[:, i] != 0) & (Dx[:, j] != 0) & (Dx[:, i] < D.NC) & (Dx[:, j] < D.NC)
        if both.any():
            same = both & (Dx[:, i] == Dx[:, j])
            ks.append(same.sum() / both.sum())
            kcs.append((same & Cx[:, i]).sum() / both.sum())
    return np.mean(ks), np.mean(kcs)


kf, kcf = D.k_parts(Dm3[None], Cm3[None])
ks_, kcs_ = k_slow(Dm3, Cm3)
check('K и K «потеря переноса» — как прямой счёт по парам; K «прочие» = K − Kc ≥ 0', abs(kf[0] - ks_) < 1e-12 and abs(kcf[0] - kcs_) < 1e-12 and kf[0] - kcf[0] >= 0,
      f'{kf[0]} {ks_} {kcf[0]} {kcs_}')

# 11. Меры среды: зерно среды, m2 от одного ящика, разбивка m3, хрупкость
fits_s = fit_s
ea = D.env_arrays(fits_s, env_s)
em, reps = D.env_measures(ea, 30, *D.env_seed(3, 'T_X29_p3', 'проверка'), 10)
em2, reps2 = D.env_measures(ea, 30, *D.env_seed(3, 'T_X29_p3', 'проверка'), 10)
check('меры среды: в мире «головы — программы» m1 > 0, m2 > 0,5 (программа — истина), m2 ≥ m2_max, |m3| < 0,15, ст. откл. конечны; '
      'то же зерно (имя, фаза) — те же числа',
      em['point']['m1'] > 0 and em['point']['m2'] > 0.5 and em['point']['m2'] >= em['point']['m2_max'] - 1e-12 and abs(em['point']['m3']) < 0.15
      and all(np.isfinite(em['sd'][k]) for k in ('m1', 'm1_phi', 'm2', 'm3')) and em == em2
      and all(np.array_equal(reps[k], reps2[k], equal_nan=True) for k in reps), json.dumps(em['point'], default=float)[:300])
em3, _ = D.env_measures(ea, 30, *D.env_seed(3, 'T_X29_p3', 'другая фаза'), 10)
check('меры среды: другая фаза — другой поток (повторы другие)', em3['sd']['m1'] != em['sd']['m1'])
check('разбивка m3: K = Kc + Ko в точке', abs(em['point']['K_obs'] - em['point']['Kc_obs'] - em['point']['Ko_obs']) < 1e-12
      and abs(em['point']['K_prog'] - em['point']['Kc_prog'] - em['point']['Ko_prog']) < 1e-12)
con = D.contributions(ea, ea['L'])
check('вклады задач: сумма вкладов «b1» = m1, «phi» = m1_phi', abs(con['b1'].sum() - em['point']['m1']) < 1e-9 and abs(con['phi'].sum() - em['point']['m1_phi']) < 1e-9)
c_flat, c_one = np.full(99, 0.01), np.r_[np.full(99, 0.001), 1.0]
f_flat, f_one = D.concentration(c_flat), D.concentration(c_one)
check('хрупкость: 99 ровных вкладов — наибольший 1/99 суммы, больше половины дают 50 задач из 99; одна задача на 1,0 из 1,099 — больше '
      'половины (хрупкий)', abs(f_flat['top_share'] - 1 / 99) < 1e-12 and abs(f_flat['half_tasks_share'] - 50 / 99) < 1e-12
      and f_one['top_share'] > D.FRAGILE and f_one['half_tasks_share'] == 0.01, json.dumps([f_flat, f_one]))
sens = D.sens_points(ea)
check('чувствительность к λ: точки при λ = 0, 1e-2, 1e-4; при 1e-3 — как основная точка',
      set(sens) == {'0', '0.01', '0.0001'} and abs(D.measures_w(ea, ea['L'], np.ones((1, ea['n'])))['m1'][0] - em['point']['m1']) < 1e-12)

# 12. Строение новых сред (совет 74, п. 3): range у new5 из кода задач — доля вне диапазона около половины, переносы «тысяч» — только в
# разряды 1–3 (как в построении), у L_X9999 — до разряда 6
sys.path.insert(0, X_DIR)
import distill02_extract as XD  # noqa: E402
cs = {e['name']: D.carry_summary([dict(a=p['a'], b=p['b'], sum=p['sum'], ood=int(p['range'] != 'ID')) for p in e['problems']])
      for e in XD.envs_d2('new5')}
check('new5: у T_X109/139/169 доля ood — от 0,45 до 0,65 (не все 1), переносы только в разряды 1–3; у L_X9999 — разряды 1–6; '
      'ood совпадает с переносом в разряд 3 (второй способ)',
      all(0.45 < cs[n]['ood_share'] < 0.65 and set(cs[n]['carry_positions']) == {'1', '2', '3'} for n in ('T_X109_p3', 'T_X139_p3', 'T_X169_p3'))
      and set(cs['L_X9999_p3']['carry_positions']) == {str(j) for j in range(1, 7)}
      and all(abs(cs[n]['ood_share'] - cs[n]['carry_positions']['3'] / 2200) < 1e-12 for n in ('T_X109_p3', 'T_X139_p3', 'T_X169_p3')),
      json.dumps(cs))

# 13. Пилот 3 на той же заглушке
out3 = D.pilot_sets(os.path.join(tmp, 'pilot3.json'), {'thousands': (os.path.join(tmp, 'fit'), None)},
                    {'проверка': ('thousands', [os.path.join(tmp, 'eval')], None)}, R=5, B=20)
pw3 = out3['sets']['проверка']['power']
check('пилот 3: мощность для m1, m1_phi, m2, m2_max и m3; у двустороннего m3 решающая = вверх + вниз; λ записана',
      set(pw3) == {'m1', 'm1_phi', 'm2', 'm2_max', 'm3'} and all(v is not None for v in pw3.values()) and out3['lam'] == D.LAMBDA
      and abs(pw3['m3']['power']['decisive'] - pw3['m3']['power']['confirm'] - pw3['m3']['power']['refute']) < 1e-12, json.dumps(pw3, default=float)[:300])

# 14. Анализ теста: без констант не идёт; с константами — вердикты всех правил; частичный json; «выкинуть среду»; детерминизм
write_merged(os.path.join(tmp, 'cons'), [('T_X19_p3', 19, 500), ('T_X49_p3', 49, 500), ('L_X9_p3', 29, 500), ('L_X99_p3', 69, 500)], heads[:4], 110)
write_merged(os.path.join(tmp, 't5'), [('T_X19_p3', 19, 400), ('T_X29_p3', 29, 400), ('T_X49_p3', 49, 400), ('T_X69_p3', 69, 400),
                                       ('L_X9_p3', 39, 400), ('L_X99_p3', 59, 400), ('L_X999_p3', 79, 400)], heads[:4], 130)
write_merged(os.path.join(tmp, 'n5'), [('T_X109_p3', 89, 400), ('T_X139_p3', 39, 400), ('T_X169_p3', 59, 400)], heads[:4], 150)
spec_t = ({'thousands': [os.path.join(tmp, 'cons')], 'length': [os.path.join(tmp, 'cons')]},
          {'test5': [os.path.join(tmp, 't5')], 'new5': [os.path.join(tmp, 'n5')]})
D.RULES_ACTIVE = None
try:
    D.test_d2(os.path.join(tmp, 'test_x.json'), *spec_t, B=10, R=3)
    no_c = False
except AssertionError:
    no_c = True
check('анализ теста без констант PREREG не идёт', no_c)
D.RULES_ACTIVE = {r: True for r in D.RULES}
pd_ = os.path.join(tmp, 'parts')
ta = D.test_d2(os.path.join(tmp, 'test_d2.json'), *spec_t, B=20, R=3, part_dir=pd_, no_time=True)
check('анализ теста: вердикты всех 10 правил (с Р4Ф-Т), среды обеих фаз, описательное m2_max и разбивка m3, хрупкость и λ у правил; '
      'в мире «головы — программы» Р1-Т — среднее m1 > 0',
      set(ta['verdicts']) == set(D.RULES) and len(ta['envs']) == 10 and {'thousands m2_max', 'thousands m3_c', 'thousands m3_o'} <= set(ta['descr'])
      and ta['rules']['Р1-Т']['delta'] > 0 and ta['rules']['Р1-Т']['fragile'] is not None and 'lambda_sens' in ta['rules']['Р4Ф-Т']
      and len(os.listdir(pd_)) == 10 and 'seconds' not in ta, json.dumps(ta['verdicts'], ensure_ascii=False))
t_again = D.test_d2(os.path.join(tmp, 'test_d2b.json'), *spec_t, B=20, R=3, part_dir=pd_, no_time=True)
check('частичный json: повторный запуск берёт готовые среды и даёт побайтно тот же вывод',
      open(os.path.join(tmp, 'test_d2.json'), 'rb').read() == open(os.path.join(tmp, 'test_d2b.json'), 'rb').read())
t_only = D.test_d2(os.path.join(tmp, 'test_only.json'), *spec_t, B=20, R=3, only=['T_X29_p3', 'L_X9_p3'], no_time=True)
check('«выкинуть среды»: у оставшихся сред те же точки и ст. откл., что в полном анализе (зерно — имя и фаза среды)',
      all(t_only['envs'][n]['point'] == ta['envs'][n]['point'] and t_only['envs'][n]['sd'] == ta['envs'][n]['sd'] for n in ('T_X29_p3', 'L_X9_p3')))
runner = os.path.join(tmp, 'run_workers.py')                      # процессы «spawn» заново читают главный модуль — отдельный запуск с защитой
open(runner, 'w', encoding='utf-8').write(
    'import json, sys\n'
    f'sys.path.insert(0, {X_DIR!r})\n'
    'import distill02 as D\n'
    "if __name__ == '__main__':\n"
    '    D.RULES_ACTIVE = {r: True for r in D.RULES}\n'
    f'    D.test_d2({os.path.join(tmp, "test_w.json")!r}, *json.loads({json.dumps(spec_t)!r}), B=20, R=3, no_time=True, workers=2)\n')
import subprocess  # noqa: E402
rw = subprocess.run([sys.executable, runner], capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
check('параллельный счёт сред (2 процесса «spawn») — побайтно тот же вывод', rw.returncode == 0 and open(os.path.join(tmp, 'test_w.json'), 'rb').read() ==
      open(os.path.join(tmp, 'test_d2.json'), 'rb').read(), rw.stderr[-300:])
D.RULES_ACTIVE = None

print(f'провалов: {len(fails)}')
