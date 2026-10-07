import time, pyspiel
from open_spiel.python import policy as P
from open_spiel.python.algorithms import exploitability, cfr
def meas(name, cfr_k=200):
    g = pyspiel.load_game(name); t = time.time()
    u = P.UniformRandomPolicy(g); nu = exploitability.nash_conv(g, u); tu = time.time() - t
    tp = P.TabularPolicy(g); n_states = len(tp.state_lookup)
    t = time.time(); s = cfr.CFRSolver(g)
    for _ in range(cfr_k): s.evaluate_and_update_policy()
    nc = exploitability.nash_conv(g, s.average_policy()); tc = time.time() - t
    print(f'{name[:90]:90s} infosets {n_states:6d} NashConv uni {nu:.3f} cfr{cfr_k} {nc:.4f} ratio {(nu-nc)/nu:.2f}  t_truth {tu:.2f}s t_cfr {tc:.1f}s', flush=True)
import sys
for n in sys.argv[1:]: meas(n)
