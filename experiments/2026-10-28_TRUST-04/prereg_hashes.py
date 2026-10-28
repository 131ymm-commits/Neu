# TRUST-04: sha256 кода на момент регистрации → prereg_hashes.json.  python3 prereg_hashes.py
import hashlib, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['exp_trust_04.py', 'analyze_trust_04.py', 'prereg_hashes.py', 'requirements.txt', 'indep_runner.py', 'indep/indep_trust_04.py',
         'indep/SPEC.md', '../2026-10-28_TRUST-01/exp_trust_01.py', '../2026-10-28_TRUST-02/exp_trust_02.py',
         '../2026-10-28_TRUST-03/exp_trust_03.py', 'pilot/v2/pilot_calib2.py', 'pilot/v2/compare_v1.py', 'pilot/v2/prereg_tables.py',
         'pilot/v2/assemble_prereg.py']
out = {}
for f in FILES:
    assert os.path.exists(f'{HERE}/{f}'), f'нет файла {f}'
    out[f] = hashlib.sha256(open(f'{HERE}/{f}', 'rb').read()).hexdigest()
json.dump(out, open(f'{HERE}/prereg_hashes.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
