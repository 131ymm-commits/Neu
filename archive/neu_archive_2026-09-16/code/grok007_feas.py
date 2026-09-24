"""GROK-007 feasibility: smallest eigenvalues of J J^T (residual Jacobian) via matrix-free Lanczos at a checkpoint of the x^2-MLP."""
import time, sys
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
alpha = float(sys.argv[1]); steps = int(sys.argv[2]); seed = 101   # spent seed
FRAC = alpha
(Xtr, Ytr), (Xte, Yte) = make_data(seed)
rng = np.random.default_rng(seed + 7); D = 512
W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
n = len(Xtr); lr, wd = 10.0, 3e-4
t0 = time.time()
for t in range(steps):
    H = Xtr @ W1; A = H * H; Out = A @ W2; G = (Out - Ytr) / n
    gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
    W1 -= lr * (gW1 + wd * W1); W2 -= lr * (gW2 + wd * W2)
H = Xtr @ W1; A = H * H; Out = A @ W2
acc_te = float(((Xte @ W1) ** 2 @ W2).argmax(1).__eq__(Yte.argmax(1)).mean())
print(f"alpha={alpha} steps={steps}: n_train={n} residuals={n*P} params={W1.size+W2.size} val_acc={acc_te:.3f} [{time.time()-t0:.0f}s]", flush=True)
def Jv(v):
    V1 = v[:W1.size].reshape(W1.shape); V2 = v[W1.size:].reshape(W2.shape)
    dH = Xtr @ V1; dA = 2 * H * dH
    return (dA @ W2 + A @ V2).ravel()
def JTu(u):
    U = u.reshape(n, P)
    gW2 = A.T @ U; gA = U @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
    return np.concatenate([gW1.ravel(), gW2.ravel()])
m = n * P
op = LinearOperator((m, m), matvec=lambda u: Jv(JTu(u)), dtype=float)
t1 = time.time(); top = eigsh(op, k=1, which="LA", tol=1e-3, maxiter=300, return_eigenvectors=False); print(f"largest eig JJ^T = {top[0]:.4e} [{time.time()-t1:.0f}s]", flush=True)
t1 = time.time()
try:
    low = eigsh(op, k=6, which="SA", tol=1e-4, maxiter=3000, return_eigenvectors=False)
    print("6 smallest eig JJ^T:", np.sort(low), f"-> sigma_min = {np.sqrt(max(np.sort(low)[0],0)):.4e}, ratio to top {np.sort(low)[0]/top[0]:.2e} [{time.time()-t1:.0f}s]", flush=True)
except Exception as e:
    print("SA failed:", repr(e)[:200], f"[{time.time()-t1:.0f}s]")
