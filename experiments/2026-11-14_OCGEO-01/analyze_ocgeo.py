#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: оценщики правильности ответов голов Pythia и выбор головы по оценщику; ИОИ вне диапазона калибровки.
python3 analyze_ocgeo.py OUT_DIR RESULT.json [--layer-frac F] [--k K]
OUT_DIR — вывод ocgeo_extract.py (answers.json, nbrs_*.npz).
Головы — модели основной ревизии без ошибки загрузки. Оценки головы h на задаче j:
  CONF  — logp ответа (сумма по токенам; нет ответа → −50);
  AGREE — доля других голов с тем же ответом;
  GEO   — доля верных ответов h среди k ближайших задач банка ID в представлении h (слой — доля F от глубины);
  GEO0  — то же в представлении необученной pythia-1.4b (step0) — начальная линия геометрии входа;
  INPUT — то же по соседям в пространстве самих чисел (a, b) — «трудность по входу»;
  SOLVE — описательно: −|kNN-сумма соседей − ответ h| (соседи с ответами от кода решают задачу сами — утечка, не оценщик).
Калибровка: изотоническая регрессия оценка → вероятность верного, по задачам ID (банк; у банка соседи без самой задачи).
Цели — задачи OOD. Для каждого оценщика на каждой цели выбирается голова с наибольшей откалиброванной вероятностью
(ничья — по порядку голов); T — доля верных у выбранных, C — средняя заявленная вероятность;
ИОИ = (1 − T) + max(0, C − T) (experiments/truth.py: незнание + самообман). Плюс AUROC и Брайер по каждой голове."""
import json
import os
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression

KS = (5, 10, 20, 50)


def auroc(score, y):
    s, y = np.asarray(score, float), np.asarray(y, bool)
    if y.all() or (~y).all():
        return None
    r = s.argsort(kind='mergesort').argsort(kind='mergesort') + 1.0
    # средние ранги для равных
    order = np.argsort(s, kind='mergesort')
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


def load(out_dir):
    d = json.load(open(os.path.join(out_dir, 'answers.json'), encoding='utf-8'))
    heads = [h for h in d['heads'] if 'rows' in h and h['revision'] == 'main']
    base = next((h for h in d['heads'] if 'rows' in h and h['revision'] == 'step0'), None)
    nb = {f"{h['model']}_{h['revision']}": dict(np.load(os.path.join(out_dir, f"nbrs_{h['model']}_{h['revision']}.npz")))
          for h in heads + ([base] if base else [])}
    return d, heads, base, nb


def layer_key(h, frac):
    """Слой — ближайший из сохранённых к доле frac глубины."""
    L = h['n_layers']
    return min(h['layers'], key=lambda l: abs(l / L - frac))


def scores(d, heads, base, nb, frac, k):
    P = d['problems']
    bank = np.array(d['bank'])
    rng_id = np.array([p['range'] == 'ID' for p in P])
    sums = np.array([p['sum'] for p in P], float)
    ab = np.array([[p['a'], p['b']] for p in P], float)
    corr = np.array([[r['correct'] for r in h['rows']] for h in heads], bool)          # (головы, задачи)
    ans = [[r['answer'] for r in h['rows']] for h in heads]
    S = {}
    S['CONF'] = np.array([[r['logp'] if r['logp'] is not None else -50.0 for r in h['rows']] for h in heads])
    nh = len(heads)
    S['AGREE'] = np.array([[np.mean([ans[o][j] is not None and ans[o][j] == ans[i][j] for o in range(nh) if o != i])
                            for j in range(len(P))] for i in range(nh)])
    geo, solve = [], []
    for i, h in enumerate(heads):
        l = layer_key(h, frac)
        idx = nb[f"{h['model']}_main"][f'idx_L{l}'][:, :k].astype(int)
        geo.append(corr[i][bank[idx]].mean(1))
        s_hat = sums[bank[idx]].mean(1)
        solve.append(-np.abs(s_hat - np.array([a if a is not None else -1 for a in ans[i]], float)))
    S['GEO'], S['SOLVE'] = np.array(geo), np.array(solve)
    if base:
        lb = layer_key(base, frac)
        idx0 = nb[f"{base['model']}_step0"][f'idx_L{lb}'][:, :k].astype(int)
        S['GEO0'] = np.array([corr[i][bank[idx0]].mean(1) for i in range(nh)])
    # соседи по входу: евклид по (a, b) среди банка, без самой задачи
    D = ((ab[:, None, :] - ab[bank][None, :, :]) ** 2).sum(-1)
    pos = {int(j): q for q, j in enumerate(bank)}
    for j, q in pos.items():
        D[j, q] = np.inf
    idxi = np.argsort(D, axis=1, kind='mergesort')[:, :k]
    S['INPUT'] = np.array([corr[i][bank[idxi]].mean(1) for i in range(nh)])
    return S, corr, rng_id


def evaluate(S, corr, rng_id, names):
    out = {}
    nh = corr.shape[0]
    tgt = ~rng_id
    for e, M in S.items():
        cal = np.zeros_like(M, dtype=float)
        per = []
        for i in range(nh):
            iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(M[i][rng_id], corr[i][rng_id].astype(float))
            cal[i] = iso.predict(M[i])
            per.append(dict(head=names[i], auroc_ood=auroc(M[i][tgt], corr[i][tgt]), auroc_id=auroc(M[i][rng_id], corr[i][rng_id]),
                            brier_ood=float(np.mean((cal[i][tgt] - corr[i][tgt]) ** 2)),
                            claim_ood=float(cal[i][tgt].mean()), acc_ood=float(corr[i][tgt].mean())))
        pick = cal[:, tgt].argmax(0)                      # ничья → первая голова по порядку
        cols = np.nonzero(tgt)[0]
        T = float(np.mean(corr[pick, cols]))
        C = float(np.mean(cal[pick, cols]))
        out[e] = dict(T=T, C=C, ignorance=1 - T, deception=max(0.0, C - T), ioi=(1 - T) + max(0.0, C - T),
                      picked=np.bincount(pick, minlength=nh).tolist(), per_head=per)
    return out


def main():
    out_dir, dst = sys.argv[1], sys.argv[2]
    frac = float(sys.argv[sys.argv.index('--layer-frac') + 1]) if '--layer-frac' in sys.argv else None
    kk = int(sys.argv[sys.argv.index('--k') + 1]) if '--k' in sys.argv else None
    d, heads, base, nb = load(out_dir)
    names = [h['model'] for h in heads]
    rr = [p['range'] for p in d['problems']]
    accs = {h['model']: {r: float(np.mean([x['correct'] for x, q in zip(h['rows'], rr) if q == r])) for r in ('ID', 'OOD')} for h in heads}
    res = dict(split=d['split'], heads=names, accuracy=accs,
               n_id=int(sum(p['range'] == 'ID' for p in d['problems'])), n_ood=int(sum(p['range'] == 'OOD' for p in d['problems'])),
               grid={})
    fracs = [frac] if frac is not None else [0.25, 0.5, 0.75, 1.0]
    ks = [kk] if kk is not None else list(KS)
    for f in fracs:
        for k in ks:
            S, corr, rng_id = scores(d, heads, base, nb, f, k)
            res['grid'][f'f{f}_k{k}'] = evaluate(S, corr, rng_id, names)
    # «лучшая голова» без оценщика: голова с наибольшей точностью на ID, заявка — её точность на ID
    corr = np.array([[r['correct'] for r in h['rows']] for h in heads], bool)
    rid = np.array([p['range'] == 'ID' for p in d['problems']])
    b = int(np.argmax(corr[:, rid].mean(1)))
    T, C = float(corr[b, ~rid].mean()), float(corr[b, rid].mean())
    res['best_head_no_evaluator'] = dict(head=names[b], T=T, C=C, ioi=(1 - T) + max(0.0, C - T), deception=max(0.0, C - T))
    res['oracle_any_head_correct_ood'] = float(corr[:, ~rid].any(0).mean())
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('точность голов (ID / OOD):', {h: (round(a['ID'], 3), round(a['OOD'], 3)) for h, a in res['accuracy'].items()})
    print('без оценщика (лучшая по ID голова):', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res['best_head_no_evaluator'].items()},
          '| хоть одна голова верна (OOD):', round(res['oracle_any_head_correct_ood'], 3))
    for key, ev in res['grid'].items():
        line = ' | '.join(f"{e}: ИОИ {v['ioi']:.3f} (T {v['T']:.3f}, C {v['C']:.3f})" for e, v in ev.items())
        print(key, line)


if __name__ == '__main__':
    main()
