import json, numpy as np
from scipy.stats import spearmanr, mannwhitneyu
r = json.load(open('/home/claude/pers01_results.json')); r = {k: v for k, v in r.items() if k != 'verdicts'}
def grp(*g): return {k: v for k, v in r.items() if v.get('group') in g}
rev = grp('dip', 'lj13'); eeg = grp('eeg'); real = grp('real'); tel = grp('tel')
V = {}
V['PP1'] = dict(rev_zero=int(sum(v['inversions'] == 0 for v in rev.values())), n_rev=len(rev), eeg_ge1=int(sum(v['inversions'] >= 1 for v in eeg.values())), n_eeg=len(eeg), real_ge1=int(sum(v['inversions'] >= 1 for v in real.values())), n_real=len(real), tel_ge1=int(sum(v['inversions'] >= 1 for v in tel.values())))
V['PP1']['ok'] = bool(V['PP1']['rev_zero'] >= 12 and V['PP1']['eeg_ge1'] >= 10); V['K1'] = dict(hit=bool(len(rev) - V['PP1']['rev_zero'] >= 5))
def rseq(v): return [v['lag'][s].get('r') for s in ('1', '2', '4', '8')]
born = ['EEG_A_Z_Z013', 'EEG_B_O_O001', 'EEG_C_N_N009', 'EEG_C_N_N013', 'EEG_D_F_F001', 'EEG_D_F_F005', 'EEG_E_S_S001']
rows = {}
for k in born:
    rs = rseq(r[k]); ok = all(x is not None for x in rs)
    rows[k] = dict(r=rs, spearman=(float(spearmanr([1, 2, 4, 8], rs)[0]) if ok else None), r1_gt1=bool(rs[0] and rs[0] > 1.0), transient=bool(ok and rs[0] > 1 and rs[3] < rs[0]), persistent=bool(ok and rs[0] > 1.15 and rs[3] >= 0.77 * rs[0]))
V['PP2'] = dict(rows=rows, n_decreasing=int(sum(v['spearman'] is not None and v['spearman'] <= -0.8 for v in rows.values())), n_r1_gt1=int(sum(v['r1_gt1'] for v in rows.values())), n_persistent=int(sum(v['persistent'] for v in rows.values())), n_transient=int(sum(v['transient'] for v in rows.values())))
V['PP2']['ok'] = bool(V['PP2']['n_decreasing'] >= 5); V['K2'] = dict(hit=bool(V['PP2']['n_persistent'] >= 4))
sp_rev = {k: (float(spearmanr([1, 2, 4, 8], rseq(v))[0]) if all(x is not None for x in rseq(v)) else None) for k, v in rev.items()}
V['PP3'] = dict(n_nondecreasing=int(sum(s is not None and s >= 0 for s in sp_rev.values())), n=len(rev), spearmans=sp_rev, ok=bool(sum(s is not None and s >= 0 for s in sp_rev.values()) >= 11))
allv = list(grp('dip', 'lj13', 'eeg', 'real', 'tel').values()); d = np.array([v['delta'] for v in allv]); inv = np.array([v['inversions'] > 0 for v in allv])
auc = float(mannwhitneyu(d[inv], d[~inv]).statistic / (inv.sum() * (~inv).sum())); V['PP4'] = dict(auc_delta=auc, n=len(allv), n_inv=int(inv.sum()), ok=bool(auc >= 0.7)); V['K3'] = dict(hit=bool(auc <= 0.55))
# leave-one-out по группам для доли инверсий ЭЭГ
V['loo_eeg'] = [int(sum(v['inversions'] >= 1 for kk, v in eeg.items() if kk != k)) for k in eeg]
V['r_medians'] = {g: [float(np.median([rseq(v)[i] for v in grp(g).values() if rseq(v)[i] is not None])) for i in range(4)] for g in ('tel', 'dip', 'lj13', 'eeg', 'real')}
out = json.load(open('/home/claude/pers01_results.json')); out['verdicts'] = V; json.dump(out, open('/home/claude/pers01_results.json', 'w'), default=float)
for k, v in V.items(): print(k, json.dumps(v, ensure_ascii=False, default=float)[:700])
