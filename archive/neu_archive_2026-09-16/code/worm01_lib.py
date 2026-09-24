"""WORM-01 — библиотека: позная динамика C. elegans (5 собственных поз, 16 Гц), куски без NaN, многомерный iAAFT (Schreiber–Schmitz 2000:
общий фазовый сдвиг по частотам, подгоняемый к исходным кросс-фазам; амплитудная подгонка по каналам), конвейер
«вложение K кадров → k-means → необратимая ML-MSM при лаге τ → PCCA(2) обратимой MSM», два радиуса, вес a₊, постоянство,
обратимый оценщик (t_w), метка направления волны по угловому моменту в плоскости (a₁, a₂)."""
import numpy as np, warnings, sys
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description, spectrum_info
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
FS = 16.0

def load_pieces(path='/home/claude/worm/eigenworm.npy'):
    X = np.load(path); n = len(X); bad = np.isnan(X).any(1); pieces = []; s = None
    for i in range(n):
        if not bad[i] and s is None: s = i
        if bad[i] and s is not None: pieces.append((s, i)); s = None
    if s is not None: pieces.append((s, n))
    return X, pieces

def embed_multi(X, K, step=1):
    """вектор запаздываний из K кадров всех каналов: строки t = (K−1)·step … n−1; порядок [x_t, x_{t−step}, …]"""
    n = len(X); m = n - (K - 1) * step
    return np.concatenate([X[(K - 1 - j) * step: (K - 1 - j) * step + m] for j in range(K)], axis=1)

def angular_momentum_label(X, W=23):
    """знак сглажённого углового момента a₁ȧ₂ − a₂ȧ₁ (окно W кадров): направление бегущей волны; +1 — большинство (вперёд), −1 — противоположное"""
    a1, a2 = X[:, 0], X[:, 1]; M = a1 * np.gradient(a2) - a2 * np.gradient(a1); Ms = np.convolve(M, np.ones(W) / W, mode='same')
    maj = 1.0 if np.mean(Ms < 0) >= 0.5 else -1.0   # знак большинства
    return np.where(Ms * maj < 0, 1, -1), Ms

def iaaft_multi(X, rng, n_iter=100):
    """многомерный iAAFT: сохраняет амплитудные спектры каждого канала, кросс-спектры (через общий сдвиг фаз) и распределения амплитуд"""
    X = np.asarray(X, float); n, c = X.shape; xs = np.sort(X, axis=0); F = np.fft.rfft(X, axis=0); amp = np.abs(F); ph0 = np.angle(F)
    Y = X[rng.permutation(n)]                      # одна и та же перестановка для всех каналов
    for _ in range(n_iter):
        G = np.fft.rfft(Y, axis=0); ph = np.angle(G)
        psi = np.angle(np.sum(np.exp(1j * (ph - ph0)), axis=1))   # общий сдвиг по частоте, ближайший к текущим фазам
        Y = np.fft.irfft(amp * np.exp(1j * (ph0 + psi[:, None])), n, axis=0)
        ranks = np.argsort(np.argsort(Y, axis=0), axis=0); Y = np.take_along_axis(xs, ranks, axis=0)
    return Y

def labels_for(Xlist, K, k, seed=0):
    """общий k-means по вложениям всех кусков; возвращает список меток по кускам"""
    E = [embed_multi(X, K) for X in Xlist]; lab = microstates(np.concatenate(E, axis=0), k, seed=seed)
    out = []; p = 0
    for e in E: out.append(lab[p:p + len(e)]); p += len(e)
    return out

def msm_pair(labs, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch([l.astype(int) for l in labs]).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return c, msm, msr

def analyze(labs, tau, dir_labels=None, K=None, nmax_cap=3000):
    """спектр и двухблочное описание при лаге τ; dir_labels — метки направления по кадрам (для точности блоков)"""
    c, msm, msr = msm_pair(labs, tau); P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution)
    states = np.asarray(c.state_symbols); pcca = np.asarray(msr.pcca(2).assignments)
    r = analyze_description(P, pi, indicator(pi, pcca), nmax_cap=nmax_cap)
    S = spectrum_info(P, pi); lam = S['lam_rho']; theta = float(abs(np.angle(lam)))
    perm = bool(r['born_plus'] and r.get('n_life_plus') is not None and r['n_life_plus'] >= r['n_max'])
    # обратимый оценщик: вторая собственная шкала обратимой MSM (в кадрах)
    ev_r = np.sort(np.real(np.linalg.eigvals(np.asarray(msr.transition_matrix))))[::-1]; lam2r = float(ev_r[1]) if len(ev_r) > 1 else float('nan')
    t_w = float(-tau / np.log(lam2r)) if 0 < lam2r < 1 else float('nan'); t_rp = float(-tau / np.log(r['rho_plus'])) if r['rho_plus'] and 0 < r['rho_plus'] < 1 else float('nan')
    out = dict(tau=int(tau), n_states=int(len(states)), rho=r['rho'], rho_plus=r['rho_plus'], rho_gap=float(r['rho'] - r['rho_plus']) if r['rho_plus'] else None,
               theta_rho=theta, alternating=bool(np.real(lam) < 0), complex_rho=bool(abs(np.imag(lam)) > 1e-9), C1=r['C1'], e_plus=float(r['C1'] - r['rho_plus']) if r['rho_plus'] else None,
               born_plus=bool(r['born_plus']), born_rho=bool(r['born_rho']), a_plus=r['a_plus'], n_life=r.get('n_life_plus'), n_max=r['n_max'], perm=perm,
               t_rho_plus_frames=t_rp, t_w_frames=t_w, f_est=float(t_w / t_rp) if (t_rp and t_rp > 0 and np.isfinite(t_w)) else float('nan'), lam2_rev=lam2r)
    if dir_labels is not None and K is not None:
        # блок кадра = блок его микросостояния (кадр t ↔ строка вложения t − (K−1)); метка — по центральному кадру окна
        acc = []
        idx_map = {int(s): i for i, s in enumerate(states)}
        for l, d in zip(labs, dir_labels):
            blk = np.array([pcca[idx_map[int(s)]] if int(s) in idx_map else -1 for s in l]); dd = d[(K - 1) // 2: (K - 1) // 2 + len(l)]
            ok = blk >= 0; blk = blk[ok]; dd = dd[ok]
            acc.append((blk, dd))
        blk = np.concatenate([a for a, _ in acc]); dd = np.concatenate([b for _, b in acc])
        def bacc(b):
            tpr = np.mean(b[dd == 1] == 1) if np.any(dd == 1) else np.nan; tnr = np.mean(b[dd == -1] == 0) if np.any(dd == -1) else np.nan
            return float((tpr + tnr) / 2)
        b1 = bacc(blk); b2 = bacc(1 - blk); out['bacc_dir'] = float(max(b1, b2)); out['block_frac'] = float(np.mean(blk))
    return out

def direction_blocks(labs, dir_labels, K, states):
    """именованное описание: блок микросостояния = знак большинства направления волны среди его кадров (1 — вперёд, 0 — не вперёд)"""
    idx_map = {int(s): i for i, s in enumerate(states)}; num = np.zeros(len(states)); den = np.zeros(len(states))
    for l, d in zip(labs, dir_labels):
        dd = d[(K - 1) // 2: (K - 1) // 2 + len(l)]
        for s, v in zip(l, dd):
            i = idx_map.get(int(s));
            if i is None: continue
            den[i] += 1; num[i] += (v == 1)
    return (num >= 0.5 * np.maximum(den, 1)).astype(int)

def analyze_named(labs, tau, dir_labels, K, nmax_cap=3000):
    """описание «вперёд / не вперёд» по большинству в микросостоянии: рождение по ρ₊, вес, жизнь; плюс совпадение с PCCA(2)"""
    c, msm, msr = msm_pair(labs, tau); P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution); states = np.asarray(c.state_symbols)
    blk = direction_blocks(labs, dir_labels, K, states); h = indicator(pi, blk)
    if h is None or blk.min() == blk.max(): return dict(tau=int(tau), degenerate=True)
    r = analyze_description(P, pi, h, nmax_cap=nmax_cap)
    pcca = np.asarray(msr.pcca(2).assignments); agree = float(max(np.mean(pcca == blk), np.mean(pcca != blk)))
    perm = bool(r['born_plus'] and r.get('n_life_plus') is not None and r['n_life_plus'] >= r['n_max'])
    return dict(tau=int(tau), degenerate=False, C1=r['C1'], e_plus=float(r['C1'] - r['rho_plus']), born_plus=bool(r['born_plus']), a_plus=r['a_plus'], n_life=r.get('n_life_plus'), n_max=r['n_max'], perm=perm,
                pi_block=float(np.sum(pi * blk)), agree_pcca=agree, rho_plus=r['rho_plus'])
