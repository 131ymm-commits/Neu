# SCORE-01: sha256 кода, текстов, заданий, меток и пилотных данных на момент регистрации → prereg_hashes.json.
#   python3 prereg_hashes.py
# Анализ перед вердиктами сверяет с этим файлом хеши всех перечисленных файлов (по умолчанию; --no-check — только сухой прогон).
# Задачи и пулы SELECT-01, по которым пересчитываются перестановка и меры, хешируются сводно (одна строка на выборку).
import glob
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['prompts_score.py', 'score01.py', 'analyze_score01.py', 'power_score01.py', 'truth_check.py', 'pilot2_describe.py',
         'pilot_tables.py', 'pilot2_tables.py', 'pilot3_tables.py', 'ctx_check.py',
         'prereg_hashes.py', 'assemble_prereg_score01.py', 'prereg_template.md',
         'run/main_opus_jobs.jsonl', 'run/rep_opus_jobs.jsonl', 'run/main_haiku_jobs.jsonl', 'run/rep_haiku_jobs.jsonl',
         'run/cfg_opus_clean.json', 'run/cfg_haiku_clean.json',
         'truth/main.json', 'truth/rep.json', 'truth/check_main.json', 'truth/check_rep.json', 'truth/check_pilot.json',
         'evals/pilot3_opus.json', 'evals/pilot3_haiku.json', 'pilot_power.json',
         '../../tools/run_sealed2.py', '../2026-10-07_SELECT-01/sim.py']
SELECT = os.path.join(HERE, '..', '2026-10-07_SELECT-01')


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def compute():
    out = {}
    for f in FILES:
        p = os.path.join(HERE, f)
        assert os.path.exists(p), f'нет файла {f}'
        out[f] = sha(p)
    for kind in ('tasks', 'pools'):          # сводный хеш файлов задач и пулов тестовых выборок
        fs = sorted(glob.glob(os.path.join(SELECT, kind, 'WH_8[0-2]*.json')))
        h = hashlib.sha256()
        for p in fs:
            h.update(os.path.basename(p).encode()); h.update(sha(p).encode())
        out[f'SELECT-01/{kind}/WH_8001–8200 ({len(fs)} файлов)'] = h.hexdigest()
    return out


if __name__ == '__main__':
    out = compute()
    json.dump(out, open(os.path.join(HERE, 'prereg_hashes.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
