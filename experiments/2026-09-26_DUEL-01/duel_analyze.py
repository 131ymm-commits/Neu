# DUEL-01: анализ контрольного набора (до/после турнира) и хода турнира.
import json, math, os, sys
from duel_run import J, D, PLAYERS


def binom_p(k, n): return 1.0 if n == 0 else sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def sign_test(d):
    w, l = sum(x < 0 for x in d), sum(x > 0 for x in d)
    return dict(wins=w, losses=l, n=w + l, p=binom_p(w, w + l))


def main():
    b1 = J(f'{D}/bench1_scores.json'); b0 = J(f'{D}/bench0_scores.json')
    ids = [i for i in b1['C'] if all(b1[k].get(i) is not None for k in list(PLAYERS) + ['C', 'B0'])]
    Dm = {i: sum(b1[p][i] for p in PLAYERS) / len(PLAYERS) for i in ids}
    tests = dict(P1_duel_vs_C=sign_test([Dm[i] - b1['C'][i] for i in ids]), P2_C_vs_B0=sign_test([b1['C'][i] - b1['B0'][i] for i in ids]))
    mean = lambda s: sum(v for v in s.values() if v is not None) / max(1, sum(v is not None for v in s.values()))
    rounds = []
    r = 0
    while os.path.exists(f'{D}/tasks{r}.json'):
        ts = [t for t in J(f'{D}/tasks{r}.json') if t.get('params')]
        rounds.append(dict(r=r, n_valid=len(ts), n_invalid=len(J(f'{D}/tasks{r}.json')) - len(ts),
                           solver_IS=sum(x['IS'] for t in ts for x in t.get('solvers', {}).values()) / max(1, sum(len(t.get('solvers', {})) for t in ts)),
                           setter_IS=sum(t['setter_IS'] for t in ts) / max(1, len(ts)), families={f: sum(t['family'] == f for t in ts) for f in ('COL3', 'PART', 'TWIN', 'SUB')}))
        r += 1
    res = dict(tests=tests, bench_mean={**{k: mean(v) for k, v in b1.items()}, **{'start_' + k: mean(v) for k, v in b0.items()}}, rounds=rounds,
               points=J(f'{D}/state.json')['points'], notes={p: J(f'{D}/state.json')['players'][p]['notes'] for p in PLAYERS})
    J(f'{D}/results.json', res); print(json.dumps({k: res[k] for k in ('tests', 'bench_mean', 'rounds', 'points')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
