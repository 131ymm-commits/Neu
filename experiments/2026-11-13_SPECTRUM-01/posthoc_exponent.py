#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01, пост-хок (14.11.2026, после отчёта и совета 49; вердикт SPECTRUM-01 не меняет).
Задание совета 49 (опись, SPECTRUM-02, «сначала, без нового прогона»):
  1) показатель α по блокам: t ∝ λ^(−α), α_b = ln(t0/t1) / ln(λ1/λ0), с бутстреп-ДИ медианы по блокам;
  2) объясняет ли логарифмическая поправка Сакса ln(s/m0) при фактической инициализации отношение к теории 0,929.
Источник чисел — run/analysis.json (меры групп, посчитанные analyze_spectrum01.py до этого анализа).
  t_align: q = 1 (вход 64) против q0_d64 (вход 64), λ1 = λ_S(q = 1), λ0 = λ_max(q0_d64) — как в P3;
  t½ «я» (поведение): первый шаг, где R² объекта SELF ≥ ½ потолка OLS; λ1 = λ_S(q = 1), λ0 = λ_S(q0_d64).
Поправка Сакса: двухслойная линейная сеть, малая инициализация σ, шаг η, отбелённый вход. Сила моды m(t) растёт
  логистически; время до доли θ насыщения t ≈ ln(θ·s/m0)/(2ηs) (Saxe и др., 2014, по памяти: решение для
  сбалансированных весов). m0 ≈ h·σ²/2 — начальная проекция при случайных весах (мой вывод, не сверялся с источником).
  Отношение времён двух мод: (s1/s0)·ln(θ·s0/m0)/ln(θ·s1/m0); множитель при √λ — ln(θ·s0/m0)/ln(θ·s1/m0).
  python3 posthoc_exponent.py → run/posthoc_exponent.json"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIGMA, ETA = 1e-3, 0.1                    # богатый режим SPECTRUM-01 = lin2_small SELF-02: init 1e-3, шаг 0,1
WIDTHS = [32, 48, 64, 96]
THETA_R2 = 1 - np.sqrt(0.5)               # R²/потолок = 1 − (1 − m/s)² = ½  ⇒  m/s = 1 − √½ ≈ 0,293


def boot(v, seed=11, reps=10000):
    v = np.asarray(v, float)
    g = np.random.default_rng(seed)
    bs = [np.median(v[g.integers(0, len(v), len(v))]) for _ in range(reps)]
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def main():
    a = json.load(open(os.path.join(HERE, 'run', 'analysis.json'), encoding='utf-8'))
    idx = {(m['block'], m['q'], m['regime'], m['d_nuis'], m['extra']): m for m in a['measures']}
    blocks = sorted({m['block'] for m in a['measures']})
    rows = []
    for b in blocks:
        g1, g0 = idx[(b, 1.0, 'rich', 52, 0)], idx[(b, 0.0, 'rich', 52, 2)]
        l1, l0max, l0S = g1['lam']['S'], max(g0['lam'].values()), g0['lam']['S']
        t1, t0 = g1['t_align'], g0['t_align']
        h1, h0 = g1['t_half_obj'][0], g0['t_half_obj'][0]
        rows.append(dict(block=b, t1=t1, t0=t0, lam1=l1, lam0_max=l0max, lam0_S=l0S,
                         alpha_align=float(np.log(t0 / t1) / np.log(l1 / l0max)),
                         t_half_self_q1=h1, t_half_self_q0=h0,
                         alpha_behav=float(np.log(h0 / h1) / np.log(l1 / l0S)),
                         lam_q1={k: g1['lam'][k] for k in ('S', 'O', 'B')}, t_half_q1=g1['t_half_obj']))
    aa = [r['alpha_align'] for r in rows]
    ab = [r['alpha_behav'] for r in rows]
    # поправка Сакса при фактической инициализации: множитель при √λ для t_align (θ неизвестна — две крайние доли)
    s1 = np.sqrt(np.median([r['lam1'] for r in rows]))
    s0 = np.sqrt(np.median([r['lam0_max'] for r in rows]))
    saxe = {}
    for h in (WIDTHS[0], WIDTHS[-1]):
        m0 = h * SIGMA ** 2 / 2
        for name, th in (('theta_0.293', THETA_R2), ('theta_1', 1.0)):
            f = float(np.log(th * s0 / m0) / np.log(th * s1 / m0))
            saxe[f'h{h}_{name}'] = dict(m0=m0, s0_over_m0=float(s0 / m0), factor=f,
                                         alpha_eff=float(np.log(s1 / s0 * f) / np.log(s1 ** 2 / s0 ** 2)))
    obs_rel = float(np.median([r['t0'] / r['t1'] / np.sqrt(r['lam1'] / r['lam0_max']) for r in rows]))
    d = np.log(s1 / s0)
    L_needed = obs_rel * d / (1 - obs_rel)                 # ln(s0/m0), при котором множитель = наблюдаемому
    # абсолютное время t½ «я» по Саксу (θ = 0,293) против наблюдаемого — для каждой ширины, при q = 1 и q0_d64
    t_pred = {f'h{h}': {'q1': float(np.log(THETA_R2 * s / (h * SIGMA ** 2 / 2)) / (2 * ETA * s))
                        for s in [np.sqrt(np.median([r['lam1'] for r in rows]))]} for h in (WIDTHS[0], WIDTHS[-1])}
    for h in (WIDTHS[0], WIDTHS[-1]):
        sS0 = np.sqrt(np.median([r['lam0_S'] for r in rows]))
        t_pred[f'h{h}']['q0_d64'] = float(np.log(THETA_R2 * sS0 / (h * SIGMA ** 2 / 2)) / (2 * ETA * sS0))
    # внутри q = 1: три моды (S, O, B) в одном прогоне — показатель поведения по наклону ln t½ на ln λ
    slopes = []
    for r in rows:
        lam = [r['lam_q1']['S'], r['lam_q1']['O'], r['lam_q1']['B']]
        th = [r['t_half_q1'][0], r['t_half_q1'][2], r['t_half_q1'][4]]      # SELF, OTHER, OBJECT
        slopes.append(float(-np.polyfit(np.log(lam), np.log(th), 1)[0]))
    out = dict(
        note='пост-хок после отчёта и совета 49; вердикт SPECTRUM-01 не меняет; числа — из run/analysis.json',
        rows=rows,
        alpha_align=dict(median=float(np.median(aa)), ci95=boot(aa), min=float(min(aa)), max=float(max(aa))),
        alpha_behav_self=dict(median=float(np.median(ab)), ci95=boot(ab), min=float(min(ab)), max=float(max(ab))),
        alpha_behav_within_q1=dict(median=float(np.median(slopes)), ci95=boot(slopes), min=float(min(slopes)), max=float(max(slopes))),
        saxe_log=dict(s1=float(s1), s0=float(s0), observed_rel=obs_rel, ln_s0_over_m0_needed=float(L_needed),
                      s0_over_m0_needed=float(np.exp(L_needed)), at_actual_init=saxe),
        t_half_self_pred=t_pred,
        t_half_self_obs=dict(q1=float(np.median([r['t_half_self_q1'] for r in rows])),
                             q0_d64=float(np.median([r['t_half_self_q0'] for r in rows]))))
    json.dump(out, open(os.path.join(HERE, 'run', 'posthoc_exponent.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('α (t_align):', out['alpha_align'])
    print('α (t½ «я», поведение):', out['alpha_behav_self'])
    print('α (поведение, три моды внутри q = 1):', out['alpha_behav_within_q1'])
    print('поправка Сакса:', json.dumps(out['saxe_log'], ensure_ascii=False))
    print('t½ «я»: предсказание', t_pred, '| наблюдение', out['t_half_self_obs'])


if __name__ == '__main__':
    main()
