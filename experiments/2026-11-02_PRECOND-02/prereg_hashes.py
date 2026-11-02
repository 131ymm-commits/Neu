# PRECOND-02: sha256 кода, сидов, плана и конфигурации на момент регистрации (как prereg_hashes.py PRECOND-01) → prereg_hashes.json.
# Плюс sha256 вступлений обеих рук (промпт без правил задачи и кандидатов) — чтобы руки нельзя было подменить после регистрации.
#   python3 prereg_hashes.py
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import harness_precond02 as HP  # noqa: E402
FILES = ['harness_precond02.py', 'analyze_precond02.py', 'run_precond02.sh', 'dryrun_precond02.py', 'power_precond02.py', 'prior_refuse.py',
         'pilot_precond02.py', 'prereg_hashes.py', 'cfg_medium_clean.json', 'plan.json', 'seeds_A.json', 'seeds_B.json',
         '../2026-10-21_PRECOND-01/prompts_precond.py', '../2026-10-21_PRECOND-01/analyze_precond.py',
         '../2026-10-07_SELECT-01/sim.py', '../2026-10-07_SELECT-01/prompts.py', '../2026-10-07_SELECT-01/analyze.py', '../../tools/run_sealed2.py']
sha = lambda p: hashlib.sha256(open(os.path.join(HERE, p), 'rb').read()).hexdigest()
pre = {a: hashlib.sha256(HP.PP.compose(set(on), '{rules}', [])[0].split('\n\n{rules}')[0].encode()).hexdigest() for a, on in HP.ARMS.items()}
out = dict(files={f: sha(f) for f in FILES}, preambles=pre)
json.dump(out, open(os.path.join(HERE, 'prereg_hashes.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
