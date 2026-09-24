"""WMAP-01 — форма числового образа W(A₀) оценённого оператора переноса: граница по опорной функции, спектр, мнимая ширина, выступ за круг. По PREREG 2026-09-10."""
import numpy as np, json, sys, time, warnings, os
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from hor02_lib import telegraph
from zeta01_lib import embed
from cog01_lib import sym_form, restrict, spectral_radius
B = '/home/claude'; OUT = f'{B}/wmap01_results.json'; res = {}; t0 = time.time()
WANT = {'DIP_400_s211', 'DIP_300_s211', 'SLEEP_SC4001E0', 'NGRIP_2D_20yr_W', 'EEG_A_Z_Z013', 'EEG_C_N_N013', 'EEG_E_S_S001', 'thermoacoustic_1_m4', 'thermoacoustic_2_m4'}
def A0_of(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest(); m = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model()
    P = np.asarray(m.transition_matrix); pi = np.asarray(m.stationary_distribution); return restrict(sym_form(P, pi), pi)
def shape(A0, n_ang=360):
    th = np.linspace(0, 2 * np.pi, n_ang, endpoint=False); h = []; pts = []
    for t in th:
        H = (np.exp(-1j * t) * A0 + np.exp(1j * t) * A0.conj().T) / 2; ev, U = np.linalg.eigh(H); f = U[:, -1]; z = complex(f.conj() @ A0 @ f); h.append(float(ev[-1])); pts.append((z.real, z.imag))
    ev = np.linalg.eigvals(A0); rho = float(np.max(np.abs(ev))); pts = np.array(pts)
    return dict(rho=rho, w=float(np.max(h)), delta=float(np.max(h) - rho), im_width=float(np.max(np.abs(pts[:, 1]))), frac_outside=float(np.mean(np.abs(pts[:, 0] + 1j * pts[:, 1]) > rho + 1e-9)),
                boundary=[[round(float(x), 4), round(float(y), 4)] for x, y in pts[::4]], spectrum=[[round(float(z.real), 4), round(float(z.imag), 4)] for z in ev])
def run(name, F, tau, k, group):
    lab = microstates(F, k, seed=0); r = shape(A0_of(lab, tau)); r['group'] = group
    if name == 'EEG_A_Z_Z013':
        n = len(lab); r['halves_im_width'] = [shape(A0_of(lab[:n // 2], tau), 90)['im_width'], shape(A0_of(lab[n // 2:], tau), 90)['im_width']]
    S = A0_of(lab, tau); S = (S + S.T) / 2; r['sym_im_width'] = shape(S, 90)['im_width']
    res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    print(f"{name:22s} [{group}] ρ {r['rho']:.3f} w {r['w']:.3f} δ {r['delta']:.3f} мнимая ширина {r['im_width']:.3f} (симм. часть {r['sym_im_width']:.4f}) доля границы вне круга {r['frac_outside']:.2f} {r.get('halves_im_width', '')} [{time.time()-t0:.0f}s]", flush=True)
rng = np.random.default_rng(1000 * 40 + 0); x, _ = telegraph(8000, 40, rng); run('tel40_m4', embed(x, 4), 1, 30, 'tel')
for name, F, tau, k, group in series(('real', 'eeg', 'insilico')):
    if name in WANT: run(name, F, tau, k, group)
rev = [k for k, v in res.items() if v['group'] in ('dip', 'real') and not k.startswith('thermo')]; osc = [k for k, v in res.items() if v['group'] == 'eeg' or k.startswith('thermo')]
V = dict(PW1=dict(osc_ge01=int(sum(res[k]['im_width'] >= 0.1 for k in osc)), n_osc=len(osc), rev_le002=int(sum(res[k]['im_width'] <= 0.02 for k in rev)), n_rev=len(rev)),
         PW2=dict(osc_frac=[round(res[k]['frac_outside'], 2) for k in osc], rev_frac=[round(res[k]['frac_outside'], 2) for k in rev]), PW3=dict(tel_im_width=res['tel40_m4']['im_width']),
         K1=dict(hit=bool(any(res[k]['im_width'] > 0.05 for k in rev))), K2=dict(hit=bool(sum(res[k]['im_width'] < 0.05 for k in osc) >= 3)))
V['PW1']['ok'] = bool(V['PW1']['osc_ge01'] >= 4 and V['PW1']['rev_le002'] == len(rev)); V['PW2']['ok'] = bool(all(f >= 0.3 for f in V['PW2']['osc_frac']) and all(f == 0 for f in V['PW2']['rev_frac']))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), default=float); print('== ВЕРДИКТЫ WMAP-01 ==', json.dumps(V, ensure_ascii=False))
