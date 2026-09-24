"""EXT-019 — psi' on the Beninca plankton community. Per PREREG (frozen 2026-09-01)."""
import json
import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260905)
df = pd.read_csv("/home/claude/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv")
day_col = df.columns[0]
species = [c for c in df.columns if c not in (day_col, "Total.dissolved.inorganic.nitrogen", "Soluble.reactive.phosphorus")]
X0 = df[species].to_numpy(float)
print(f"ряд: {X0.shape[0]} узлов × {len(species)} видов: {species}")
if len(species) < 4:
    raise SystemExit("СТОП постановки: < 4 видов")

def gmi(a, b):
    r = float(np.clip(np.corrcoef(a, b)[0, 1], -0.999999, 0.999999))
    return -0.5 * np.log(1 - r * r)

def psi_l(X, tau=1):
    keep = X.std(0) > 1e-12
    Xk = (X[:, keep] - X[:, keep].mean(0)) / X[:, keep].std(0)
    M = Xk.mean(1)
    v = gmi(M[:-tau], M[tau:])
    xs = [gmi(Xk[:-tau, j], M[tau:]) for j in range(Xk.shape[1])]
    jmax = int(np.argmax(xs))
    return v - max(xs), int(keep.sum()), jmax, v

n = len(X0); B = 5; L = n // B
blocks, surs = [], []
for b in range(B):
    Xb = X0[b * L:(b + 1) * L]
    p, nk, jm, v = psi_l(Xb)
    Xs = Xb.copy(); RNG.shuffle(Xs, axis=0)
    ps, *_ = psi_l(Xs)
    blocks.append(dict(b=b, psi=p, n_species=nk, top_species=jm, v_mi=v))
    surs.append(ps)
    print(f"блок {b}: ψ′={p:+.3f} (видов {nk}, лидер #{jm}) | суррогат {ps:+.4f}")
npos = sum(1 for r in blocks if r["psi"] > 0)
frac_small = float(np.mean([abs(s) <= 0.05 for s in surs]))
pfull, nkf, jmf, vf = psi_l(X0)
loo = {}
for j, sp in enumerate(species):
    Xl = np.delete(X0, j, axis=1)
    loo[sp] = float(psi_l(Xl)[0])
pb5a = npos >= 4; pb5a_kill = npos <= 1
pb5b = frac_small >= 0.9; pb5b_kill = float(np.median(np.abs(surs))) >= 0.2
res = dict(blocks=blocks, surs=surs, npos=npos, frac_sur_small=frac_small,
           psi_full=pfull, top_species_full=species[jmf], loo=loo,
           PB5a=bool(pb5a), PB5a_killed=bool(pb5a_kill), PB5b=bool(pb5b), PB5b_killed=bool(pb5b_kill))
json.dump(res, open("/home/claude/ext019_results.json", "w"), default=float)
print(f"\nψ′ полного ряда: {pfull:+.3f} (вид-лидер: {species[jmf]})")
print(f"LOO по видам (знак): " + ", ".join(f"{k}:{'+' if v>0 else '−'}" for k, v in loo.items()))
print(f"P-B5a (ψ′>0 в {npos}/5 блоков): {'ПОДТВЕРЖДЁН' if pb5a else ('УБИТ' if pb5a_kill else 'не установлен')}")
print(f"P-B5b (суррогаты малы {frac_small*100:.0f}%): {'ПОДТВЕРЖДЁН' if pb5b else ('УБИТ' if pb5b_kill else 'не уст.')}")
print("-> ext019_results.json")
