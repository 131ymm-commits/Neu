# AUTO-01: обучение с автоматическим регулятором на основе ПСУ-2 (см. PREREG-AUTO-01.md)
# Ветви: A0 (без добавки), AW (мировая цель), AS (своя цель), AA (регулятор переключает цель по ПСУ-2)
import sys, os, time, pickle, json
import numpy as np
import jax, jax.numpy as jnp, optax
from eq01_common import *

arm, seed = sys.argv[1], int(sys.argv[2])
STEPS, LAM, TAU, W8 = int(os.environ.get('AUTO_STEPS', 2000)), 0.3, 16, 8
POS = np.arange(16, 41)                       # позиции t, для которых окно t+16..t+23 помещается в контекст
out = f'auto/{arm}_s{seed}'
os.makedirs(out, exist_ok=True)
E6 = jnp.eye(V)


def targets(seq, logits):
    """Своя и мировая переходная статистика окна t+16..t+23 для позиций POS. seq: (B,65), logits: (B,64,V)."""
    pr = jax.lax.stop_gradient(jax.nn.softmax(logits, -1))
    ys, yw = 0.0, 0.0
    for j in range(W8):
        tp = POS + TAU + j                     # позиция t'
        a = E6[seq[:, tp]]                     # увиденный токен x_t'   (B, P, V)
        ys = ys + jnp.einsum('bpi,bpj->bpij', a, pr[:, tp]).reshape(seq.shape[0], len(POS), V * V)
        yw = yw + jnp.einsum('bpi,bpj->bpij', a, E6[seq[:, tp + 1]]).reshape(seq.shape[0], len(POS), V * V)
    return ys / W8, yw / W8


def total_loss(params, seq, use_self, lam):
    p, head = params
    logits, resid = forward(p, seq[:, :-1])
    logp = jax.nn.log_softmax(logits, -1)
    ce = -jnp.take_along_axis(logp, seq[:, 1:, None], -1).mean()
    ys, yw = targets(seq, logits)
    y = use_self * ys + (1.0 - use_self) * yw
    y = jax.lax.stop_gradient(y)
    r = resid[:, POS, :]
    yhat = r @ head['W'] + head['b']
    var = y.reshape(-1, V * V).var(0) + 1e-6
    aux = (((yhat - y) ** 2).reshape(-1, V * V).mean(0) / var).mean()
    return ce + lam * aux, (ce, aux)


key = jax.random.PRNGKey(seed)
p = init_params(key)
head = {'W': jnp.zeros((D, V * V)), 'b': jnp.zeros(V * V)}
params = (p, head)
sched = optax.warmup_cosine_decay_schedule(0.0, 1e-3, 100, STEPS, 1e-4)
opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(sched, weight_decay=0.01))
st = opt.init(params)


@jax.jit
def step(params, st, seq, use_self, lam):
    (l, (ce, aux)), g = jax.value_and_grad(total_loss, has_aux=True)(params, seq, use_self, lam)
    upd, st = opt.update(g, st, params)
    return optax.apply_updates(params, upd), st, ce, aux


# ---------- регулятор: совпадение своего и мирового уровня (ПСУ-2) ----------
mon_rng = np.random.default_rng(777)
MX, _ = sample(500, rng=mon_rng)


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def cca_dirs(X, Y, k=2, reg=1e-10):
    n = len(X)
    Sxx, Syy, Sxy = X.T @ X / n, Y.T @ Y / n, X.T @ Y / n
    Sxx = Sxx + reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx))
    Syy = Syy + reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx = inv_sqrt(Sxx)
    U, s, _ = np.linalg.svd(Wx @ Sxy @ inv_sqrt(Syy))
    return (Wx @ U)[:, :k], s[:k]


def alignment(p):
    logp, resid = model_outputs(p, MX[:, :64])
    pr = np.exp(logp)
    X = resid[:, POS, :]
    X = X - X.mean(0, keepdims=True)
    e6 = np.eye(V)
    ys = sum(np.einsum('npi,npj->npij', e6[MX[:, POS + TAU + j]], pr[:, POS + TAU + j]).reshape(len(MX), len(POS), 36) for j in range(W8)) / W8
    yw = sum(np.einsum('npi,npj->npij', e6[MX[:, POS + TAU + j]], e6[MX[:, POS + TAU + j + 1]]).reshape(len(MX), len(POS), 36) for j in range(W8)) / W8
    ys = ys - ys.mean(0, keepdims=True); yw = yw - yw.mean(0, keepdims=True)
    Xf = X.reshape(-1, D)
    As, ss = cca_dirs(Xf, ys.reshape(-1, 36))
    Aw, sw = cca_dirs(Xf, yw.reshape(-1, 36))
    Q1, _ = np.linalg.qr(Xf @ As); Q2, _ = np.linalg.qr(Xf @ Aw)
    c = np.linalg.svd(Q1.T @ Q2, compute_uv=False)
    return float(c.min()), ss.tolist(), sw.tolist()


rng = np.random.default_rng(2000 + seed)
lam = 0.0 if arm == 'A0' else LAM
mode = {'A0': 0.0, 'AW': 0.0, 'AS': 1.0, 'AA': 0.0}[arm]
log = []
t0 = time.time()
for i in range(STEPS + 1):
    if i % 250 == 0:
        pickle.dump(jax.device_get(params[0]), open(f'{out}/p_{i:05d}.pkl', 'wb'))
        if arm == 'AA':
            c, ss, sw = alignment(params[0])
            mode = 1.0 if c >= 0.95 else 0.0
            log.append(dict(step=i, kind='ctrl', cos_min=c, rho_self=ss, rho_world=sw, mode='self' if mode else 'world'))
            print('ctrl', i, round(c, 3), 'self' if mode else 'world', flush=True)
    if i == STEPS:
        break
    seq, _ = sample(64, rng=rng)
    params, st, ce, aux = step(params, st, jnp.asarray(seq), jnp.float32(mode), jnp.float32(lam))
    if i % 100 == 0:
        log.append(dict(step=i, kind='train', ce=float(ce), aux=float(aux), mode=float(mode)))
        print(arm, seed, i, round(float(ce), 4), round(float(aux), 4), round(time.time() - t0, 1), flush=True)
json.dump(log, open(f'{out}/log.json', 'w'))
print('done', round(time.time() - t0, 1), flush=True)
