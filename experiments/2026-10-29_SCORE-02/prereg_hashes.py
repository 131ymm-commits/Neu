# SCORE-02: sha256 кода, текстов, заданий, меток, солей и пилотных данных на момент регистрации → prereg_hashes.json.
#   python3 prereg_hashes.py
# Анализ перед вердиктами сверяет с этим файлом хеши всех перечисленных файлов (compute()). Задачи и пулы выборок хешируются сводно.
# Импорт ничего не пишет: запись — только при запуске.
import glob
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, '..')
FILES = ['score02.py', 'score02_lib.py', 'analyze_score02.py', 'power_score02.py', 'pilot_describe.py', 'truth_check_score02.py',
         'calib_rows_score02.py', 'assemble_prereg_score02.py', 'prereg_template.md', 'prereg_hashes.py', 'dry/make_stub.py', 'dry/dry_run.sh',
         'jobs/main_jobs.jsonl', 'jobs/rep_jobs.jsonl', 'jobs/cfg_opus_clean.json', 'jobs/cfg_haiku_clean.json', 'run/pilot_jobs.jsonl',
         'salts/main_salt.txt', 'salts/rep_salt.txt', 'truth/main.json', 'truth/rep.json', 'truth/check_main.json', 'truth/check_rep.json',
         'evals/pilot_opus.json', 'evals/pilot_haiku.json', 'pilot_describe.json', 'pilot_power.json',
         '../2026-10-28_SCORE-01/prompts_score.py', '../2026-10-28_SCORE-01/ctx_check.py', '../2026-10-28_SCORE-01/run/pilot_ctx_line.json',
         '../2026-10-28_SCORE-01/truth/check_pilot.json', '../2026-10-07_SELECT-01/sim.py', '../../tools/run_sealed2.py']
AGG = [('THINK-01', '2026-10-15_THINK-01', 'WH_8[23]*.json'), ('PRECOND-01', '2026-10-21_PRECOND-01', 'WH_83*.json'),
       ('SELECT-01 (пилот)', '2026-10-07_SELECT-01', 'WH_7[03]*.json')]


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def compute():
    out = {}
    for f in FILES:
        p = os.path.join(HERE, f)
        assert os.path.exists(p), f'нет файла {f}'
        out[f] = sha(p)
    for name, d, pat in AGG:
        for kind in ('tasks', 'pools'):
            fs = sorted(glob.glob(os.path.join(EXP, d, kind, pat)))
            h = hashlib.sha256()
            for p in fs:
                h.update(os.path.basename(p).encode()); h.update(sha(p).encode())
            out[f'{name}/{kind}/{pat} ({len(fs)} файлов)'] = h.hexdigest()
    return out


if __name__ == '__main__':
    out = compute()
    json.dump(out, open(os.path.join(HERE, 'prereg_hashes.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(out), 'хешей')
