# TRUST-01: sha256 кода на момент регистрации → prereg_hashes.json.  python3 prereg_hashes.py
import hashlib, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['exp_trust_01.py', 'analyze_trust_01.py', 'prereg_hashes.py', 'requirements.txt']
out = {}
for f in FILES:
    assert os.path.exists(f'{HERE}/{f}'), f'нет файла {f}'
    out[f] = hashlib.sha256(open(f'{HERE}/{f}', 'rb').read()).hexdigest()
json.dump(out, open(f'{HERE}/prereg_hashes.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
