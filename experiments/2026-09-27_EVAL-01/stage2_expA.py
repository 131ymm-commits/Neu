# Опыт А (совет 14, 29.09.2026): разведочный переанализ стадии 2, новых вызовов нет.
# По нему ветви не открываются и не закрываются; выходы — для мощности и гипотез опыта Б.
#   python3 stage2_expA.py → stage2/expA.json
import json, os, sys, random, math, re, statistics as st
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'stage2'); sys.path.insert(0, HERE)
from eval01_pilot import label
from eval01_main import clip, num, recal, metrics, agg, ci, holm, TRUTH

key = json.load(open(os.path.join(D, 'sample_key.json'))); truth = json.load(open(TRUTH))
items = {it['id']: it for it in (json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl')))}
out = json.load(open(os.path.join(D, 'out.json')))['out']; al = key['aliases']; cells = key['cells']
y = {al[i]: bool(label(items[i], truth)) for i in key['ids']}; item = {al[i]: items[i] for i in key['ids']}
def g(arm, a):
    r = out[arm].get(a); p = num(r.get('p_correct')) if r else None
    return 0.5 if p is None else clip(p)
P = {a: dict(BLIND=g('BLIND', a), RC1=g('RC1', a), C2=g('C2', a), C3=g('C3', a)) for a in y}
for a in y: P[a]['BLIND_RECAL'] = recal(P[a]['BLIND']); P[a]['COUNCIL'] = st.mean([P[a][k] for k in ('RC1', 'C2', 'C3')])
by = {}
for a in sorted(y): by.setdefault(cells[a], []).append(a)

# 1. базовая линия «доля верных в клетке»: 2 фолда, стратификация по клетке и правде, 20 повторов; p элемента — среднее вне-фолдовых оценок
rng = random.Random(29); base = {a: [] for a in y}
for _ in range(20):
    for c, lst in by.items():
        pos = [a for a in lst if y[a]]; neg = [a for a in lst if not y[a]]; rng.shuffle(pos); rng.shuffle(neg)
        f = [pos[0::2] + neg[0::2], pos[1::2] + neg[1::2]]
        for k in (0, 1):
            tr = f[1 - k]; rate = st.mean(y[a] for a in tr)
            for a in f[k]: base[a].append(rate)
for a in y: P[a]['CELLRATE'] = st.mean(base[a])

# 2. модель поверхностных признаков (без правды): числа из текста задачи и ответа; логистическая, перекрёстная подгонка внутри клетки
def feats(it):
    ans = it['answer']; est = num(ans.get('estimate')) if isinstance(ans, dict) else None
    nums = [int(x) for x in re.findall(r'\d+', it['task'])]
    lo, hi = (num(ans.get('lo')), num(ans.get('hi'))) if isinstance(ans, dict) else (None, None)
    w = (hi - lo) / max(1.0, abs(est)) if None not in (lo, hi, est) else 0.0
    note = (ans.get('note') or '') if isinstance(ans, dict) else ''
    return [math.log10(1 + max(nums or [0])), math.log10(1 + abs(est or 0)), w, math.log10(1 + len(note)), math.log10(1 + len(it['task'])),
            float(ans.get('n_values') or 0) if isinstance(ans, dict) else 0.0]
for c, lst in by.items():
    ys = np.array([y[a] for a in lst]); X = np.array([feats(item[a]) for a in lst]); acc = {a: [] for a in lst}
    if ys.min() == ys.max():
        for a in lst: P[a]['FEAT'] = 0.5
        continue
    for _ in range(20):
        pos = [i for i in range(len(lst)) if ys[i]]; neg = [i for i in range(len(lst)) if not ys[i]]; rng.shuffle(pos); rng.shuffle(neg)
        f = [pos[0::2] + neg[0::2], pos[1::2] + neg[1::2]]
        for k in (0, 1):
            tr = f[1 - k]
            if len(set(ys[tr])) < 2: pr = [ys[tr].mean()] * len(f[k])
            else:
                m = LogisticRegression(C=1.0, max_iter=2000).fit((X[tr] - X[tr].mean(0)) / (X[tr].std(0) + 1e-9), ys[tr])
                pr = m.predict_proba((X[f[k]] - X[tr].mean(0)) / (X[tr].std(0) + 1e-9))[:, 1]
            for i, p in zip(f[k], pr): acc[lst[i]].append(float(p))
    for a in lst: P[a]['FEAT'] = st.mean(acc[a])

SYS = ['BLIND', 'BLIND_RECAL', 'COUNCIL', 'RC1', 'C2', 'C3', 'CELLRATE', 'FEAT']
def murphy(ps, bins=10):  # надёжность, разрешение, неопределённость (Брайер ≈ REL − RES + UNC)
    ob = st.mean(v for _, v in ps); b = {}
    for p, v in ps: b.setdefault(min(bins - 1, int(p * bins)), []).append((p, v))
    rel = sum(len(l) * (st.mean(p for p, _ in l) - st.mean(v for _, v in l)) ** 2 for l in b.values()) / len(ps)
    res = sum(len(l) * (st.mean(v for _, v in l) - ob) ** 2 for l in b.values()) / len(ps)
    return dict(rel=rel, res=res, unc=ob * (1 - ob))
def cut(s, sub=None):
    sub = sub or by
    return agg([metrics([(P[a][s], y[a]) for a in l]) for l in sub.values()])
res = dict(note='разведочный опыт А (совет 14); ветви по нему не открываются и не закрываются', n=len(y), plan=key['plan'])
res['main_cut'] = {s: cut(s) for s in SYS}
res['murphy'] = {c: {s: murphy([(P[a][s], y[a]) for a in l]) for s in SYS} for c, l in by.items()}

# 3. Брайер: CELLRATE − BLIND_RECAL, бутстреп внутри клеток
B = 2000; rng = random.Random(0); boots = []
for _ in range(B):
    s = {c: [rng.choice(l) for _ in l] for c, l in by.items()}; boots.append({k: cut(k, s)['brier'] for k in ('CELLRATE', 'BLIND_RECAL', 'COUNCIL', 'FEAT')})
res['brier_cellrate_minus_recal'] = dict(point=res['main_cut']['CELLRATE']['brier'] - res['main_cut']['BLIND_RECAL']['brier'], ci95=ci([b['CELLRATE'] - b['BLIND_RECAL'] for b in boots]))
res['brier_cellrate_minus_council'] = dict(point=res['main_cut']['CELLRATE']['brier'] - res['main_cut']['COUNCIL']['brier'], ci95=ci([b['CELLRATE'] - b['COUNCIL'] for b in boots]))

# 4. AUROC внутри клеток (где определён): судьи против 0,5 и против FEAT, парный бутстреп внутри клетки; Холм по клеткам
def auc(l, s):
    ys = [y[a] for a in l]
    return None if len(set(ys)) < 2 else roc_auc_score(ys, [P[a][s] for a in l])
aucres = {}; pv = {}
for c, l in by.items():
    if auc(l, 'BLIND') is None: aucres[c] = 'не определён (один класс)'; continue
    pos = [a for a in l if y[a]]; neg = [a for a in l if not y[a]]; bs = {s: [] for s in SYS}; dfe = {s: [] for s in ('BLIND', 'COUNCIL')}
    for _ in range(B):
        s = [rng.choice(pos) for _ in pos] + [rng.choice(neg) for _ in neg]
        v = {k: auc(s, k) for k in SYS}
        for k in SYS: bs[k].append(v[k])
        for k in dfe: dfe[k].append(v[k] - v['FEAT'])
    aucres[c] = {k: dict(point=auc(l, k), ci95=ci(bs[k])) for k in SYS}
    for k in ('BLIND', 'COUNCIL'):
        v = bs[k]; pv[f'{c}|{k}>0.5'] = (sum(x <= 0.5 for x in v) + 1) / (B + 1)
        aucres[c][f'{k}-FEAT'] = dict(point=aucres[c][k]['point'] - aucres[c]['FEAT']['point'], ci95=ci(dfe[k]), p_one=(sum(x <= 0 for x in dfe[k]) + 1) / (B + 1))
        pv[f'{c}|{k}>FEAT'] = aucres[c][f'{k}-FEAT']['p_one']
    aucres[c]['n_pos'], aucres[c]['n_neg'] = len(pos), len(neg)
res['auroc'] = aucres; res['holm_auroc'] = holm(pv, alpha=0.05)
w = {c: aucres[c]['n_pos'] * aucres[c]['n_neg'] for c in aucres if isinstance(aucres[c], dict)}
res['auroc_strat'] = {k: sum(w[c] * aucres[c][k]['point'] for c in w) / sum(w.values()) for k in SYS}

# 5. равное покрытие: каждая система оставляет долю q самых уверенных (|p − 0,5|), Брайер на оставленных
def cov(s, q):
    out_ = []
    for l in by.values():
        k = max(1, round(q * len(l))); keep = sorted(l, key=lambda a: -abs(P[a][s] - 0.5))[:k]; out_.append(st.mean((P[a][s] - y[a]) ** 2 for a in keep))
    return st.mean(out_)
res['risk_coverage'] = {str(q): {s: cov(s, q) for s in ('BLIND', 'COUNCIL', 'FEAT', 'CELLRATE')} for q in (1.0, 0.9, 0.71, 0.5, 0.3)}

# 6. корреляции для мощности опыта Б
def corr(u, v): return float(np.corrcoef(u, v)[0, 1])
res['corr'] = {c: {'BLIND~COUNCIL': corr([P[a]['BLIND'] for a in l], [P[a]['COUNCIL'] for a in l]),
                   'RC1~C2': corr([P[a]['RC1'] for a in l], [P[a]['C2'] for a in l]), 'RC1~C3': corr([P[a]['RC1'] for a in l], [P[a]['C3'] for a in l]),
                   'C2~C3': corr([P[a]['C2'] for a in l], [P[a]['C3'] for a in l])} for c, l in by.items()}
json.dump(res, open(os.path.join(D, 'expA.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ('brier_cellrate_minus_recal', 'brier_cellrate_minus_council', 'auroc_strat')}, ensure_ascii=False, indent=1))
print({s: round(res['main_cut'][s]['brier'], 3) for s in SYS})
for c, v in aucres.items(): print(c, v if isinstance(v, str) else {k: (round(v[k]['point'], 3), [round(x, 3) for x in v[k]['ci95']]) for k in ('BLIND', 'COUNCIL', 'FEAT', 'BLIND-FEAT', 'COUNCIL-FEAT')}, v if isinstance(v, str) else (v['n_pos'], v['n_neg']))
print('holm', {k: v['reject'] for k, v in res['holm_auroc']['table'].items()})
print('risk_coverage', json.dumps(res['risk_coverage'], ensure_ascii=False))
print('corr', json.dumps(res['corr'], ensure_ascii=False))
