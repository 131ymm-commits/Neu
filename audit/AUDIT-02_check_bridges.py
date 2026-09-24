"""Численная проверка мостов Э1 и Э5 из документа «Один проект» (21.09.2026).
Э5: сингулярные числа D_pi^{1/2} P D_pi'^{-1/2} = канонические корреляции цепи Маркова (X_t, X_{t+1}), one-hot словарь.
Э1: гауссов IB (Chechik et al. 2005): критические beta_c = 1/(1 - lambda_i), lambda_i — с.з. Sigma_{x|y} Sigma_x^{-1}; lambda_i = 1 - rho_i^2 => beta = rho^{-2}.
"""
import numpy as np
rng = np.random.default_rng(0)

def cca_corrs(X, Y, ridge=0.0):
    X = X - X.mean(0); Y = Y - Y.mean(0)
    Sxx = X.T @ X / len(X) + ridge*np.eye(X.shape[1])
    Syy = Y.T @ Y / len(Y) + ridge*np.eye(Y.shape[1])
    Sxy = X.T @ Y / len(X)
    # symmetric inverse square roots via eigh (drop null directions)
    def isqrt(S):
        w, V = np.linalg.eigh(S); keep = w > 1e-12*w.max()
        return V[:, keep] @ np.diag(w[keep]**-0.5) @ V[:, keep].T
    M = isqrt(Sxx) @ Sxy @ isqrt(Syy)
    return np.sort(np.linalg.svd(M, compute_uv=False))[::-1]

print("=== Э5: цепь Маркова, точные величины (population) ===")
for trial, reversible in enumerate([False, True, False]):
    n = 5
    if reversible:
        W = rng.random((n, n)); W = W + W.T  # symmetric weights -> reversible chain
        P = W / W.sum(1, keepdims=True)
    else:
        P = rng.random((n, n)); P = P / P.sum(1, keepdims=True)
    # stationary distribution
    w, V = np.linalg.eig(P.T); pi = np.real(V[:, np.argmin(abs(w-1))]); pi = pi/pi.sum()
    pi2 = pi @ P  # distribution of X_{t+1} (= pi at stationarity)
    A = np.diag(pi**0.5) @ P @ np.diag(pi2**-0.5)
    sv = np.sort(np.linalg.svd(A, compute_uv=False))[::-1]
    # exact population CCA of one-hot X_t vs one-hot X_{t+1}: joint = diag(pi) P
    J = np.diag(pi) @ P
    # covariance of one-hot vectors: Sxx = diag(pi) - pi pi^T (rank n-1), Sxy = J - pi pi2^T, Syy = diag(pi2)-pi2 pi2^T
    Sxx = np.diag(pi) - np.outer(pi, pi); Syy = np.diag(pi2) - np.outer(pi2, pi2); Sxy = J - np.outer(pi, pi2)
    def isqrt(Sm):
        w_, V_ = np.linalg.eigh(Sm); keep = w_ > 1e-12
        return V_[:, keep] @ np.diag(w_[keep]**-0.5) @ V_[:, keep].T
    rho = np.sort(np.linalg.svd(isqrt(Sxx) @ Sxy @ isqrt(Syy), compute_uv=False))[::-1]
    print(f"trial {trial} reversible={reversible}")
    print("  sing.values D^1/2 P D'^-1/2 :", np.round(sv, 6))
    print("  canonical corrs (population):", np.round(rho, 6))
    print("  max |sv[1:] - rho[:n-1]| =", np.max(abs(sv[1:] - rho[:n-1])), " (sv[0]=1 — тривиальная мода константы, у центрированной CCA её нет)")
    # sampled trajectory estimate
    T = 200000; x = np.zeros(T, int); x[0] = rng.choice(n, p=pi)
    cum = np.cumsum(P, 1)
    u = rng.random(T)
    for t in range(1, T): x[t] = np.searchsorted(cum[x[t-1]], u[t])
    X = np.eye(n)[x[:-1]]; Y = np.eye(n)[x[1:]]
    rho_hat = cca_corrs(X, Y)
    print("  sampled CCA (T=2e5):          ", np.round(rho_hat[:n-1], 4), " -> расхождение ~1e-3 — выборочная ошибка, как 0,617/0,620 в документе")

print("\n=== Э1: гауссов IB, beta_c = 1/(1-lambda) = rho^-2 ===")
dx, dy, N = 4, 3, 400000
A = rng.normal(size=(dy, dx)); X = rng.normal(size=(N, dx)); Y = X @ A.T + 0.7*rng.normal(size=(N, dy))
Sx = np.cov(X.T); Sy = np.cov(Y.T); Sxy = np.cov(X.T, Y.T)[:dx, dx:]
Sx_given_y = Sx - Sxy @ np.linalg.inv(Sy) @ Sxy.T
lam = np.sort(np.linalg.eigvals(Sx_given_y @ np.linalg.inv(Sx)).real)
rho = cca_corrs(X, Y)
print("  eigenvalues of Sigma_{x|y} Sigma_x^-1:", np.round(lam, 6))
print("  1 - rho^2 (rho from CCA, padded 1s): ", np.round(np.sort(np.concatenate([1-rho**2, np.ones(dx-len(rho))])), 6))
print("  beta_c = 1/(1-lambda) vs rho^-2:     ", np.round(1/(1-lam[:dy]), 4), np.round(np.sort(rho**-2), 4))
rho_s = np.sort(rho)[::-1]
print("  w_k = 2 log(rho_k/rho_k+1) vs log(beta_k+1/beta_k):", np.round(2*np.log(rho_s[:-1]/rho_s[1:]), 6), np.round(np.log((rho_s[1:]**-2)/(rho_s[:-1]**-2)), 6))
