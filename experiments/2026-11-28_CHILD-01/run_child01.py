"""CHILD-01: очередь прогонов с продолжением с места остановки.
  python3 run_child01.py pilot   — сиды 990–992 в каталог pilot/ (в тест не входят)
  python3 run_child01.py test    — сиды 100–119 в каталог runs/ (только после регистрации PREREG-CHILD-01.md)"""
import os, sys, json, time, subprocess
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = ('T1', 'T2', 'T3', 'T4', 'T5', 'T6')
ARMS = ('FIX', 'RND', 'ALT_12', 'ALT_25', 'ALT_50', 'ALT_75', 'NOISE_25', 'NOISE_50', 'MIX_25', 'MIX_50', 'FINAL_25', 'FINAL_50',
        'RND4', 'ALT_6_N64', 'ALT_25_T20')
SEEDS = {'pilot': (990, 991, 992), 'test': tuple(range(100, 120))}

def job(a):
    task, arm, seed, outdir = a
    out = os.path.join(outdir, f'{task}_{arm}_s{seed}.json')
    if os.path.exists(out): return None
    p = subprocess.run([sys.executable, os.path.join(HERE, 'child01.py'), task, arm, str(seed), outdir], capture_output=True, text=True)
    return (p.stdout.strip() or p.stderr.strip()[-300:])

if __name__ == '__main__':
    mode = sys.argv[1]; outdir = os.path.join(HERE, 'pilot' if mode == 'pilot' else 'runs'); os.makedirs(outdir, exist_ok=True)
    jobs = [(t, a, s, outdir) for s in SEEDS[mode] for t in TASKS for a in ARMS]
    t0 = time.time(); done = 0
    with ProcessPoolExecutor(max_workers=4) as ex:
        for r in ex.map(job, jobs):
            done += 1
            if r: print(r, flush=True)
    have = sum(os.path.exists(os.path.join(outdir, f'{t}_{a}_s{s}.json')) for t, a, s, _ in jobs)
    print(f'готово: {done} заданий за {round(time.time() - t0)} с; файлов {have} из {len(jobs)}', flush=True)
    sys.exit(0 if have == len(jobs) else 1)
