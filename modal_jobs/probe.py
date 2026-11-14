"""Проба Modal для Neu: несколько секунд процессора и видеокарты T4 (из бесплатных кредитов). Без личных данных.
Запуск — workflow neu-modal: `modal run modal_jobs/probe.py --out modal_out/probe`."""
import json
import os

import modal

app = modal.App("neu-probe")
image = modal.Image.debian_slim(python_version="3.12").pip_install("numpy")


@app.function(image=image, timeout=120)
def cpu_probe():
    import platform
    import time
    import numpy as np
    a = np.random.default_rng(0).standard_normal((2000, 2000))
    t = time.time()
    _ = a @ a
    return {'cpus': os.cpu_count(), 'platform': platform.platform(), 'numpy': np.__version__,
            'matmul_2000_s': round(time.time() - t, 3)}


@app.function(image=image, gpu="T4", timeout=120)
def gpu_probe():
    import subprocess
    return {'nvidia_smi': subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True).stdout.strip() or 'нет'}


@app.local_entrypoint()
def main(out: str = "modal_out/probe"):
    res = {'cpu': cpu_probe.remote(), 'gpu': gpu_probe.remote()}
    os.makedirs(out, exist_ok=True)
    json.dump(res, open(os.path.join(out, 'probe.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
