"""SORT-04 — прогон по PREREG (2026-09-16): 75 НОВЫХ сегментов Бонна (индексы, не кратные 4, среди первых 20 файлов группы; по 15 на группу)
× конвейер COG-01 × 20 iAAFT-суррогатов (те же суррогаты — для нуля конвейера и для нуля TR(2)). Числа — sort04_results.json.
Сид суррогатов — crc32 имени сегмента (в SORT-03 был abs(hash(name)) — рандомизирован между процессами, невоспроизводим)."""
import numpy as np, json, time, warnings, sys, zlib, glob, os
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort03_lib import iaaft
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/sort04_results.json'; NS = 20; TAU_TR = 2
GROUPS = ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S')
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
def pipeline(x):
    lab = microstates(embed(x, 5, 2), 30, seed=0); P, pi, pcca = est(lab, 2); return analyze_description(P, pi, indicator(pi, pcca), nmax_cap=3000)
def TR(x, tau=TAU_TR):
    d = x[tau:] - x[:-tau]; return float(np.mean(d ** 3) / np.mean(d ** 2) ** 1.5)
res = {}
for grp in GROUPS:
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4 == 0: continue                      # кратные 4 — пилотные 25 сегментов COG-01/SORT-03, не в зачёт
        name = f'EEG_{grp}_{os.path.basename(fp)[:4]}'; x = np.loadtxt(fp); r = pipeline(x)
        rng = np.random.default_rng(zlib.crc32(name.encode()))
        surs = [iaaft(x, rng) for _ in range(NS)]; sur = [pipeline(y) for y in surs]
        e_eeg = float(r['C1'] - r['rho']); e_s = np.array([s['C1'] - s['rho'] for s in sur]); a_s = np.array([s['a_plus'] for s in sur]); rho_s = np.array([s['rho'] for s in sur])
        tr = TR(x); tr_s = np.array([TR(y) for y in surs]); tr_p95 = float(np.percentile(np.abs(tr_s), 95)); z = float((tr - tr_s.mean()) / tr_s.std()) if tr_s.std() > 0 else float('nan')
        e_p95 = float(np.percentile(e_s, 95))
        res[name] = dict(group=grp[0], rho=r['rho'], C1=r['C1'], e=e_eeg, born=bool(r['born_rho']), a_plus=r['a_plus'], n_life=r.get('n_life_rho'),
                         sur_frac=float(np.mean([s['born_rho'] for s in sur])), e_p95=e_p95, e_above=bool(e_eeg > e_p95), born_above=bool(r['born_rho'] and e_eeg > e_p95),
                         a_p95=float(np.percentile(a_s, 95)), a_above=bool(r['a_plus'] > np.percentile(a_s, 95)), rho_sur_mean=float(rho_s.mean()), rho_dev=float(abs(rho_s.mean() - r['rho'])),
                         TR=tr, TR_sur_abs_p95=tr_p95, TR_z=z, TR_sig=bool(abs(tr) > tr_p95))
        d = res[name]; print(f"{name}: ρ={d['rho']:.3f} e={d['e']:+.3f} рожд={d['born']} a₊={d['a_plus']:.2f} | сурр: рожд {d['sur_frac']:.2f}, e P95 {d['e_p95']:+.3f} → сверх {d['e_above']} (строго {d['born_above']}); ρ̄ {d['rho_sur_mean']:.3f} (Δ {d['rho_dev']:.3f}) | TR={d['TR']:+.3f} P95|TR_сурр|={d['TR_sur_abs_p95']:.3f} z={d['TR_z']:+.1f} знач={d['TR_sig']} [{time.time()-t0:.0f}s]", flush=True)
# ---- сводка по группам (тест: 75 новых) ----
names = list(res)
def cnt(g, key): return int(sum(res[n][key] for n in names if res[n]['group'] == g))
G = {g: dict(n=int(sum(res[n]['group'] == g for n in names)), TR_sig=cnt(g, 'TR_sig'), born=cnt(g, 'born'), e_above=cnt(g, 'e_above'), born_above=cnt(g, 'born_above'), a_above=cnt(g, 'a_above'),
             sur_frac_mean=float(np.mean([res[n]['sur_frac'] for n in names if res[n]['group'] == g])), rho_ok=int(sum(res[n]['rho_dev'] <= 0.03 for n in names if res[n]['group'] == g))) for g in 'ABCDE'}
above = [n for n in names if res[n]['e_above']]; rest = [n for n in names if not res[n]['e_above']]
share_above = float(np.mean([res[n]['TR_sig'] for n in above])) if above else float('nan'); share_rest = float(np.mean([res[n]['TR_sig'] for n in rest])) if rest else float('nan')
diff = share_above - share_rest if above and rest else float('nan')
V = dict(groups=G, n_above=len(above), n_rest=len(rest), share_TR_above=share_above, share_TR_rest=share_rest, share_diff=float(diff),
         above_names=above, born_above_names=[n for n in names if res[n]['born_above']], born_names=[n for n in names if res[n]['born']],
         total_e_above=len(above), total_born=int(sum(res[n]['born'] for n in names)), total_born_above=int(sum(res[n]['born_above'] for n in names)), total_TR_sig=int(sum(res[n]['TR_sig'] for n in names)))
V['PR1'] = bool(G['E']['TR_sig'] >= 12 and G['D']['TR_sig'] >= 9 and G['A']['TR_sig'] <= 6)
V['PR2'] = bool(G['E']['born_above'] >= 2 and G['A']['born_above'] + G['B']['born_above'] <= 1)
V['PR3'] = bool(G['E']['e_above'] >= 5 and G['A']['e_above'] <= 3)
V['PR4'] = bool(above and rest and diff >= 0.10)
V['K1'] = bool(G['E']['TR_sig'] < 8); V['K2'] = bool(G['E']['born_above'] == 0); V['K3'] = bool(G['E']['e_above'] <= 1); V['K4'] = bool(above and rest and diff <= -0.10)
# джекнайф по сегментам: запас счёта над кромкой «≥» (удаление одного сегмента-события снимает 1)
V['margins'] = dict(PR1_E=G['E']['TR_sig'] - 12, PR1_D=G['D']['TR_sig'] - 9, PR2_E=G['E']['born_above'] - 2, PR3_E=G['E']['e_above'] - 5, PR4=float(diff - 0.10) if above and rest else None)
# LOO для P-R4: разность долей при удалении каждого сегмента
loo = []
for n in names:
    ab = [m for m in above if m != n]; rs = [m for m in rest if m != n]
    if ab and rs: loo.append(float(np.mean([res[m]['TR_sig'] for m in ab]) - np.mean([res[m]['TR_sig'] for m in rs])))
V['PR4_loo_min'] = float(min(loo)) if loo else None; V['PR4_loo_max'] = float(max(loo)) if loo else None
# ---- сводка по 100 (25 пилотных + 75; не в зачёт) ----
try:
    p3 = json.load(open('/home/claude/sort03_results.json'))['segments']; p4 = json.load(open('/home/claude/sort04_pilot.json'))
    S100 = {}
    for g in 'ABCDE':
        old = [n for n in p3 if n.split('_')[1] == g]
        S100[g] = dict(TR_sig=G[g]['TR_sig'] + int(sum(p4[n]['sig'] for n in old)), e_above=G[g]['e_above'] + int(sum(p3[n]['e_above'] for n in old)),
                       born_above=G[g]['born_above'] + int(sum(p3[n]['born'] and p3[n]['e_above'] for n in old)), born=G[g]['born'] + int(sum(p3[n]['born'] for n in old)), n=G[g]['n'] + len(old))
    V['summary100'] = S100
except Exception as ex:
    V['summary100'] = f'нет: {ex}'
json.dump(dict(segments=res, verdict=V, params=dict(NS=NS, tau_TR=TAU_TR, k=30, m=5, step=2, tau_msm=2, seed_kmeans=0, seed_sur='crc32(name)')), open(OUT, 'w'), default=float, ensure_ascii=False, indent=0)
print('ГРУППЫ', json.dumps(G, ensure_ascii=False)); print('ВЕРДИКТ', json.dumps({k: v for k, v in V.items() if k not in ('groups', 'above_names')}, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
