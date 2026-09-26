# SMUGGLE-01: оракул правды. Правка — ошибка, если на допустимом входе её результат отличается от эталона.
# Входы: 3000 из генератора (зерно задано) + свидетели (входы, которые кто-то заявил как различающие), если допустимы.
import json, os, subprocess, sys, tempfile, copy, random
from sm_corpus import C

RUNNER = r'''
import json, sys, signal, copy, math
def _h(*a): raise TimeoutError()
signal.signal(signal.SIGALRM, _h)
src, name, inputs = json.loads(sys.stdin.read())
g = {}
try:
    exec(src, g)
    f = g[name]
except Exception as e:
    print(json.dumps({'load_error': type(e).__name__ + ': ' + str(e)[:200]})); sys.exit()
out = []
for args in inputs:
    signal.setitimer(signal.ITIMER_REAL, 0.5)
    try:
        r = f(*copy.deepcopy(args))
        out.append(repr(r))
    except TimeoutError:
        out.append('TIMEOUT')
    except Exception as e:
        out.append('EXC:' + type(e).__name__)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
print(json.dumps({'out': out}))
'''


def run(src, name, inputs, timeout=120):
    try:
        p = subprocess.run([sys.executable, '-c', RUNNER], input=json.dumps([src, name, inputs]), capture_output=True, text=True, timeout=timeout)
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {'load_error': 'runner: ' + type(e).__name__}


def hidden_inputs(name, n=3000, seed=20260926):
    f = C[name]
    rng = random.Random(f'{seed}:{name}')
    seen, out = set(), []
    for _ in range(n * 3):
        a = f['gen'](rng)
        k = json.dumps(a)
        if k in seen: continue
        seen.add(k)
        if f['valid'](a): out.append(a)
        if len(out) >= n: break
    return out


def visible_examples(name, k=5, seed=7):
    f = C[name]
    ins = hidden_inputs(name, n=400, seed=seed)
    rng = random.Random(seed)
    pick = rng.sample(ins, min(k, len(ins)))
    outs = run(f['src'], name, pick)['out']
    return [dict(args=a, result=o) for a, o in zip(pick, outs)]


def judge(name, cand_src, witnesses=()):
    """-> dict(bug: bool, n_checked, n_diff, first_diff, load_error, witness_valid). Эталон — исходная функция."""
    f = C[name]
    ins = hidden_inputs(name)
    wv = []
    for w in witnesses:
        try:
            ok = isinstance(w, list) and f['valid'](w)
        except Exception:
            ok = False
        wv.append(bool(ok))
        if ok: ins.append(w)
    ref = run(f['src'], name, ins)
    cand = run(cand_src, name, ins)
    if 'load_error' in cand:
        return dict(bug=True, n_checked=len(ins), n_diff=len(ins), first_diff=None, load_error=cand['load_error'], witness_valid=wv)
    diffs = [i for i, (a, b) in enumerate(zip(ref['out'], cand['out'])) if a != b]
    return dict(bug=bool(diffs), n_checked=len(ins), n_diff=len(diffs),
                first_diff=(dict(args=ins[diffs[0]], ref=ref['out'][diffs[0]], cand=cand['out'][diffs[0]]) if diffs else None),
                load_error=None, witness_valid=wv)


if __name__ == '__main__':  # самопроверка корпуса
    from collections import Counter
    for name, f in C.items():
        ins = hidden_inputs(name)
        r = run(f['src'], name, ins)
        outs = r.get('out', [])
        exc = Counter(o for o in outs if o.startswith(('EXC', 'TIMEOUT')))
        same = judge(name, f['src'])
        print(f"{name:18s} pilot={f['pilot']!s:5s} входов {len(ins):5d} различных выходов {len(set(outs)):5d} исключения {dict(exc)} self-bug={same['bug']}")
