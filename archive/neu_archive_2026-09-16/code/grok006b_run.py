"""GROK-006b — flicker window by lr and catapult failure multiplier. Per PREREG (frozen 2026-09-02)."""
import sys, json, os, time
import numpy as np
src = open("/home/claude/grok006_run.py").read().split("MAIN = [415")[0]
# lr schedule: lr0 until t_switch (birth), then lr1 (amendment 2026-09-02: lr = 14 diverges at init on fresh seeds)
src = src.replace("def run_flicker(seed, wd0, t_switch, wd1, post, with_sharp=True):", "def run_flicker(seed, wd0, t_switch, wd1, post, with_sharp=True, lr0=10.0, lr1=10.0):")
src = src.replace("        wd = wd0 if t < t_switch else wd1\n", "        wd = wd0 if t < t_switch else wd1\n        LR = lr0 if t < t_switch else lr1\n")
assert "LR = lr0 if t < t_switch else lr1" in src
exec(src)
CK = "/home/claude/grok006b_ckpt.json"
mode = sys.argv[1]
t0 = time.time()
def load():
    return json.load(open(CK)) if os.path.exists(CK) else {}
if mode == "run":
    sd = int(sys.argv[2])
    for lr in (14.0, 7.0, 5.0):
        key = f"{sd}_lr{lr:g}"
        if key in load(): continue
        lr0 = 10.0 if lr > 10 else lr     # warm start at lr=10 for the lr=14 node only (amendment); lr=5/7 unchanged
        pre_acc, pre_sharp, rec, cold = run_flicker(sd, 3e-4, 1000, 1e-3, 6000, with_sharp=True, lr0=lr0, lr1=lr)
        np.save(f"/home/claude/grok006b_rec_{sd}_lr{lr:g}.npy", rec)
        born = bool((pre_acc >= 0.5).any())
        a = analyze(rec, pre_sharp) if born else dict(flicker=False, n_bursts=0)
        a["born"] = born; a["final_acc"] = float(rec[-1, 1]); a["frac_below"] = float(np.mean(rec[:, 1] < 0.5))
        sh = rec[:, 5]; s = sh[~np.isnan(sh)]
        a["final_sharp"] = float(np.median(s[-10:])) if len(s) >= 10 else None
        a["final_norm"] = float(rec[-1, 3])
        disc = [abs(y - z) / max(abs(z), 1e-9) for _, y, z in cold]
        a["cold_disc_med"] = float(np.median(disc)) if disc else None
        a["T_lr"] = (a["T_med"] * lr) if a.get("T_med") else None
        a.pop("ib", None)
        ck = load(); ck[key] = a; json.dump(ck, open(CK, "w"), default=float)
        print(f"сид {sd} lr={lr:g}: born={born} bursts={a.get('n_bursts')} T_med={a.get('T_med')} T*lr={a.get('T_lr')} pre_sharp={a.get('pre_sharp_med')} "
              f"final_sharp={a.get('final_sharp')} final_norm={a['final_norm']:.2f} final_acc={a['final_acc']:.3f} cold_disc={a.get('cold_disc_med')} [{time.time()-t0:.0f}s]", flush=True)
elif mode == "verdict":
    ck = load(); V = {}
    def g(sd, lr): return ck.get(f"{sd}_lr{lr:g}", {})
    r14 = [g(s, 14) for s in (421, 422)]
    ok14 = all(r.get("born") and r.get("n_bursts", 0) >= 20 and r.get("pre_sharp_med") is not None and 2.9 <= r["pre_sharp_med"] <= 3.9 and (r.get("cold_disc_med") or 0) <= 0.10 for r in r14)
    kill14 = all(r.get("pre_sharp_med") is not None and (r["pre_sharp_med"] >= 4.4 or r["pre_sharp_med"] <= 2.4) for r in r14)
    V["PH1"] = dict(ok=bool(ok14), killed=bool(kill14), vals=[r.get("pre_sharp_med") for r in r14], bursts=[r.get("n_bursts") for r in r14])
    low = [g(s, lr) for s in (421, 422) for lr in (5, 7)]
    ok2 = all(r.get("born") and r.get("n_bursts", 99) < 5 and r.get("final_acc", 0) >= 0.9 for r in low)
    kill2 = all(g(s, 7).get("n_bursts", 0) >= 20 for s in (421, 422))
    V["PH2"] = dict(ok=bool(ok2), killed=bool(kill2), bursts={f"{s}_lr{lr}": g(s, lr).get("n_bursts") for s in (421, 422) for lr in (5, 7)},
                    final_sharp={f"{s}_lr{lr}": g(s, lr).get("final_sharp") for s in (421, 422) for lr in (5, 7)})
    ok3 = all(r.get("T_lr") is not None and 720 <= r["T_lr"] <= 1080 for r in r14)
    kill3 = all(r.get("T_lr") is not None and (r["T_lr"] < 600 or r["T_lr"] > 1300) for r in r14)
    V["PH3"] = dict(ok=bool(ok3), killed=bool(kill3), vals=[r.get("T_lr") for r in r14])
    ck["verdicts"] = V; json.dump(ck, open(CK, "w"), default=float)
    for k, v in V.items():
        print(k, "ПОДТВЕРЖДЁН" if v["ok"] else ("УБИТ" if v["killed"] else "не установлен"), {kk: vv for kk, vv in v.items() if kk not in ("ok", "killed")})
print(f"[{time.time()-t0:.0f}s]")
