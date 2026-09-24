# EQUIV-01: обучение трансформера, контрольные точки каждые 250 шагов
import sys, time, pickle, os
import numpy as np
import jax, jax.numpy as jnp, optax
from eq01_common import *

seed = int(sys.argv[1])
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
out = f'ckpt_s{seed}'
os.makedirs(out, exist_ok=True)

key = jax.random.PRNGKey(seed)
p = init_params(key)
sched = optax.warmup_cosine_decay_schedule(0.0, 1e-3, 200, steps, 1e-4)
opt = optax.adamw(sched, weight_decay=0.01)
st = opt.init(p)


@jax.jit
def step(p, st, seq):
    l, g = jax.value_and_grad(loss_fn)(p, seq)
    g, _ = optax.clip_by_global_norm(1.0).update(g, None)
    upd, st = opt.update(g, st, p)
    return optax.apply_updates(p, upd), st, l


rng = np.random.default_rng(1000 + seed)
t0 = time.time()
log = []
for i in range(steps + 1):
    if i % 250 == 0:
        with open(f'{out}/p_{i:05d}.pkl', 'wb') as f:
            pickle.dump(jax.device_get(p), f)
    if i == steps:
        break
    seq, _ = sample(64, rng=rng)
    p, st, l = step(p, st, jnp.asarray(seq))
    if i % 100 == 0:
        log.append((i, float(l), time.time() - t0))
        print(i, round(float(l), 4), round(time.time() - t0, 1), flush=True)
with open(f'{out}/trainlog.pkl', 'wb') as f:
    pickle.dump(log, f)
print('done', time.time() - t0, flush=True)
