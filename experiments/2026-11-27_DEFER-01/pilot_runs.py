"""DEFER-01, пилот: ветви MIRROR_0/25/50/100 (код EVO-03) и FIXED16, RANDOM16 (код EVO-01) на пилотных сидах 996–998.
Эти сиды не входят ни в один тест (EVO-01: 0–19, EVO-03: 20–39, EVO-06: 80–99). Код мира не меняется: функции вызываются
из каталога EVO-03, результаты пишутся только в DEFER-01/pilot/. Тестовые каталоги runs/ не читаются и не пишутся."""
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '2026-09-26_EVO-03')
OUT = os.path.join(HERE, 'pilot')

def job(a):
    task, arm, seed = a
    out = os.path.join(OUT, f'{task}_{arm}_s{seed}.json')
    if os.path.exists(out): return f'{task} {arm} {seed}: уже есть'
    sys.path.insert(0, SRC); os.chdir(SRC)
    import evo01, evo03
    t0 = time.time()
    hist = evo03.run_mirror(task, int(arm.split('_')[1]) / 100, seed) if arm.startswith('MIRROR') else evo01.run(task, arm, seed)['hist']
    tmp = out + '.tmp'
    json.dump(dict(task=task, arm=arm, seed=seed, hist=hist, sec=round(time.time() - t0, 1)), open(tmp, 'w')); os.replace(tmp, out)
    return f'{task} {arm} {seed}: {round(time.time() - t0, 1)} с'

if __name__ == '__main__':
    jobs = [(t, a, s) for s in (996, 997, 998) for t in ('T1', 'T2', 'T3')
            for a in ('MIRROR_0', 'MIRROR_25', 'MIRROR_50', 'MIRROR_100', 'FIXED16', 'RANDOM16')]
    with ProcessPoolExecutor(max_workers=4) as ex:
        for r in ex.map(job, jobs): print(r, flush=True)
