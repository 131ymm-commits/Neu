"""GROK-001 — battery on grokking curves. Per PREREG (frozen 2026-09-01)."""
import json, os, time
import numpy as np

exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])       # P, make_data, run (FRAC global)
exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])      # feats, classify, LAG_R2
TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
CK = "/home/claude/grok001_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def runf(seed, frac, steps):
    global FRAC
    FRAC = frac
    return run(seed, 10.0, 3e-4, 512, steps, rec_every=2)

def battery(h):
    te = h[:, 2]
    cr_rec = np.flatnonzero(te >= 0.5)
    if cr_rec.size == 0:
        return dict(born=False, label="нет рождения")
    cut = min(3 * int(cr_rec[0]) + 1, len(te))
    seg = te[:cut]
    x = np.interp(np.linspace(0, len(seg) - 1, 200), np.arange(len(seg)), seg)
    cr = np.flatnonzero(x >= 0.5)
    if cr.size == 0 or cr[0] < 10:
        return dict(born=True, label="флаг: ранний кроссинг", flag=True, t_grok=int(h[cr_rec[0], 0]))
    f = feats(x, int(cr[0]))
    # v2 oscillator gates on the same resampled window (z from feats; T and A):
    t2 = np.arange(len(x))
    res = x - np.polyval(np.polyfit(t2, x, 1), t2)
    u = res[LAG_R2:]; v = res[:-LAG_R2]
    phi = np.arctan2(v, u)
    d = np.angle(np.exp(1j * np.diff(phi)))
    T = float(abs(d.sum()) / (2 * np.pi))
    E = x[:max(int(cr[0]) - 5, 10)]
    tE = np.arange(len(E))
    resE = E - np.polyval(np.polyfit(tE, E, 1), tE)
    sE = 1.4826 * np.median(np.abs(resE - np.median(resE))) + 1e-12
    A = float(np.sqrt(np.mean(res ** 2)) / sE)
    if f["z"] >= TH["thR2"] and T >= 2.0 and A >= 3.0:
        lab = "осциллятор"
    elif f["rise"] < TH["thRise"]:
        lab = "нет рождения"
    elif f["S"] is not None and f["S"] >= TH["thS"]:
        lab = "фолд"
    else:
        lab = "непрерывный"
    return dict(born=True, label=lab, S=f["S"], rise=f["rise"], z=f["z"], T=T, A=A,
                t_grok=int(h[cr_rec[0], 0]), cut=cut)

def stepcert_log(h, t_grok_rec):
    """EXT-014c certificate on log10-time grid up to 3x crossing."""
    te = h[:, 2]; steps = h[:, 0]
    cut = min(3 * t_grok_rec + 1, len(te))
    m = steps[:cut] >= 10
    ls, y = np.log10(steps[:cut][m] + 1), te[:cut][m]
    grid = np.linspace(ls[0], ls[-1], 100)
    yy = np.interp(grid, ls, y)
    n = len(yy)
    def fit_step(w):
        best = (None, np.inf, None)
        for k in range(3, n - 3):
            m1, m2 = w[:k].mean(), w[k:].mean()
            s = ((w[:k] - m1) ** 2).sum() + ((w[k:] - m2) ** 2).sum()
            if s < best[1]: best = (k, s, abs(m2 - m1))
        return best
    def fit_kink(w):
        t = np.arange(n, dtype=float); best = (None, np.inf)
        for k in range(3, n - 3):
            X = np.column_stack([np.ones(n), t, np.maximum(t - k, 0)])
            b, *_ = np.linalg.lstsq(X, w, rcond=None)
            s = float(((w - X @ b) ** 2).sum())
            if s < best[1]: best = (k, s)
        return best
    ks, ss, dm = fit_step(yy)
    kk, sk = fit_kink(yy)
    dbic = (n * np.log(sk / n) + 4 * np.log(n)) - (n * np.log(ss / n) + 3 * np.log(n))
    bic = "ступень" if dbic >= 6 else ("излом" if dbic <= -6 else "неразличимо")
    cross_node = int(np.argmin(np.abs(grid - np.log10(steps[t_grok_rec] + 1))))
    return dict(bic=bic, dbic=float(dbic), k=ks, cross_node=cross_node, pos_ok=bool(abs(ks - cross_node) <= 10))

ARMS = [("main", 0.5, 3000, [201, 202, 203, 204, 205, 206]),
        ("a30", 0.30, 10000, [211, 212, 213]),
        ("a25", 0.25, 16000, [221, 222, 223]),
        ("ctrl", 0.20, 30000, [301, 302, 303, 304, 305, 306])]
for name, frac, steps, seeds in ARMS:
    for sd in seeds:
        key = f"{name}_{sd}"
        if key in ck: continue
        h = runf(sd, frac, steps)
        b = battery(h)
        if name == "main" and b.get("born") and not b.get("flag"):
            cr_rec = int(np.flatnonzero(h[:, 2] >= 0.5)[0])
            b["step"] = stepcert_log(h, cr_rec)
        ck[key] = b
        json.dump(ck, open(CK, "w"), default=float)
        print(f"{name} α={frac} сид {sd}: {b.get('label')} t_grok={b.get('t_grok')} "
              f"S={b.get('S') if b.get('S') is None else round(b.get('S'),2)} "
              f"{('BIC:' + b['step']['bic'] + (' поз✓' if b['step']['pos_ok'] else ' поз✗')) if 'step' in b else ''} "
              f"[{time.time()-t0:.0f}s]", flush=True)

# ---------- verdicts ----------
main = [ck[f"main_{s}"] for s in (201, 202, 203, 204, 205, 206)]
born = sum(1 for b in main if b.get("born"))
fold = sum(1 for b in main if b.get("label") == "фолд")
osc = sum(1 for b in main if b.get("label") == "осциллятор")
ctrl_none = sum(1 for s in (301, 302, 303, 304, 305, 306) if not ck[f"ctrl_{s}"].get("born"))
steps_ok = sum(1 for b in main if b.get("step", {}).get("bic") == "ступень" and b["step"]["pos_ok"])
kinks = sum(1 for b in main if b.get("step", {}).get("bic") == "излом")
med = {}
for nm, ss in (("main", (201, 202, 203, 204, 205, 206)), ("a30", (211, 212, 213)), ("a25", (221, 222, 223))):
    tg = [ck[f"{nm}_{s}"].get("t_grok") for s in ss if ck[f"{nm}_{s}"].get("t_grok")]
    med[nm] = float(np.median(tg)) if tg else None
S_main = [b.get("S") for b in main if b.get("S") is not None]
S_a25 = [ck[f"a25_{s}"].get("S") for s in (221, 222, 223) if ck[f"a25_{s}"].get("S") is not None]
pg1 = born == 6 and fold >= 4 and osc == 0
pg1_kill = born <= 3 or (6 - fold - osc) >= 4 or (sum(1 for b in main if b.get("label") in ("непрерывный", "нет рождения")) >= 4)
pg2 = ctrl_none >= 5; pg2_kill = (6 - ctrl_none) >= 3
pg3 = steps_ok >= 4; pg3_kill = kinks >= 4
pg4 = None not in med.values() and med["main"] < med["a30"] < med["a25"]
pg5 = bool(S_a25) and bool(S_main) and float(np.median(S_a25)) > float(np.median(S_main))
ck["verdicts"] = dict(born=born, fold=fold, osc=osc, ctrl_none=ctrl_none, steps_ok=steps_ok, kinks=kinks,
                      med_tgrok=med, S_main_med=(float(np.median(S_main)) if S_main else None),
                      S_a25_med=(float(np.median(S_a25)) if S_a25 else None),
                      PG1=bool(pg1), PG1_killed=bool(pg1_kill), PG2=bool(pg2), PG2_killed=bool(pg2_kill),
                      PG3=bool(pg3), PG3_killed=bool(pg3_kill), PG4=bool(pg4), PG4_killed=bool(not pg4),
                      PG5=bool(pg5), PG5_killed=bool(not pg5))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-G1: рождение {born}/6, фолд {fold}/6, осц {osc}/6 -> {'ПОДТВЕРЖДЁН' if pg1 else ('УБИТ' if pg1_kill else 'не установлен')}")
print(f"P-G2: контроль без рождения {ctrl_none}/6 -> {'ПОДТВЕРЖДЁН' if pg2 else ('УБИТ' if pg2_kill else 'не установлен')}")
print(f"P-G3: ступень+позиция {steps_ok}/6 (изломов {kinks}) -> {'ПОДТВЕРЖДЁН' if pg3 else ('УБИТ' if pg3_kill else 'не установлен')}")
print(f"P-G4: медианы t_grok {med} -> {'ПОДТВЕРЖДЁН' if pg4 else 'УБИТ'}")
print(f"P-G5: S медианы {ck['verdicts']['S_main_med']} (α=0.5) vs {ck['verdicts']['S_a25_med']} (α=0.25) -> {'ПОДТВЕРЖДЁН' if pg5 else 'УБИТ'}")
print(f"[{time.time()-t0:.0f}s] -> {CK}")
