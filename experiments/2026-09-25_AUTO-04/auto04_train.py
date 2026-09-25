# AUTO-04: перенос AUTO-02/03 на настоящий текст (см. PREREG-AUTO-04.md).
# Модель и оптимизатор — как в AUTO-01..03; данные — английская «Алиса» по буквам (PG #11, гл. 1–10 — обучение).
# Ветви: A0 — только следующий знак; AW — плюс голова, предсказывающая переходную статистику знаков окна t+16..t+23;
# AR (контроль) — та же голова и вес, но цель взята у соседней последовательности батча (не связана с контекстом).
import sys, os, time, pickle, json
import numpy as np
import jax, jax.numpy as jnp, optax
import eq01_common as E

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN = open(os.path.join(HERE, 'alice_en_ch01-10.txt'), encoding='utf-8').read().lower()
TEST = open(os.path.join(HERE, 'alice_en_ch11-12.txt'), encoding='utf-8').read().lower()
CHARS = sorted(set(TRAIN) | set(TEST))
E.V = V = len(CHARS)                          # словарь знаков вместо 6 состояний процесса
IDX = {c: i for i, c in enumerate(CHARS)}
TR = np.array([IDX[c] for c in TRAIN], np.int32)
TE = np.array([IDX[c] for c in TEST], np.int32)
L = E.L


def batches(n, rng):
    st = rng.integers(0, len(TR) - L - 1, n)
    return TR[st[:, None] + np.arange(L + 1)]


def test_windows():
    k = (len(TE) - 1) // (L + 1)
    return TE[:k * (L + 1)].reshape(k, L + 1)


def test_nll(p):
    X = test_windows()
    logp, _ = E.model_outputs(p, X[:, :-1])
    return float(-np.take_along_axis(logp, X[:, 1:, None], -1).mean())


if __name__ == '__main__':
    arm, seed = sys.argv[1], int(sys.argv[2])
    STEPS, LAM, TAU, W8 = int(os.environ.get('AUTO_STEPS', 2000)), 0.3, 16, 8
    POS = np.arange(16, 41)
    out = os.path.join(HERE, f'auto/{arm}_s{seed}')
    os.makedirs(out, exist_ok=True)
    EV = jnp.eye(V)

    def world_target(seq):
        yw = 0.0
        for j in range(W8):
            tp = POS + TAU + j
            yw = yw + jnp.einsum('bpi,bpj->bpij', EV[seq[:, tp]], EV[seq[:, tp + 1]]).reshape(seq.shape[0], len(POS), V * V)
        return yw / W8

    def total_loss(params, seq, lam, shuffle):
        p, head = params
        logits, resid = E.forward(p, seq[:, :-1])
        logp = jax.nn.log_softmax(logits, -1)
        ce = -jnp.take_along_axis(logp, seq[:, 1:, None], -1).mean()
        y = world_target(seq)
        y = jax.lax.stop_gradient(jnp.where(shuffle > 0, jnp.roll(y, 1, axis=0), y))
        yhat = resid[:, POS, :] @ head['W'] + head['b']
        var = y.reshape(-1, V * V).var(0) + 1e-6
        aux = (((yhat - y) ** 2).reshape(-1, V * V).mean(0) / var).mean()
        return ce + lam * aux, (ce, aux)

    params = (E.init_params(jax.random.PRNGKey(seed)), {'W': jnp.zeros((E.D, V * V)), 'b': jnp.zeros(V * V)})
    sched = optax.warmup_cosine_decay_schedule(0.0, 1e-3, 100, STEPS, 1e-4)
    opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(sched, weight_decay=0.01))
    st = opt.init(params)

    @jax.jit
    def step(params, st, seq, lam, shuffle):
        (l, (ce, aux)), g = jax.value_and_grad(total_loss, has_aux=True)(params, seq, lam, shuffle)
        upd, st = opt.update(g, st, params)
        return optax.apply_updates(params, upd), st, ce, aux

    rng = np.random.default_rng(2000 + seed)
    lam = 0.0 if arm == 'A0' else LAM
    log, t0 = [], time.time()
    for i in range(STEPS + 1):
        if i % 500 == 0 or i == STEPS:
            pickle.dump(jax.device_get(params[0]), open(f'{out}/p_{i:05d}.pkl', 'wb'))
            log.append(dict(step=i, kind='test', nll=test_nll(params[0])))
        if i == STEPS:
            break
        params, st, ce, aux = step(params, st, jnp.asarray(batches(64, rng)), jnp.float32(lam), jnp.float32(arm == 'AR'))
        if i % 100 == 0:
            log.append(dict(step=i, kind='train', ce=float(ce), aux=float(aux)))
            print(arm, seed, i, round(float(ce), 4), round(float(aux), 4), round(time.time() - t0, 1), flush=True)
    json.dump(log, open(f'{out}/log.json', 'w'))
    print('done', round(time.time() - t0, 1), 'test_nll', log[-1]['nll'], flush=True)
