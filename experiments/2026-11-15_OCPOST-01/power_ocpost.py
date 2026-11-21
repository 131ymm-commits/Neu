#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: мощность и ожидания до регистрации — счёт по сводкам пилота (gha_out/ocpost_pilot). python3 power_ocpost.py
P0–P3, N: мощность из pilot_envs.json (ocpost.pilot) — модель «новая среда» (точка ~ N(mu, (tau² + s²)/5), полуширина M4 = z·s/√5)
  и перебор 32 наборов «одна среда на диапазон» из десяти сред OCSHIFT-01.
Т: три способа для каждой статистики и стороны при размере теста (60 миров × 200 опытов, B = 200):
  (а) апостериорный: доля промахов ~ Beta(x + ½, n − x + ½) по пилотным мирам, счёт теста ~ Bin(N, p); стороны и статистики
      считаются независимыми (приближение: в одном опыте они связаны);
  (б) нормальный: промах снизу ≈ Φ̄(z·r − d), сверху ≈ Φ̄(z·r + d), r — ст. откл. повторов / истинное, d — смещение точки
      в единицах истинного ст. откл. (по пилотным мирам); шум ст. откл. при B повторах — сдвигом r на множитель (1 + ε),
      ε ~ N(0, 1 / (2(B − 1))), усреднением по ε (тяжёлых хвостов не видит);
  (в) Стьюдент: t = (точка − правда) / ст. откл. повторов по всем опытам пилотных миров (B — как в тесте); t ~ s_t·T_ν/√(ν/(ν−2)),
      ν = 4 + 6/κ по эксцессу κ (ν ≤ 300), промах на сторону — P(t > z); стороны и статистики — независимо. Ожидание E7 — этот способ:
      (а) завышает неопределённость (400 опытов, Джеффрис, независимость), (б) не видит эксцесса +0,4…+0,5 в пилоте.
Вывод — expect_ocpost.json и консоль."""
import json
import os
import sys

import numpy as np
from scipy.stats import binom, kurtosis, norm, skew
from scipy.stats import t as student

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault('OCPOST_IMPORT_ONLY', '1')
import ocpost as P  # noqa: E402

PIL = os.path.join(ROOT, 'gha_out', 'ocpost_pilot')
N_WORLDS, N_EXP, B_T = 60, 200, 200
P_METHOD = 0.95                       # вероятность, что метод опыта сработает (извлечение, сверка, годные среды) — по суждению
N_T = N_WORLDS * N_EXP
R = 20000
g = np.random.default_rng(7_880_000)


def tail_verdict(xs, n):
    """xs — список (промахов снизу, сверху) по статистикам P0–P3, N; правило ocpost.tail."""
    conf = all(P.cp(a, n, P.LEVEL, 'hi') < P.TAIL_MAX and P.cp(b, n, P.LEVEL, 'hi') < P.TAIL_MAX for a, b in xs)
    refu = any(P.cp(a, n, P.LEVEL / 10, 'lo') > P.TAIL_MAX or P.cp(b, n, P.LEVEL / 10, 'lo') > P.TAIL_MAX for a, b in xs)
    return 'подтверждено' if (conf and not refu) else ('опровергнуто' if refu else 'не решено')


def crit(n):
    xc = max(x for x in range(0, 400) if P.cp(x, n, P.LEVEL, 'hi') < P.TAIL_MAX)
    xr = min(x for x in range(0, 800) if P.cp(x, n, P.LEVEL / 10, 'lo') > P.TAIL_MAX)
    return xc, xr


def main():
    pe = json.load(open(os.path.join(PIL, 'pilot_envs.json'), encoding='utf-8'))
    pt = json.load(open(os.path.join(PIL, 'pilot_tail.json'), encoding='utf-8'))
    pw = json.load(open(os.path.join(PIL, 'pilot_worlds.json'), encoding='utf-8'))
    out = dict(source='gha_out/ocpost_pilot', n_t=N_T, b_t=B_T, n_worlds=N_WORLDS, n_exp=N_EXP, rules={}, tail={})
    for k, v in pe['power'].items():
        out['rules'][k] = dict(power_confirm_model=v['power_confirm'], power_refute_model=v['power_refute'], mu=v['mu'], tau=v['tau'], s_rms=v['s_rms'],
                               subsets=v.get('subsets'))
        # совет 64, п. 6: τ по десяти средам обрезана по нулю (у P3 и N τ = 0) — мощность и при τ = s
        cs_, rs_ = P.power_one(v['kind'], v['mu'], max(v['tau'], v['s_rms']), v['s_rms'], pe['m_new'])
        out['rules'][k]['power_confirm_tau_s'], out['rules'][k]['power_refute_tau_s'] = cs_, rs_
        if v['kind'] == 'sign':                    # та же модель, но с предохранителем «без одного диапазона» (5 сред — 5 диапазонов)
            m = pe['m_new']
            d = g.normal(v['mu'], v['tau'], (R, m)) + g.normal(0, v['s_rms'], (R, m))
            mean = d.mean(1)
            h = P.Z * v['s_rms'] / np.sqrt(m)
            loo = (d.sum(1, keepdims=True) - d) / (m - 1)
            holds = (np.sign(loo) == np.sign(mean)[:, None]).all(1)
            out['rules'][k]['power_confirm_guard'] = float(np.mean((mean + h < 0) & holds))
            out['rules'][k]['power_refute_guard'] = float(np.mean((mean - h > 0) & holds))
    xc, xr = crit(N_T)
    out['tail']['x_confirm_max'], out['tail']['x_refute_min'] = xc, xr
    # (а) апостериорный
    post = {}
    for s in P.RULES:
        e = pt['stats'][s]
        post[s] = [(e['miss_low'], e['n']), (e['miss_high'], e['n'])]
    cnt = {'подтверждено': 0, 'опровергнуто': 0, 'не решено': 0}
    pass_one = {s: [0, 0] for s in P.RULES}
    for _ in range(R):
        xs = []
        for s in P.RULES:
            row = []
            for side, (x, n) in enumerate(post[s]):
                p = g.beta(x + 0.5, n - x + 0.5)
                X = int(g.binomial(N_T, p))
                row.append(X)
                pass_one[s][side] += X <= xc
            xs.append(tuple(row))
        okc = all(a <= xc and b <= xc for a, b in xs)
        okr = any(a >= xr or b >= xr for a, b in xs)
        cnt['подтверждено' if (okc and not okr) else ('опровергнуто' if okr else 'не решено')] += 1
    out['tail']['posterior'] = dict(**{k: v / R for k, v in cnt.items()}, pass_one={s: [x / R for x in v] for s, v in pass_one.items()},
                                    pilot_misses={s: dict(low=post[s][0][0], high=post[s][1][0], n=post[s][0][1]) for s in P.RULES})
    # (б) нормальный
    eps = g.normal(0, 1 / np.sqrt(2 * (B_T - 1)), 4000)
    nm = {}
    prob_all = 1.0
    for si, s in enumerate(P.TAIL_KEYS):
        if s not in P.RULES:
            continue
        r = pt['stats'][s]['sd_ratio_mean']
        # смещение точки: среднее (точка − правда) / истинное ст. откл. по мирам пилота
        d = float(np.mean([(np.mean([p[si] for p in w['point']]) - w['truth'][s]) / max(w['sd_true'][s], 1e-12) for w in pw['worlds']]))
        lo = float(np.mean(norm.sf(P.Z * r * (1 + eps) - d)))
        hi = float(np.mean(norm.sf(P.Z * r * (1 + eps) + d)))
        p_lo, p_hi = binom.cdf(xc, N_T, lo), binom.cdf(xc, N_T, hi)
        prob_all *= p_lo * p_hi
        nm[s] = dict(sd_ratio=r, bias_in_sd=d, rate_low=lo, rate_high=hi, pass_low=float(p_lo), pass_high=float(p_hi))
    out['tail']['normal'] = dict(by_stat=nm, p_confirm_indep=float(prob_all))
    # (в) Стьюдент по эксцессу пилотных t
    st_, prob_t = {}, 1.0
    for si, s in enumerate(P.TAIL_KEYS):
        if s not in P.RULES:
            continue
        tt = np.concatenate([(np.array([p[si] for p in w['point']]) - w['truth'][s]) / np.array([q[si] for q in w['boot_sd']]) for w in pw['worlds']])
        sd_t, ku, sk = float(tt.std(ddof=1)), float(kurtosis(tt)), float(skew(tt))
        nu = float(min(300.0, 4 + 6 / max(ku, 0.02)))
        rate = float(student.sf(P.Z * np.sqrt(nu / (nu - 2)) / sd_t, nu))
        pp = float(binom.cdf(xc, N_T, rate))
        prob_t *= pp ** 2
        st_[s] = dict(n=int(len(tt)), sd_t=sd_t, excess_kurtosis=ku, skew=sk, nu=nu, rate_per_side=rate, pass_per_side=pp,
                      observed_low=int((tt < -P.Z).sum()), observed_high=int((tt > P.Z).sum()))
    out['tail']['student'] = dict(by_stat=st_, p_confirm_indep=float(prob_t))
    # правда в мирах пилота: wc POST и wc FIXED (полоса P3 и N)
    # правило чтения P2 по Брайеру: мощность «POST-CV хуже ONE-BEST по Брайеру» (нижняя граница M4 при 0,0025 > 0) — та же модель
    bk = 'Брайер POST-CV − ONE-BEST'
    xb = np.array([e['descr_env'][bk]['point'] for e in pe['envs'].values() if 'descr_env' in e])
    sb = np.array([e['descr_env'][bk]['sd'] for e in pe['envs'].values() if 'descr_env' in e])
    taub = float(np.sqrt(max(0.0, xb.var(ddof=1) - np.mean(sb ** 2))))
    worse, better = P.power_one('sign', -float(xb.mean()), taub, float(np.sqrt(np.mean(sb ** 2))), pe['m_new'])
    out['brier_reading'] = dict(mu=float(xb.mean()), tau=taub, s_rms=float(np.sqrt(np.mean(sb ** 2))), p_worse=worse, p_better=better)
    # ожидания (для tools/self_calibration.py): вероятность исхода = P_METHOD × мощность (модель «новая среда»)
    rp = out['rules']
    out['expect'] = dict(
        E1_P0_confirm=P_METHOD * rp['P0']['power_confirm_guard'], E2_P1_confirm=P_METHOD * rp['P1']['power_confirm_guard'],
        E3_P2_confirm=P_METHOD * rp['P2']['power_confirm_guard'], E4_P2_refute=P_METHOD * rp['P2']['power_refute_guard'],
        E5_P3_confirm=P_METHOD * rp['P3']['power_confirm_tau_s'], E6_N_confirm=P_METHOD * rp['N']['power_confirm_tau_s'],   # совет 64, п. 6
        E7_T_confirm=out['tail']['student']['p_confirm_indep'], E7_T_confirm_posterior=out['tail']['posterior']['подтверждено'],
        E7_T_confirm_normal=out['tail']['normal']['p_confirm_indep'],
        E8_brier_worse=P_METHOD * worse, p_method=P_METHOD)
    out['worlds_truth'] = {s: dict(mean=float(np.mean(list(pt['stats'][s]['truth_by_world'].values()))),
                                   min=float(np.min(list(pt['stats'][s]['truth_by_world'].values()))),
                                   max=float(np.max(list(pt['stats'][s]['truth_by_world'].values()))))
                           for s in ('P0', 'P3', 'N', 'P1', 'P2')}
    json.dump(out, open(os.path.join(HERE, 'expect_ocpost.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
