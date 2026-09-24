"""GROK-005 — clock certificate on grokking birth time + init/split decomposition. Per PREREG (frozen 2026-09-02)."""
import json, os, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])   # P, make_data (FRAC global)
CK = "/home/claude/grok005_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
LR, WD, D, REC, HOLD = 10.0, 3e-4, 512, 2, 200

def run2(data_seed, init_seed, frac, budget):
    """Same dynamics as grok_cal.run, but data split and init seeded separately; early stop HOLD steps after birth."""
    global FRAC
    FRAC = frac
    (Xtr, Ytr), (Xte, Yte) = make_data(data_seed)
    rng = np.random.default_rng(init_seed)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr); t_grok = None; hold = None; acc_tr = 0.0
    for t in range(budget):
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        W1 -= LR * (gW1 + WD * W1); W2 -= LR * (gW2 + WD * W2)
        if t % REC == 0:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc_te = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            acc_tr = float((Out.argmax(1) == Ytr.argmax(1)).mean())
            if t_grok is None and acc_te >= 0.5:
                t_grok = t
            if t_grok is not None and t >= t_grok + HOLD:
                hold = bool(acc_te >= 0.5)
                break
    return dict(t_grok=t_grok, hold=hold, acc_tr=acc_tr, censored=(t_grok is None), steps=t + 1)

ARMS = {
    "A_nat_050":  dict(frac=0.50, budget=3000,  runs=[(s, s + 7) for s in range(601, 611)]),
    "B_nat_023":  dict(frac=0.23, budget=20000, runs=[(s, s + 7) for s in range(611, 621)]),
    "C1_init_023": dict(frac=0.23, budget=20000, runs=[(700, s) for s in range(701, 709)]),
    "C2_split_023": dict(frac=0.23, budget=20000, runs=[(s, 700) for s in range(711, 719)]),
    "D1_init_050": dict(frac=0.50, budget=3000,  runs=[(720, s) for s in range(721, 729)]),
    "D2_split_050": dict(frac=0.50, budget=3000,  runs=[(s, 720) for s in range(731, 739)]),
}
ORDER = ["A_nat_050", "D1_init_050", "D2_split_050", "B_nat_023", "C1_init_023", "C2_split_023"]
for arm in ORDER:
    spec = ARMS[arm]
    for ds, is_ in spec["runs"]:
        key = f"{arm}:{ds}:{is_}"
        if key in ck: continue
        r = run2(ds, is_, spec["frac"], spec["budget"])
        ck[key] = r
        json.dump(ck, open(CK, "w"), default=float)
        print(f"{arm} data={ds} init={is_}: t_grok={r['t_grok']} hold={r['hold']} tr={r['acc_tr']:.3f} "
              f"{'ЦЕНЗ' if r['censored'] else ''} [{time.time()-t0:.0f}s]", flush=True)

# ---------- verdicts ----------
def cv_of(arm):
    rs = [ck[f"{arm}:{ds}:{is_}"] for ds, is_ in ARMS[arm]["runs"]]
    tg = np.array([r["t_grok"] for r in rs if not r["censored"]], float)
    cens = sum(1 for r in rs if r["censored"])
    if cens >= 3 or len(tg) < 4:
        return dict(cv=None, n=len(tg), cens=cens, mean=None, loo=None, unreadable=True)
    cv = float(tg.std(ddof=1) / tg.mean())
    loo = [float(np.delete(tg, i).std(ddof=1) / np.delete(tg, i).mean()) for i in range(len(tg))]
    return dict(cv=cv, n=len(tg), cens=cens, mean=float(tg.mean()), sd=float(tg.std(ddof=1)),
                loo_min=float(min(loo)), loo_max=float(max(loo)), t=tg.tolist(), unreadable=False,
                holds=sum(1 for r in rs if r["hold"]), tr_flags=sum(1 for r in rs if r["acc_tr"] < 0.99))
S = {arm: cv_of(arm) for arm in ARMS}
def ok(*arms): return all(not S[a]["unreadable"] for a in arms)
cvA, cvB = S["A_nat_050"]["cv"], S["B_nat_023"]["cv"]
cvI23, cvS23 = S["C1_init_023"]["cv"], S["C2_split_023"]["cv"]
cvI50, cvS50 = S["D1_init_050"]["cv"], S["D2_split_050"]["cv"]
V = {}
V["PC7a"] = dict(ok=bool(ok("A_nat_050") and cvA <= 0.15), killed=bool(ok("A_nat_050") and cvA >= 0.30))
V["PC7b"] = dict(ok=bool(ok("A_nat_050", "B_nat_023") and cvB >= 2 * cvA), killed=bool(ok("A_nat_050", "B_nat_023") and cvB <= cvA))
V["PC7c"] = dict(ok=bool(ok("C1_init_023", "C2_split_023") and cvS23 >= 2 * cvI23), killed=bool(ok("C1_init_023", "C2_split_023") and cvI23 >= cvS23))
V["PC7d"] = dict(ok=bool(ok("D1_init_050", "D2_split_050") and cvI50 >= cvS50), killed=bool(ok("D1_init_050", "D2_split_050") and cvS50 >= 2 * cvI50))
ck["summary"] = S; ck["verdicts"] = V
json.dump(ck, open(CK, "w"), default=float)
for a in ORDER:
    s = S[a]; print(f"{a}: CV={None if s['cv'] is None else round(s['cv'],4)} n={s['n']} cens={s['cens']} mean={s['mean']} LOO=[{s.get('loo_min')},{s.get('loo_max')}]")
for k, v in V.items():
    print(f"{k}: {'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен')}")
print(f"[{time.time()-t0:.0f}s] -> {CK}")
