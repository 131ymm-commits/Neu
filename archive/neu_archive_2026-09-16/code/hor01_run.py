"""HOR-01 — атлас шкал: верхняя шкала t₁ против горизонта (префиксы и суффиксы n/8…n), β = d ln t₁ / d ln n; реальные ряды (ZETA-01 + сон + NGRIP 2D),
in silico (LJ13 10⁵ кадров, дипептид), синтетика (AR(1), fGn 0.9, редкий телеграф). По PREREG 2026-09-09."""
import numpy as np, pandas as pd, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
import scipy.io as sio
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
B = '/home/claude'; OUT = f'{B}/hor01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
from zeta01_lib import embed

def t1(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); ts = np.sort(msm.timescales(3))[::-1]; return float(ts[0]) if np.isfinite(ts[0]) else None
def beta_curve(F, tau, k, name, group):
    if name in res: return
    n = len(F); fr = [1/8, 1/4, 1/2, 1] if n >= 2000 else [1/4, 1/2, 1]
    ns, tp, ts_ = [], [], []
    for f in fr:
        m = int(n * f); lab_p = microstates(F[:m], k, seed=0); lab_s = microstates(F[n - m:], k, seed=0)
        try: a = t1(lab_p, tau)
        except Exception: a = None
        try: b = t1(lab_s, tau)
        except Exception: b = None
        ns.append(m); tp.append(a); ts_.append(b)
    def slope(tv):
        ok = [i for i, v in enumerate(tv) if v is not None and v > 0]
        return float(np.polyfit(np.log([ns[i] for i in ok]), np.log([tv[i] for i in ok]), 1)[0]) if len(ok) >= 3 else None
    bp, bs = slope(tp), slope(ts_); beta = float(np.mean([x for x in (bp, bs) if x is not None])) if (bp is not None or bs is not None) else None
    cls = None if beta is None else ('сошлось' if beta < 0.15 else ('горизонт' if beta >= 0.5 else 'не установлено'))
    res[name] = dict(group=group, n=n, k=k, tau=tau, ns=ns, t1_prefix=tp, t1_suffix=ts_, beta_prefix=bp, beta_suffix=bs, beta=beta, cls=cls, agree=(bool(abs(bp - bs) <= 0.3) if (bp is not None and bs is not None) else None))
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name:28s} [{group}] n={n:6d} k={k} | t1 префиксы {[None if v is None else round(v, 1) for v in tp]} суффиксы {[None if v is None else round(v, 1) for v in ts_]} | β {None if beta is None else round(beta, 2)} (преф {None if bp is None else round(bp, 2)} / суф {None if bs is None else round(bs, 2)}) → {cls} [{time.time()-t0:.0f}s]", flush=True)

# --- синтетика ---
rng = np.random.default_rng(0); n = 4000
x = np.zeros(n); phi = np.exp(-1 / 10)
for i in range(1, n): x[i] = phi * x[i - 1] + rng.normal() * np.sqrt(1 - phi ** 2)
beta_curve(embed(x, 4), 1, 30, 'synth_AR1_t10', 'synth')
def fgn(n, H, rng):
    # спектральный синтез: дробный гауссов шум через спектр 1/f^(2H−1)
    f = np.fft.rfftfreq(n)[1:]; amp = f ** (-(2 * H - 1) / 2); ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(f)))
    X = np.concatenate([[0], amp * ph]); y = np.fft.irfft(X, n=n); return (y - y.mean()) / y.std()
beta_curve(embed(fgn(n, 0.9, rng), 4), 1, 30, 'synth_fGn_H0.9', 'synth')
s = np.zeros(n); state = 1.0; i = 0
while i < n:
    L = int(rng.exponential(1000)) + 1; s[i:i + L] = state; state = -state; i += L
beta_curve(embed(s + 0.3 * rng.normal(size=n), 4), 1, 30, 'synth_telegraph_1000', 'synth')
# --- реальные ряды ZETA-01 ---
import xlrd
wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
for r in range(61, sh.nrows):
    a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
    if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18)[np.argsort(ages)]
beta_curve(embed(d18, 4), 1, 30, 'NGRIP_d18O_20yr_m4', 'real'); beta_curve(d18.reshape(-1, 1), 1, 30, 'NGRIP_d18O_20yr_m1', 'real')
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4: continue
        beta_curve(embed(np.loadtxt(fp), 5, 2), 2, 30, f'EEG_{grp}_{os.path.basename(fp)[:4]}', 'eeg')
df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv'); num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]; beta_curve(X, 1, 15, 'plankton_Beninca_12sp', 'real')
lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]; beta_curve(embed(x[:3000], 4), 1, 30, 'LR04_benthic_m4', 'real')
def read_wdc(fp, col):
    out = []
    for line in open(fp, encoding='latin-1'):
        p = line.split()
        if len(p) < col + 1: continue
        try: out.append([float(v) for v in p[:col + 1]])
        except Exception: pass
    return np.array(out)
deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); beta_curve(embed(deu[:, 3], 4), 1, 30, 'EPICA_deuterium_m4', 'real')
s_ = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); beta_curve(embed(s_, 4, 3), 1, 30, 'sunspots_monthly_m4', 'real')
m_ = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m_.columns if c.upper().startswith('NEW YORK')][0]; mx = m_[col].interpolate().to_numpy(float); beta_curve(embed(np.log1p(mx), 4, 2), 1, 30, 'measles_NY_weekly_m4', 'real')
c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
for country in ('Germany', 'US', 'Italy'):
    row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.maximum(np.diff(row), 0); beta_curve(embed(np.log1p(inc), 4), 1, 15, f'COVID_{country}_daily_m4', 'real')
th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv'); ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')][0]
for tid in sorted(th['tsid'].unique())[:3]:
    xx = th[th['tsid'] == tid][ycol].to_numpy(float)[:20000]; beta_curve(embed(xx, 4, 2), 2, 30, f'thermoacoustic_{tid}_m4', 'real')
for psg_p in sorted(glob.glob(f'{B}/combsleepnet/example_data/psg/*.mat')):
    psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20); beta_curve(F, 1, 15, 'SLEEP_' + os.path.basename(psg_p).split('-')[0], 'real')
# NGRIP 2D (DUST-02)
from dust01_run_lib import load, std
a2, d2, lc2 = load(f'{B}/ngrip2d/ngrip_ca_20yr_full.txt'); beta_curve(std(np.column_stack([d2, lc2])), 1, 15, 'NGRIP_2D_20yr_W', 'real'); mg = a2 >= 23000; beta_curve(std(np.column_stack([d2[mg], lc2[mg]])), 1, 15, 'NGRIP_2D_20yr_Wg', 'real')
# --- in silico ---
for fp in sorted(glob.glob(f'{B}/net01L_T*_s*.npz')):
    d = np.load(fp); beta_curve(d['D'].astype(float), 2, 100, 'LJ13_' + os.path.basename(fp)[7:-4], 'insilico')
for f in sorted(glob.glob(f'{B}/mol_ala2_m5_T*_s*.npz')):
    sc = np.load(f)['scal']; phi_, psi_ = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi_), np.sin(phi_), np.cos(psi_), np.sin(psi_)])
    beta_curve(F, 2, 100, f'DIP_{os.path.basename(f)[13:-4]}', 'insilico')
# --- вердикты ---
def grp(g): return {k: v for k, v in res.items() if v.get('group') == g and v.get('beta') is not None}
real, eeg, ins, syn = grp('real'), grp('eeg'), grp('insilico'), grp('synth')
fr_real = np.mean([v['beta'] >= 0.3 for v in real.values()]); n_ins_hi = sum(v['beta'] >= 0.3 for v in ins.values()); n_ins_lo = sum(v['beta'] < 0.15 for v in ins.values())
V = dict(PH1=dict(ok=bool(fr_real >= 0.6), frac=float(fr_real), n=len(real), betas={k: round(v['beta'], 2) for k, v in real.items()}),
         PH2=dict(ok=bool(n_ins_lo >= 12), n_lo=n_ins_lo, n=len(ins), betas={k: round(v['beta'], 2) for k, v in ins.items()}),
         PH3=dict(ok=bool(syn['synth_AR1_t10']['beta'] < 0.15 and syn['synth_fGn_H0.9']['beta'] >= 0.3 and syn['synth_telegraph_1000']['beta'] >= 0.5), betas={k: round(v['beta'], 2) for k, v in syn.items()}),
         PH4=dict(ok=bool(np.median([v['beta'] for v in eeg.values()]) < 0.3), median=float(np.median([v['beta'] for v in eeg.values()])), n=len(eeg)),
         K1=dict(hit=bool(fr_real < 0.4)), K2=dict(hit=bool(n_ins_hi >= 3)), K3=dict(hit=bool(syn['synth_AR1_t10']['beta'] >= 0.3 or syn['synth_fGn_H0.9']['beta'] < 0.15)),
         agree=dict(real=float(np.mean([v['agree'] for v in real.values() if v['agree'] is not None])), eeg=float(np.mean([v['agree'] for v in eeg.values() if v['agree'] is not None]))))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
