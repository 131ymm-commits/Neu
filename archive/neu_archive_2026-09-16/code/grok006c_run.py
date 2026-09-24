"""GROK-006c — edge of the flicker window in lr. Per PREREG (frozen 2026-09-02). Sharpness grid every 10 steps + trigger on loss rise > 20%."""
import sys, json, os, time
import numpy as np
src = open("/home/claude/grok006_run.py").read().split("MAIN = [415")[0]
src = src.replace("def run_flicker(seed, wd0, t_switch, wd1, post, with_sharp=True):", "def run_flicker(seed, wd0, t_switch, wd1, post, with_sharp=True, lr0=10.0, lr1=10.0):")
src = src.replace("        wd = wd0 if t < t_switch else wd1\n", "        wd = wd0 if t < t_switch else wd1\n        LR = lr0 if t < t_switch else lr1\n")
src = src.replace("(((t - t_switch) % 30 == 0) or (ltr_prev is not None and ltr > ltr_prev))",
                  "(((t - t_switch) % 10 == 0) or (ltr_prev is not None and ltr > 1.2 * ltr_prev))")
assert "LR = lr0 if t < t_switch else lr1" in src and "ltr > 1.2 * ltr_prev" in src
exec(src)
CK = "/home/claude/grok006c_ckpt.json"
mode = sys.argv[1]; t0 = time.time()
def load(): return json.load(open(CK)) if os.path.exists(CK) else {}
if mode == "run":
    sd = int(sys.argv[2])
    for lr in (8.0, 9.5, 9.0):
        key = f"{sd}_lr{lr:g}"
        if key in load(): continue
        pre_acc, pre_sharp, rec, cold = run_flicker(sd, 3e-4, 1000, 1e-3, 6000, with_sharp=True, lr0=lr, lr1=lr)
        np.save(f"/home/claude/grok006c_rec_{sd}_lr{lr:g}.npy", rec)
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
    r8 = [g(s, 8) for s in (423, 424)]; r95 = [g(s, 9.5) for s in (423, 424)]
    ok_a = all(r.get("born") and r.get("n_bursts", 99) < 5 and r.get("final_acc", 0) >= 0.9 and r.get("final_sharp") is not None and 1.9 <= r["final_sharp"] <= 2.4 for r in r8)
    kill_a = all(r.get("n_bursts", 0) >= 20 for r in r8)
    V["PH4a"] = dict(ok=bool(ok_a), killed=bool(kill_a), bursts=[r.get("n_bursts") for r in r8], final_sharp=[r.get("final_sharp") for r in r8])
    ok_b = all(r.get("born") and r.get("n_bursts", 0) >= 20 and r.get("pre_sharp_med") is not None and 2.9 <= r["pre_sharp_med"] <= 3.9 and (r.get("cold_disc_med") or 0) <= 0.10 for r in r95)
    kill_b = all(r.get("n_bursts", 0) < 5 for r in r95) or all(r.get("pre_sharp_med") is not None and not (2.4 <= r["pre_sharp_med"] <= 4.4) for r in r95)
    V["PH4b"] = dict(ok=bool(ok_b), killed=bool(kill_b), bursts=[r.get("n_bursts") for r in r95], pre_sharp=[r.get("pre_sharp_med") for r in r95])
    V["node9"] = {f"{s}": dict(bursts=g(s, 9).get("n_bursts"), pre_sharp=g(s, 9).get("pre_sharp_med"), final_sharp=g(s, 9).get("final_sharp"), T_lr=g(s, 9).get("T_lr")) for s in (423, 424)}
    ck["verdicts"] = V; json.dump(ck, open(CK, "w"), default=float)
    for k, v in V.items():
        if k.startswith("PH"): print(k, "ПОДТВЕРЖДЁН" if v["ok"] else ("УБИТ" if v["killed"] else "не установлен"), {kk: vv for kk, vv in v.items() if kk not in ("ok", "killed")})
        else: print(k, v)
print(f"[{time.time()-t0:.0f}s]")
