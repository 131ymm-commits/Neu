"""UNI-07 — hysteresis of the route: death as reverse pass. Per PREREG (frozen 2026-08-31)."""
import json, os, time
import numpy as np

h = {}
exec(open("/home/claude/pre005b_run.py").read().split("ck = json.load")[0], h)   # sim_ext, drift, const, constants
k1s, k4s, SN1, Ww = h["k1s"], h["k4s"], h["SN1"], h["Ww"]
REC_DT = h["REC_DT"]
CK = "/home/claude/uni07_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

T_REV = 3600.0
rev = lambda t: 1.10 - (1.10 - (-0.10)) * min(t / T_REV, 1.0)
hot_const = lambda t: 1.10

def sim_rev(par_fn, seed, ntraj, V, T_tot):
    """sim_ext structural copy: start on the HOT root (rts[-1]); duration T_tot."""
    rng = np.random.default_rng(seed)
    fr0 = par_fn(0.0)
    k30 = SN1 + fr0 * Ww
    rts = np.roots([-1.0, k1s, -k4s, k30]); rts = np.sort(rts[np.isreal(rts)].real)
    n = np.full(ntraj, int(round(V * rts[-1])), dtype=np.int64)
    DT = 0.005
    steps = int(T_tot / DT)
    stride = int(REC_DT / DT)
    nsamp = int(T_tot / REC_DT)
    rec = np.empty((ntraj, nsamp))
    for i in range(steps):
        fr = par_fn(i * DT)
        k3 = SN1 + fr * Ww
        x = n / V
        bp = V * np.maximum(k3 + k1s * x * x, 0)
        bm = V * (k4s * x + x ** 3)
        n = np.maximum(n + rng.poisson(bp * DT) - rng.poisson(bm * DT), 0)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < nsamp: rec[:, k] = n / V
    return rec

# ---------- root sanity: line 2.2 between branches over the corridor ----------
if "sanity" not in ck:
    ok = True; rows = []
    for fr in np.arange(0.05, 1.10001, 0.05):
        k3 = SN1 + fr * Ww
        r = np.roots([-1.0, k1s, -k4s, k3]); r = np.sort(r[np.isreal(r)].real)
        if len(r) == 3:
            dark, hot = r[0], r[-1]
            rows.append((float(fr), float(dark), float(hot)))
            if not (dark < 2.2 < hot): ok = False
    ck["sanity"] = dict(ok=bool(ok), n_bistable=len(rows),
                        fr_range=[rows[0][0], rows[-1][0]] if rows else None)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"санити корней: бистабильный коридор fr ∈ {ck['sanity']['fr_range']}, линия 2.2 между ветвями: {ok}", flush=True)
if not ck["sanity"]["ok"]:
    print("линия 2.2 не разделяет ветви — стоп по предрегистрации")
    raise SystemExit

FUP = {20: 0.3969666666666667, 200: 0.8673666666666668, 2000: 0.9849666666666668}  # frozen from VER-001d

for V in (20, 200, 2000):
    key = f"V{V}"
    if key in ck: continue
    drf = sim_rev(rev, 20280854 + V + 154, 5, V, T_REV)
    fr_down, miss = [], 0
    for r in range(5):
        below = np.flatnonzero(drf[r] < 2.2)
        if below.size:
            fr_down.append(float(rev(below[0] * REC_DT)))
        else:
            miss += 1
    ctl = sim_rev(hot_const, 20280854 + V + 77, 3, V, T_REV)
    ctl_stay = sum(1 for r in range(3) if not np.flatnonzero(ctl[r] < 2.2).size)
    ck[key] = dict(fr_down=fr_down, miss=miss, ctl_stay=ctl_stay,
                   med_down=(float(np.median(fr_down)) if fr_down else None))
    if V == 200:
        np.save("/home/claude/uni07_death200.npy", drf)   # for P-U7-3
    json.dump(ck, open(CK, "w"), default=float)
    print(f"V={V}: fr_down={[round(x,3) for x in fr_down]} (мимо: {miss}) | медиана {ck[key]['med_down']} | "
          f"горячий контроль удержался {ctl_stay}/3 [{time.time()-t0:.0f}s]", flush=True)

# ---------- P-U7-3: death records reversed -> fold? ----------
if "death_read" not in ck:
    exec(open("/home/claude/ext001_run.py").read().split("# ---------- Phase A")[0], h)   # feats, classify into h
    TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
    drf = np.load("/home/claude/uni07_death200.npy")
    labs = []
    for r in range(5):
        tr = drf[r][::-1]                                  # time-reversed death = birth-like
        blocks = tr[:len(tr) // 240 * 240].reshape(-1, 240).mean(1)
        cr = np.flatnonzero(blocks > 2.2)
        if cr.size and cr[0] >= 20:
            i_on = int(cr[0]); lo = max(i_on - 80, 0)
            w = blocks[lo:min(i_on + 20, len(blocks))]
            labs.append(h["classify"](h["feats"](w, i_on - lo), TH))
        else:
            labs.append("нет пересечения")
    nf = sum(1 for l in labs if l == "фолд")
    ck["death_read"] = dict(labs=labs, n_fold=nf)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-U7-3: обращённые записи смерти -> {labs} | фолд {nf}/5", flush=True)

# ---------- verdicts ----------
w = {V: (FUP[V] - ck[f"V{V}"]["med_down"]) if ck[f"V{V}"]["med_down"] is not None else None for V in (20, 200, 2000)}
p1 = all(w[V] is not None and w[V] > 0 for V in (200, 2000))
p1_kill = any(w[V] is not None and w[V] <= 0 for V in (200, 2000))
p2 = None not in w.values() and w[20] < w[200] < w[2000] and w[2000] >= 0.7
p2_kill = None not in w.values() and not (w[20] < w[200] < w[2000])
nf = ck["death_read"]["n_fold"]
p3 = nf >= 4; p3_kill = nf <= 2
ctl_ok = all(ck[f"V{V}"]["ctl_stay"] >= 2 for V in (20, 200, 2000))
ck["verdicts"] = dict(fr_up=FUP, med_down={str(V): ck[f"V{V}"]["med_down"] for V in (20, 200, 2000)},
                      w={str(V): w[V] for V in w}, PU71=bool(p1), PU71_killed=bool(p1_kill),
                      PU72=bool(p2), PU72_killed=bool(p2_kill), PU73=bool(p3), PU73_killed=bool(p3_kill),
                      ctl_ok=bool(ctl_ok), n_fold_death=nf)
json.dump(ck, open(CK, "w"), default=float)
print(f"\nокна w(V): {w} (детерминированное: 1.0)")
print(f"P-U7-1 (окно открыто при V=200,2000): {'ПОДТВЕРЖДЁН' if p1 else ('УБИТ' if p1_kill else 'не установлен')}")
print(f"P-U7-2 (монотонность + w(2000)>=0.7): {'ПОДТВЕРЖДЁН' if p2 else ('УБИТ' if p2_kill else 'не установлен')}")
print(f"P-U7-3 (смерть читается фолдом, {nf}/5): {'ПОДТВЕРЖДЁН' if p3 else ('УБИТ' if p3_kill else 'не установлен')}")
print(f"контроли: {'✓' if ctl_ok else '✗'} [{time.time()-t0:.0f}s]")
