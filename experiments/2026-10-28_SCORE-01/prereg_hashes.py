# SCORE-01: sha256 кода, текстов, заданий и меток на момент регистрации → prereg_hashes.json.  python3 prereg_hashes.py
# Анализ перед вердиктом сверяет с этим файлом хеши кода (analyze_score01.py --check-hashes).
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['prompts_score.py', 'score01.py', 'analyze_score01.py', 'power_score01.py', 'truth_check.py', 'pilot2_describe.py',
         'prereg_hashes.py', 'assemble_prereg_score01.py', 'prereg_template.md',
         'run/main_opus_jobs.jsonl', 'run/rep_opus_jobs.jsonl', 'run/main_haiku_jobs.jsonl', 'run/rep_haiku_jobs.jsonl',
         'run/cfg_opus.json', 'run/cfg_haiku.json', 'truth/main.json', 'truth/rep.json', 'truth/check_main.json', 'truth/check_rep.json',
         'pilot_power.json', 'pilot_power_single.json',
         '../../tools/run_sealed2.py', '../2026-10-07_SELECT-01/sim.py']
out = {}
for f in FILES:
    p = os.path.join(HERE, f)
    assert os.path.exists(p), f'нет файла {f}'
    out[f] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(out, open(os.path.join(HERE, 'prereg_hashes.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
