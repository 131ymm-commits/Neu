# Пробный запуск Neu на Kaggle: окружение машины (без видеокарты, без интернета). Вывод — в журнал и probe.json.
import json, os, platform, subprocess, sys, time
t0 = time.time()
info = {'python': sys.version.split()[0], 'platform': platform.platform(), 'cpus': os.cpu_count()}
try:
    import numpy as np
    info['numpy'] = np.__version__
    a = np.random.default_rng(0).standard_normal((2000, 2000))
    t = time.time(); _ = a @ a; info['matmul_2000_s'] = round(time.time() - t, 3)
except Exception as e:
    info['numpy_error'] = str(e)
try:
    info['nvidia_smi'] = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=20).stdout.strip() or 'нет'
except Exception:
    info['nvidia_smi'] = 'нет'
info['seconds'] = round(time.time() - t0, 2)
json.dump(info, open('probe.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(info, ensure_ascii=False))
