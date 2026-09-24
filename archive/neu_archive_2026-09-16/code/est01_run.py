"""EST-01 — завышение верхней шкалы обратимой ML-MSM на вложениях запаздываний: калибровка на телеграфе (k, m, τ) и пересчёт архива
на замороженных словарях обратимой и необратимой оценками. По PREREG 2026-09-09."""
import numpy as np, pandas as pd, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
import scipy.io as sio
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from zeta01_lib import embed, spacing_stats
from hor02_lib import telegraph
B = '/home/claude'; OUT = f'{B}/est01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
def spectra(lab, tau, kts=14):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest(); out = {}
    for name, rev in (('rev', True), ('nonrev', False)):
        try:
            msm = MaximumLikelihoodMSM(reversible=rev).fit(c).fetch_model(); ts = np.sort(np.abs(np.real(msm.timescales(kts))))[::-1]
            ts = ts[np.isfinite(ts) & (ts > 0)]; st = spacing_stats(ts, tau)
            out[name] = dict(t1=float(ts[0]), its=[float(x) for x in ts[:6]], zeta=(st['z1_rest'] if st else None), m=(st['m'] if st else 0))
        except Exception as e:
            out[name] = dict(t1=None, its=[], zeta=None, m=0, error=str(e))
    return out
def cls(z): return None if z is None else ('выброс' if z >= 2 else ('иерархия' if z >= 0.9 else 'континуум'))
def run(name, F, tau, k, kind):
    if name in res: return
    n = len(F); lab = microstates(F, k, seed=0); S = spectra(lab, tau); Sh = spectra(microstates(F[:n // 2], k, seed=0), tau)
    f = (S['rev']['t1'] / S['nonrev']['t1']) if (S['rev']['t1'] and S['nonrev']['t1']) else None
    fh = (Sh['rev']['t1'] / Sh['nonrev']['t1']) if (Sh['rev']['t1'] and Sh['nonrev']['t1']) else None
    r = dict(kind=kind, n=n, k=k, tau=tau, full=S, half=Sh, f=f, f_half=fh, cls_rev=cls(S['rev']['zeta']), cls_nonrev=cls(S['nonrev']['zeta']))
    res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    print(f"{name:26s} [{kind}] t1 обр {S['rev']['t1']:.1f} необр {S['nonrev']['t1']:.1f} f = {f:.2f} (половина {fh if fh is None else round(fh, 2)}) | ζ обр {S['rev']['zeta'] if S['rev']['zeta'] is None else round(S['rev']['zeta'], 2)} → необр {S['nonrev']['zeta'] if S['nonrev']['zeta'] is None else round(S['nonrev']['zeta'], 2)} | {r['cls_rev']} → {r['cls_nonrev']} [{time.time()-t0:.0f}s]", flush=True)
stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
if stage in ('all', 'tel'):
    if 'telegraph' not in res:
        T = {}
        for s in range(5):
            rng = np.random.default_rng(500 + s); x, h = telegraph(8000, 40, rng); true_t1 = None
            lab_h = (h > 0).astype(int); true_t1 = spectra(lab_h[:len(embed(x, 4))], 1)['nonrev']['t1']
            for k in (2, 4, 10, 30, 100):
                S = spectra(microstates(embed(x, 4), k, seed=0), 1); T.setdefault(f'k{k}', []).append(S['rev']['t1'] / S['nonrev']['t1'])
            for m in (1, 2, 4, 8):
                S = spectra(microstates(embed(x, m), 30, seed=0), 1); T.setdefault(f'm{m}', []).append(S['rev']['t1'] / S['nonrev']['t1'])
                if m == 1:
                    for k in (10, 30, 100): S = spectra(microstates(embed(x, 1), k, seed=0), 1); T.setdefault(f'm1_k{k}', []).append(S['rev']['t1'] / S['nonrev']['t1'])
            for tau in (1, 2, 4, 8):
                S = spectra(microstates(embed(x, 4), 30, seed=0), tau); T.setdefault(f'tau{tau}', []).append(S['rev']['t1'] / S['nonrev']['t1'])
            T.setdefault('true_t1', []).append(true_t1)
        res['telegraph'] = {kk: dict(vals=v, median=float(np.median(v))) for kk, v in T.items()}; json.dump(res, open(OUT, 'w'), default=float)
        print('телеграф f:', {kk: round(v['median'], 2) for kk, v in res['telegraph'].items()}, flush=True)
if stage in ('all', 'real'):
    import xlrd
    wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
    for r_ in range(61, sh.nrows):
        a, d = sh.cell_value(r_, 0), sh.cell_value(r_, 2)
        if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
    ages = np.array(ages); d18 = np.array(d18)[np.argsort(ages)]
    run('NGRIP_d18O_20yr_m4', embed(d18, 4), 1, 30, 'emb'); run('NGRIP_d18O_20yr_m1', d18.reshape(-1, 1), 1, 30, 'raw')
    for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
        files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
        for i, fp in enumerate(files):
            if i % 4: continue
            run(f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(np.loadtxt(fp), 5, 2), 2, 30, 'emb')
    df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv'); num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
    X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]; run('plankton_Beninca_12sp', X, 1, 15, 'raw')
    lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]; run('LR04_benthic_m4', embed(x[:3000], 4), 1, 30, 'emb')
    def read_wdc(fp, col):
        out = []
        for line in open(fp, encoding='latin-1'):
            p = line.split()
            if len(p) < col + 1: continue
            try: out.append([float(v) for v in p[:col + 1]])
            except Exception: pass
        return np.array(out)
    deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); run('EPICA_deuterium_m4', embed(deu[:, 3], 4), 1, 30, 'emb')
    s_ = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); run('sunspots_monthly_m4', embed(s_, 4, 3), 1, 30, 'emb')
    m_ = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m_.columns if c.upper().startswith('NEW YORK')][0]; mx = m_[col].interpolate().to_numpy(float); run('measles_NY_weekly_m4', embed(np.log1p(mx), 4, 2), 1, 30, 'emb')
    c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
    for country in ('Germany', 'US', 'Italy'):
        row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.maximum(np.diff(row), 0); run(f'COVID_{country}_daily_m4', embed(np.log1p(inc), 4), 1, 15, 'emb')
    th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv'); ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')][0]
    for tid in sorted(th['tsid'].unique())[:3]:
        xx = th[th['tsid'] == tid][ycol].to_numpy(float)[:20000]; run(f'thermoacoustic_{tid}_m4', embed(xx, 4, 2), 2, 30, 'emb')
    for psg_p in sorted(glob.glob(f'{B}/combsleepnet/example_data/psg/*.mat')):
        psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20); run('SLEEP_' + os.path.basename(psg_p).split('-')[0], F, 1, 15, 'raw')
    from dust01_run_lib import load, std
    a2, d2, lc2 = load(f'{B}/ngrip2d/ngrip_ca_20yr_full.txt'); run('NGRIP_2D_20yr_W', std(np.column_stack([d2, lc2])), 1, 15, 'raw'); mg = a2 >= 23000; run('NGRIP_2D_20yr_Wg', std(np.column_stack([d2[mg], lc2[mg]])), 1, 15, 'raw')
    # DUST-01/02 описательно: замороженные словари DUST-02 (k = 20, τ = 1; 1D — вложение m = 2)
    for wname, mask in (('W', np.ones(len(a2), bool)), ('Wg', mg)):
        run(f'DUST_1D_{wname}', std(embed(d2[mask], 2)), 1, 20, 'dust1d'); run(f'DUST_2D_{wname}', std(np.column_stack([d2[mask], lc2[mask]])), 1, 20, 'dust2d')
if stage in ('all', 'insilico'):
    for f in sorted(glob.glob(f'{B}/mol_ala2_m5_T*_s*.npz')):
        sc = np.load(f)['scal']; phi_, psi_ = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi_), np.sin(phi_), np.cos(psi_), np.sin(psi_)]); run(f'DIP_{os.path.basename(f)[13:-4]}', F, 2, 100, 'raw')
    for fp in sorted(glob.glob(f'{B}/net01L_T*_s*.npz')):
        d = np.load(fp); run('LJ13_' + os.path.basename(fp)[7:-4], d['D'].astype(float), 2, 100, 'raw')
print('ГОТОВО', f'{time.time()-t0:.0f}s', flush=True)
