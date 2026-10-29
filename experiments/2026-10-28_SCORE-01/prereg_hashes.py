# SCORE-01: sha256 кода, текстов, заданий (jobs/), меток и пилотных данных на момент регистрации → prereg_hashes.json.
#   python3 prereg_hashes.py
# Анализ перед вердиктами сверяет с этим файлом хеши всех перечисленных файлов (по умолчанию; --no-check — только сухой прогон).
# Задачи и пулы SELECT-01, по которым пересчитываются перестановка и меры, хешируются сводно (одна строка на выборку).
import glob
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['prompts_score.py', 'score01.py', 'score01_lib.py', 'analyze_score01.py', 'power_score01.py', 'truth_check.py', 'pilot2_describe.py',
         'pilot_tables.py', 'pilot2_tables.py', 'pilot3_tables.py', 'ctx_check.py',
         'prereg_hashes.py', 'assemble_prereg_score01.py', 'prereg_template.md',
         'jobs/main_opus_jobs.jsonl', 'jobs/rep_opus_jobs.jsonl', 'jobs/main_haiku_jobs.jsonl', 'jobs/rep_haiku_jobs.jsonl',
         'jobs/cfg_opus_clean.json', 'jobs/cfg_haiku_clean.json',
         'truth/main.json', 'truth/rep.json', 'truth/pilot.json', 'truth/check_main.json', 'truth/check_rep.json', 'truth/check_pilot.json',
         'pilot_salt.txt',
         # источники §3–§6 и таблиц пилотов (LENSES-1b, N7)
         'evals/pilot0_opus.json', 'evals/pilot0_haiku.json', 'evals/pilot1_opus.json', 'evals/pilot1_haiku.json',
         'evals/pilot12_opus.json', 'evals/pilot12_haiku.json', 'evals/pilot3_opus.json', 'evals/pilot3_haiku.json',
         'pilot_power.json', 'pilot12_power.json', 'pilot12_power_single.json', 'run/pilot_ctxcheck.log',
         *[f'run/pilot_ctx_stage_{p}_{m}.json' for p in ('pilot1', 'pilot2', 'pilot3') for m in ('opus', 'haiku')],
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
