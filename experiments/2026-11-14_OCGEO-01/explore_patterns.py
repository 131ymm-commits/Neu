#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01, пост-хок разведка закономерностей (слово автора 14.11.2026: «Давай искать. Я думаю мы сможем найти какие-то
закономерности.»). Вердикты OCGEO-01 не меняет. Каждая мера считается на пилоте (pilot1/out) и на тесте (run/out):
закономерность, которая есть только в одной части, в итог не идёт. Результат → explore_patterns.json.
  1. Вид ошибок вне диапазона: доля неверных ответов с верной цифрой единиц (сдвиг кратен 10), частые сдвиги.
  2. Перенос: P(сдвиг −10 | перенос в единицах) против P(−10 | без переноса); то же для +10.
  3. Граница 100: доля неверных ответов ниже 100 («отступ в знакомый диапазон») по диапазонам суммы; у 100–109 — цифра
     десятков неверного ответа и проверка «копирует десятки слагаемого» против случайного уровня.
  4. Общие ошибки: доля одинаковых неверных ответов у пары голов (где ошиблись обе); кто поддерживает неверный ответ
     головы (никто / только близнец / близнец и другие / только не-близнецы); доля задач OOD с общим неверным ответом.
  5. Сходство представлений голов: средняя по 10 парам доля общих из 20 соседей (банк ID) по числу верных голов, слои
     ¼, ½, ¾, 1; контроль на сумму — связь внутри диапазонов суммы (корреляция после вычитания средних по диапазону).
  6. То же сходство как оценщик: AUROC OOD для своей головы (средняя доля общих соседей с остальными четырьмя);
     сравнение с AGREE и GEO; AUROC внутри слоёв с одинаковым AGREE (добавляет ли что-то к AGREE).
  7. Самообман GEO (заявка − верно) по четвертям удалённости цели от банка (средний косинус 50 соседей, слой ¼).
  8. Ошибки по свойствам задачи: перенос; диапазоны суммы; число токенов верного ответа.
  9. AGREE с поправкой на общие ошибки (NB-AGREE), отношения правдоподобий по ID; ИОИ против AGREE с бутстрепом.
Порядок поиска: меры 1–8 и NB-AGREE придуманы по ходу разведки на обеих частях; «повторилось» значит лишь, что знак и
величина близки на пилоте и тесте. Для проверки нужен новый опыт на свежих данных."""
import collections
import itertools
import json
import os
import sys
from math import erf, sqrt

import numpy as np
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocgeo as A  # noqa: E402
import analyze_ocgeo_test as T  # noqa: E402

PARTS = {'pilot': os.path.join(HERE, 'pilot1', 'out'), 'test': os.path.join(HERE, 'run', 'out')}
SUM_BINS = [(100, 109), (110, 119), (120, 139), (140, 169), (170, 198)]
OV_BINS = {'ID': [(20, 59), (60, 79), (80, 99)], 'OOD': [(100, 119), (120, 139), (140, 169), (170, 198)]}
TWIN = {'pythia-1.4b': 'pythia-1.4b-deduped', 'pythia-1.4b-deduped': 'pythia-1.4b',
        'pythia-2.8b': 'pythia-2.8b-deduped', 'pythia-2.8b-deduped': 'pythia-2.8b'}
LAYERS = ('1/4', '1/2', '3/4', '1')
K_OV = 20


def frac(x):
    x = list(x)
    return float(np.mean(x)) if x else None


def part(base):
    d, heads, b0, nb = A.load(base)
    P = d['problems']
    names = [h['model'] for h in heads]
    nh = len(heads)
    corr = np.array([[r['correct'] for r in h['rows']] for h in heads])
    ans = [[r['answer'] for r in h['rows']] for h in heads]
    rid = np.array([p['range'] == 'ID' for p in P])
    ood, idi = np.nonzero(~rid)[0], np.nonzero(rid)[0]
    sums = np.array([p['sum'] for p in P])
    a_, b_ = np.array([p['a'] for p in P]), np.array([p['b'] for p in P])
    carry = (a_ % 10 + b_ % 10) >= 10
    out = dict(n_id=int(len(idi)), n_ood=int(len(ood)), heads=names)

    # 1–3. вид ошибок, перенос, граница 100
    kinds = {}
    for i, n in enumerate(names):
        err = [j for j in ood if not corr[i][j] and ans[i][j] is not None]
        off = collections.Counter(int(ans[i][j] - sums[j]) for j in err)
        oj = [j for j in ood if ans[i][j] is not None]
        offa = np.array([ans[i][j] - sums[j] for j in oj])
        cj = carry[oj]
        b100 = [j for j in err if 100 <= sums[j] <= 109]
        tens = np.array([(ans[i][j] // 10) % 10 for j in b100])
        mn = np.array([min(a_[j], b_[j]) // 10 for j in b100])
        marg = collections.Counter(tens.tolist())
        kinds[n] = dict(
            n_wrong=len(err), units_right=frac(k % 10 == 0 for k in [ans[i][j] - sums[j] for j in err]),
            top_offsets=[[k, v] for k, v in off.most_common(6)],
            p_minus10_carry=frac(offa[cj] == -10), p_minus10_nocarry=frac(offa[~cj] == -10),
            p_plus10_nocarry=frac(offa[~cj] == 10), p_plus10_carry=frac(offa[cj] == 10),
            below100_by_sum={f'{lo}-{hi}': frac(ans[i][j] < 100 for j in err if lo <= sums[j] <= hi) for lo, hi in SUM_BINS},
            b100=dict(n_wrong=len(b100), tens_dist={str(k): v for k, v in sorted(marg.items())},
                      units_right=frac(ans[i][j] % 10 == sums[j] % 10 for j in b100),
                      tens_eq_min_operand=frac(tens == mn) if len(b100) else None,
                      tens_eq_min_chance=frac(marg[x] / len(b100) for x in mn) if len(b100) else None))
    out['error_kinds'] = kinds

    # 4. общие ошибки
    M = {}
    for a, b in itertools.combinations(range(nh), 2):
        both = [j for j in ood if not corr[a][j] and not corr[b][j]]
        M[f'{names[a]}|{names[b]}'] = dict(both_wrong=len(both), same_frac=frac(ans[a][j] is not None and ans[a][j] == ans[b][j] for j in both))
    out['shared_wrong_pairs'] = M
    who = {}
    for rr, idx in (('ID', idi), ('OOD', ood)):
        c = collections.Counter()
        for i, n in enumerate(names):
            for j in idx:
                if corr[i][j] or ans[i][j] is None:
                    continue
                ag = [names[o] for o in range(nh) if o != i and ans[o][j] == ans[i][j]]
                c['никто' if not ag else 'только близнец' if ag == [TWIN.get(n)] else 'близнец и другие' if TWIN.get(n) in ag
                  else 'только не-близнецы'] += 1
        s = sum(c.values())
        who[rr] = dict(n=s, **{k: v / s for k, v in c.items()})
    out['who_backs_wrong_answer'] = who
    out['ood_with_shared_wrong_frac'] = frac(
        (lambda c: bool(c) and c.most_common(1)[0][1] >= 2)(collections.Counter(ans[i][j] for i in range(nh) if not corr[i][j] and ans[i][j] is not None))
        for j in ood)
    # 4б. переносится ли устройство общих ошибок из ID в OOD: те же пары на ID; доля завышений среди ошибок (знак ошибки)
    pid = {}
    for a, b in itertools.combinations(range(nh), 2):
        both = [j for j in idi if not corr[a][j] and not corr[b][j]]
        pid[f'{names[a]}|{names[b]}'] = frac(ans[a][j] is not None and ans[a][j] == ans[b][j] for j in both)
    keys = list(M)
    out['shared_wrong_id_vs_ood'] = dict(id=pid, spearman_10_pairs=float(spearmanr([pid[k] for k in keys], [M[k]['same_frac'] for k in keys]).correlation))
    out['overshoot_share'] = {rr: {n: frac(ans[i][j] > sums[j] for j in idx if not corr[i][j] and ans[i][j] is not None) for i, n in enumerate(names)}
                              for rr, idx in (('ID', idi), ('OOD', ood))}

    # 5–6. сходство представлений голов
    ncorr = corr.sum(0)
    S, corr2, rid2 = A.scores(d, heads, b0, nb, 0.25, 50)
    rep, ra_eval = {}, {}
    for li, lname in enumerate(LAYERS):
        nbs = []
        for h in heads:
            z = nb[f"{h['model']}_main"]
            keys = sorted([k for k in z if k.startswith('idx_L')], key=lambda k: int(k[5:]))
            nbs.append([set(r) for r in z[keys[li]][:, :K_OV].astype(int).tolist()])
        pair = {}
        for a, b in itertools.combinations(range(nh), 2):
            pair[(a, b)] = pair[(b, a)] = np.array([len(nbs[a][j] & nbs[b][j]) / K_OV for j in range(len(P))])
        ov = sum(pair[(a, b)] for a, b in itertools.combinations(range(nh), 2)) / (nh * (nh - 1) / 2)
        rl = {}
        for rr in ('ID', 'OOD'):
            m_r = rid == (rr == 'ID')
            by_k = {str(k): (float(ov[m_r & (ncorr == k)].mean()) if (m_r & (ncorr == k)).sum() >= 20 else None) for k in range(nh + 1)}
            cx, cy = [], []
            for lo, hi in OV_BINS[rr]:
                m = m_r & (sums >= lo) & (sums <= hi)
                cx += list(ncorr[m] - ncorr[m].mean())
                cy += list(ov[m] - ov[m].mean())
            rl[rr] = dict(by_ncorrect=by_k, r_raw=float(np.corrcoef(ncorr[m_r], ov[m_r])[0, 1]),
                          r_within_sum_bins=float(np.corrcoef(cx, cy)[0, 1]))
        rep[lname] = rl
        RA = np.array([sum(pair[(i, o)] for o in range(nh) if o != i) / (nh - 1) for i in range(nh)])
        within = []
        for i in range(nh):
            vals, ws = [], []
            for v in np.unique(S['AGREE'][i][ood]):
                m = ood[S['AGREE'][i][ood] == v]
                y = corr2[i][m]
                if y.sum() >= 10 and (~y).sum() >= 10:
                    vals.append(A.auroc(RA[i][m], y))
                    ws.append(len(m))
            within.append(float(np.average(vals, weights=ws)) if vals else None)
        ra_eval[lname] = dict(auroc_ood_RA=[A.auroc(RA[i][ood], corr2[i][ood]) for i in range(nh)], auroc_ood_RA_within_AGREE=within)
    out['rep_overlap'] = rep
    out['rep_agreement_as_evaluator'] = dict(by_layer=ra_eval, auroc_ood_AGREE=[A.auroc(S['AGREE'][i][ood], corr2[i][ood]) for i in range(nh)],
                                             auroc_ood_GEO=[A.auroc(S['GEO'][i][ood], corr2[i][ood]) for i in range(nh)])

    # 7. самообман GEO по удалённости от банка (четверти: от дальних к ближним)
    dist = {}
    for i, h in enumerate(heads):
        iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(S['GEO'][i][idi], corr2[i][idi].astype(float))
        claim, y = iso.predict(S['GEO'][i][ood]), corr2[i][ood].astype(float)
        cos = nb[f"{h['model']}_main"][f'cos_L{A.layer_key(h, 0.25)}'][:, :50].astype(float).mean(1)[ood]
        q = np.quantile(cos, [0, 0.25, 0.5, 0.75, 1])
        rows = []
        for k in range(4):
            m = (cos >= q[k]) & ((cos <= q[k + 1]) if k == 3 else (cos < q[k + 1]))
            rows.append(dict(n=int(m.sum()), claim=float(claim[m].mean()), acc=float(y[m].mean()), over=float(claim[m].mean() - y[m].mean())))
        dist[h['model']] = dict(quartiles_far_to_near=rows, r_cos_sum=float(np.corrcoef(cos, sums[ood])[0, 1]))
    out['geo_overclaim_by_distance'] = dist

    # 8. свойства задачи
    feat = {}
    for i, n in enumerate(names):
        e = ~corr[i]
        feat[n] = dict(ood_carry=float(e[ood][carry[ood]].mean()), ood_nocarry=float(e[ood][~carry[ood]].mean()),
                       id_carry=float(e[idi][carry[idi]].mean()), id_nocarry=float(e[idi][~carry[idi]].mean()),
                       by_sum={f'{lo}-{hi}': float(e[(sums >= lo) & (sums <= hi)].mean()) for lo, hi in SUM_BINS})
    out['errors_by_feature'] = feat
    ntok = {}
    for i in range(nh):
        for j in range(len(P)):
            if corr[i][j]:
                ntok.setdefault(int(sums[j]), set()).add(heads[i]['rows'][j]['n_tok'])
    out['answer_tokens'] = dict(n_sums_seen=len(ntok), all_single_token=all(v == {1} for v in ntok.values()))

    # 9. AGREE с поправкой на общие ошибки (NB-AGREE): сумма по другим головам логарифма отношения правдоподобий
    #    P(совпал/не совпал | голова верна) / P(… | голова неверна), оценённого на ID (сглаживание +1/+2). Калибровка,
    #    выбор головы (ничья «поровну»), верхние 10 % — те же функции, что в зарегистрированном анализе. Бутстреп с
    #    переподгонкой оценок и калибровки, B = 400, зерно 1114. Разведка, не проверка.
    agm = np.array([[[ans[o][j] is not None and ans[o][j] == ans[i][j] for j in range(len(P))] for o in range(nh)] for i in range(nh)])

    def nb_scores(fit):
        Mx = np.zeros((nh, len(P)))
        for i in range(nh):
            c = corr[i][fit]
            for o in range(nh):
                if o != i:
                    g_ = agm[i, o][fit]
                    p1 = (g_[c].sum() + 1) / (c.sum() + 2)
                    p0 = (g_[~c].sum() + 1) / ((~c).sum() + 2)
                    Mx[i] += np.where(agm[i, o], np.log(p1 / p0), np.log((1 - p1) / (1 - p0)))
        return Mx

    def ioi_pair(fit, cols):
        r = {}
        for e, Mx in (('AGREE', S['AGREE']), ('NB-AGREE', nb_scores(fit))):
            cal = T.calibrate(Mx, corr, fit, cols)
            t, c, tie = T.select(cal, corr[:, cols].astype(float))
            r[e] = dict(T.ioi(t, c), tie_frac=tie, cal=cal)
        return r

    base_r = ioi_pair(idi, ood)
    nbe = {}
    for e, r in base_r.items():
        fp, fy = r['cal'].ravel(), corr[:, ood].astype(float).ravel()
        sel = np.argsort(-fp, kind='mergesort')[:int(np.ceil(0.1 * len(fp)))]
        Mx = S['AGREE'] if e == 'AGREE' else nb_scores(idi)
        nbe[e] = dict(ioi=r['ioi'], ignorance=r['ignorance'], deception=r['deception'], tie_frac=r['tie_frac'],
                      top10=dict(accuracy=float(fy[sel].mean()), claim=float(fp[sel].mean()), deception=float(fp[sel].mean() - fy[sel].mean())),
                      auroc_ood=[A.auroc(Mx[i][ood], corr[i][ood]) for i in range(nh)])
    g = np.random.default_rng(1114)
    bs = []
    for _ in range(400):
        r = ioi_pair(g.choice(idi, len(idi)), g.choice(ood, len(ood)))
        bs.append(r['NB-AGREE']['ioi'] - r['AGREE']['ioi'])
    bs = np.array(bs)
    nbe['delta_nb_minus_agree'] = dict(point=base_r['NB-AGREE']['ioi'] - base_r['AGREE']['ioi'], ci95=[float(x) for x in np.quantile(bs, [0.025, 0.975])],
                                       ci99=[float(x) for x in np.quantile(bs, [0.005, 0.995])], share_below_0=float((bs < 0).mean()), B=400, seed=1114)
    out['nb_agree'] = nbe
    return out


def main():
    res = {k: part(v) for k, v in PARTS.items()}
    res['note'] = 'пост-хок разведка; вердикты OCGEO-01 не меняет; найденное — гипотезы для новых опытов на свежих данных'
    # мощность повторной проверки NB-AGREE на наборе того же размера: эффект теста вдвое меньше (урок № 152/154),
    # стандартная ошибка — по ширине ДИ 99 % теста; односторонний уровень 0,005
    t = res['test']['nb_agree']['delta_nb_minus_agree']
    se = (t['ci99'][1] - t['ci99'][0]) / (2 * 2.576)
    eff = abs(t['point']) / 2
    res['nb_agree_power_same_size'] = dict(se=se, effect_halved=eff, power=0.5 * (1 + erf((eff / se - 2.576) / sqrt(2))))
    json.dump(res, open(os.path.join(HERE, 'explore_patterns.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k in PARTS:
        r = res[k]
        print('==', k, '| OOD с общим неверным ответом:', round(r['ood_with_shared_wrong_frac'], 3),
              '| кто поддерживает неверный (OOD):', {kk: round(v, 3) for kk, v in r['who_backs_wrong_answer']['OOD'].items() if kk != 'n'})
        print('  близнецы 2.8b: одинаковых неверных', round(r['shared_wrong_pairs']['pythia-2.8b|pythia-2.8b-deduped']['same_frac'], 3))
        for n, v in r['error_kinds'].items():
            print(f"  {n:20s} единицы верны {v['units_right']:.3f} | ниже 100 на 100–109 {v['below100_by_sum']['100-109']:.2f} | "
                  f"−10|перенос {v['p_minus10_carry']:.3f} −10|нет {v['p_minus10_nocarry']:.3f} | ошибка 100–109 "
                  f"{r['errors_by_feature'][n]['by_sum']['100-109']:.3f}")
        for l in LAYERS:
            print('  слой', l, 'OOD r сырое %.3f, внутри диапазонов суммы %.3f' % (r['rep_overlap'][l]['OOD']['r_raw'], r['rep_overlap'][l]['OOD']['r_within_sum_bins']),
                  '| AUROC RA', np.round(r['rep_agreement_as_evaluator']['by_layer'][l]['auroc_ood_RA'], 3))


if __name__ == '__main__':
    main()
