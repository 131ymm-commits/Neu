#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: сухой прогон анализа теста на заглушках (совет 74, п. 10) — B = 4000, R = 20, 15 сред, 4 процесса, те же
# размеры построения и теста; время и память; частичный json и продолжение с готовых сред; повтор на детерминизм — 2 среды, B = 200,
# побайтное сравнение. Ответы голов — заглушки dry_d2.py (настоящих ответов здесь нет).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__, 'sklearn', sklearn.__version__)" | tee "$OUT/versions.txt"
echo "ядер: $(nproc)" | tee "$OUT/machine.txt"; free -m | tee -a "$OUT/machine.txt"
python3 $E/test_distill02.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
W=$(mktemp -d)
python3 $E/dry_d2.py make "$W"
( while true; do free -m | awk '/Mem:/{print $3}'; sleep 5; done ) > "$OUT/mem_used_mb.txt" &
MEMPID=$!
echo "== основной прогон (B = 4000, R = 20, 15 сред, 4 процесса)"
T0=$(date +%s)
/usr/bin/time -v timeout 180m python3 $E/dry_d2.py run "$OUT/dry_main.json" "$W/spec_main.json" > "$OUT/main.log" 2> "$OUT/time_main.txt" || echo "основной прогон завершился с ошибкой" | tee -a "$OUT/main.log"
T1=$(date +%s)
echo "== продолжение с готовых сред (тот же spec)"
python3 $E/dry_d2.py run "$OUT/dry_resume.json" "$W/spec_main.json" > "$OUT/resume.log" 2>&1 || echo "продолжение завершилось с ошибкой" | tee -a "$OUT/resume.log"
T2=$(date +%s)
echo "== повтор на детерминизм (2 среды, B = 200, дважды)"
python3 $E/dry_d2.py run "$OUT/det1.json" "$W/spec_det1.json" > "$OUT/det.log" 2>&1
python3 $E/dry_d2.py run "$OUT/det2.json" "$W/spec_det2.json" >> "$OUT/det.log" 2>&1
T3=$(date +%s)
kill $MEMPID || true
python3 - "$OUT" "$T0" "$T1" "$T2" "$T3" <<'PY' | tee "$OUT/dry_summary.txt"
import json, sys, os
out, t0, t1, t2, t3 = sys.argv[1], *map(int, sys.argv[2:])
mem = [int(x) for x in open(os.path.join(out, 'mem_used_mb.txt')).read().split() if x.strip().isdigit()]
tm = open(os.path.join(out, 'time_main.txt'), encoding='utf-8', errors='replace').read()
rss = [l for l in tm.splitlines() if 'Maximum resident set size' in l or 'Elapsed (wall clock)' in l]
a = json.load(open(os.path.join(out, 'dry_main.json'), encoding='utf-8'))
b = json.load(open(os.path.join(out, 'dry_resume.json'), encoding='utf-8'))
sa, sb = a.pop('seconds', None), b.pop('seconds', None)
same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
det = open(os.path.join(out, 'det1.json'), 'rb').read() == open(os.path.join(out, 'det2.json'), 'rb').read()
print('основной прогон, с:', t1 - t0, '| по выводу анализа, с:', sa)
print('продолжение с готовых сред, с:', t2 - t1, '| вывод тот же, кроме времени:', same)
print('повтор на детерминизм (2 × 2 среды, B = 200), с:', t3 - t2, '| побайтно одинаково:', det)
print('память машины, МБ: до', mem[0] if mem else None, '| наибольшая', max(mem) if mem else None)
print('\n'.join(rss))
print('сред в анализе:', len(a['envs']), '| правил:', len(a['rules']))
PY
rm -rf "$W"
