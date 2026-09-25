# EQUIV-01: общий код — процесс «тема × фаза», прямой алгоритм, трансформер на JAX
import numpy as np
import jax
import jax.numpy as jnp

K, M, V = 3, 3, 6
P_SWITCH = 0.02
L = 64          # контекст
D, H, NL, DM = 64, 4, 2, 256


def make_process():
    C = np.roll(np.eye(M), 1, axis=1)          # C[s, s+1] = 1
    T = np.zeros((K, M, M))
    T[0] = 0.1 * np.eye(M) + 0.8 * C + 0.1 * C.T   # цикл вперёд
    T[1] = 0.1 * np.eye(M) + 0.1 * C + 0.8 * C.T   # цикл назад
    T[2] = 0.8 * np.eye(M) + 0.1 * C + 0.1 * C.T   # липкая
    Z = np.full((K, K), P_SWITCH / (K - 1))
    np.fill_diagonal(Z, 1 - P_SWITCH)
    B = np.full((M, V), 0.05)
    for s in range(M):
        B[s, 2 * s] = 0.4
        B[s, 2 * s + 1] = 0.4
    Tj = np.zeros((K * M, K * M))
    for z in range(K):
        for s in range(M):
            for z2 in range(K):
                for s2 in range(M):
                    Tj[z * M + s, z2 * M + s2] = Z[z, z2] * T[z2][s, s2]
    Bj = np.tile(B, (K, 1))
    return Tj, Bj


TJ, BJ = make_process()
TJ_CUM = np.cumsum(TJ, axis=1)
BJ_CUM = np.cumsum(BJ, axis=1)


def sample(n, length=L + 1, rng=None):
    """Возвращает токены (n, length) и скрытые состояния (n, length)."""
    rng = rng or np.random.default_rng()
    h = np.zeros((n, length), dtype=np.int64)
    x = np.zeros((n, length), dtype=np.int64)
    h[:, 0] = rng.integers(0, K * M, size=n)
    for t in range(length):
        if t > 0:
            u = rng.random(n)
            h[:, t] = (u[:, None] > TJ_CUM[h[:, t - 1]]).sum(1)
        u = rng.random(n)
        x[:, t] = (u[:, None] > BJ_CUM[h[:, t]]).sum(1)
    h = np.minimum(h, K * M - 1)
    x = np.minimum(x, V - 1)
    return x, h


def forward_filter(x):
    """Апостериорная тема P(Z_t | x_0..t) (n, T, K), совместная вера (n, T, 9) и оптимальный лог-лосс."""
    n, T = x.shape
    alpha = np.full((n, K * M), 1.0 / (K * M))
    post_z = np.zeros((n, T, K))
    belief = np.zeros((n, T, K * M))
    nll = np.zeros((n, T - 1))
    for t in range(T):
        if t > 0:
            pred = alpha @ TJ                      # P(h_t | x_<t)
            px = pred @ BJ                         # P(x_t | x_<t)
            nll[:, t - 1] = -np.log(px[np.arange(n), x[:, t]])
            alpha = pred * BJ[:, x[:, t]].T
        else:
            alpha = alpha * BJ[:, x[:, 0]].T
        alpha /= alpha.sum(1, keepdims=True)
        belief[:, t] = alpha
        post_z[:, t] = alpha.reshape(n, K, M).sum(2)
    return post_z, belief, nll


# ---------------- модель ----------------

def init_params(key):
    ks = jax.random.split(key, 3 + 4 * NL)
    std = 0.02
    p = {
        'WE': jax.random.normal(ks[0], (V, D)) * std,
        'WP': jax.random.normal(ks[1], (L, D)) * std,
        'WU': jax.random.normal(ks[2], (D, V)) * std,
        'lnf_g': jnp.ones(D), 'lnf_b': jnp.zeros(D),
        'layers': [],
    }
    for l in range(NL):
        k = ks[3 + 4 * l: 3 + 4 * l + 4]
        p['layers'].append({
            'ln1_g': jnp.ones(D), 'ln1_b': jnp.zeros(D),
            'Wqkv': jax.random.normal(k[0], (D, 3 * D)) * std,
            'Wo': jax.random.normal(k[1], (D, D)) * std / np.sqrt(2 * NL),
            'ln2_g': jnp.ones(D), 'ln2_b': jnp.zeros(D),
            'W1': jax.random.normal(k[2], (D, DM)) * std, 'b1': jnp.zeros(DM),
            'W2': jax.random.normal(k[3], (DM, D)) * std / np.sqrt(2 * NL), 'b2': jnp.zeros(D),
        })
    return p


def _ln(x, g, b):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / jnp.sqrt(var + 1e-5) * g + b


def forward(p, x):
    B_, T_ = x.shape
    h = p['WE'][x] + p['WP'][:T_]
    mask = jnp.tril(jnp.ones((T_, T_), dtype=bool))
    dh = D // H
    for lp in p['layers']:
        z = _ln(h, lp['ln1_g'], lp['ln1_b'])
        qkv = z @ lp['Wqkv']
        q, k, v = jnp.split(qkv, 3, axis=-1)
        q = q.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        k = k.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        v = v.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        att = (q @ k.transpose(0, 1, 3, 2)) / np.sqrt(dh)
        att = jnp.where(mask, att, -1e9)
        att = jax.nn.softmax(att, axis=-1)
        o = (att @ v).transpose(0, 2, 1, 3).reshape(B_, T_, D)
        h = h + o @ lp['Wo']
        z = _ln(h, lp['ln2_g'], lp['ln2_b'])
        h = h + jax.nn.gelu(z @ lp['W1'] + lp['b1']) @ lp['W2'] + lp['b2']
    resid = h
    logits = _ln(h, p['lnf_g'], p['lnf_b']) @ p['WU']
    return logits, resid


def loss_fn(p, seq):
    logits, _ = forward(p, seq[:, :-1])
    logp = jax.nn.log_softmax(logits, -1)
    tgt = seq[:, 1:]
    return -jnp.take_along_axis(logp, tgt[..., None], -1).mean()


@jax.jit
def run_model(p, x):
    logits, resid = forward(p, x)
    return jax.nn.log_softmax(logits, -1), resid


def model_outputs(p, x, bs=500):
    lps, rs = [], []
    for i in range(0, x.shape[0], bs):
        lp, r = run_model(p, jnp.asarray(x[i:i + bs]))
        lps.append(np.asarray(lp, dtype=np.float64))
        rs.append(np.asarray(r, dtype=np.float64))
    return np.concatenate(lps), np.concatenate(rs)


def forward_layers(p, x):
    """Как forward, но возвращает residual после блока 1 и после блока 2 (последний)."""
    B_, T_ = x.shape
    h = p['WE'][x] + p['WP'][:T_]
    mask = jnp.tril(jnp.ones((T_, T_), dtype=bool))
    dh = D // H
    per_block = []
    for lp in p['layers']:
        z = _ln(h, lp['ln1_g'], lp['ln1_b'])
        q, k, v = jnp.split(z @ lp['Wqkv'], 3, axis=-1)
        q = q.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        k = k.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        v = v.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        att = jax.nn.softmax(jnp.where(mask, (q @ k.transpose(0, 1, 3, 2)) / np.sqrt(dh), -1e9), axis=-1)
        h = h + (att @ v).transpose(0, 2, 1, 3).reshape(B_, T_, D) @ lp['Wo']
        z = _ln(h, lp['ln2_g'], lp['ln2_b'])
        h = h + jax.nn.gelu(z @ lp['W1'] + lp['b1']) @ lp['W2'] + lp['b2']
        per_block.append(h)
    logits = _ln(h, p['lnf_g'], p['lnf_b']) @ p['WU']
    return jax.nn.log_softmax(logits, -1), per_block[0], per_block[1]


run_layers = jax.jit(forward_layers)


def model_outputs_layers(p, x, bs=500):
    a, b, c = [], [], []
    for i in range(0, x.shape[0], bs):
        lp, r1, r2 = run_layers(p, jnp.asarray(x[i:i + bs]))
        a.append(np.asarray(lp, np.float64)); b.append(np.asarray(r1, np.float64)); c.append(np.asarray(r2, np.float64))
    return np.concatenate(a), np.concatenate(b), np.concatenate(c)
