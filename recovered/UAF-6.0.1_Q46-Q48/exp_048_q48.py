"""
EXP-048 / Q48: Добавляет ли Γ значимый вклад поверх φ?

Контекст:
- Q46: |err| ~ φ (partial_r=+0.459), R²=0.30
- Q47: A0_corr = K0/(λmax·(1+0.12·φ)), снижение ошибки 9% (BA: 24%)
- Бухгалтерский закон v5.2: ε = π/11·φ + 2·Γ − 10·φΓ + C/8
- Q48: Проверить, добавляет ли Γ (и C) значимый вклад в v6.0

Γ = <k·A_ss> / (<k>·<A_ss>) − 1  — ковариационный перекос:
  насколько активность коррелирует со степенью узла.

Гипотеза:
  log|err| ~ α·log(φ) + β·Γ + γ·C + δ·φΓ  → R² > 0.30?
  Если β,γ,δ значимы — закон v5.2 применим в v6.0.
  Если нет — φ достаточен, бухгалтерский закон v5.2 не переносится.

Метод:
- Генерируем сети (ER, BA, WS, Mixed), N=20..200
- Для каждой: симуляция UAF → A_ss при A0 чуть выше порога
- Вычисляем φ, Γ, C, |err|
- Сравниваем модели: φ only vs φ+Γ+C vs φ+Γ+C+φΓ
- F-test на значимость добавления Γ
"""

import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
from scipy.stats import pearsonr
import warnings
warnings.filterwarnings('ignore')

RNG = np.random.default_rng(314)

ALPHA_S = 0.06
F       = 0.002
DELTA   = 0.012
K0      = (DELTA - F) / ALPHA_S   # 0.16667

# ── Базовые метрики ──────────────────────────────────────────────────────────

def phi(A):
    k = A.sum(axis=1)
    k2m = np.mean(k**2)
    return float(np.var(k) / k2m) if k2m > 1e-10 else 0.0

def lambda_max(A):
    return float(np.linalg.eigvalsh(A)[-1])

def simulate_threshold(A, tol=5e-3):
    """Бисекция: A0_crit где <A_ss> = 0.05."""
    n = A.shape[0]; dt = 0.05
    def ss(a0):
        v = np.full(n, a0)
        for _ in range(1500):
            ns = A @ v
            dv = ALPHA_S*ns*(1-v) + F*(1-v) - DELTA*(1-0.3*v)
            v = np.clip(v + dt*dv, 0, 1)
        return v.mean()
    lo, hi = 0.01, 0.99
    for _ in range(20):
        mid = (lo+hi)/2
        if ss(mid) > 0.05: hi = mid
        else: lo = mid
        if hi-lo < tol: break
    return (lo+hi)/2

def steady_state_above(A, a0_crit, factor=1.5):
    """Устойчивое состояние при A0 = factor * a0_crit."""
    n = A.shape[0]; dt = 0.05
    v = np.full(n, min(a0_crit * factor, 0.95))
    for _ in range(2000):
        ns = A @ v
        dv = ALPHA_S*ns*(1-v) + F*(1-v) - DELTA*(1-0.3*v)
        v = np.clip(v + dt*dv, 0, 1)
    return v

def gamma(A, A_ss):
    """Γ = <k·A_ss> / (<k>·<A_ss>) − 1"""
    k = A.sum(axis=1).astype(float)
    mk = k.mean(); mA = A_ss.mean()
    if mk < 1e-10 or mA < 1e-10: return 0.0
    return float(np.mean(k * A_ss) / (mk * mA) - 1.0)

def clustering(A):
    G = nx.from_numpy_array(A)
    return nx.average_clustering(G)

# ── Генераторы ───────────────────────────────────────────────────────────────

def gen(kind, n):
    s = int(RNG.integers(1e6))
    if kind == 'er':  G = nx.erdos_renyi_graph(n, min(0.3, 6/n), seed=s)
    elif kind == 'ba': G = nx.barabasi_albert_graph(n, 2, seed=s)
    elif kind == 'ba3': G = nx.barabasi_albert_graph(n, 3, seed=s)
    else:             G = nx.watts_strogatz_graph(n, 4, 0.1, seed=s)
    G.remove_nodes_from(list(nx.isolates(G)))
    if G.number_of_nodes() < 5: return None
    return nx.to_numpy_array(G, dtype=float)

# ── Основной цикл ────────────────────────────────────────────────────────────

SIZES  = [20, 30, 40, 50, 60, 80, 100, 120, 150, 200]
KINDS  = ['er', 'ba', 'ba3', 'ws']
N_REP  = 8

print("Q48: φ vs φ+Γ+C — добавляет ли Γ объяснительную силу?")
print(f"Сетей: {len(SIZES)*len(KINDS)*N_REP} запланировано")
print("=" * 60)

records = []
done = 0

for n in SIZES:
    for kind in KINDS:
        for _ in range(N_REP):
            A = gen(kind, n)
            if A is None: continue

            lmax = lambda_max(A)
            if lmax <= 0: continue

            ph   = phi(A)
            a0p  = K0 / lmax
            a0s  = simulate_threshold(A)
            if a0s <= 0: continue

            rel_err = abs(a0p - a0s) / a0s

            # Γ требует A_ss — считаем при 1.5·a0_crit
            A_ss = steady_state_above(A, a0s, factor=1.5)
            gam  = gamma(A, A_ss)
            C    = clustering(A)

            records.append({
                'kind': kind, 'N': A.shape[0],
                'phi': ph, 'gamma': gam, 'C': C,
                'lmax': lmax, 'a0_pred': a0p, 'a0_sim': a0s,
                'rel_err': rel_err,
                'log_phi': np.log(ph + 1e-6),
                'log_err': np.log(rel_err + 1e-6),
                'log_N':   np.log(A.shape[0]),
                'phi_gamma': ph * gam,
            })
            done += 1

print(f"Выполнено: {done}")

df = pd.DataFrame(records)

# ── OLS утилита ──────────────────────────────────────────────────────────────

def ols(X, y):
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    ss_res = np.sum((y - y_hat)**2)
    ss_tot = np.sum((y - y.mean())**2)
    R2 = 1 - ss_res / ss_tot
    return beta, R2, ss_res

y = df['log_err'].values
ones = np.ones(len(df))

# M0: только константа
_, _, ss0 = ols(ones.reshape(-1,1), y)

# M1: φ (baseline Q46)
X1 = np.column_stack([df['log_phi'], ones])
b1, R2_1, ss1 = ols(X1, y)

# M2: φ + N
X2 = np.column_stack([df['log_phi'], df['log_N'], ones])
b2, R2_2, ss2 = ols(X2, y)

# M3: φ + Γ
X3 = np.column_stack([df['log_phi'], df['gamma'], ones])
b3, R2_3, ss3 = ols(X3, y)

# M4: φ + C
X4 = np.column_stack([df['log_phi'], df['C'], ones])
b4, R2_4, ss4 = ols(X4, y)

# M5: φ + Γ + C  (v5.2-подобная без взаимодействия)
X5 = np.column_stack([df['log_phi'], df['gamma'], df['C'], ones])
b5, R2_5, ss5 = ols(X5, y)

# M6: φ + Γ + C + φΓ  (полный бухгалтерский закон v5.2)
X6 = np.column_stack([df['log_phi'], df['gamma'], df['C'], df['phi_gamma'], ones])
b6, R2_6, ss6 = ols(X6, y)

# M7: φ + N + Γ + C + φΓ  (всё)
X7 = np.column_stack([df['log_phi'], df['log_N'], df['gamma'], df['C'], df['phi_gamma'], ones])
b7, R2_7, ss7 = ols(X7, y)

n_obs = len(df)

def f_test(ss_restricted, ss_full, p_restricted, p_full, n):
    """F-тест: значимо ли улучшение M_full над M_restricted?"""
    df1 = p_full - p_restricted
    df2 = n - p_full
    if df1 <= 0 or ss_full <= 0: return np.nan, np.nan
    F = ((ss_restricted - ss_full) / df1) / (ss_full / df2)
    p = 1 - stats.f.cdf(F, df1, df2)
    return F, p

# ── Таблица результатов ──────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("СРАВНЕНИЕ МОДЕЛЕЙ (зависимая: log|err|)")
print(f"{'Модель':<30} {'R²':>6}  {'ΔR²':>7}  F-test")
print("-" * 60)

models = [
    ("M1: φ",                  R2_1, ss1, 2),
    ("M2: φ + N",              R2_2, ss2, 3),
    ("M3: φ + Γ",              R2_3, ss3, 3),
    ("M4: φ + C",              R2_4, ss4, 3),
    ("M5: φ + Γ + C",          R2_5, ss5, 4),
    ("M6: φ + Γ + C + φΓ",     R2_6, ss6, 5),
    ("M7: φ+N+Γ+C+φΓ",         R2_7, ss7, 6),
]

base_R2 = R2_1; base_ss = ss1; base_p = 2
for name, R2, ss, p in models:
    dR2 = R2 - base_R2
    F, pval = f_test(base_ss, ss, base_p, p, n_obs)
    if name.startswith("M1"):
        print(f"{name:<30} {R2:>6.3f}  {'—':>7}  baseline")
    else:
        sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "ns"
        print(f"{name:<30} {R2:>6.3f}  {dR2:>+7.3f}  F={F:.1f} p={pval:.4f} {sig}")

# ── Коэффициенты M6 (бухгалтерский закон) ───────────────────────────────────

print("\nКОЭФФИЦИЕНТЫ M6 (φ + Γ + C + φΓ):")
names6 = ['log(φ)', 'Γ', 'C', 'φ·Γ', 'const']
for nm, coef in zip(names6, b6):
    print(f"  {nm:<10}: {coef:+.4f}")

# Сравнение с v5.2: ε = π/11·φ + 2·Γ − 10·φΓ + C/8
print(f"\n  v5.2 теоретические: φ→{np.pi/11:.4f}, Γ→+2.0, φΓ→-10.0, C→{1/8:.4f}")
print(f"  v6.0 подобранные:   (выше, но в log-шкале — прямое сравнение некорректно)")

# ── Частные корреляции ───────────────────────────────────────────────────────

def partial_r(x, y, z_list):
    """Частная корреляция x~y при контроле всех z в z_list."""
    Z = np.column_stack(z_list + [np.ones(len(y))])
    def resid(v):
        b, _, _, _ = np.linalg.lstsq(Z, v, rcond=None)
        return v - Z @ b
    r, p = pearsonr(resid(x), resid(y))
    return r, p

controls_base = [df['log_phi'].values, df['log_N'].values]
r_gam, p_gam = partial_r(df['gamma'].values, y, controls_base)
r_C,   p_C   = partial_r(df['C'].values,     y, controls_base)
r_phg, p_phg = partial_r(df['phi_gamma'].values, y, controls_base)

print("\nЧАСТНЫЕ КОРРЕЛЯЦИИ (при контроле log_φ и log_N):")
print(f"  Γ        partial_r = {r_gam:+.3f}  p = {p_gam:.4f}")
print(f"  C        partial_r = {r_C:+.3f}  p = {p_C:.4f}")
print(f"  φ·Γ      partial_r = {r_phg:+.3f}  p = {p_phg:.4f}")

# ── По типам сетей ───────────────────────────────────────────────────────────

print("\n<Γ> И <C> ПО ТИПАМ СЕТЕЙ:")
print(f"{'тип':<8} {'<φ>':<7} {'<Γ>':<8} {'<C>':<7} {'<|err|>':<9}")
for k in ['er', 'ba', 'ba3', 'ws']:
    sub = df[df['kind']==k]
    print(f"{k:<8} {sub['phi'].mean():.3f}  {sub['gamma'].mean():+.4f}  {sub['C'].mean():.3f}  {sub['rel_err'].mean():.4f}")

# ── Вердикт ──────────────────────────────────────────────────────────────────

gamma_sig = p_gam < 0.05
C_sig     = p_C   < 0.05
phg_sig   = p_phg < 0.05
delta_R2  = R2_6 - R2_1

print("\n" + "=" * 60)
print("ВЕРДИКТ Q48:")

if delta_R2 > 0.05 and (gamma_sig or C_sig):
    if gamma_sig and C_sig:
        verdict = "ДЕРЖИТСЯ СИЛЬНО: Γ и C оба значимы, бухгалтерский закон v5.2 переносится в v6.0"
    elif gamma_sig:
        verdict = "ДЕРЖИТСЯ ЧАСТИЧНО: Γ значим, C нет — Γ добавляет объяснительную силу"
    else:
        verdict = "ДЕРЖИТСЯ ЧАСТИЧНО: C значим, Γ нет — кластеризация важнее перекоса"
elif delta_R2 > 0.02 and (gamma_sig or C_sig):
    verdict = "СЛАБО ДЕРЖИТСЯ: улучшение R² мало (<5%), но один из факторов значим"
else:
    verdict = "ОПРОВЕРГНУТА: Γ и C не добавляют значимого вклада — φ достаточен в v6.0"

print(f"  {verdict}")
print(f"  ΔR² (M6 vs M1) = {delta_R2:+.3f}")
print(f"  Γ значим:  {'ДА' if gamma_sig else 'НЕТ'}  (partial_r={r_gam:+.3f}, p={p_gam:.4f})")
print(f"  C значим:  {'ДА' if C_sig else 'НЕТ'}  (partial_r={r_C:+.3f}, p={p_C:.4f})")
print(f"  φΓ значим: {'ДА' if phg_sig else 'НЕТ'}  (partial_r={r_phg:+.3f}, p={p_phg:.4f})")

if not gamma_sig and not C_sig:
    print(f"\n  → Закон v6.0 остаётся: A0_corr = K0 / (λmax·(1 + 0.12·φ))")
    print(f"  → Бухгалтерский закон v5.2 не переносится на задачу v6.0")
    print(f"     (v5.2 предсказывал ε на фиксированных A*; v6.0 — ошибку порога A0_crit)")
else:
    print(f"\n  → Расширенный закон v6.0:")
    print(f"     A0_corr = K0 / (λmax·(1 + c₁·φ + c₂·Γ·sign))")

df.to_csv('/home/claude/q48_results.csv', index=False)
print("\nДанные → /home/claude/q48_results.csv")
