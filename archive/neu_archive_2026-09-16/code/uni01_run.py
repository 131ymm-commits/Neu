"""UNI-01 — hodograph/linearization route predictor on a 10-system zoo. Per PREREG (frozen 2026-08-27)."""
import json
import numpy as np

def jac_num(F, x, eps=1e-6):
    n = len(x); J = np.zeros((n, n))
    f0 = F(x)
    for j in range(n):
        xp = x.copy(); xp[j] += eps
        J[:, j] = (F(xp) - f0) / eps
    return J

def relax(F, x0, dt=0.005, steps=400000):
    x = np.array(x0, float)
    for _ in range(steps):
        x = np.maximum(x + dt * F(x), 0)
    return x

def family_flow(J):
    ev = np.linalg.eigvals(J)
    lead = ev[np.argmax(ev.real)]
    return ("осцилляторный" if abs(lead.imag) > 1e-6 else "стационарный"), ev

def family_map(mults):
    lead = mults[np.argmax(np.abs(mults))]
    if abs(lead.imag) > 1e-6: return "осцилляторный"
    return "flip" if lead.real < 0 else "стационарный"

Z = []

# 1 Schlogl fr=0.8 (fold)
k1s, k4s = 5.75, 8.75; SN1, Ww = 1.37154, 4.00578 - 1.37154
def mk_schlogl(fr):
    k3 = SN1 + fr * Ww
    return lambda x: np.array([k3 + k1s * x[0] ** 2 - k4s * x[0] - x[0] ** 3])
F = mk_schlogl(0.8); xs = relax(F, [0.5])
Z.append(("Шлёгль fr=0.8", "flow", F, xs, "стационарный", "фолд"))

# 2 Verhulst lam=0.9 (transcritical)
EPSV, KCAP = 0.1, 5.0
Fv = lambda x: np.array([0.9 * x[0] + EPSV - x[0] - x[0] ** 2 / KCAP])
xv = relax(Fv, [0.5])
Z.append(("Ферхюльст λ=0.9", "flow", Fv, xv, "стационарный", "транскритика"))

# 3 Brusselator b=4.5 (Hopf)
A_ = 2.0
Fb = lambda x: np.array([A_ - (4.5 + 1) * x[0] + x[0] ** 2 * x[1], 4.5 * x[0] - x[0] ** 2 * x[1]])
xb = relax(Fb, [2.0, 2.2])
Z.append(("Брюсселятор b=4.5", "flow", Fb, xb, "осцилляторный", "Хопф"))

# 4-5 DEL chains k=6, k=4 (Hopf)
BETA, H = 2.336, 4
def mk_chain(k):
    def F(x):
        d = np.empty(k)
        d[0] = BETA / (1 + x[-1] ** H) - x[0]
        d[1:] = x[:-1] - x[1:]
        return d
    return F
for kk in (6, 4):
    Fc = mk_chain(kk); xc = relax(Fc, [1.0] * kk)
    Z.append((f"цепь k={kk}", "flow", Fc, xc, "осцилляторный", "Хопф"))

# 6 logistic map r=2.8 (flip route; x*=1-1/r, mult=2-r=-0.8)
Z.append(("лог. карта r=2.8", "map", None, np.array([1 - 1 / 2.8]), "flip", "flip"))
mult_log = np.array([2 - 2.8 + 0j])

# 7 delayed logistic map r=1.9 (NS at 2): x_{t+1}=r x_t (1-x_{t-1}); as 2D map
r_ = 1.9
def dlog_map(v):
    x, y = v
    return np.array([r_ * x * (1 - y), x])
xd = np.array([1 - 1 / r_, 1 - 1 / r_])
Jd = jac_num(dlog_map, xd)
mult_dlog = np.linalg.eigvals(Jd)
Z.append(("запазд. логистика r=1.9", "map", None, xd, "осцилляторный", "NS"))

# 8 network g5203 h2 at 0.6*kappa_mid (fold)
exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])
M = 10
edges = edges_seq(M, 5203); A8 = adj_at(edges, M, k_cycle(edges, M)).astype(float)
km = json.load(open("/home/claude/ord001_results.json"))["5203"]["kappa_mid"]
def h2f(n): return n * n / (16.0 + n * n)
F8 = lambda n: EPS + 0.6 * km * (A8.T @ h2f(n)) - n
x8 = relax(F8, np.full(M, EPS))
Z.append(("сеть g5203-h2 0.6κ", "flow", F8, x8, "стационарный", "фолд"))

# 9 ring2 AND kappa=12 (fold at 16)
def mk_ring2(kap):
    Ar = np.zeros((10, 10))
    for j in range(10):
        Ar[(j - 1) % 10, j] = 1; Ar[(j - 2) % 10, j] = 1
    ins = [np.flatnonzero(Ar[:, j]) for j in range(10)]
    def F(n):
        h = n / (4.0 + n)
        b = np.full(10, 0.10)
        for j in range(10):
            b[j] += kap * np.prod(h[ins[j]])
        return b - n
    return F
F9 = mk_ring2(12.0); x9 = relax(F9, np.full(10, 0.10))
Z.append(("кольцо²-AND κ=12", "flow", F9, x9, "стационарный", "фолд"))

# 10 toggle a=1.8 (pitchfork at 2)
def Ft(x): return np.array([1.8 / (1 + x[1] ** 2) - x[0], 1.8 / (1 + x[0] ** 2) - x[1]])
xt = relax(Ft, [0.9, 0.9])
Z.append(("тоггл a=1.8", "map-flow", Ft, xt, "стационарный", "питчфорк"))

rows, correct = [], 0
for i, (name, kind, F, xstar, want_fam, want_route) in enumerate(Z):
    if name.startswith("лог. карта"):
        fam = family_map(mult_log); ev = mult_log
    elif name.startswith("запазд."):
        fam = family_map(mult_dlog); ev = mult_dlog
    else:
        J = jac_num(F, np.array(xstar, float))
        fam, ev = family_flow(J)
    lead = ev[np.argmax(ev.real)] if not name.startswith(("лог.", "запазд.")) else ev[np.argmax(np.abs(ev))]
    ok = fam == want_fam
    correct += ok
    rows.append(dict(name=name, fam=fam, want=want_fam, ok=bool(ok),
                     lead=[float(lead.real), float(lead.imag)]))
    print(f"{name}: ведущая {lead:.4f} -> {fam} (истина {want_fam}) {'✓' if ok else '✗'}", flush=True)

# secondary: fold vs transcritical probe on stationary systems (equilibria count both sides)
def count_eq(mkF, knob_lo, knob_hi, x0s):
    out = []
    for kv in (knob_lo, knob_hi):
        F = mkF(kv)
        sols = set()
        for x0 in x0s:
            xf = relax(F, x0, steps=200000)
            sols.add(tuple(np.round(xf, 2)))
        out.append(len(sols))
    return out

sub = {}
sub["Шлёгль"] = dict(n=count_eq(mk_schlogl, 0.95, 1.05, [[0.5], [4.0]]), want="фолд")      # dark exists below fold only
def mk_verh(lam): return lambda x: np.array([lam * x[0] + EPSV - x[0] - x[0] ** 2 / KCAP])
sub["Ферхюльст"] = dict(n=count_eq(mk_verh, 0.95, 1.05, [[0.05], [3.0]]), want="транскритика")
def mk_ring2k(k): return mk_ring2(k)
sub["кольцо²"] = dict(n=count_eq(mk_ring2k, 14.0, 18.0, [np.full(10, 0.1), np.full(10, 8.0)]), want="фолд")
def mk_tog(a): return lambda x: np.array([a / (1 + x[1] ** 2) - x[0], a / (1 + x[0] ** 2) - x[1]])
sub["тоггл"] = dict(n=count_eq(mk_tog, 1.9, 2.4, [[0.3, 2.0], [2.0, 0.3], [1.0, 1.0]]), want="питчфорк")
# fold signature: attractor count CHANGES 1->2 (or 2->1) across knob*; transcritical: stays (branch exchange keeps 1 positive attractor)
sub_ok = 0; sub_n = 0
for k, v in sub.items():
    lo, hi = v["n"]
    fold_like = (lo != hi)
    guess = "фолд/питчфорк (счёт меняется)" if fold_like else "транскритика (счёт постоянен)"
    ok = (fold_like and v["want"] in ("фолд", "питчфорк")) or ((not fold_like) and v["want"] == "транскритика")
    sub_ok += ok; sub_n += 1
    print(f"суб {k}: аттракторов {lo}->{hi} -> {guess} (истина {v['want']}) {'✓' if ok else '✗'}", flush=True)

pun1 = correct >= 9; pun1_kill = correct <= 6
out = dict(rows=rows, correct=correct, sub={k: v["n"] for k, v in sub.items()}, sub_ok=sub_ok, sub_n=sub_n,
           verdicts=dict(PUN1=bool(pun1), PUN1_killed=bool(pun1_kill), PUN2=bool(sub_ok >= 3)))
json.dump(out, open("/home/claude/uni01_results.json", "w"), default=float)
print(f"\nP-UN1: {correct}/10 -> {'ПОДТВЕРЖДЁН' if pun1 else ('УБИТ' if pun1_kill else 'не установлен')}")
print(f"P-UN2 (суб-классификация): {sub_ok}/{sub_n}")
