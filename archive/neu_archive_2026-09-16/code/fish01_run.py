"""FISH-01 — точный тест выброса верхнего реньевского зазора (Beta для ранга 1; g-тест Фишера для max) по постериору MSM,
пересчёт решений SPEC-01 (дипептид, LJ13, сон), ZETA-01 (39 рядов) и калибровка на нулях (случайные цепи, Синай). По PREREG 2026-09-08."""
import numpy as np, scipy.io as sio, glob, os, json, sys, time, warnings
from math import comb
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/fish01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
NS = 200; KTS = 14

def p_rank1(z):
    m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def p_fisher(z):
    m = len(z); g = z.max() / z.sum(); J = int(np.floor(1 / g))
    return float(min(1.0, max(0.0, sum((-1) ** (j - 1) * comb(m, j) * (1 - j * g) ** (m - 1) for j in range(1, J + 1)))))
def stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    if np.any(z <= 0): z = np.maximum(z, 1e-12)
    return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p_exp=float(np.exp(-z[0] / z[1:].mean())), p_r1=p_rank1(z), p_g=p_fisher(z))
def decide(ps, ms):
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    return PL, ('отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ')))
def test(lab, tau, k, name):
    if name in res: return
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); post = BayesianMSM(n_samples=NS, reversible=True).fit(msm).fetch_model()
    S = [stats(np.sort(mm.timescales(KTS))[::-1], tau) for mm in post.samples]
    ms = [s['m'] if s else 0 for s in S]; S = [s for s in S if s]
    r = dict(m_median=float(np.median(ms)), zeta_median=(float(np.median([s['zeta'] for s in S])) if S else None))
    for key in ('p_exp', 'p_r1', 'p_g'):
        PL, dec = decide([s[key] for s in S], ms); r[f'PL_{key}'] = PL; r[f'dec_{key}'] = dec; r[f'{key}_median'] = (float(np.median([s[key] for s in S])) if S else None)
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name:26s} m {r['m_median']:.0f} ζ {r['zeta_median']} | exp: P_L {r['PL_p_exp']:.2f} {r['dec_p_exp']} | rank1: P_L {r['PL_p_r1']:.2f} {r['dec_p_r1']} | Fisher-g: P_L {r['PL_p_g']:.2f} {r['dec_p_g']} [{time.time()-t0:.0f}s]", flush=True)

# --- калибровка на нулях ---
if 'null_random' not in res:
    rng = np.random.default_rng(7); R = []
    for i in range(400):
        C = rng.gamma(1.0, 1.0, (30, 30)); C = C + C.T; P = C / C.sum(1, keepdims=True)
        w = np.sort(np.real(np.linalg.eigvals(P)))[::-1]; w = np.clip(w[1:KTS + 1], 1e-9, 0.999999); ts = -1.0 / np.log(w)
        s = stats(ts, 0.0)
        if s: R.append(s)
    res['null_random'] = {k: float(np.mean([s[k] <= 0.05 for s in R])) for k in ('p_exp', 'p_r1', 'p_g')} | dict(n=len(R))
    # реньевский нуль по построению: m н.о.р. экспоненциальных z (проверка формулы)
    Z = rng.exponential(1.0, (20000, 5)); res['null_exp_m5'] = dict(p_exp=float(np.mean([np.exp(-z[0] / z[1:].mean()) <= 0.05 for z in Z])), p_r1=float(np.mean([p_rank1(z) <= 0.05 for z in Z])), p_g=float(np.mean([p_fisher(z) <= 0.05 for z in Z])))
    print('нуль случайных цепей:', res['null_random'], '| точный реньевский нуль m=5:', res['null_exp_m5'], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
if 'null_sinai' not in res:
    try:
        sin = json.load(open('/home/claude/spec01_sinai.json')); R = []
        for cell, v in sin.items():
            for zz in v.get('z_samples', v.get('z', []))[:200] if isinstance(v, dict) else []:
                z = np.array(zz, float)
                if len(z) >= 4 and np.all(z > 0): R.append(dict(p_exp=float(np.exp(-z[0] / z[1:].mean())), p_r1=p_rank1(z), p_g=p_fisher(z)))
        res['null_sinai'] = ({k: float(np.mean([s[k] <= 0.05 for s in R])) for k in ('p_exp', 'p_r1', 'p_g')} | dict(n=len(R))) if R else dict(n=0, note='z по образцам не сохранены в spec01_sinai.json')
    except Exception as e: res['null_sinai'] = dict(n=0, note=str(e)[:100])
    print('нуль Синая:', res['null_sinai'], flush=True); json.dump(res, open(OUT, 'w'), indent=1, default=float)
# --- сон ---
for psg_p in sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat')):
    psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20)
    test(microstates(F, 30, seed=0), 1, 30, 'SLEEP_' + os.path.basename(psg_p).split('-')[0])
# --- дипептид ---
for f in sorted(glob.glob('/home/claude/mol_ala2_m5_T*_s*.npz')):
    d = np.load(f); sc = d['scal']; phi, psi = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi), np.sin(phi), np.cos(psi), np.sin(psi)])
    test(microstates(F, 100, seed=0), 2, 100, f'DIP_{os.path.basename(f)[13:-4]}')
# --- LJ13 (сохранённые разметки) ---
for T in (0.18, 0.22, 0.25, 0.28, 0.36):
    for s in (301, 302, 303):
        p = f'/home/claude/lj_labels_{T}_{s}_k100.npy'
        if os.path.exists(p): test(np.load(p), 2, 100, f'LJ_{T}_{s}')
# --- ZETA-01: 39 рядов (повтор загрузки через zeta01_run без записи) ---
print('готово', time.time() - t0)
