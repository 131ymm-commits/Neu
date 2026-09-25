# AUTO-07: «зоопарк голов» — 256 простых скалярных голов разных функций (см. PREREG-AUTO-07.md). Данные и модель — как в AUTO-04/06.
# Типы (Z — нулевая цель — убран: при нулевых начальных весах головы градиент тождественно ноль, ветвь = A0; проверено на сиде 99):
# N — свежий шум; S — F-цели чужой последовательности батча; P — «знак v был k шагов назад»;
# C — «текущий знак = v»; F — «через k шагов будет знак v»; B — доля знака v в следующих 16 знаках; M — смесь всех шести.
import sys, os, time, json
import numpy as np
import jax, jax.numpy as jnp, optax
import eq01_common as E

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN = open(os.path.join(HERE, 'alice_en_ch01-10.txt'), encoding='utf-8').read().lower()
TEST = open(os.path.join(HERE, 'alice_en_ch11-12.txt'), encoding='utf-8').read().lower()
CHARS = sorted(set(TRAIN) | set(TEST))
E.V = V = len(CHARS)
IDX = {c: i for i, c in enumerate(CHARS)}
TR = np.array([IDX[c] for c in TRAIN], np.int32)
TE = np.array([IDX[c] for c in TEST], np.int32)
L = E.L
POS = np.arange(16, 48)                       # t-16 >= 0 и t+16 <= 63
K = 256
TYPES = 'NSPCFB'


def test_nll(p):
    k = (len(TE) - 1) // (L + 1)
    X = TE[:k * (L + 1)].reshape(k, L + 1)
    logp, _ = E.model_outputs(p, X[:, :-1])
    return float(-np.take_along_axis(logp, X[:, 1:, None], -1).mean())


if __name__ == '__main__':
    arm, seed = sys.argv[1], int(sys.argv[2])
    STEPS, LAM = int(os.environ.get('AUTO_STEPS', 2000)), 0.3
    out = os.path.join(HERE, f'auto/{arm}_s{seed}')
    os.makedirs(out, exist_ok=True)
    hr = np.random.default_rng(10_000 + seed)
    kinds = np.array([TYPES[i % 6] for i in range(K)]) if arm == 'M' else np.array([arm] * K)
    KJ = jnp.asarray(hr.integers(1, 17, K)); VJ = jnp.asarray(hr.integers(0, V, K))
    masks = {t: jnp.asarray(kinds == t, jnp.float32) for t in TYPES}
    WIN = np.arange(1, 17)

    def target(seq, key):
        B_ = seq.shape[0]
        fut = (seq[:, POS[:, None] + KJ[None, :]] == VJ).astype(jnp.float32)          # F
        past = (seq[:, POS[:, None] - KJ[None, :]] == VJ).astype(jnp.float32)         # P
        cur = (seq[:, POS][:, :, None] == VJ).astype(jnp.float32)                      # C
        win = seq[:, POS[:, None] + WIN[None, :]]                                      # (B,P,16)
        bag = (win[:, :, :, None] == VJ).mean(2).astype(jnp.float32)                   # B
        noise = jax.random.normal(key, (B_, len(POS), K))                               # N
        shuf = jnp.roll(fut, 1, axis=0)                                                 # S
        parts = dict(N=noise, S=shuf, P=past, C=cur, F=fut, B=bag)
        return sum(parts[t] * masks[t] for t in TYPES)

    def total_loss(params, seq, key, lam):
        p, head = params
        logits, resid = E.forward(p, seq[:, :-1])
        logp = jax.nn.log_softmax(logits, -1)
        ce = -jnp.take_along_axis(logp, seq[:, 1:, None], -1).mean()
        y = jax.lax.stop_gradient(target(seq, key))
        yhat = resid[:, POS, :] @ head['W'] + head['b']
        var = y.reshape(-1, K).var(0)
        var = var + 1e-6
        aux = (((yhat - y) ** 2).reshape(-1, K).mean(0) / var).mean()
        return ce + lam * aux, (ce, aux)

    params = (E.init_params(jax.random.PRNGKey(seed)), {'W': jnp.zeros((E.D, K)), 'b': jnp.zeros(K)})
    sched = optax.warmup_cosine_decay_schedule(0.0, 1e-3, 100, STEPS, 1e-4)
    opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(sched, weight_decay=0.01))
    st = opt.init(params)

    @jax.jit
    def step(params, st, seq, key, lam):
        (l, (ce, aux)), g = jax.value_and_grad(total_loss, has_aux=True)(params, seq, key, lam)
        upd, st = opt.update(g, st, params)
        return optax.apply_updates(params, upd), st, ce, aux

    rng = np.random.default_rng(2000 + seed)
    key = jax.random.PRNGKey(50_000 + seed)
    lam = 0.0 if arm == 'A0' else LAM
    log, t0 = [], time.time()
    for i in range(STEPS + 1):
        if i % 500 == 0 or i == STEPS:
            log.append(dict(step=i, kind='test', nll=test_nll(params[0])))
        if i == STEPS:
            break
        st_ = rng.integers(0, len(TR) - L - 1, 64)
        key, sk = jax.random.split(key)
        params, st, ce, aux = step(params, st, jnp.asarray(TR[st_[:, None] + np.arange(L + 1)]), sk, jnp.float32(lam))
        if i % 100 == 0:
            log.append(dict(step=i, kind='train', ce=float(ce), aux=float(aux)))
            print(arm, seed, i, round(float(ce), 4), round(float(aux), 4), round(time.time() - t0, 1), flush=True)
    json.dump(log, open(f'{out}/log.json', 'w'))
    print('done', round(time.time() - t0, 1), 'test_nll', log[-1]['nll'], flush=True)
