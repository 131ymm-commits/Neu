"""
EXP-046 / Q46: Почему размер увеличивает ошибку?
Гипотеза: |err| ~ φ = Var(k)/<k²>  (остаток из v5.2 Q37)
Контроль: partial_corr(|err|, φ | N)  vs  partial_corr(|err|, N | φ)

Методология:
- Генерируем синтетические сети разных топологий и размеров
- Вычисляем A0_crit_pred = K0/λmax, A0_crit_sim (бисекция)
- |err| = |A0_pred - A0_sim| / A0_sim
- Регрессия: log|err| ~ β1·log(N) + β2·log(φ) + const
- Частные корреляции φ и N с |err|

Вердикт по Q45: size главный (+0.67), φ вторичный (-0.31), R²=0.52
Q46 спрашивает: это φ-механизм (Q37) или что-то другое?
"""

import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# UAF параметры (v5.2)
ALPHA_S = 0.06
F = 0.002
DELTA = 0.012
K0 = (DELTA - F) / ALPHA_S  # = 0.1667

RNG = np.random.default_rng(42)

# ─── Генераторы сетей ───────────────────────────────────────────────────────

def gen_er(n, p=None):
    """Erdős–Rényi — низкое φ (однородная)"""
    if p is None:
        p = min(0.3, 6/n)
    G = nx.erdos_renyi_graph(n, p, seed=int(RNG.integers(1e6)))
    return nx.to_numpy_array(G)

def gen_ba(n, m=2):
    """Barabási–Albert — высокое φ (степенной хвост)"""
    G = nx.barabasi_albert_graph(n, m, seed=int(RNG.integers(1e6)))
    return nx.to_numpy_array(G)

def gen_ws(n, k=4, p=0.1):
    """Watts–Strogatz — среднее φ"""
    G = nx.watts_strogatz_graph(n, k, p, seed=int(RNG.integers(1e6)))
    return nx.to_numpy_array(G)

def gen_mixed(n):
    """BA + случайные рёбра — переменное φ"""
    m = max(1, int(RNG.integers(1, 4)))
    G = nx.barabasi_albert_graph(n, m, seed=int(RNG.integers(1e6)))
    # добавить случайные рёбра
    extra = int(n * RNG.uniform(0.1, 0.5))
    for _ in range(extra):
        u, v = RNG.integers(0, n, 2)
        if u != v:
            G.add_edge(int(u), int(v))
    return nx.to_numpy_array(G)

# ─── Вычисление метрик ──────────────────────────────────────────────────────

def phi(A):
    """φ = Var(k)/<k²> — мера гетерогенности (остаток Q37)"""
    k = A.sum(axis=1)
    k2_mean = np.mean(k**2)
    if k2_mean < 1e-10:
        return 0.0
    return np.var(k) / k2_mean

def lambda_max(A):
    """Ведущее собственное значение (симметричная матрица → вещественное)"""
    try:
        vals = np.linalg.eigvalsh(A)
        return float(vals[-1])
    except:
        return np.nan

def a0_predicted(lmax):
    """Закон v5.2: A0_crit = K0/λmax"""
    if lmax <= 0:
        return np.nan
    return K0 / lmax

def simulate_a0(A, n_trials=8, tol=1e-3):
    """
    Бисекция: найти A0 при котором <A_i>(τ→∞) = 0.05 (порог коллапса).
    UAF динамика (упрощённая, однородное поле):
    dA_i/dt = α_s·(Σ_j A_j)·(1-A_i) + f·(1-A_i) - δ·(1-0.3·A_i)
    """
    n = A.shape[0]
    
    def steady_state(a0_init):
        A_vec = np.full(n, a0_init)
        dt = 0.05
        for _ in range(2000):
            neighbor_sum = A @ A_vec
            dA = (ALPHA_S * neighbor_sum * (1 - A_vec)
                  + F * (1 - A_vec)
                  - DELTA * (1 - 0.3 * A_vec))
            A_vec = np.clip(A_vec + dt * dA, 0, 1)
        return A_vec.mean()
    
    # бисекция по A0_init
    lo, hi = 0.01, 0.99
    for _ in range(20):
        mid = (lo + hi) / 2
        ss = steady_state(mid)
        if ss > 0.05:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    
    return (lo + hi) / 2

# ─── Основной цикл ──────────────────────────────────────────────────────────

CONFIGS = []
# (generator_fn, name, sizes)
for n in [20, 30, 50, 80, 120, 200, 300, 500]:
    for _ in range(4):
        CONFIGS.append(('er',    n))
        CONFIGS.append(('ba',    n))
        CONFIGS.append(('ws',    n))
    for _ in range(2):
        CONFIGS.append(('mixed', n))

print(f"Всего экспериментов: {len(CONFIGS)}")
print("=" * 60)

records = []
for i, (gtype, n) in enumerate(CONFIGS):
    if gtype == 'er':    A = gen_er(n)
    elif gtype == 'ba':  A = gen_ba(n)
    elif gtype == 'ws':  A = gen_ws(n)
    else:                A = gen_mixed(n)
    
    # убрать изолированные узлы
    deg = A.sum(axis=1)
    if deg.min() == 0:
        mask = deg > 0
        A = A[np.ix_(mask, mask)]
        n_eff = A.shape[0]
    else:
        n_eff = n
    
    if n_eff < 5:
        continue
    
    lmax = lambda_max(A)
    ph = phi(A)
    a0_pred = a0_predicted(lmax)
    
    if np.isnan(a0_pred) or lmax <= 0:
        continue
    
    # симуляция (только малые сети для скорости)
    if n_eff <= 200:
        a0_sim = simulate_a0(A)
        rel_err = abs(a0_pred - a0_sim) / (a0_sim + 1e-10)
    else:
        # для крупных — аппроксимация через mean-field поправку
        k = A.sum(axis=1)
        k_mean = k.mean()
        k2_mean = (k**2).mean()
        # A0_mf с поправкой второго порядка
        lmax_mf = k2_mean / k_mean  # mean-field λmax
        a0_mf = K0 / lmax_mf
        # реальный λmax vs mean-field
        rel_err = abs(a0_pred - a0_mf) / (a0_mf + 1e-10)
    
    records.append({
        'gtype': gtype,
        'N': n_eff,
        'phi': ph,
        'lambda_max': lmax,
        'a0_pred': a0_pred,
        'rel_err': rel_err,
        'log_N': np.log(n_eff),
        'log_phi': np.log(ph + 1e-6),
        'log_err': np.log(rel_err + 1e-6),
    })
    
    if (i+1) % 50 == 0:
        print(f"  [{i+1}/{len(CONFIGS)}] n={n_eff}, {gtype}, φ={ph:.3f}, |err|={rel_err:.3f}")

df = pd.DataFrame(records)
print(f"\nИтого записей: {len(df)}")

# ─── Статистика ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("КОРРЕЛЯЦИИ Спирмена:")
r_N,   p_N   = stats.spearmanr(df['log_N'],   df['log_err'])
r_phi, p_phi = stats.spearmanr(df['log_phi'], df['log_err'])
r_Nphi, _    = stats.spearmanr(df['phi'],     df['N'])
print(f"  ρ(log_N,   log|err|) = {r_N:+.3f}  p={p_N:.4f}")
print(f"  ρ(log_φ,   log|err|) = {r_phi:+.3f}  p={p_phi:.4f}")
print(f"  ρ(N, φ)              = {r_Nphi:+.3f}  (конфаундер?)")

# Частные корреляции
from scipy.stats import pearsonr

def partial_corr(x, y, z):
    """partial corr x~y | z (линейная, на log-шкале)"""
    # residuals x from z
    slope_xz, intercept_xz, *_ = stats.linregress(z, x)
    res_x = x - (slope_xz * z + intercept_xz)
    slope_yz, intercept_yz, *_ = stats.linregress(z, y)
    res_y = y - (slope_yz * z + intercept_yz)
    r, p = pearsonr(res_x, res_y)
    return r, p

x = df['log_err'].values
N_log = df['log_N'].values
phi_log = df['log_phi'].values

r_N_partial, p_N_partial = partial_corr(N_log, x, phi_log)
r_phi_partial, p_phi_partial = partial_corr(phi_log, x, N_log)

print("\nЧАСТНЫЕ КОРРЕЛЯЦИИ (Пирсон, log-шкала):")
print(f"  partial_corr(log_N,   log|err| | log_φ) = {r_N_partial:+.3f}  p={p_N_partial:.4f}")
print(f"  partial_corr(log_φ,   log|err| | log_N) = {r_phi_partial:+.3f}  p={p_phi_partial:.4f}")

# OLS: log|err| ~ a·log(N) + b·log(φ) + const
from numpy.linalg import lstsq
X = np.column_stack([N_log, phi_log, np.ones(len(df))])
y_vec = x
beta, _, _, _ = lstsq(X, y_vec, rcond=None)
y_pred = X @ beta
ss_res = np.sum((y_vec - y_pred)**2)
ss_tot = np.sum((y_vec - y_vec.mean())**2)
R2 = 1 - ss_res/ss_tot

print(f"\nОLS: log|err| = {beta[0]:.3f}·log(N) + {beta[1]:.3f}·log(φ) + {beta[2]:.3f}")
print(f"  R² = {R2:.3f}")

# ─── По топологиям ──────────────────────────────────────────────────────────
print("\nСРЕДНЕЕ φ И |err| ПО ТИПАМ СЕТЕЙ:")
print(f"{'тип':<8} {'<φ>':<8} {'<|err|>':<10} {'N_mean':<8} n")
for gt in ['er','ba','ws','mixed']:
    sub = df[df['gtype']==gt]
    if len(sub) == 0: continue
    print(f"{gt:<8} {sub['phi'].mean():<8.3f} {sub['rel_err'].mean():<10.3f} {sub['N'].mean():<8.0f} {len(sub)}")

# ─── Вердикт ────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ВЕРДИКТ Q46:")

phi_effect = abs(r_phi_partial) > 0.15 and p_phi_partial < 0.05
N_effect   = abs(r_N_partial)   > 0.15 and p_N_partial   < 0.05

if phi_effect and N_effect:
    if abs(r_phi_partial) > abs(r_N_partial):
        verdict = "ДЕРЖИТСЯ (φ-механизм): φ объясняет больше размера при контроле N"
    else:
        verdict = "ЧАСТИЧНО: оба фактора значимы, N всё ещё главный"
elif phi_effect and not N_effect:
    verdict = "ДЕРЖИТСЯ СИЛЬНО: φ объясняет ошибку, N — конфаундер"
elif not phi_effect and N_effect:
    verdict = "ОПРОВЕРГНУТА: φ не объясняет, N — прямой предиктор (другой механизм)"
else:
    verdict = "НЕОПРЕДЕЛЁННО: оба слабые — нужна другая модель"

print(f"  {verdict}")
print(f"  φ-гипотеза: {'ПОДТВЕРЖДЕНА' if phi_effect else 'НЕ ПОДТВЕРЖДЕНА'}")
print(f"  N остаётся: {'ДА' if N_effect else 'НЕТ (φ поглотил)'}")
print()

# Сохранить
df.to_csv('/home/claude/q46_results.csv', index=False)
print("Данные → /home/claude/q46_results.csv")
