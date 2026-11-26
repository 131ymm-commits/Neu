#!/bin/bash
# Проба раннера GitHub: описание машины → $1/probe.json (без личных данных).
set -e
OUT="$1"
python3 -m pip install -q numpy
python3 - "$OUT" <<'PY'
import json, os, platform, sys, time
out = sys.argv[1]
info = {'python': sys.version.split()[0], 'platform': platform.platform(), 'cpus': os.cpu_count()}
try:
    info['mem_total'] = open('/proc/meminfo').readline().split(':')[1].strip()
except Exception:
    pass
import numpy as np
info['numpy'] = np.__version__
a = np.random.default_rng(0).standard_normal((2000, 2000))
t = time.time(); _ = a @ a; info['matmul_2000_s'] = round(time.time() - t, 3)
info['utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
json.dump(info, open(os.path.join(out, 'probe.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(info, ensure_ascii=False))
PY
