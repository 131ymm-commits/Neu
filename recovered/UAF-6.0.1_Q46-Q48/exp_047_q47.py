"""
EXP-047 / Q47: φ-поправка A0_corr = K0/λmax · (1 + c·φ)
Проверка на сетях, реалистичных по доменам Q43/Q44/Q45 (MJS20-proxy).

Метод:
1. Для каждого домена генерируем N_rep=30 сетей с параметрами, 
   соответствующими известным реальным данным (N, тип, φ-диапазон).
2. Для каждой сети: A0_pred (без поправки), A0_corr (с φ-поправкой, c=0.49),
   A0_sim (симуляция / mean-field reference).
3. Сравниваем RMSE_pred vs RMSE_corr по домену и суммарно.
4. Подбираем оптимальный c_opt методом LSQ.
5. Вердикт: поправка снижает ошибку? На сколько? Универсальна ли c?

c_init = 0.49 из Q46 OLS (exp(0.397)−1).
"""

import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats, optimize
import warnings
warnings.filterwarnings('ignore')

RNG = np.random.default_rng(2024)

# ── UAF константы ────────────────────────────────────────────────────────────
ALPHA_S = 0.06
F       = 0.002
DELTA   = 0.012
K0      = (DELTA - F) / ALPHA_S   # 0.16667
C_INIT  = 0.49                     # из Q46

# ── Метрики ──────────────────────────────────────────────────────────────────

def phi(A):
    k = A.sum(axis=1)
    k2m = np.mean(k**2)
    return float(np.var(k) / k2m) if k2m > 1e-10 else 0.0

def lambda_max_real(A):
    """Ведущее вещественное с.з. (симметричная матрица)."""
    try:
        return float(np.linalg.eigvalsh(A)[-1])
    except:
        return np.nan

def a0_mf_reference(A):
    """
    Mean-field reference A0 с полной поправкой второго порядка.
    Используем как 'ground truth' для сравнения (доступно для всех N).
    
    Из мастер-уравнения в среднем поле второго порядка:
    A0* = K0 / λmax_eff,  λmax_eff = <k²>/<k>  (mean-field для неоднородных сетей)
    
    Это то, к чему φ-поправка должна корректировать спектральный λmax.
    """
    k = A.sum(axis=1)
    k_mean = k.mean()
    k2_mean = (k**2).mean()
    if k_mean < 1e-10:
        return np.nan
    lmax_mf2 = k2_mean / k_mean   # Heterogeneous mean-field
    return K0 / lmax_mf2

def simulate_a0_bisect(A, tol=1e-3, max_iter=25):
    """Бисекция порога (N ≤ 150 для скорости)."""
    n = A.shape[0]
    dt = 0.05

    def ss(a0):
        v = np.full(n, a0)
        for _ in range(2000):
            ns = A @ v
            dv = ALPHA_S*ns*(1-v) + F*(1-v) - DELTA*(1-0.3*v)
            v = np.clip(v + dt*dv, 0, 1)
        return v.mean()

    lo, hi = 0.01, 0.99
    for _ in range(max_iter):
        mid = (lo+hi)/2
        if ss(mid) > 0.05:
            hi = mid
        else:
            lo = mid
        if hi-lo < tol:
            break
    return (lo+hi)/2

# ── Генераторы доменно-реалистичных сетей ────────────────────────────────────

def gen_domain_net(domain, seed):
    rng_loc = np.random.default_rng(seed)
    
    if domain == 'food_web':
        # BA m=2, N=40-80, φ≈0.4-0.5 — как реальные пищевые сети
        n = int(rng_loc.integers(35, 80))
        G = nx.barabasi_albert_graph(n, 2, seed=int(seed))
    
    elif domain == 'metabolic':
        # BA m=3, N=60-120, φ≈0.45-0.55
        n = int(rng_loc.integers(60, 120))
        G = nx.barabasi_albert_graph(n, 3, seed=int(seed))
    
    elif domain == 'trade':
        # ER p≈0.12-0.20, N=50-80, φ≈0.15-0.25
        n = int(rng_loc.integers(50, 80))
        p = float(rng_loc.uniform(0.10, 0.22))
        G = nx.erdos_renyi_graph(n, p, seed=int(seed))
    
    elif domain == 'neural':
        # BA m=4, N=150-300, φ≈0.38-0.48 — C.elegans-like
        n = int(rng_loc.integers(150, 280))
        G = nx.barabasi_albert_graph(n, 4, seed=int(seed))
    
    elif domain == 'social':
        # WS k=6 p=0.15, N=80-150, φ≈0.02-0.08
        n = int(rng_loc.integers(80, 150))
        G = nx.watts_strogatz_graph(n, 6, 0.15, seed=int(seed))
    
    elif domain == 'gene_regulation':
        # DAG-like: построим BA + удалим циклы (ациклическая иерархия)
        n = int(rng_loc.integers(30, 60))
        G = nx.barabasi_albert_graph(n, 2, seed=int(seed))
        # Оставим только DAG-рёбра (удалим «обратные»)
        # Используем топологическую сортировку
        DG = nx.DiGraph(G)
        try:
            topo = list(nx.topological_sort(DG))
        except:
            # Если есть циклы, удалим их
            DG2 = nx.DiGraph()
            DG2.add_nodes_from(range(n))
            for u, v in G.edges():
                if u < v:
                    DG2.add_edge(u, v)
            topo = list(range(n))
            DG = DG2
        # Симметризуем для спектрального анализа
        G = nx.Graph(DG)
    
    else:
        n = 50
        G = nx.barabasi_albert_graph(n, 2, seed=int(seed))
    
    # Убрать изоляты
    G.remove_nodes_from(list(nx.isolates(G)))
    if G.number_of_nodes() < 5:
        return None
    
    A = nx.to_numpy_array(G, dtype=float)
    return A

# ── Основной цикл ────────────────────────────────────────────────────────────

DOMAINS = ['food_web', 'metabolic', 'trade', 'neural', 'social', 'gene_regulation']
N_REP = 40

print("Q47: φ-поправка на доменно-реалистичных сетях")
print(f"c_init = {C_INIT:.3f}  (из Q46 OLS)")
print("=" * 65)

records = []
seeds = RNG.integers(0, 100000, size=N_REP * len(DOMAINS))
si = 0

for domain in DOMAINS:
    for rep in range(N_REP):
        A = gen_domain_net(domain, int(seeds[si])); si += 1
        if A is None:
            continue
        
        n = A.shape[0]
        ph = phi(A)
        lmax = lambda_max_real(A)
        
        if np.isnan(lmax) or lmax <= 0:
            continue
        
        # Предсказания
        a0_pred = K0 / lmax
        a0_corr = a0_pred * (1 + C_INIT * ph)
        
        # Ground truth: симуляция (N≤150) или mean-field 2-го порядка (N>150)
        if n <= 150:
            a0_ref = simulate_a0_bisect(A)
        else:
            a0_ref = a0_mf_reference(A)
        
        if np.isnan(a0_ref) or a0_ref <= 0:
            continue
        
        err_pred = abs(a0_pred - a0_ref) / a0_ref
        err_corr = abs(a0_corr - a0_ref) / a0_ref
        
        records.append({
            'domain': domain,
            'N': n,
            'phi': ph,
            'lambda_max': lmax,
            'a0_ref': a0_ref,
            'a0_pred': a0_pred,
            'a0_corr': a0_corr,
            'err_pred': err_pred,
            'err_corr': err_corr,
            'improvement': err_pred - err_corr,   # >0 = улучшение
            'rel_improvement': (err_pred - err_corr) / (err_pred + 1e-10),
        })

df = pd.DataFrame(records)
print(f"Итого записей: {len(df)}")

# ── Подбор оптимального c ────────────────────────────────────────────────────
# Минимизируем среднее |A0_corr(c) - A0_ref| / A0_ref

def mean_err_c(c):
    a0_c = df['a0_pred'] * (1 + c * df['phi'])
    return (abs(a0_c - df['a0_ref']) / df['a0_ref']).mean()

res = optimize.minimize_scalar(mean_err_c, bounds=(0, 3), method='bounded')
c_opt = res.x
print(f"\nc_opt (LSQ по всем доменам) = {c_opt:.4f}  (c_init={C_INIT:.3f})")

# ── Статистика по доменам ────────────────────────────────────────────────────

print("\n" + "=" * 65)
print(f"{'Домен':<18} {'<φ>':<7} {'RMSE_pred':<11} {'RMSE_corr':<11} {'Δ%':<8} n")
print("-" * 65)

total_pred_sq, total_corr_sq, total_n = 0, 0, 0

for domain in DOMAINS:
    sub = df[df['domain'] == domain]
    if len(sub) == 0:
        continue
    rmse_p = sub['err_pred'].mean()
    rmse_c = sub['err_corr'].mean()
    delta_pct = (rmse_p - rmse_c) / (rmse_p + 1e-10) * 100
    total_pred_sq += sub['err_pred'].sum()
    total_corr_sq += sub['err_corr'].sum()
    total_n += len(sub)
    sign = '↓' if delta_pct > 0 else '↑'
    print(f"{domain:<18} {sub['phi'].mean():<7.3f} {rmse_p:<11.4f} {rmse_c:<11.4f} {delta_pct:+.1f}%{sign}  {len(sub)}")

print("-" * 65)
rmse_pred_total = total_pred_sq / total_n
rmse_corr_total = total_corr_sq / total_n
delta_total = (rmse_pred_total - rmse_corr_total) / (rmse_pred_total + 1e-10) * 100
print(f"{'ИТОГО':<18} {df['phi'].mean():<7.3f} {rmse_pred_total:<11.4f} {rmse_corr_total:<11.4f} {delta_total:+.1f}%")

# ── Проверка универсальности c по доменам ────────────────────────────────────

print("\n" + "=" * 65)
print("ОПТИМАЛЬНОЕ c ПО ДОМЕНАМ (универсальность?):")
c_by_domain = {}
for domain in DOMAINS:
    sub = df[df['domain'] == domain]
    if len(sub) < 5:
        continue
    def err_c_domain(c):
        a0_c = sub['a0_pred'] * (1 + c * sub['phi'])
        return (abs(a0_c - sub['a0_ref']) / sub['a0_ref']).mean()
    r = optimize.minimize_scalar(err_c_domain, bounds=(0, 5), method='bounded')
    c_by_domain[domain] = r.x
    print(f"  {domain:<18}: c_opt = {r.x:.4f}")

c_vals = list(c_by_domain.values())
c_std = np.std(c_vals)
c_mean = np.mean(c_vals)
cv = c_std / (c_mean + 1e-10)
print(f"\n  c_mean={c_mean:.3f}  c_std={c_std:.3f}  CV={cv:.2f}")
universality = "УНИВЕРСАЛЬНА (CV<0.3)" if cv < 0.3 else "НЕ УНИВЕРСАЛЬНА (CV≥0.3)"
print(f"  Константа: {universality}")

# ── Частные корреляции φ vs N для ошибки (проверка Q46 на этих данных) ───────

from scipy.stats import pearsonr

log_err  = np.log(df['err_pred'].clip(1e-6))
log_N    = np.log(df['N'].astype(float))
log_phi  = np.log(df['phi'].clip(1e-6))

def partial_r(x, y, z):
    sx, intercept_xz, *_ = stats.linregress(z, x)
    rx = x - (sx*z + intercept_xz)
    sy, intercept_yz, *_ = stats.linregress(z, y)
    ry = y - (sy*z + intercept_yz)
    r, p = pearsonr(rx, ry)
    return r, p

r_phi_N,  p_phi_N  = partial_r(log_phi,  log_err, log_N)
r_N_phi,  p_N_phi  = partial_r(log_N,    log_err, log_phi)

print(f"\nЧАСТНЫЕ КОРРЕЛЯЦИИ (репликация Q46 на domain-сетях):")
print(f"  partial_r(log_φ, log|err| | log_N) = {r_phi_N:+.3f}  p={p_phi_N:.4f}")
print(f"  partial_r(log_N, log|err| | log_φ) = {r_N_phi:+.3f}  p={p_N_phi:.4f}")

# ── Итоговый вердикт ─────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("ВЕРДИКТ Q47:")

improves = delta_total > 1.0   # поправка даёт >1% улучшения
univ     = cv < 0.3

if improves and univ:
    verdict = "ДЕРЖИТСЯ СИЛЬНО: φ-поправка работает и c универсальна"
elif improves and not univ:
    verdict = "ДЕРЖИТСЯ ЧАСТИЧНО: поправка снижает ошибку, но c домен-зависима"
elif not improves and univ:
    verdict = "ОПРОВЕРГНУТА: c универсальна, но поправка не помогает"
else:
    verdict = "ОПРОВЕРГНУТА: поправка не работает, c не универсальна"

print(f"  {verdict}")
print(f"  Снижение ошибки: {delta_total:+.1f}%")
print(f"  c_opt = {c_opt:.3f}  (c_init = {C_INIT:.3f})")
print(f"  CV(c по доменам) = {cv:.2f}  → {universality}")
print(f"  φ как предиктор ошибки: partial_r={r_phi_N:+.3f}  p={p_phi_N:.4f}")

corrected_law = f"A0_corr = K0/λmax · (1 + {c_opt:.2f}·φ)"
print(f"\n  ОБНОВЛЁННЫЙ ЗАКОН: {corrected_law}")
print(f"  Ожидаемая точность при φ<0.1: ~{(rmse_pred_total*(1-0.01*delta_total*(0.05/df['phi'].mean()))):.3f}")

df.to_csv('/home/claude/q47_results.csv', index=False)
print("\nДанные → /home/claude/q47_results.csv")
