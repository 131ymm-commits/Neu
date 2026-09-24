"""EST-01 — вердикты по est01_results.json (PREREG 2026-09-09)."""
import json, numpy as np
from scipy.stats import spearmanr
r = json.load(open('/home/claude/est01_results.json')); T = r['telegraph']; r = {k: v for k, v in r.items() if k not in ('telegraph', 'verdicts')}
emb = {k: v for k, v in r.items() if v['kind'] == 'emb'}; raw = {k: v for k, v in r.items() if v['kind'] == 'raw'}
fe = {k: v['f'] for k, v in emb.items() if v['f']}; fr = {k: v['f'] for k, v in raw.items() if v['f']}
V = {}
V['PE1'] = dict(frac_emb_ge15=float(np.mean([f >= 1.5 for f in fe.values()])), n_emb=len(fe), frac_raw_in=float(np.mean([0.8 <= f <= 1.25 for f in fr.values()])), n_raw=len(fr), med_emb=float(np.median(list(fe.values()))), med_raw=float(np.median(list(fr.values()))),
              eeg=dict(median=float(np.median([f for k, f in fe.items() if k.startswith('EEG')])), ge15=int(sum(f >= 1.5 for k, f in fe.items() if k.startswith('EEG'))), n=int(sum(k.startswith('EEG') for k in fe))), non_eeg={k: round(f, 2) for k, f in fe.items() if not k.startswith('EEG')})
V['PE1']['ok'] = bool(V['PE1']['frac_emb_ge15'] >= 0.6 and V['PE1']['frac_raw_in'] >= 0.8)
V['K1'] = dict(hit=bool(V['PE1']['frac_emb_ge15'] < 0.3)); V['K1b'] = dict(hit=bool(V['PE1']['frac_raw_in'] < 0.5))
ks = [2, 4, 10, 30, 100]; ms = [1, 2, 4, 8]; taus = [1, 2, 4, 8]
fk = [T[f'k{k}']['median'] for k in ks]; fm = [T[f'm{m}']['median'] for m in ms]; ft = [T[f'tau{t}']['median'] for t in taus]
V['PE3'] = dict(f_by_k=dict(zip(map(str, ks), fk)), f_by_m=dict(zip(map(str, ms), fm)), f_by_tau=dict(zip(map(str, taus), ft)), f_m1_by_k={k: T[f'm1_k{k}']['median'] for k in (10, 30, 100)},
                rho_k=float(spearmanr(ks, fk)[0]), rho_m=float(spearmanr(ms, fm)[0]), rho_tau=float(spearmanr(taus, ft)[0]), true_t1=T['true_t1']['median'])
V['PE3']['ok'] = bool(V['PE3']['rho_k'] >= 0.8 and V['PE3']['rho_m'] >= 0.8 and V['PE3']['rho_tau'] <= -0.8 and all(v <= 1.15 for v in V['PE3']['f_m1_by_k'].values()))
V['K3'] = dict(hit=bool(any(v >= 1.5 for v in V['PE3']['f_m1_by_k'].values())))
# джекнайф по сидам телеграфа для монотонностей
jk = []
for s in range(5):
    fk_ = [np.median([x for i, x in enumerate(T[f'k{k}']['vals']) if i != s]) for k in ks]; fm_ = [np.median([x for i, x in enumerate(T[f'm{m}']['vals']) if i != s]) for m in ms]
    jk.append((float(spearmanr(ks, fk_)[0]), float(spearmanr(ms, fm_)[0])))
V['PE3']['jackknife_rho'] = jk
# ζ-часть: действительность наблюдаемой
def complex_pairs(its): its = np.array(its); return int(np.sum(np.isclose(its[:-1], its[1:], rtol=1e-6))) if len(its) > 1 else 0
cp = {k: complex_pairs(v['full']['nonrev']['its']) for k, v in emb.items()}
V['PE2'] = dict(valid=False, n_complex=int(sum(c > 0 for c in cp.values())), n=len(cp), note='ζ по модулям комплексного спектра не определена (нулевые зазоры внутри пар) — класс B, вердикт не выносится',
                raw_transitions=[(k, v['cls_rev'], v['cls_nonrev']) for k, v in emb.items() if v['cls_rev'] != v['cls_nonrev']], hier_rev=int(sum(v['cls_rev'] == 'иерархия' for v in emb.values())))
V['PE4'] = dict(valid=False, note='как P-E2')
V['conv'] = dict(frac=float(np.mean([abs(v['f_half'] - v['f']) / v['f'] <= 0.3 for v in emb.values() if v['f'] and v['f_half']])))
V['DUST'] = {k: dict(t1_rev=v['full']['rev']['t1'], t1_nonrev=v['full']['nonrev']['t1'], f=v['f'], zeta_rev=v['full']['rev']['zeta'], zeta_nonrev=v['full']['nonrev']['zeta']) for k, v in r.items() if k.startswith('DUST')}
V['DUST']['R_Wg'] = dict(rev=r['DUST_2D_Wg']['full']['rev']['t1'] / r['DUST_1D_Wg']['full']['rev']['t1'], nonrev=r['DUST_2D_Wg']['full']['nonrev']['t1'] / r['DUST_1D_Wg']['full']['nonrev']['t1'])
V['DUST']['R_W'] = dict(rev=r['DUST_2D_W']['full']['rev']['t1'] / r['DUST_1D_W']['full']['rev']['t1'], nonrev=r['DUST_2D_W']['full']['nonrev']['t1'] / r['DUST_1D_W']['full']['nonrev']['t1'])
out = json.load(open('/home/claude/est01_results.json')); out['verdicts'] = V; json.dump(out, open('/home/claude/est01_results.json', 'w'), default=float)
for k, v in V.items(): print(k, json.dumps(v, ensure_ascii=False, default=float)[:700])
